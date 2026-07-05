"""Seed the shared read-only demo dashboard for the deployed SignalForge demo.

Creates (idempotently) a demo user, a demo project, and a coherent incident
story: normal traffic rollups, an error spike, fingerprints, anomalies, an
open critical incident with a deterministic summary, alert history, and
worker-job rows for the pipeline-health page.

Run it with the worker virtualenv (it already has psycopg installed):

    cd services/worker
    .venv\\Scripts\\python ..\\..\\scripts\\seed_demo_dashboard.py ^
        --database-url "YOUR_NEON_DATABASE_URL" --demo-password "chosen-password"

Re-run with --reset to refresh the timeline (timestamps are relative to now).
Afterwards set PUBLIC_DEMO_EMAIL / PUBLIC_DEMO_PASSWORD in Vercel so the
login page shows the "Explore the live demo" button. The API keeps this
account read-only through the DEMO_USER_EMAIL guard.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import secrets
import sys
import uuid
from datetime import UTC, datetime, timedelta

try:
    import psycopg
except ImportError:  # pragma: no cover - guidance for direct runs
    sys.exit("psycopg is required. Run this script with the worker virtualenv.")

DEMO_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "https://signalforge.dev/demo")
PASSWORD_ITERATIONS = 260_000  # keep in sync with services/api/app/utils/security.py

CHECKOUT = "checkout-api"
PAYMENT = "payment-api"
ENVIRONMENT = "production"
ERROR_MESSAGE = "Stripe checkout timeout while creating session"
NORMALIZED_ERROR = "stripe checkout timeout while creating session"


def demo_id(name: str) -> str:
    return str(uuid.uuid5(DEMO_NAMESPACE, name))


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS)
    return "pbkdf2_sha256${}${}${}".format(
        PASSWORD_ITERATIONS,
        base64.b64encode(salt).decode("ascii"),
        base64.b64encode(digest).decode("ascii"),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL", ""))
    parser.add_argument("--demo-email", default="demo@signalforge.dev")
    parser.add_argument("--demo-password", required=True)
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete existing demo project data first so the timeline is rebuilt fresh.",
    )
    args = parser.parse_args()

    if not args.database_url:
        sys.exit("Provide --database-url or set DATABASE_URL.")

    now = datetime.now(UTC).replace(second=0, microsecond=0)
    user_id = demo_id("user")
    project_id = demo_id("project")

    with psycopg.connect(args.database_url) as conn:
        with conn.cursor() as cur:
            if args.reset:
                cur.execute("DELETE FROM projects WHERE id = %s", (project_id,))
                cur.execute("DELETE FROM worker_jobs WHERE entity_id = %s", (project_id,))

            cur.execute(
                """
                INSERT INTO users (id, email, password_hash)
                VALUES (%s, %s, %s)
                ON CONFLICT (email) DO UPDATE SET password_hash = EXCLUDED.password_hash
                """,
                (user_id, args.demo_email.strip().lower(), hash_password(args.demo_password)),
            )
            cur.execute(
                """
                INSERT INTO projects (id, user_id, name, slug, description, environment_default)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING
                """,
                (
                    project_id,
                    user_id,
                    "Checkout Demo",
                    "checkout-demo",
                    "Shared read-only demo project with a pre-built incident story.",
                    ENVIRONMENT,
                ),
            )

            seed_rollups(cur, project_id, now)
            seed_events_and_fingerprint(cur, project_id, now)
            seed_anomalies_incident_alerts(cur, project_id, now)
            seed_worker_jobs(cur, project_id, now)

    print(
        json.dumps(
            {
                "status": "seeded",
                "demoEmail": args.demo_email,
                "projectId": project_id,
                "anchoredAt": now.isoformat(),
                "next": "Set PUBLIC_DEMO_EMAIL and PUBLIC_DEMO_PASSWORD in Vercel.",
            },
            indent=2,
        )
    )


def seed_rollups(cur, project_id: str, now: datetime) -> None:
    rows = []
    for minutes_ago in range(120, 0, -1):
        bucket = now - timedelta(minutes=minutes_ago)
        spike = 25 <= minutes_ago <= 40

        # checkout-api: healthy baseline, then an error spike ~40-25 min ago.
        total = 14 if spike else 10
        errors = 9 if spike else 0
        fatal = 1 if minutes_ago in (33, 31) else 0
        rows.append(
            (
                demo_id(f"rollup/{CHECKOUT}/{minutes_ago}"),
                project_id,
                CHECKOUT,
                ENVIRONMENT,
                bucket,
                60,
                total,
                errors,
                1 if minutes_ago % 17 == 0 else 0,
                fatal,
                240 + (40 if spike else 0),
                2600 if spike else 420,
            )
        )

        # payment-api: steady healthy traffic throughout.
        rows.append(
            (
                demo_id(f"rollup/{PAYMENT}/{minutes_ago}"),
                project_id,
                PAYMENT,
                ENVIRONMENT,
                bucket,
                60,
                8,
                0,
                1 if minutes_ago % 23 == 0 else 0,
                0,
                180,
                310,
            )
        )

    cur.executemany(
        """
        INSERT INTO metric_rollups
          (id, project_id, service, environment, bucket_start, bucket_size_seconds,
           total_events, error_events, warning_events, fatal_events,
           latency_avg_ms, latency_p95_ms)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (project_id, service, environment, bucket_start, bucket_size_seconds)
        DO NOTHING
        """,
        rows,
    )


def seed_events_and_fingerprint(cur, project_id: str, now: datetime) -> None:
    fingerprint_hash = hashlib.sha256(
        f"{CHECKOUT}|{ENVIRONMENT}|error|504|{NORMALIZED_ERROR}".encode("utf-8")
    ).hexdigest()

    cur.execute(
        """
        INSERT INTO event_fingerprints
          (id, project_id, service, environment, level, status_code, fingerprint_hash,
           normalized_message, first_seen_at, last_seen_at, occurrence_count)
        VALUES (%s, %s, %s, %s, 'error', 504, %s, %s, %s, %s, %s)
        ON CONFLICT (project_id, fingerprint_hash) DO NOTHING
        """,
        (
            demo_id("fingerprint/stripe-timeout"),
            project_id,
            CHECKOUT,
            ENVIRONMENT,
            fingerprint_hash,
            NORMALIZED_ERROR,
            now - timedelta(minutes=40),
            now - timedelta(minutes=25),
            27,
        ),
    )

    events = []
    for index in range(18):
        minutes_ago = 40 - index
        events.append(
            (
                demo_id(f"event/error/{index}"),
                project_id,
                f"evt_demo_err_{index:03d}",
                "sf_demo_seeded00",
                now - timedelta(minutes=minutes_ago, seconds=(index * 7) % 50),
                now - timedelta(minutes=minutes_ago, seconds=((index * 7) % 50) - 1),
                CHECKOUT,
                ENVIRONMENT,
                "error",
                ERROR_MESSAGE,
                NORMALIZED_ERROR,
                fingerprint_hash,
                504,
                2100 + (index * 60) % 900,
                f"trace_demo_{index:03d}",
                f"req_demo_{index:03d}",
                json.dumps({"route": "/checkout", "region": "us-east-1", "provider": "stripe"}),
            )
        )
    for index in range(24):
        minutes_ago = 115 - index * 5
        service = CHECKOUT if index % 2 == 0 else PAYMENT
        events.append(
            (
                demo_id(f"event/info/{index}"),
                project_id,
                f"evt_demo_ok_{index:03d}",
                "sf_demo_seeded00",
                now - timedelta(minutes=minutes_ago),
                now - timedelta(minutes=minutes_ago) + timedelta(seconds=1),
                service,
                ENVIRONMENT,
                "info",
                "Checkout session completed" if service == CHECKOUT else "Payment captured",
                "checkout session completed" if service == CHECKOUT else "payment captured",
                hashlib.sha256(f"{service}|ok".encode("utf-8")).hexdigest(),
                200,
                180 + (index * 13) % 240,
                f"trace_demo_ok_{index:03d}",
                f"req_demo_ok_{index:03d}",
                json.dumps({"route": "/checkout" if service == CHECKOUT else "/capture"}),
            )
        )

    cur.executemany(
        """
        INSERT INTO events_metadata
          (id, project_id, event_id, api_key_prefix, timestamp, received_at, service,
           environment, level, message, normalized_message, fingerprint_hash,
           status_code, latency_ms, trace_id, request_id, metadata)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (project_id, event_id) DO NOTHING
        """,
        events,
    )


def seed_anomalies_incident_alerts(cur, project_id: str, now: datetime) -> None:
    fingerprint_hash = hashlib.sha256(
        f"{CHECKOUT}|{ENVIRONMENT}|error|504|{NORMALIZED_ERROR}".encode("utf-8")
    ).hexdigest()
    window_start = now - timedelta(minutes=35)
    window_end = now - timedelta(minutes=30)
    error_anomaly_id = demo_id("anomaly/error-rate")
    fingerprint_anomaly_id = demo_id("anomaly/repeated-error")
    incident_id = demo_id("incident/checkout")

    cur.executemany(
        """
        INSERT INTO anomalies
          (id, project_id, service, environment, anomaly_type, severity, score,
           baseline_value, observed_value, window_start, window_end, status,
           fingerprint_hash, metadata, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO NOTHING
        """,
        [
            (
                error_anomaly_id,
                project_id,
                CHECKOUT,
                ENVIRONMENT,
                "error_rate_spike",
                "critical",
                8.4,
                0.02,
                0.64,
                window_start,
                window_end,
                "open",
                None,
                json.dumps({}),
                window_end,
            ),
            (
                fingerprint_anomaly_id,
                project_id,
                CHECKOUT,
                ENVIRONMENT,
                "new_repeated_error",
                "high",
                27.0,
                5.0,
                27.0,
                window_start,
                window_end,
                "open",
                fingerprint_hash,
                json.dumps({"normalized_message": NORMALIZED_ERROR}),
                window_end + timedelta(minutes=1),
            ),
        ],
    )

    summary_payload = {
        "summary": (
            "Critical incident in checkout-api for production based on 2 grouped anomalies. "
            "The first signal was error rate spike driven by Stripe checkout timeouts."
        ),
        "affectedService": CHECKOUT,
        "impact": "Roughly two thirds of checkout attempts are failing with 504 timeouts.",
        "likelyCause": "Upstream Stripe session API latency is exceeding the checkout timeout budget.",
        "timeline": [
            {"time": window_start.isoformat(), "event": "error rate spike detected"},
            {"time": (window_end + timedelta(minutes=1)).isoformat(), "event": "new repeated error detected"},
        ],
        "recommendedActions": [
            "Inspect recent deployments and configuration changes for checkout-api",
            "Review the Stripe status page and observed session-creation latency",
            "Raise the checkout timeout or fail over to the queued-payment path",
        ],
        "confidence": "medium",
        "source": "fallback",
    }

    cur.execute(
        """
        INSERT INTO incidents
          (id, project_id, title, service, environment, severity, status, ai_summary,
           likely_cause, recommended_actions, started_at, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, 'critical', 'open', %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO NOTHING
        """,
        (
            incident_id,
            project_id,
            "High error rate in checkout-api",
            CHECKOUT,
            ENVIRONMENT,
            json.dumps(summary_payload, sort_keys=True),
            summary_payload["likelyCause"],
            json.dumps(summary_payload["recommendedActions"]),
            window_start,
            window_end,
            now - timedelta(minutes=20),
        ),
    )

    cur.executemany(
        """
        INSERT INTO incident_events (id, incident_id, anomaly_id)
        VALUES (%s, %s, %s)
        ON CONFLICT (id) DO NOTHING
        """,
        [
            (demo_id("incident-event/error-rate"), incident_id, error_anomaly_id),
            (demo_id("incident-event/repeated-error"), incident_id, fingerprint_anomaly_id),
        ],
    )

    cur.execute(
        """
        INSERT INTO alerts
          (id, project_id, incident_id, channel, status, payload, sent_at, error_message, created_at)
        VALUES (%s, %s, %s, 'discord', 'skipped', %s, NULL, %s, %s)
        ON CONFLICT (id) DO NOTHING
        """,
        (
            demo_id("alert/opened"),
            project_id,
            incident_id,
            json.dumps(
                {
                    "alert_type": "opened",
                    "content": "Incident opened: High error rate in checkout-api",
                }
            ),
            "DISCORD_WEBHOOK_URL is not configured",
            window_end,
        ),
    )


def seed_worker_jobs(cur, project_id: str, now: datetime) -> None:
    jobs = []
    for index in range(10):
        created = now - timedelta(minutes=90 - index * 8)
        jobs.append(
            (
                demo_id(f"job/completed/{index}"),
                "process_event",
                project_id,
                "completed",
                1,
                3,
                None,
                json.dumps({"project_id": project_id, "seeded": True}),
                created,
                created + timedelta(seconds=1),
                created + timedelta(seconds=2),
            )
        )
    jobs.append(
        (
            demo_id("job/dead-letter"),
            "process_event",
            project_id,
            "dead_letter",
            3,
            3,
            "missing required string field: message",
            json.dumps({"project_id": project_id, "seeded": True}),
            now - timedelta(minutes=55),
            now - timedelta(minutes=55, seconds=-1),
            now - timedelta(minutes=54),
        )
    )

    cur.executemany(
        """
        INSERT INTO worker_jobs
          (id, job_type, entity_id, status, attempts, max_attempts, error_message,
           payload, created_at, started_at, completed_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO NOTHING
        """,
        jobs,
    )


if __name__ == "__main__":
    main()
