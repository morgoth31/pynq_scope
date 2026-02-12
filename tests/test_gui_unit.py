import pytest
import numpy as np
from unittest.mock import MagicMock, patch
import sys

# Mock wx and matplotlib before importing gui
sys.modules['wx'] = MagicMock()
sys.modules['matplotlib'] = MagicMock()
sys.modules['matplotlib.pyplot'] = MagicMock()
sys.modules['matplotlib.figure'] = MagicMock()
sys.modules['matplotlib.backends.backend_wxagg'] = MagicMock()

# Now import the GUI class
from gui.pynq_scope_gui import PYNQScopeGUI

class TestGUIUnit:
    @pytest.fixture
    def gui(self):
        """Creates a GUI instance with mocked dependencies."""
        with patch('gui.pynq_scope_gui.ServerCommunicator') as MockCommunicator:
            app = PYNQScopeGUI()
            app.communicator = MockCommunicator.return_value
            # Mock UI elements that might be accessed
            app.main_sizer = MagicMock()
            app.panel = MagicMock()
            app.lines = [MagicMock() for _ in range(8)]
            app.canvas = MagicMock()
            app.refresh_rate_label = MagicMock()
            app.bandwidth_label = MagicMock()
            return app

    def test_initial_state(self, gui):
        """Verify initial state of buffering and config."""
        assert len(gui.plot_buffers) == 8
        assert len(gui.plot_buffers[0]) == 1000
        assert gui.is_recording is False

    def test_update_plot_logic(self, gui):
        """Verify that update_plot correctly shifts buffer and adds new data."""
        # Initial buffer state (zeros)
        assert np.all(gui.plot_buffers[0] == 0)
        
        # Incoming data chunk for channel 0 (10 samples)
        new_data = np.ones(10, dtype=np.int16) * 5
        
        gui.update_plot(0, new_data)
        
        # Verify buffer shifted: last 10 samples should be 5
        assert np.all(gui.plot_buffers[0][-10:] == 5)
        # Verify previous samples are still 0 (checking index -11)
        assert gui.plot_buffers[0][-11] == 0

    def test_start_acquisition(self, gui):
        """Verify start acquisition parameters."""
        gui.server_ip_input = MagicMock()
        gui.server_ip_input.GetValue.return_value = "1.2.3.4"
        gui.rate_input = MagicMock()
        gui.rate_input.GetValue.return_value = "2000"
        gui.timed_mode_radio = MagicMock()
        gui.timed_mode_radio.GetValue.return_value = False # Auto mode
        
        # Mock WorkerThread to avoid actual threading
        with patch('gui.pynq_scope_gui.WorkerThread') as MockWorker:
            gui.start_acquisition()
            
            # Check if WorkerThread was initialized with correct rate
            args, _ = MockWorker.call_args
            # args[3] is rate in constructor: __init__(self, communicator, mode, duration, rate, ...)
            assert args[3] == 2000 
            
            # Check if thread started
            MockWorker.return_value.start.assert_called_once()
