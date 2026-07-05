import argparse
import asyncio
from dataclasses import asdict, dataclass
from datetime import UTC, datetime

from app.config import get_settings
from app.jobs.process_event import EventJobProcessor


@dataclass(frozen=True)
class WorkerStatus:
    service: str
    status: str
    version: str
    mode: str
    timestamp: str


def get_worker_status(mode: str = "local-queue") -> WorkerStatus:
    settings = get_settings()
    return WorkerStatus(
        service=settings.service_name,
        status="healthy",
        version=settings.version,
        mode=mode,
        timestamp=datetime.now(UTC).isoformat(),
    )


async def poll_once() -> dict:
    return await EventJobProcessor().process_next()


async def drain_queue(max_jobs: int = 100) -> dict:
    """Process queued jobs until the queue is empty or max_jobs is reached.

    Used by scheduled runners (for example GitHub Actions) so the deployed
    demo keeps processing without an always-on hosted worker.
    """
    processor = EventJobProcessor()
    attempts = 0
    completed = 0
    failed = 0
    while attempts < max_jobs:
        result = await processor.process_next()
        if not result.get("processed") and result.get("reason") == "queue_empty":
            break
        attempts += 1
        if result.get("processed"):
            completed += 1
        else:
            failed += 1
        print(result)
    summary = {
        "mode": "drain",
        "jobsSeen": attempts,
        "completed": completed,
        "failedOrDeadLetter": failed,
        "queueEmptied": attempts < max_jobs,
    }
    print(summary)
    return summary


async def run_polling_loop(interval_seconds: float = 5.0) -> None:
    print(asdict(get_worker_status(mode="polling-loop")))
    while True:
        result = await poll_once()
        if result.get("processed") or result.get("status") in {"failed", "dead_letter"}:
            print(result)
        await asyncio.sleep(interval_seconds)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the SignalForge worker skeleton.")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Process at most one queued job, then exit.",
    )
    parser.add_argument(
        "--drain",
        nargs="?",
        const=100,
        type=int,
        metavar="MAX_JOBS",
        help="Process queued jobs until the queue is empty (or MAX_JOBS, default 100), then exit.",
    )
    args = parser.parse_args()

    if args.once:
        result = asyncio.run(poll_once())
        print(result if result["processed"] else asdict(get_worker_status()))
        return

    if args.drain is not None:
        asyncio.run(drain_queue(max_jobs=args.drain))
        return

    asyncio.run(run_polling_loop())


if __name__ == "__main__":
    main()
