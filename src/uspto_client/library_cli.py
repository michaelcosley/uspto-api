"""Command-line operations. Live collection and bulk execution are explicit."""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

from uspto_client.assignment import AssignmentCenterClient
from uspto_client.client import UsptoClient
from uspto_client.library import DocumentSpec, Library, Release, Selection


def _selection(args: argparse.Namespace) -> Selection:
    return Selection(
        kinds=tuple(args.kind if args.kind is not None else ("reexam", "reissue")),
        applications=tuple(args.application),
        patents=tuple(args.patent),
        trials=tuple(args.trial),
        companies=tuple(args.company),
        all_records=args.all_records,
    )


def _filters(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--kind",
        action="append",
        choices=("reexam", "reissue", "application", "ipr", "ptab"),
    )
    parser.add_argument("--application", action="append", default=[])
    parser.add_argument("--patent", action="append", default=[])
    parser.add_argument("--trial", action="append", default=[])
    parser.add_argument("--company", action="append", default=[])
    parser.add_argument("--all-records", action="store_true")


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog="uspto-library", description=__doc__)
    result.add_argument("--root", default=os.environ.get("USPTO_DATA_ROOT", "data"))
    sub = result.add_subparsers(dest="command", required=True)
    for command in (
        "init",
        "status",
        "verify",
        "matches",
        "match",
        "rebuild-text-index",
    ):
        sub.add_parser(command)
    restore = sub.add_parser("restore-database")
    restore.add_argument("backup")
    discovery = sub.add_parser("discover")
    discovery.add_argument("--from", dest="date_from", required=True)
    discovery.add_argument("--to", dest="date_to", required=True)
    discovery.add_argument(
        "--kind", action="append", choices=("reexam", "reissue", "ipr")
    )
    discovery.add_argument("--max-records", type=int, default=1000)
    backup = sub.add_parser("backup")
    backup.add_argument("destination")
    watch = sub.add_parser("watch-company")
    watch.add_argument("company_id")
    watch.add_argument("name")
    watch.add_argument("--alias", action="append", default=[])
    for command in ("company-patents", "collect-assignments"):
        child = sub.add_parser(command)
        child.add_argument("company_id")
    for command in ("patent-history", "ownership-candidates"):
        child = sub.add_parser(command)
        child.add_argument("patent")
    search = sub.add_parser("search-text")
    search.add_argument("query")
    add = sub.add_parser("add-document")
    add.add_argument("pdf")
    add.add_argument("--spec", required=True, help="JSON DocumentSpec manifest")
    text = sub.add_parser("add-text")
    text.add_argument("source")
    text.add_argument("document_id")
    text.add_argument("pages", help="JSON array of page strings")
    text.add_argument("--method", required=True)
    text.add_argument("--version", required=True)
    collect = sub.add_parser("collect")
    collect.add_argument("--application", action="append", default=[])
    collect.add_argument("--trial", action="append", default=[])
    collect.add_argument("--download-id", action="append", default=[])
    catalog = sub.add_parser("catalog")
    catalog.add_argument("--query")
    catalog.add_argument("--product")
    for command in ("import", "sync-bulk", "coverage"):
        child = sub.add_parser(command)
        _filters(child)
        child.add_argument(
            "--product", required=True, choices=("PTFWPRE", "PTFWPRD", "PASYR", "PASDL")
        )
        child.add_argument("--from", dest="date_from", required=True)
        child.add_argument("--to", dest="date_to", required=True)
        if command == "import":
            child.add_argument("path")
            child.add_argument("--source-as-of", default="")
            child.add_argument("--max-expanded-bytes", type=int)
        if command == "sync-bulk":
            child.add_argument("--max-download-bytes", type=int, required=True)
            child.add_argument(
                "--execute",
                action="store_true",
                help="Download and import; default only lists the plan",
            )
            child.add_argument("--discard-archives", action="store_true")
    return result


