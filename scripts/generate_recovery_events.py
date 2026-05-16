import argparse

from demo_common import recovery_events, send_events


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate healthy recovery traffic after a SignalForge incident.")
    parser.add_argument("--project-key", required=True, help="Raw SignalForge ingestion API key.")
    parser.add_argument("--api-url", default="http://localhost:8000", help="SignalForge API base URL.")
    parser.add_argument("--service", default="payment-api", help="Recovering service.")
    parser.add_argument("--environment", default="production", help="Event environment.")
    parser.add_argument("--count", type=int, default=20, help="Healthy recovery events to send.")
    parser.add_argument("--dry-run", action="store_true", help="Print the first generated event without sending.")
    args = parser.parse_args()

    events = recovery_events(args.count, args.service, args.environment)
    return send_events(args.api_url, args.project_key, events, dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
