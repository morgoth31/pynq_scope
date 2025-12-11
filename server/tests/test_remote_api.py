import pytest
import httpx
import argparse
import asyncio
import sys

# Configure default base URL
DEFAULT_BASE_URL = "http://localhost:8000"

def get_base_url():
    """Retrieves URI from command line args or default."""
    # This is a bit hacky for pytest, but allows passing --url
    for arg in sys.argv:
        if arg.startswith("--url="):
            return arg.split("=", 1)[1]
    return DEFAULT_BASE_URL

BASE_URL = get_base_url()
print(f"Testing against: {BASE_URL}")

@pytest.fixture
def api_client():
    return httpx.Client(base_url=BASE_URL, timeout=5.0)

def test_status_endpoint(api_client):
    """Test that the /status endpoint is accessible and returns valid JSON."""
    try:
        response = api_client.get("/status")
    except httpx.ConnectError:
        pytest.fail(f"Could not connect to {BASE_URL}. Is the server running?")
    
    assert response.status_code == 200, f"Status endpoint returned {response.status_code}"
    data = response.json()
    assert "running" in data
    assert "clients" in data

def test_start_stop_flow(api_client):
    """Test the start and stop flow."""
    # Start
    resp = api_client.post("/start", json={"mode": "auto"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "Acquisition démarrée"

    # Check status
    resp = api_client.get("/status")
    assert resp.status_code == 200
    assert resp.json()["running"] is True

    # Stop
    resp = api_client.post("/stop")
    assert resp.status_code == 200
    assert resp.json()["status"] == "Acquisition arrêtée"
    
    # Check status finally
    resp = api_client.get("/status")
    assert resp.status_code == 200
    assert resp.json()["running"] is False

if __name__ == "__main__":
    # If run directly as a script
    url = DEFAULT_BASE_URL
    if len(sys.argv) > 1:
        url = sys.argv[1]
    
    print(f"Running manual check on {url}...")
    try:
        with httpx.Client(base_url=url, timeout=5.0) as client:
            print("Checking status...")
            r = client.get("/status")
            print(f"Status: {r.status_code} - {r.json()}")
            
            print("Starting acquisition...")
            r = client.post("/start", json={"mode": "auto"})
            print(f"Start: {r.status_code} - {r.json()}")
            
            print("Stopping acquisition...")
            r = client.post("/stop")
            print(f"Stop: {r.status_code} - {r.json()}")
            
    except Exception as e:
        print(f"Test failed: {e}")
