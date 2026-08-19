from pathlib import Path
import pytest
import soul


def test_load_persona_returns_text(tmp_path):
    (tmp_path / "persona").mkdir()
    (tmp_path / "persona" / "demo.md").write_text("# Persona demo\nvoz", encoding="utf-8")
    text = soul.load_persona("demo", base=tmp_path)
    assert "Persona demo" in text


def test_load_persona_missing_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        soul.load_persona("nope", base=tmp_path)
