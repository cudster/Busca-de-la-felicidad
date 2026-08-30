import json
import datetime as dt
import dashboard


def test_load_clients_reads_configs(tmp_path):
    d = tmp_path / "clients" / "demo"
    d.mkdir(parents=True)
    (d / "config.json").write_text(json.dumps({"slug": "demo", "name": "Demo"}), encoding="utf-8")
    clients = dashboard.load_clients(base=tmp_path)
    assert len(clients) == 1
    assert clients[0]["slug"] == "demo"


def test_load_clients_missing_returns_empty(tmp_path):
    assert dashboard.load_clients(base=tmp_path) == []


def _iso(days_ago):
    return (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days_ago)).strftime("%Y-%m-%dT%H:%M:%S+0000")


def test_summarize_period_splits_and_trend():
    posts = [
        {"timestamp": _iso(1), "like": 10, "comment": 2, "reach": 1000},
        {"timestamp": _iso(3), "like": 20, "comment": 0, "reach": 2000},
        {"timestamp": _iso(9), "like": 5,  "comment": 0, "reach": 500},
    ]
    s = dashboard.summarize_period(posts, days=7)
    assert s["cur"]["n"] == 2
    assert s["cur"]["reach"] == 1500
    assert s["prev"]["n"] == 1
    assert s["reach_trend_pct"] == 200  # (1500-500)/500*100
