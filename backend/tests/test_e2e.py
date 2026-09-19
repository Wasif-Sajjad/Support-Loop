"""End-to-end integration tests hitting the running Docker backend.

Requires INTEGRATION=1 and the Docker stack to be up (docker compose up).
"""
import os
import httpx
import pytest

API_URL = os.getenv("API_URL", "http://localhost:8000")

import uuid

@pytest.mark.asyncio
@pytest.mark.skipif(
    os.getenv("INTEGRATION") != "1",
    reason="Integration test — set INTEGRATION=1 to run against live Docker stack",
)
async def test_e2e_recover_password():
    """Submit a recover_password ticket. It is KB-backed, so it should auto-resolve."""
    async with httpx.AsyncClient(base_url=API_URL) as client:
        # POST /tickets - use unique string to bypass semantic cache
        unique_id = uuid.uuid4().hex[:8]
        payload = {"raw_text": f"I forgot my password and need to reset it. How do I do that? [{unique_id}]"}
        response = await client.post("/tickets", json=payload, timeout=60.0)
        assert response.status_code == 200, response.text
        ticket = response.json()
        
        assert ticket["intent"] == "recover_password"
        assert ticket["decision"] == "auto_resolve"
        assert ticket["status"] == "resolved"
        assert ticket["final_answer"] is not None
        assert "password" in ticket["final_answer"].lower()
        
        # GET /tickets/{id}/trace
        trace_resp = await client.get(f"/tickets/{ticket['id']}/trace")
        assert trace_resp.status_code == 200
        trace = trace_resp.json()
        
        assert trace["ticket_id"] == ticket["id"]
        assert trace["intent"] == "recover_password"
        assert trace["retrieved_chunk_count"] > 0
        assert trace["decision"] == "auto_resolve"
        assert len(trace["entailment_steps"]) > 0
        assert trace["citation_supported"] is True


@pytest.mark.asyncio
@pytest.mark.skipif(
    os.getenv("INTEGRATION") != "1",
    reason="Integration test — set INTEGRATION=1 to run against live Docker stack",
)
async def test_e2e_delete_account():
    """Submit a delete_account ticket. It is on the denylist (and has no KB), so it must escalate."""
    async with httpx.AsyncClient(base_url=API_URL) as client:
        # POST /tickets
        payload = {"raw_text": "Please delete my account immediately, I am done using this service."}
        response = await client.post("/tickets", json=payload, timeout=60.0)
        assert response.status_code == 200, response.text
        ticket = response.json()
        
        assert ticket["intent"] == "delete_account"
        assert ticket["decision"] == "escalate"
        assert ticket["status"] == "escalated"
        assert ticket["final_answer"] is None
        
        # GET /tickets/{id}/trace
        trace_resp = await client.get(f"/tickets/{ticket['id']}/trace")
        assert trace_resp.status_code == 200
        trace = trace_resp.json()
        
        assert trace["intent"] == "delete_account"
        assert trace["decision"] == "escalate"
        assert "denylist" in trace["critic_reason"].lower()
