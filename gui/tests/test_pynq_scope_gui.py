import sys
from unittest.mock import MagicMock, patch

import pytest
from PyQt6.QtCore import Qt

# Mock 'pynq' to avoid ImportError and dependencies on hardware
sys.modules['pynq'] = MagicMock()

# Import the module and the communication class
from gui import pynq_scope_gui
from gui import communication

@pytest.fixture
def gui_app(qtbot):
    """
    Provides a clean instance of the PYNQScopeGUI for each test.
    """
    with patch('gui.pynq_scope_gui.ServerCommunicator'):
        window = pynq_scope_gui.PYNQScopeGUI()
        qtbot.addWidget(window)
        yield window

def test_toggle_channel_visibility(gui_app, qtbot):
    """Test that toggling a channel checkbox updates the plot visibility."""
    channel_index = 0
    checkbox = gui_app.channel_checkboxes[channel_index]
    assert checkbox.isChecked()

    # Uncheck the checkbox directly
    checkbox.setChecked(False)
    assert not checkbox.isChecked()
    assert not gui_app.plot_curves[channel_index].isVisible()

    # Check the checkbox again
    checkbox.setChecked(True)
    assert checkbox.isChecked()
    assert gui_app.plot_curves[channel_index].isVisible()

@patch('gui.pynq_scope_gui.WorkerThread')
def test_start_acquisition_success(mock_worker_thread, gui_app, qtbot):
    """Test the start button's behavior on a successful connection."""
    gui_app.start_button.click()

    mock_worker_thread.assert_called_once()
    gui_app.worker_thread.start.assert_called_once()

    # Get the callback function passed to connect() and call it
    connected_slot = gui_app.worker_thread.connection_status.connect.call_args.args[0]
    connected_slot(True, "Connected")

    assert "Server Status: Connected" in gui_app.status_label.text()
    assert "color: green" in gui_app.status_label.styleSheet()

@patch('gui.pynq_scope_gui.WorkerThread')
def test_start_acquisition_failure(mock_worker_thread, gui_app, qtbot):
    """Test the start button's behavior on a failed connection."""
    gui_app.start_button.click()

    mock_worker_thread.assert_called_once()
    gui_app.worker_thread.start.assert_called_once()

    # Get the callback function passed to connect() and call it
    connected_slot = gui_app.worker_thread.connection_status.connect.call_args.args[0]
    connected_slot(False, "Connection failed")

    assert "Server Status: Connection failed" in gui_app.status_label.text()
    assert "color: red" in gui_app.status_label.styleSheet()

@patch('gui.pynq_scope_gui.QMessageBox')
def test_start_acquisition_exception(mock_message_box, gui_app, qtbot):
    """Test that an exception during start_acquisition shows an error message."""
    with patch('gui.pynq_scope_gui.WorkerThread', side_effect=Exception("Test Error")):
        gui_app.start_button.click()
        # Assert that a QMessageBox instance was created and shown
        mock_message_box.return_value.exec.assert_called_once()
        assert "Server Status: Disconnected" in gui_app.status_label.text()

@patch('gui.pynq_scope_gui.WorkerThread')
def test_stop_acquisition(mock_worker_thread, gui_app, qtbot):
    """Test the stop button's behavior."""
    # Start acquisition first
    gui_app.start_button.click()
    mock_worker_thread.assert_called_once()
    gui_app.worker_thread.start.assert_called_once()

    # Now, stop it
    gui_app.stop_button.click()

    # Assert that the worker thread's stop and wait methods were called
    gui_app.worker_thread.stop.assert_called_once()
    gui_app.worker_thread.wait.assert_called_once()
    assert "Server Status: Disconnected" in gui_app.status_label.text()
