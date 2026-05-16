import argparse

from demo_common import error_spike_events, send_events


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a SignalForge error-rate spike.")
    parser.add_argument("--project-key", required=True, help="Raw SignalForge ingestion API key.")
    parser.add_argument("--api-url", default="http://localhost:8000", help="SignalForge API base URL.")
    parser.add_argument("--service", default="payment-api", help="Service that should spike.")
    parser.add_argument("--environment", default="production", help="Event environment.")
    parser.add_argument("--baseline-count", type=int, default=20, help="Historical healthy events to seed.")
    parser.add_argument("--spike-count", type=int, default=12, help="Error events to send in the current window.")
    parser.add_argument("--dry-run", action="store_true", help="Print the first generated event without sending.")
    args = parser.parse_args()

    events = error_spike_events(args.baseline_count, args.spike_count, args.service, args.environment)
    return send_events(args.api_url, args.project_key, events, dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
