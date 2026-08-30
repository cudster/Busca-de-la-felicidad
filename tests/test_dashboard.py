import json
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
