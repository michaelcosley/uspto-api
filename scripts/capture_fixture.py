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
        description="Capture sanitized USPTO patent application fixtures."
    )
    parser.add_argument(
        "method",
        choices=["get", "get-metadata"],
        help="Application method to capture.",
    )
    parser.add_argument("application_number")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    load_dotenv()
    api_key = os.environ.get("USPTO_API_KEY")
    if not api_key:
        raise SystemExit("USPTO_API_KEY is required")

    client = UsptoClient(api_key=api_key)
    if args.method == "get":
        response = client.applications.get(args.application_number)
    else:
        response = client.applications.get_metadata(args.application_number)

    capture = sanitize_capture(
        {
            "request": {
                "method": args.method,
                "application_number": args.application_number,
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
