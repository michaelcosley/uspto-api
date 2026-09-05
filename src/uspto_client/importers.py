"""Streaming PFW JSON and PADX XML readers; archive members are never extracted."""

from __future__ import annotations

import gzip
import re
import zipfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any, BinaryIO, cast
from xml.etree.ElementTree import Element, tostring

from uspto_client.library_models import Record, identifier


def json_records(stream: BinaryIO) -> Iterator[Record]:
    try:
        import ijson  # type: ignore[import-untyped]
    except ImportError as error:
        raise ImportError(
            "Install uspto-client[library] to stream JSON archives"
        ) from error
    builder: Any = None
    depth = 0
    target = ""
    wrapper = False
    recognized = False
    prefixes = {
        "item",
        "patentFileWrapperDataBag.item",
        "patentTrialProceedingDataBag.item",
    }
    for prefix, event, value in ijson.parse(
        stream, multiple_values=True, use_float=True
    ):
        if event == "start_array" and prefix in {
            "",
            "patentFileWrapperDataBag",
            "patentTrialProceedingDataBag",
        }:
            wrapper = True
            recognized = True
            if target == "":
                builder = None
                depth = 0
        if event == "start_map" and (
            prefix in prefixes or (prefix == "" and not wrapper)
        ):
            builder = ijson.common.ObjectBuilder()
            target = prefix
            depth = 0
        if builder is not None:
            builder.event(event, value)
            if event in {"start_map", "start_array"}:
                depth += 1
            elif event in {"end_map", "end_array"}:
                depth -= 1
            if depth == 0:
                record = builder.value
                builder = None
                recognized = True
                if not isinstance(record, dict):
                    raise ValueError("Expected a JSON record object")
                yield record
    if not recognized:
        raise ValueError("Unrecognized or empty JSON input")


def _text(element: Element, path: str) -> str:
    return (element.findtext(path) or "").strip()


def _date(value: str) -> str:
    return (
        f"{value[:4]}-{value[4:6]}-{value[6:8]}"
        if re.fullmatch(r"\d{8}", value)
        else value
    )


def assignment_records(stream: BinaryIO) -> Iterator[Record]:
    try:
        from defusedxml.ElementTree import iterparse  # type: ignore[import-untyped]
    except ImportError as error:
        raise ImportError(
            "Install uspto-client[library] to read assignment XML"
        ) from error
    stack: list[Element] = []
    recognized = False
    for event, element in iterparse(
        stream, events=("start", "end"), forbid_entities=True, forbid_external=True
    ):
        if event == "start":
            element.tag = element.tag.split("}")[-1]
            stack.append(element)
            if len(stack) == 1 and element.tag != "us-patent-assignments":
                raise ValueError("Expected PADX us-patent-assignments root")
            continue
        if element.tag == "data-available-code" and element.text == "N":
            recognized = True
        if element.tag == "patent-assignment":
            recognized = True
            record: Record = {
                "reel_frame": (
                    _text(element, "assignment-record/reel-no")
                    + "/"
                    + _text(element, "assignment-record/frame-no")
                ),
                "recorded_date": _date(
                    _text(element, "assignment-record/recorded-date/date")
                ),
                "source_modified": _date(
                    _text(element, "assignment-record/last-update-date/date")
                ),
                "purged": _text(element, "assignment-record/purge-indicator") == "Y",
                "conveyance": _text(element, "assignment-record/conveyance-text"),
                "assignees": [
                    _text(p, "name")
                    for p in element.findall("patent-assignees/patent-assignee")
                ],
                "assignors": [
                    _text(p, "name")
                    for p in element.findall("patent-assignors/patent-assignor")
                ],
                "patents": [],
                "applications": [],
                "publications": [],
                "property_links": [],
                "raw_xml": tostring(element, encoding="unicode"),
            }
            for prop in element.findall("patent-properties/patent-property"):
                application, patents = "", []
                for index, doc in enumerate(prop.findall("document-id")):
                    number, kind = _text(doc, "doc-number"), _text(doc, "kind")
                    if not number or _text(doc, "country") not in {"", "US"}:
                        continue
                    if kind == "X0" or index == 0:
                        application = identifier(number)
                        record["applications"].append(application)
                    elif number.startswith("US") and len(identifier(number)) >= 13:
                        record["publications"].append(identifier(number))
                    elif re.fullmatch(r"(?:RE|D|PP|H|T)?\d{4,9}", identifier(number)):
                        record["patents"].append(identifier(number))
                        patents.append(identifier(number))
                    else:
                        record.setdefault("unrecognized_properties", []).append(number)
                if application:
                    record["property_links"].extend(
                        {"application": application, "patent": patent}
                        for patent in patents
                    )
            yield record
            if len(stack) > 1:
                stack[-2].remove(element)
            element.clear()
        stack.pop()
    if not recognized:
        raise ValueError("No assignments or explicit no-data marker in PADX file")


class LimitedStream:
    def __init__(self, stream: BinaryIO, budget: int | None) -> None:
        self.stream = stream
        self.remaining = budget

    def read(self, size: int = -1) -> bytes:
        if self.remaining is not None:
            size = min(size, self.remaining + 1) if size >= 0 else self.remaining + 1
        data = self.stream.read(size)
        if self.remaining is not None:
            self.remaining -= len(data)
            if self.remaining < 0:
                raise ValueError("Input exceeds expanded byte budget")
        return data

    def readinto(self, buffer: Any) -> int:
        data = self.read(len(buffer))
        buffer[: len(data)] = data
        return len(data)


def read_records(
    path: Path, *, assignments: bool = False, max_expanded_bytes: int | None = None
) -> Iterator[Record]:
    reader = assignment_records if assignments else json_records
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            suffixes = (".xml",) if assignments else (".json", ".jsonl", ".ndjson")
            members = [
                info
                for info in archive.infolist()
                if not info.is_dir() and info.filename.lower().endswith(suffixes)
            ]
            if not members:
                raise ValueError("Archive contains no supported data members")
            if (
                max_expanded_bytes is not None
                and sum(info.file_size for info in members) > max_expanded_bytes
            ):
                raise ValueError("Archive exceeds expanded byte budget")
            for info in members:
                with archive.open(info) as stream:
                    yield from reader(
                        cast(
                            BinaryIO,
                            LimitedStream(cast(BinaryIO, stream), max_expanded_bytes),
                        )
                    )
    elif path.suffix.lower() == ".gz":
        with gzip.open(path, "rb") as stream:
            yield from reader(
                cast(
                    BinaryIO, LimitedStream(cast(BinaryIO, stream), max_expanded_bytes)
                )
            )
    else:
        if max_expanded_bytes is not None and path.stat().st_size > max_expanded_bytes:
            raise ValueError("Input exceeds expanded byte budget")
        with path.open("rb") as stream:
            yield from reader(cast(BinaryIO, LimitedStream(stream, max_expanded_bytes)))
