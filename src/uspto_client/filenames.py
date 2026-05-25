"""Document filename helpers."""

from __future__ import annotations

import csv
import io
import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from importlib.resources import files
from pathlib import Path
from typing import Any, Literal

FilenameFormat = Literal[
    "document_id",
    "date_description",
    "application_date_description",
    "date_patent_description",
    "application_date_patent_description",
]


@dataclass(frozen=True)
class DocumentFilename:
    """Resolved document filename details."""

    filename: str
    document_code: str | None
    description: str
    official_date: str | None
    application_number: str | None
    patent_last_three: str | None


class DocumentCodeMapper:
    """Maps USPTO document codes to preferred short descriptions."""

    def __init__(self, mapping: dict[str, str]) -> None:
        self._mapping = mapping

    @classmethod
    def from_default(cls) -> DocumentCodeMapper:
        path = files("uspto_client.data").joinpath("doc_code_mapping.csv")
        text = _decode_csv_bytes(path.read_bytes())
        return cls.from_csv_rows(csv.DictReader(io.StringIO(text)))

    @classmethod
    def from_csv_path(cls, path: str | Path) -> DocumentCodeMapper:
        text = _decode_csv_bytes(Path(path).read_bytes())
        return cls.from_csv_rows(csv.DictReader(io.StringIO(text)))

    @classmethod
    def from_csv_rows(
        cls,
        rows: Iterable[dict[str, str]],
    ) -> DocumentCodeMapper:
        mapping: dict[str, str] = {}
        for row in rows:
            code = (row.get("documentCode") or "").strip()
            shorthand = (row.get("shorthand") or "").strip()
            if code and shorthand:
                mapping[code] = shorthand
        return cls(mapping)

    def description_for(
        self,
        document_code: str | None,
        fallback: str | None,
    ) -> str:
        if document_code and document_code in self._mapping:
            return self._mapping[document_code]
        return fallback or document_code or "Document"


def build_document_filename(
    document: dict[str, Any],
    *,
    filename_format: FilenameFormat = "document_id",
    filename_template: str | None = None,
    patent_number: str | None = None,
    mapper: DocumentCodeMapper | None = None,
    extension: str = "pdf",
) -> DocumentFilename:
    """Build a safe filename from USPTO document metadata."""

    document_identifier = str(document.get("documentIdentifier") or "document")
    document_code = _optional_str(document.get("documentCode"))
    if mapper is None and (
        filename_template is not None or filename_format != "document_id"
    ):
        mapper = DocumentCodeMapper.from_default()
    description = (mapper or DocumentCodeMapper({})).description_for(
        document_code,
        _optional_str(document.get("documentCodeDescriptionText")),
    )
    application_number = _optional_str(document.get("applicationNumberText"))
    official_date = _date_part(_optional_str(document.get("officialDate")))
    patent_last_three = _patent_last_three(patent_number)

    values = {
        "app_no": application_number or "",
        "application_number": application_number or "",
        "date": official_date or "",
        "patent_last_three": f"('{patent_last_three})" if patent_last_three else "",
        "short_desc": description,
        "description": description,
        "doc_code": document_code or "",
        "document_code": document_code or "",
        "document_id": document_identifier,
        "document_identifier": document_identifier,
    }
    stem = (
        filename_template.format(**values)
        if filename_template is not None
        else _format_filename_stem(filename_format, values)
    )
    filename = f"{_sanitize_filename(stem)}.{extension.lstrip('.')}"
    return DocumentFilename(
        filename=filename,
        document_code=document_code,
        description=description,
        official_date=official_date,
        application_number=application_number,
        patent_last_three=patent_last_three,
    )


def unique_path(path: Path) -> Path:
    """Append (2), (3), etc. until the path does not already exist."""

    if not path.exists():
        return path

    counter = 2
    while True:
        candidate = path.with_name(f"{path.stem} ({counter}){path.suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


def _format_filename_stem(
    filename_format: FilenameFormat,
    values: dict[str, str],
) -> str:
    if filename_format == "document_id":
        return values["document_id"]
    if filename_format == "date_description":
        return "{date} {short_desc}".format(**values)
    if filename_format == "application_date_description":
        return "{app_no} {date} {short_desc}".format(**values)
    if filename_format == "date_patent_description":
        return "{date} {patent_last_three} {short_desc}".format(**values)
    if filename_format == "application_date_patent_description":
        return "{app_no} {date} {patent_last_three} {short_desc}".format(**values)
    raise ValueError(f"Unsupported filename format: {filename_format}")


def _sanitize_filename(stem: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', " ", stem)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned.rstrip(".") or "document"


def _date_part(value: str | None) -> str | None:
    if not value:
        return None
    if len(value) >= 10 and re.match(r"^\d{4}-\d{2}-\d{2}", value):
        return value[:10]
    try:
        return datetime.fromisoformat(value).date().isoformat()
    except ValueError:
        return value[:10]


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _patent_last_three(patent_number: str | None) -> str | None:
    if not patent_number:
        return None
    digits = re.sub(r"\D", "", patent_number)
    if not digits:
        return None
    return digits[-3:]


def _decode_csv_bytes(content: bytes) -> str:
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8-sig", errors="replace")
