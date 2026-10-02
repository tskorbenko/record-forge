from types import SimpleNamespace

from app.api import routes


def test_preview_is_served_inline(monkeypatch, tmp_path):
    (tmp_path / "preview.wav").write_bytes(b"RIFF")
    monkeypatch.setattr(routes, "_job", lambda _: SimpleNamespace(status="ready", directory=tmp_path))
    response = routes.preview("test-job")
    assert response.media_type == "audio/wav"
    assert "attachment" not in response.headers.get("content-disposition", "")
