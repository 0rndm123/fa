"""Offline API and workbench tests; no network providers or paid AI."""
from fastapi.testclient import TestClient
from fa_agents.webapp import app

client = TestClient(app)


def test_page_assets_and_chat_controls():
    page = client.get("/")
    assert page.status_code == 200
    assert "Research chat" in page.text
    assert 'id="chatMinimize"' in page.text
    assert 'id="chatMaximize"' in page.text
    assert 'id="reportArea"' in page.text
    js = client.get("/static/app.js")
    assert js.status_code == 200
    assert "chat-minimized" in js.text
    assert "chat-maximized" in js.text
    assert client.get("/static/styles.css").status_code == 200


def test_financial_data_capability():
    r = client.get("/api/capabilities")
    assert r.status_code == 200
    agent_ids = [x["id"] for x in r.json()["agents"]]
    assert "financial_data" in agent_ids


def test_chat_analysis_and_historical_financials():
    r = client.post("/api/analyze", json={
        "symbol": "DEMO", "mode": "demo", "asset_class": "equity",
        "question": "How did revenue and free cash flow develop?",
        "agents": ["financial_data", "fundamental", "risk"],
        "history": [{"role": "user", "content": "Review the company's finances."}],
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert "DEMO" in body["answer"]
    assert body["report"]["data_mode"] == "demo"
    data = next(x for x in body["report"]["results"] if x["agent_id"] == "financial_data")
    assert data["status"] == "completed"
    assert len(data["observations"]) == 8
    assert all(x["source_id"] for x in data["observations"])


def test_reject_demo_ticker_or_llm():
    assert client.post("/api/analyze", json={"symbol": "NVDA", "mode": "demo"}).status_code == 400
    assert client.post("/api/analyze", json={"symbol": "DEMO", "mode": "demo", "llm": True}).status_code == 400


def test_reject_unknown_agents():
    r = client.post("/api/analyze", json={"symbol": "DEMO", "mode": "demo", "agents": ["typo"]})
    assert r.status_code == 400


def test_csv_upload_technical_series():
    content = "\n".join(["date,close"] + [
        f"2026-01-{day:02d},{100+day}" for day in range(1,29)
    ]) + "\n"
    upload = client.post("/api/upload-prices", files={"file": ("prices.csv", content, "text/csv")})
    assert upload.status_code == 200, upload.text
    upload_id = upload.json()["upload_id"]
    result = client.post("/api/analyze", json={
        "symbol": "DEMO", "mode": "demo", "asset_class": "equity",
        "agents": ["technical"], "question": "Show daily moving averages.",
        "price_upload_id": upload_id,
    })
    assert result.status_code == 200, result.text
    agent = result.json()["report"]["results"][0]
    assert agent["agent_id"] == "technical"
    assert agent["metrics"]["sma20"] == 118.5
    assert len(agent["observations"]) == 28


def test_invalid_and_oversized_csv_uploads():
    r = client.post("/api/upload-prices", files={"file": ("data.txt", b"hello", "text/plain")})
    assert r.status_code == 400
    r = client.post("/api/upload-prices", files={"file": ("large.csv", b"1"*2_000_100, "text/csv")})
    assert r.status_code == 413


def test_reject_foreign_request_origin():
    r = client.post("/api/analyze", headers={"Origin": "https://another-site.example"},
                    json={"symbol": "DEMO", "mode": "demo"})
    assert r.status_code == 403
