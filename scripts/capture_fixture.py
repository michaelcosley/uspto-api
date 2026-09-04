from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from dotenv import load_dotenv

from uspto_client import UsptoClient
from uspto_client.fixture_capture import sanitize_capture


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Capture sanitized USPTO patent and PTAB fixtures."
    )
    parser.add_argument(
        "method",
        choices=[
            "get",
            "get-metadata",
            "ptab-proceeding",
            "ptab-document",
            "ptab-decision",
        ],
        help="Client method to capture.",
    )
    parser.add_argument("identifier")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    load_dotenv()
    api_key = os.environ.get("USPTO_API_KEY")
    if not api_key:
        raise SystemExit("USPTO_API_KEY is required")

    client = UsptoClient(api_key=api_key)
    if args.method == "get":
        response = client.applications.get(args.identifier)
    elif args.method == "get-metadata":
        response = client.applications.get_metadata(args.identifier)
    elif args.method == "ptab-proceeding":
        response = client.ptab.trials.get_proceeding(args.identifier)
    elif args.method == "ptab-document":
        response = client.ptab.trials.get_document(args.identifier)
    else:
        response = client.ptab.trials.get_decision(args.identifier)

    capture = sanitize_capture(
        {
            "request": {
                "method": args.method,
                "identifier": args.identifier,
                "headers": {"X-API-KEY": api_key},
            },
            "response": response.raw_data,
        },
        secret_values=[api_key],
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(capture, indent=2, sort_keys=True),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