def _live_client() -> UsptoClient:
    key = os.environ.get("USPTO_API_KEY")
    if not key:
        raise ValueError("USPTO_API_KEY is required for this live operation")
    return UsptoClient(api_key=key)


def run(args: argparse.Namespace) -> Any:
    # Catalog inspection creates no library directories or database.
    if args.command == "catalog":
        with _live_client() as client:
            return (
                client.bulk.get_product(args.product)
                if args.product
                else client.bulk.search(q=args.query)
            ).raw_data
    if args.command == "restore-database":
        with Library.restore_database(args.backup, args.root) as restored:
            return restored.verify()
    with Library(args.root) as library:
        if args.command in {"init", "status"}:
            return library.status()
        if args.command == "verify":
            return library.verify()
        if args.command == "backup":
            return {
                "database_backup": str(library.backup(args.destination)),
                "pdfs_included": False,
            }
        if args.command == "watch-company":
            library.watch_company(args.company_id, args.name, aliases=args.alias)
            return {"registered": args.company_id}
        if args.command == "company-patents":
            return library.company_patents(args.company_id)
        if args.command == "patent-history":
            return library.patent_history(args.patent)
        if args.command == "ownership-candidates":
            return library.ownership_candidates(args.patent)
        if args.command == "collect-assignments":
            with AssignmentCenterClient() as assignments:
                return library.collect_assignments(
                    assignments, company_id=args.company_id
                )
        if args.command == "matches":
            return library.matches()
        if args.command == "match":
            return library.match_companies()
        if args.command == "search-text":
            return library.search_text(args.query)
        if args.command == "rebuild-text-index":
            library.rebuild_text_index()
            return {"rebuilt": True}
        if args.command == "add-document":
            spec = DocumentSpec(
                **json.loads(Path(args.spec).read_text(encoding="utf-8"))
            )
            return {"path": str(library.add_document(args.pdf, spec))}
        if args.command == "add-text":
            return {
                "text_run": library.add_text(
                    args.source,
                    args.document_id,
                    json.loads(Path(args.pages).read_text(encoding="utf-8")),
                    method=args.method,
                    version=args.version,
                )
            }
        if args.command == "discover":
            with _live_client() as client:
                return library.discover(
                    client,
                    date_from=args.date_from,
                    date_to=args.date_to,
                    kinds=tuple(args.kind or ("reexam", "reissue", "ipr")),
                    max_records=args.max_records,
                )
        if args.command == "collect":
            if not args.application and not args.trial:
                raise ValueError("Supply at least one application or trial")
            with _live_client() as client:
                return library.collect(
                    client,
                    applications=args.application,
                    trials=args.trial,
                    download_ids=args.download_id,
                )
        selection = _selection(args)
        if args.command == "coverage":
            return library.coverage(
                args.product, selection, date_from=args.date_from, date_to=args.date_to
            )
        if args.command == "import":
            release = Release(
                args.product,
                Path(args.path).name,
                args.date_from,
                args.date_to,
                "delta" if args.product in {"PTFWPRD", "PASDL"} else "snapshot",
                source_as_of=args.source_as_of,
            )
            return asdict(
                library.import_file(
                    args.path,
                    release=release,
                    selection=selection,
                    max_expanded_bytes=args.max_expanded_bytes,
                )
            )
        if args.command == "sync-bulk":
            with _live_client() as client:
                return library.sync_bulk(
                    client,
                    product=args.product,
                    date_from=args.date_from,
                    date_to=args.date_to,
                    selection=selection,
                    max_download_bytes=args.max_download_bytes,
                    execute=args.execute,
                    retain_archives=not args.discard_archives,
                )
        raise ValueError("Unknown operation")


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        result = run(args)
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
        if isinstance(result, dict) and (
            result.get("complete") is False
            or result.get("missing")
            or result.get("changed")
            or (result.get("integrity") and result["integrity"] != "ok")
        ):
            return 2
        return 0
    except (ValueError, OSError, KeyError) as error:
        print(f"{type(error).__name__}: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
