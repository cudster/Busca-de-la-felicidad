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


def test_content_status_counts():
    header = ["id", "date", "time_utc", "type", "approved", "published"]
    rows = [
        header,
        ["2026-09-P01", "2026-09-01", "22:00", "reel", "TRUE", "TRUE"],
        ["2026-09-P02", "2026-09-02", "22:00", "reel", "FALSE", "FALSE"],
        ["2026-09-P03", "2026-09-03", "22:00", "image", "TRUE", "FALSE"],
    ]
    st = dashboard.content_status(rows[1:], header, "2026-09")
    assert st["pendientes"] == 1          # P02 sin aprobar
    assert st["proximo"] == "2026-09-03"  # próximo aprobado sin publicar


def test_compute_health():
    assert dashboard.compute_health(None) == "gray"
    assert dashboard.compute_health({"cur": {"comments": 3}, "reach_trend_pct": 25}) == "green"
    assert dashboard.compute_health({"cur": {"comments": 0}, "reach_trend_pct": -30}) == "red"
    assert dashboard.compute_health({"cur": {"comments": 0}, "reach_trend_pct": 2}) == "yellow"


def test_build_decisions_has_four_sections():
    d = dashboard.build_decisions(
        {"name": "Demo"},
        {"cur": {"comments": 0, "reach": 600}, "reach_trend_pct": 2, "followers": 78000},
        {"pendientes": 2, "proximo": "2026-09-03"},
    )
    assert set(d) == {"contenido", "estrategia", "presupuesto", "cliente"}
    assert "2" in d["contenido"]  # menciona los 2 pendientes


def test_render_html_contains_client_and_decisions():
    data = [{
        "cfg": {"name": "Epic.Plane", "channels": {"instagram": {"enabled": True, "handle": "epic.plane"},
                 "youtube": {"enabled": False}, "linkedin": {"enabled": False}, "tiktok": {"enabled": False}}},
        "snap": {"followers": 78000, "cur": {"reach": 650, "likes": 9, "comments": 0}, "reach_trend_pct": 1, "top": None},
        "content": {"pendientes": 0, "proximo": "2026-09-03"},
        "health": "yellow",
        "decisions": {"contenido": "Al día.", "estrategia": "Prioriza reels.",
                      "presupuesto": "Sin acción.", "cliente": "Epic.Plane: estable."},
    }]
    html = dashboard.render_html(data)
    assert "Epic.Plane" in html
    assert "Prioriza reels." in html
    assert "78" in html  # followers formateados
    assert "próximamente" in html.lower()  # canales no habilitados


def test_build_decisions_declining_reach_alerts():
    d = dashboard.build_decisions(
        {"name": "X"},
        {"cur": {"comments": 0, "reach": 600}, "reach_trend_pct": -18, "followers": 78000},
        {"pendientes": 0, "proximo": None},
    )
    assert "BAJANDO" in d["estrategia"]


def test_build_decisions_no_content_says_unavailable():
    d = dashboard.build_decisions({"name": "X"}, None, {})
    assert "no disponible" in d["contenido"].lower()
