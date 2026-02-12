import pytest
from playwright.sync_api import Playwright, APIRequestContext, expect

@pytest.fixture(scope="module")
def api_context(playwright: Playwright, run_server):
    """
    Creates an APIRequestContext for the Playwright tests,
    pointing to the running server instance.
    """
    # run_server fixture ensures the server is running and returns the base URL
    base_url = "http://127.0.0.1:8000" 
    
    headers = {
        "Accept": "application/json",
    }
    request_context = playwright.request.new_context(
        base_url=base_url,
        extra_http_headers=headers
    )
    yield request_context
    request_context.dispose()

@pytest.mark.e2e
def test_full_acquisition_flow(api_context: APIRequestContext):
    """
    E2E Test simulating a client session:
    1. Check initial status (should be idle)
    2. Start Acquisition
    3. Verify running status
    4. Stop Acquisition
    5. Attempt to save data (mocked)
    """
    
    # 1. Check initial status
    response = api_context.get("/status")
    assert response.ok
    status = response.json()
    assert status["running"] is False
    
    # 2. Start Acquisition
    start_response = api_context.post("/start")
    assert start_response.ok
    assert start_response.json() == {"status": "Acquisition démarrée"}
    
    # 3. Verify running status
    # We might need a small delay here if the server updates status asynchronously
    # But since we are testing the API responsiveness, it should be reasonably fast.
    status_response = api_context.get("/status")
    assert status_response.ok
    assert status_response.json()["running"] is True
    
    # 4. Stop Acquisition
    stop_response = api_context.post("/stop")
    assert stop_response.ok
    assert stop_response.json() == {"status": "Acquisition arrêtée"}
    
    # 5. Verify stopped status
    final_status = api_context.get("/status")
    assert final_status.ok
    assert final_status.json()["running"] is False

@pytest.mark.e2e
def test_configure_flow(api_context: APIRequestContext):
    """
    Test the configuration flow via API.
    """
    # Set Sample Rate
    response = api_context.post("/configure", data={"action": "set_sample_rate", "params": {"value": 10000}})
    assert response.ok
    assert response.json()["action"] == "set_sample_rate"
    
