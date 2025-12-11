import sys
import threading
import time
from unittest.mock import MagicMock, patch

import pytest
import wx

# Mock 'pynq' to avoid ImportError and dependencies on hardware
sys.modules['pynq'] = MagicMock()

# Import the module and the communication class
from gui import pynq_scope_gui
from gui import communication

@pytest.fixture(scope='session')
def wx_app():
    """
    Ensure a wx.App exists for the tests.
    """
    app = wx.App(False)
    yield app
    app.Destroy()

@pytest.fixture
def gui_frame(wx_app):
    """
    Provides a clean instance of the PYNQScopeGUI for each test.
    """
    with patch('gui.pynq_scope_gui.ServerCommunicator'):
        frame = pynq_scope_gui.PYNQScopeGUI()
        frame.Show()
        yield frame
        frame.Close()
        wx.Yield() # Process pending events

def test_toggle_channel_visibility(gui_frame):
    """Test that toggling a channel checkbox updates the plot visibility."""
    channel_index = 0
    checkbox = gui_frame.channel_checkboxes[channel_index]
    assert checkbox.GetValue()

    # Uncheck the checkbox directly
    checkbox.SetValue(False)
    # Trigger event manually since programmatic change doesn't always trigger it in wx
    event = wx.CommandEvent(wx.EVT_CHECKBOX.typeId, checkbox.GetId())
    event.SetInt(0)
    checkbox.GetEventHandler().ProcessEvent(event)
    
    assert not checkbox.GetValue()
    assert not gui_frame.lines[channel_index].get_visible()

    # Check the checkbox again
    checkbox.SetValue(True)
    event = wx.CommandEvent(wx.EVT_CHECKBOX.typeId, checkbox.GetId())
    event.SetInt(1)
    checkbox.GetEventHandler().ProcessEvent(event)
    
    assert checkbox.GetValue()
    assert gui_frame.lines[channel_index].get_visible()

@patch('gui.pynq_scope_gui.WorkerThread')
def test_start_acquisition_success(mock_worker_thread_cls, gui_frame):
    """Test the start button's behavior on a successful connection."""
    # Mock the worker thread instance
    mock_thread_instance = mock_worker_thread_cls.return_value
    mock_thread_instance.start = MagicMock()

    # Simulate button click
    gui_frame.start_stop_button.SetValue(True)
    gui_frame.toggle_acquisition(None)

    mock_worker_thread_cls.assert_called_once()
    mock_thread_instance.start.assert_called_once()
    
    # Simulate status update callback from thread
    gui_frame.update_status_label(True, "Connected")
    wx.Yield() # Process UI updates

    assert "Server Status: Connected" in gui_frame.status_label.GetLabel()
    # Check color by checking foreground color of the label
    # Note: wx.Colour comparison might need explicit check
    assert gui_frame.status_label.GetForegroundColour() == wx.GREEN

@patch('gui.pynq_scope_gui.WorkerThread')
def test_start_acquisition_failure(mock_worker_thread_cls, gui_frame):
    """Test the start button's behavior on a failed connection."""
    mock_thread_instance = mock_worker_thread_cls.return_value
    
    # Simulate button click
    gui_frame.start_stop_button.SetValue(True)
    gui_frame.toggle_acquisition(None)

    mock_worker_thread_cls.assert_called_once()
    mock_thread_instance.start.assert_called_once()

    # Simulate callback
    gui_frame.update_status_label(False, "Connection failed")
    wx.Yield()

    assert "Server Status: Connection failed" in gui_frame.status_label.GetLabel()
    assert gui_frame.status_label.GetForegroundColour() == wx.RED

@patch('gui.pynq_scope_gui.wx.MessageBox')
def test_start_acquisition_exception(mock_message_box, gui_frame):
    """Test that an exception during start_acquisition shows an error message."""
    with patch('gui.pynq_scope_gui.WorkerThread', side_effect=Exception("Test Error")):
        gui_frame.start_stop_button.SetValue(True)
        gui_frame.toggle_acquisition(None)
        
        wx.Yield() # Allow CallAfter to process
        
        # Assert that a MessageBox was called
        mock_message_box.assert_called_once()
        assert "Server Status: Disconnected" in gui_frame.status_label.GetLabel()

@patch('gui.pynq_scope_gui.WorkerThread')
def test_stop_acquisition(mock_worker_thread_cls, gui_frame):
    """Test the stop button's behavior."""
    # Start acquisition first
    mock_thread_instance = mock_worker_thread_cls.return_value
    mock_thread_instance.is_alive.return_value = True

    gui_frame.start_stop_button.SetValue(True)
    gui_frame.toggle_acquisition(None)
    
    # Now, stop it
    gui_frame.start_stop_button.SetValue(False)
    gui_frame.toggle_acquisition(None)

    # Assert that the worker thread's stop and join methods were called
    mock_thread_instance.stop.assert_called_once()
    mock_thread_instance.join.assert_called_once()
    assert "Server Status: Disconnected" in gui_frame.status_label.GetLabel()
