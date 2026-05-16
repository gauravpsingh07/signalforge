import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime, timedelta


def post_event(api_url: str, project_key: str, event: dict) -> dict:
    request = urllib.request.Request(
        f"{api_url.rstrip('/')}/v1/events",
        data=json.dumps(event).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {project_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a SignalForge latency spike.")
    parser.add_argument("--project-key", required=True)
    parser.add_argument("--api-url", default="http://localhost:8000")
    parser.add_argument("--service", default="checkout-service")
    parser.add_argument("--environment", default="production")
    parser.add_argument("--baseline-count", type=int, default=20)
    parser.add_argument("--spike-count", type=int, default=8)
    args = parser.parse_args()

    now = datetime.now(UTC)
    events = []
    for index in range(args.baseline_count):
        timestamp = now - timedelta(minutes=45 - (index % 30))
        events.append(
            {
                "eventId": f"evt_latency_baseline_{int(time.time() * 1000)}_{index}",
                "timestamp": timestamp.isoformat(),
                "service": args.service,
                "environment": args.environment,
                "level": "info",
                "message": "Checkout request completed",
                "statusCode": 200,
                "latencyMs": 120 + (index % 30),
                "metadata": {"script": "generate_latency_spike", "phase": "baseline"},
            }
        )
    for index in range(args.spike_count):
        events.append(
            {
                "eventId": f"evt_latency_spike_{int(time.time() * 1000)}_{index}",
                "timestamp": now.isoformat(),
                "service": args.service,
                "environment": args.environment,
                "level": "info",
                "message": "Checkout request completed slowly",
                "statusCode": 200,
                "latencyMs": 1800 + (index * 25),
                "metadata": {"script": "generate_latency_spike", "phase": "spike"},
            }
        )

    print(f"Sending {len(events)} events to {args.api_url}")
    try:
        for event in events:
            accepted = post_event(args.api_url, args.project_key, event)
            print(f"accepted eventId={accepted['eventId']} jobId={accepted['jobId']}")
    except urllib.error.HTTPError as exc:
        print(f"request failed: HTTP {exc.code} {exc.read().decode('utf-8')}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
