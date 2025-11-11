import sys
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

# Mock 'pynq' to avoid ImportError and dependencies on hardware
sys.modules['pynq'] = MagicMock()

# Now that 'pynq' is mocked, we can safely import the server application.
# We import the module itself to modify its global 'manager' variable.
from server import pynq_scope_server
from server.pynq_scope_server import app, AcquisitionManager
from fastapi.testclient import TestClient

# Instantiate a manager for testing and assign it to the global variable
# in the server module. This is crucial and must be done before creating TestClient.
test_manager_instance = AcquisitionManager(emulate=True)
pynq_scope_server.manager = test_manager_instance

# Now that the manager is set, create the client.
client = TestClient(app)


@pytest.fixture(autouse=True)
def manager():
    """
    Provides the test manager instance for tests and resets its state
    before each test for isolation.
    """
    # Reset state for test isolation
    test_manager_instance.is_running = False
    if test_manager_instance.acquisition_task:
        if not test_manager_instance.acquisition_task.done():
            test_manager_instance.acquisition_task.cancel()
    test_manager_instance.acquisition_task = None
    test_manager_instance.active_connections = []
    test_manager_instance.data_buffer = []
    yield test_manager_instance


@pytest.mark.asyncio
async def test_handle_action_set_sample_rate(manager):
    """Test the 'set_sample_rate' action."""
    action = "set_sample_rate"
    params = {"value": 2000}
    result = await manager.handle_action(action, params)
    assert result == {"status": "Action traitée", "action": action}


@pytest.mark.asyncio
async def test_handle_action_save_to_csv(manager):
    """Test the 'save_to_csv' action."""
    manager.save_recorded_data = AsyncMock()
    action = "save_to_csv"
    params = {}
    result = await manager.handle_action(action, params)
    assert result == {"status": "Action traitée", "action": action}
    manager.save_recorded_data.assert_called_once()


@pytest.mark.asyncio
async def test_handle_action_unknown_action(manager):
    """Test an unknown action."""
    action = "unknown_action"
    params = {}
    result = await manager.handle_action(action, params)
    assert result == {"status": "Action traitée", "action": action}


@pytest.mark.asyncio
async def test_handle_action_with_error(manager):
    """Test an action that raises an error."""
    with patch.object(manager, 'save_recorded_data', side_effect=Exception("Test Error")):
        action = "save_to_csv"
        params = {}
        result = await manager.handle_action(action, params)
        assert result["status"] == "erreur"
        assert result["message"] == "Test Error"


@pytest.mark.asyncio
async def test_status_endpoint_comprehensive(manager):
    """Test the /status endpoint comprehensively."""
    # 1. Test status before acquisition
    response = client.get("/status")
    assert response.status_code == 200
    assert response.json() == {"running": False, "clients": 0}

    # 2. Test status during acquisition
    client.post("/start")
    await asyncio.sleep(0)  # Yield control to allow the task to start
    response = client.get("/status")
    assert response.status_code == 200
    assert response.json() == {"running": True, "clients": 0}

    # 3. Test status with a connected client
    with client.websocket_connect("/ws/data") as websocket:
        response = client.get("/status")
        assert response.status_code == 200
        assert response.json() == {"running": True, "clients": 1}

    # 4. Test status after client disconnects
    response = client.get("/status")
    assert response.status_code == 200
    assert response.json() == {"running": True, "clients": 0}

    # 5. Test status after acquisition stops
    client.post("/stop")
    await asyncio.sleep(0) # Yield control to allow the task to stop
    response = client.get("/status")
    assert response.status_code == 200
    assert response.json() == {"running": False, "clients": 0}


@pytest.mark.asyncio
async def test_start_endpoint(manager):
    """Test the /start endpoint."""
    response = client.post("/start")
    assert response.status_code == 200
    assert response.json() == {"status": "Acquisition démarrée"}
    await asyncio.sleep(0)  # Yield control to allow the task to start
    assert manager.is_running is True


@pytest.mark.asyncio
async def test_stop_endpoint(manager):
    """Test the /stop endpoint."""
    # First, start the acquisition
    client.post("/start")
    await asyncio.sleep(0)  # Yield control to allow the task to start
    assert manager.is_running is True

    # Then, stop it
    response = client.post("/stop")
    assert response.status_code == 200
    assert response.json() == {"status": "Acquisition arrêtée"}
    assert manager.is_running is False


@pytest.mark.asyncio
async def test_configure_endpoint(manager):
    """Test the /configure endpoint."""
    response = client.post("/configure", json={"action": "set_sample_rate", "params": {"value": 3000}})
    assert response.status_code == 200
    assert response.json() == {"status": "Action traitée", "action": "set_sample_rate"}
