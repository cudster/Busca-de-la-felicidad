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


def _write_facts(tmp_path):
    d = tmp_path / "knowledge" / "demo"
    d.mkdir(parents=True)
    (d / "facts.csv").write_text(
        "id,subject,fact,detail,source,tags,pillar\n"
        "F01,SR-71,Fast plane,detail,src,military,technical_awe\n",
        encoding="utf-8",
    )


def test_load_facts_reads_rows(tmp_path):
    _write_facts(tmp_path)
    facts = soul.load_facts("demo", base=tmp_path)
    assert len(facts) == 1
    assert facts[0]["subject"] == "SR-71"
    assert facts[0]["pillar"] == "technical_awe"


def test_load_facts_missing_returns_empty(tmp_path):
    assert soul.load_facts("nope", base=tmp_path) == []


def test_load_news_reads_json(tmp_path):
    d = tmp_path / "data" / "news"
    d.mkdir(parents=True)
    (d / "demo.json").write_text('[{"title":"t","summary":"s","url":"u","date":"d"}]', encoding="utf-8")
    news = soul.load_news("demo", base=tmp_path)
    assert news[0]["title"] == "t"


def test_load_news_missing_returns_empty(tmp_path):
    assert soul.load_news("nope", base=tmp_path) == []
