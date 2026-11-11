"""Explicit repository report revision commands; never moves research data."""

import argparse
import json
import sys
from pathlib import Path
from uuid import UUID

from .config import ROOT
from .report_revisions import MAX_BYTES, ReportRevisions


def main(argv=None):
    parser = argparse.ArgumentParser(description="Preserve original reports and append dated, registered editions")
    parser.add_argument("action", choices=("versions", "revise"))
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--path", required=True, help="Repository-relative original/report Markdown path")
    parser.add_argument("--body-file", type=Path, help="Complete proposed report text; original remains unchanged")
    parser.add_argument("--reason")
    parser.add_argument("--date", help="Explicit revision date, YYYY-MM-DD")
    parser.add_argument("--original-date", help="Optional known original date; never inferred")
    parser.add_argument("--operation-id", type=UUID, help="Stable UUID to reuse after an interrupted revision")
    parser.add_argument("--expected-edition", type=int)
    parser.add_argument("--expected-parent-hash")
    parser.add_argument("--series")
    parser.add_argument("--language", choices=("zh", "en"))
    args = parser.parse_args(argv)
    try:
        store = ReportRevisions(args.root)
        if args.action == "versions":
            result = store.history(args.path)
        else:
            required = (args.body_file, args.reason, args.date, args.operation_id,
                        args.expected_edition, args.expected_parent_hash)
            if any(value is None for value in required):
                raise ValueError("revise requires body-file, reason, date, operation-id, expected-edition and parent-hash")
            with args.body_file.open("rb") as stream:
                raw = stream.read(MAX_BYTES + 1)
            if len(raw) > MAX_BYTES:
                raise ValueError("proposed report exceeds 2 MB")
            result = store.revise(
                args.path, raw.decode("utf-8-sig"), reason=args.reason, date=args.date,
                operation_id=args.operation_id, expected_edition=args.expected_edition,
                expected_parent_hash=args.expected_parent_hash, series=args.series,
                language=args.language, original_date=args.original_date,
            )
        print(json.dumps(result, ensure_ascii=False, allow_nan=False))
    except (ValueError, OSError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
