import json
import pytest
import youtube_generate as yt


def test_load_channel_reads_config(tmp_path):
    d = tmp_path / "youtube" / "demo"
    d.mkdir(parents=True)
    (d / "config.json").write_text(json.dumps({"channel": "demo", "mix": {"short": 2, "long": 1}}), encoding="utf-8")
    cfg = yt.load_channel("demo", base=tmp_path)
    assert cfg["channel"] == "demo"


def test_load_channel_missing_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        yt.load_channel("nope", base=tmp_path)


def test_build_month_mix_and_ids():
    cfg = {"mix": {"short": 3, "long": 2}}
    items = yt.build_month(cfg, 2026, 10)
    assert len(items) == 5
    assert sum(1 for i in items if i["format"] == "short") == 3
    assert sum(1 for i in items if i["format"] == "long") == 2
    assert items[0]["id"] == "2026-10-S01"
    assert items[-1]["id"] == "2026-10-L02"
    # todas las fechas son de octubre 2026 y días hábiles
    import datetime as dt
    for it in items:
        y, m, day = (int(x) for x in it["date"].split("-"))
        assert (y, m) == (2026, 10)
        assert dt.date(y, m, day).weekday() < 5


def test_merge_keeps_skeleton_and_creative():
    skeleton = [{"id": "2026-10-S01", "format": "short", "date": "2026-10-01"}]
    creative = {"2026-10-S01": {"id": "2026-10-S01", "title": "Un auto brutal", "script_es": "guión"}}
    out = yt.merge(skeleton, creative)
    assert out[0]["title"] == "Un auto brutal"
    assert out[0]["format"] == "short"
    assert out[0]["date"] == "2026-10-01"
    assert out[0]["shortable_moments"] == []
