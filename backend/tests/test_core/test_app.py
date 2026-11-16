from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import main
from app.core.config import Settings
from app.embeddings import embedder


def test_serves_built_frontend_without_hiding_the_api(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "index.html").write_text("<h1>Decision Intelligence</h1>")
    monkeypatch.setattr(main, "get_settings", lambda: Settings(frontend_dist=tmp_path))

    client = TestClient(main.create_app())

    assert "Decision Intelligence" in client.get("/").text
    assert client.get("/api/v1/health").json() == {"status": "ok"}


def test_warm_up_failure_does_not_crash(monkeypatch: pytest.MonkeyPatch) -> None:
    def broken():
        raise RuntimeError("model missing")

    monkeypatch.setattr(embedder, "get_embedder", broken)

    main.warm_up_models()
