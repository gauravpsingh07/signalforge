import json
from pathlib import Path
from typing import Any

import httpx

from app.config import get_settings


class QueueConsumer:
    async def pop(self) -> dict[str, Any] | None:
        settings = get_settings()
        if settings.upstash_redis_rest_url and settings.upstash_redis_rest_token:
            return await self._pop_upstash()
        return self._pop_local()

    def requeue(self, payload: dict[str, Any]) -> None:
        path = Path(get_settings().local_queue_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as queue_file:
            queue_file.write(json.dumps(payload, default=str) + "\n")

    def _pop_local(self) -> dict[str, Any] | None:
        path = Path(get_settings().local_queue_path)
        if not path.exists():
            return None

        lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        if not lines:
            path.write_text("", encoding="utf-8")
            return None

        first = lines[0]
        path.write_text("\n".join(lines[1:]) + ("\n" if len(lines) > 1 else ""), encoding="utf-8")
        return json.loads(first)

    async def _pop_upstash(self) -> dict[str, Any] | None:
        settings = get_settings()
        url = settings.upstash_redis_rest_url.rstrip("/")
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(
                f"{url}/rpop/signalforge:jobs",
                headers={"Authorization": f"Bearer {settings.upstash_redis_rest_token}"},
            )
            response.raise_for_status()
            data = response.json()
            result = data.get("result")
            if not result:
                return None
            return json.loads(result)
