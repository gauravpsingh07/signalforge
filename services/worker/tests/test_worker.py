from app.worker import get_worker_status


def test_worker_status_is_importable() -> None:
    status = get_worker_status()

    assert status.service == "signalforge-worker"
    assert status.status == "healthy"
    assert status.mode == "local-placeholder"
