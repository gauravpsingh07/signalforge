import argparse
import asyncio
from dataclasses import asdict, dataclass
from datetime import UTC, datetime

from app.config import get_settings


@dataclass(frozen=True)
class WorkerStatus:
    service: str
    status: str
    version: str
    mode: str
    timestamp: str


def get_worker_status(mode: str = "local-placeholder") -> WorkerStatus:
    settings = get_settings()
    return WorkerStatus(
        service=settings.service_name,
        status="healthy",
        version=settings.version,
        mode=mode,
        timestamp=datetime.now(UTC).isoformat(),
    )


async def poll_once() -> WorkerStatus:
    return get_worker_status()


async def run_polling_loop(interval_seconds: float = 5.0) -> None:
    print(asdict(get_worker_status(mode="polling-loop")))
    while True:
        await asyncio.sleep(interval_seconds)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the SignalForge worker skeleton.")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Print worker status and exit.",
    )
    args = parser.parse_args()

    if args.once:
        print(asdict(get_worker_status()))
        return

    asyncio.run(run_polling_loop())


if __name__ == "__main__":
    main()
