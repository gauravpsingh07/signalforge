import argparse
from pathlib import Path


DEFAULT_FILES = [
    "tmp/signalforge-events.jsonl",
    "tmp/signalforge-processed-events.jsonl",
    "tmp/signalforge-worker-jobs.json",
    "tmp/signalforge-fingerprints.json",
    "tmp/signalforge-metric-rollups.json",
    "tmp/signalforge-anomalies.json",
    "tmp/signalforge-incidents.json",
    "tmp/signalforge-alerts.json",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Reset local SignalForge demo fallback files.")
    parser.add_argument("--api-url", default="http://localhost:8000", help="SignalForge API base URL for consistency.")
    parser.add_argument("--project-key", required=True, help="Raw SignalForge ingestion API key for consistency.")
    parser.add_argument("--root", default=".", help="Repository root containing the tmp directory.")
    parser.add_argument("--yes", action="store_true", help="Actually delete local demo files.")
    parser.add_argument("--dry-run", action="store_true", help="Print files that would be removed.")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    targets = [root / relative for relative in DEFAULT_FILES]
    print(f"Resetting local demo state for {args.api_url}")
    print(f"Using project key prefix {args.project_key[:16]}...")

    if args.dry_run or not args.yes:
        print("dry-run: pass --yes to remove these files")
        for target in targets:
            print(f"would remove {target}")
        return 0

    for target in targets:
        if target.exists():
            target.unlink()
            print(f"removed {target}")
        else:
            print(f"skipped missing {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
