import sys
import os
import threading
import time
import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient
import uvicorn

# 1. Mock 'pynq' ONLY if we are NOT running on real hardware (default behavior)
# This allows tests to run on the actual PYNQ board without mocking.
if os.environ.get("PYNQ_SCOPE_REAL_HW") != "1":
    sys.modules['pynq'] = MagicMock()
    sys.modules['pynq.overlay'] = MagicMock()
    sys.modules['pynq.lib'] = MagicMock()
else:
    print("Running on REAL HARDWARE. pynq library will NOT be mocked.")

# Add project root to sys.path to allow imports from 'server'
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from server import pynq_scope_server
from server.pynq_scope_server import app, AcquisitionManager

# Initialize manager based on environment
# If REAL_HW, emulate=False. Otherwise emulate=True.
is_emulation = os.environ.get("PYNQ_SCOPE_REAL_HW") != "1"
test_manager_instance = AcquisitionManager(emulate=is_emulation)
pynq_scope_server.manager = test_manager_instance


@pytest.fixture(autouse=True)
def reset_manager_state():
    """
    Resets the global manager state before each test to ensure isolation.
    """
    test_manager_instance.is_running = False
    if test_manager_instance.acquisition_task:
        if not test_manager_instance.acquisition_task.done():
            test_manager_instance.acquisition_task.cancel()
    test_manager_instance.acquisition_task = None
    test_manager_instance.active_connections = []
    test_manager_instance.data_buffer = []


@pytest.fixture
def client():
    """
    FastAPI TestClient for integration tests.
    """
    return TestClient(app)


@pytest.fixture(scope="session")
def run_server():
    """
    Starts the Uvicorn server in a separate thread for E2E tests with Playwright.
    Returns the base URL.
    """
    proc = threading.Thread(target=uvicorn.run, args=(app,), kwargs={"host": "127.0.0.1", "port": 8000, "log_level": "critical"}, daemon=True)
    proc.start()
    time.sleep(1)  # Give server time to start
    return "http://127.0.0.1:8000"
