import pytest
import asyncio
from unittest.mock import patch, AsyncMock

@pytest.mark.asyncio
async def test_status_endpoint_initial(client):
    """Test initial status of the server."""
    response = client.get("/status")
    assert response.status_code == 200
    assert response.json() == {"running": False, "clients": 0}

@pytest.mark.asyncio
async def test_start_and_stop_acquisition(client):
    """Test starting and then stopping the acquisition."""
    # Start
    response = client.post("/start")
    assert response.status_code == 200
    assert response.json() == {"status": "Acquisition démarrée"}
    
    # Verify running status
    response = client.get("/status")
    assert response.status_code == 200
    assert response.json()["running"] is True

    # Stop
    response = client.post("/stop")
    assert response.status_code == 200
    assert response.json() == {"status": "Acquisition arrêtée"}

    # Verify stopped status
    # Note: The server task cancellation might be async, so we might need a small delay or retry in a real scenario,
    # but strictly speaking the 'manager.is_running' flag should be updated immediately.
    # However, since we are using TestClient and the app is running in the same process/loop if using AsyncClient (which we aren't here, we are using TestClient which is sync wrapping async), 
    # we rely on the manager state update.
    # The original test used await asyncio.sleep(0) which implies direct async execution.
    # With TestClient, the endpoints are called synchronously.
    
    response = client.get("/status")
    assert response.status_code == 200
    assert response.json()["running"] is False

@pytest.mark.asyncio
async def test_configure_sample_rate(client):
    """Test configuring the sample rate."""
    response = client.post("/configure", json={"action": "set_sample_rate", "params": {"value": 5000}})
    assert response.status_code == 200
    assert response.json() == {"status": "Action traitée", "action": "set_sample_rate"}

@pytest.mark.asyncio
async def test_invalid_action_graceful_handling(client):
    """Test that invalid actions are handled gracefully."""
    response = client.post("/configure", json={"action": "flying_pig_mode", "params": {}})
    # Based on original implementation, it returns status 'Action traitée' even for unknown actions, 
    # but arguably it should verify the implementation. 
    # The existing test expected {"status": "Action traitée", "action": "unknown_action"}
    assert response.status_code == 200
    assert response.json() == {"status": "Action traitée", "action": "flying_pig_mode"}

@pytest.mark.asyncio
async def test_websocket_data_streaming(client):
    """
    PRD Req: Visualisation, Data Plane.
    Verify that the WebSocket endpoint accepts connections and streams data.
    """
    # Start acquisition first to ensure data is being produced
    client.post("/start")
    
    with client.websocket_connect("/ws/data") as websocket:
        # Receive a message (binary data)
        data = websocket.receive_bytes()
        assert len(data) > 0, "Should receive non-empty binary data"
        
        # PRD Req: 8 channels, int16. 
        # We verify that the data length is a multiple of 8 * 2 (bytes per int16)
        assert len(data) % 16 == 0, "Data length should be multiple of 16 bytes (8 channels * 2 bytes)"

@pytest.mark.asyncio
async def test_client_disconnect_handler(client):
    """
    PRD Req: Stability.
    Verify that the server handles client disconnection gracefully and updates status.
    """
    client.post("/start")
    
    # 1. Connect
    with client.websocket_connect("/ws/data") as websocket:
        # Verify client is counted
        response = client.get("/status")
        assert response.json()["clients"] == 1
        
    # 2. Disconnect (Context manager exit closes connection)
    # Verify client count drops back to 0
    response = client.get("/status")
    assert response.json()["clients"] == 0

@pytest.mark.asyncio
async def test_save_to_csv_action(client):
    """
    PRD Req: Export.
    Verify the 'save_to_csv' action triggers the save logic.
    We mock the internal method to avoid actual file system writes.
    """
    from server.pynq_scope_server import manager
    
    # Mock the save_recorded_data method on the global manager instance
    with patch.object(manager, 'save_recorded_data', new_callable=AsyncMock) as mock_save:
        response = client.post("/configure", json={"action": "save_to_csv", "params": {}})
        assert response.status_code == 200
        assert response.json() == {"status": "Action traitée", "action": "save_to_csv"}
        
        # Verify the internal method was called
        mock_save.assert_called_once()

