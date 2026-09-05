"""Portable library contracts; independent of SQLite and HTTP."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Literal

Record = dict[str, Any]


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def fingerprint(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def identifier(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", value.upper())


def company_key(value: str) -> str:
    # Do not strip corporate suffixes or conflate unreviewed aliases.
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def record_kind(record: Record) -> str:
    trial = str(record.get("trialNumber") or "")
    if trial:
        return "ipr" if trial.startswith("IPR") else "ptab"
    metadata = record.get("applicationMetaData") or {}
    category = re.sub(
        r"[^a-z]", "", str(metadata.get("applicationTypeCategory", "")).lower()
    )
    label = re.sub(
        r"[^a-z]", "", str(metadata.get("applicationTypeLabelName", "")).lower()
    )
    if category == "reexam" or label == "reexamination":
        return "reexam"
    if category == "reissue" or label == "reissue":
        return "reissue"
    if label in {
        "utility",
        "plant",
        "design",
        "provisional",
        "pct",
        "regular",
        "supplementalexamination",
    }:
        return "application"
    return "unknown"


@dataclass(frozen=True)
class Selection:
    kinds: tuple[str, ...] = ("reexam", "reissue")
    applications: tuple[str, ...] = ()
    patents: tuple[str, ...] = ()
    trials: tuple[str, ...] = ()
    companies: tuple[str, ...] = ()
    all_records: bool = False

    def __post_init__(self) -> None:
        if any(
            not item.strip()
            for values in (self.applications, self.patents, self.trials, self.companies)
            for item in values
        ):
            raise ValueError("Selection identifiers and company names cannot be empty")
        if set(self.kinds) - {"reexam", "reissue", "application", "ipr", "ptab"}:
            raise ValueError("Unknown selection kind")

    @property
    def fingerprint(self) -> str:
        data = asdict(self)
        for key in ("kinds", "applications", "patents", "trials", "companies"):
            data[key] = sorted(set(data[key]))
        return fingerprint(data)

    def accepts(self, record: Record) -> bool:
        metadata = (
            record.get("applicationMetaData") or record.get("patentOwnerData") or {}
        )
        return (
            self.all_records
            or record_kind(record) in self.kinds
            or identifier(str(record.get("applicationNumberText") or ""))
            in {identifier(x) for x in self.applications}
            or identifier(str(metadata.get("patentNumber") or ""))
            in {identifier(x) for x in self.patents}
            or str(record.get("trialNumber") or "") in self.trials
        )

    def accepts_assignment(self, record: Record) -> bool:
        return (
            self.all_records
            or bool(
                {identifier(x) for x in self.patents} & set(record.get("patents", []))
            )
            or bool(
                {identifier(x) for x in self.applications}
                & set(record.get("applications", []))
            )
            or bool(
                {company_key(x) for x in self.companies}
                & {
                    company_key(x)
                    for x in record.get("assignees", []) + record.get("assignors", [])
                }
            )
        )


@dataclass(frozen=True)
class Release:
    product: str
    file_name: str
    data_from: str
    data_to: str
    kind: Literal["snapshot", "delta", "targeted"]
    source_as_of: str = ""
    sha256: str = ""
    # A multi-file snapshot must not imply completeness before all parts exist.
    coverage_complete: bool = False

    def __post_init__(self) -> None:
        start, end = date.fromisoformat(self.data_from), date.fromisoformat(
            self.data_to
        )
        if start > end:
            raise ValueError("Release dates are reversed")
        if self.kind not in {"snapshot", "delta", "targeted"}:
            raise ValueError("Invalid release kind")


@dataclass
class ImportResult:
    retained: int = 0
    skipped: int = 0
    unrecognized: int = 0
    already_imported: bool = False
    complete: bool = True


def clean_component(value: str) -> str:
    text = unicodedata.normalize("NFKC", value)
    text = re.sub(r'[<>:"/\\|?*\x00-\x1f]', " ", text)
    text = " ".join(text.split()).strip(" .")
    if not text or text.upper().split(".")[0] in {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *(f"COM{i}" for i in range(1, 10)),
        *(f"LPT{i}" for i in range(1, 10)),
    }:
        text = "Document " + text
    return text


@dataclass(frozen=True)
class DocumentSpec:
    source: str
    document_id: str
    proceeding: str
    kind: str
    patent: str = ""
    official_date: str = ""
    description: str = "Document"
    paper_number: str = ""
    exhibit_number: str = ""
    side: str = "unknown"
    part: int | None = None
    status: str = ""
    source_metadata: Record | None = None

    def relative_path(self) -> Path:
        if not re.fullmatch(r"[A-Za-z0-9-]+", self.proceeding):
            raise ValueError("Proceeding identifier is not path-safe")
        roots = {
            "reexam": "reexams",
            "reissue": "reissues",
            "application": "applications",
            "ipr": "iprs",
            "ptab": "ptab",
            "assignment": "assignments",
        }
        if self.kind not in roots:
            raise ValueError("Unknown document layout")
        shorthand = (
            f" ('{identifier(self.patent)[-3:]})"
            if len(identifier(self.patent)) >= 3
            else ""
        )
        folder = self.proceeding + shorthand
        path = Path(roots[self.kind]) / folder
        description = clean_component(self.description)
        suffix = f" - Part {self.part:02d}" if self.part is not None else ""
        suffix += f" ({clean_component(self.status)})" if self.status else ""
        if self.exhibit_number:
            if not self.exhibit_number.isdigit():
                raise ValueError("Exhibit number must be an actual numeric identifier")
            sides = {
                "petitioner": "Pet. Exhibits",
                "owner": "PO Exhibits",
                "board": "Board Exhibits",
                "requester": "Request Exhibits",
            }
            path /= sides.get(self.side, "Unclassified Exhibits")
            prefix = f"Ex {int(self.exhibit_number):04d} "
        else:
            official = self.official_date[:10]
            if official:
                date.fromisoformat(official)
            paper = f" ({int(self.paper_number):03d})" if self.paper_number else ""
            prefix = f"{official}{paper} {folder} ".lstrip()
        # Reserve collision/version suffix space and honor conservative Windows paths.
        available = max(20, 160 - len(prefix) - len(suffix))
        return path / f"{prefix}{description[:available].rstrip(' .')}{suffix}.pdf"
