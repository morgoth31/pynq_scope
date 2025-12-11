import sys
import asyncio
import time
import csv
import os
import logging
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime
import threading

import wx
import yaml
import numpy as np

import matplotlib
matplotlib.use('WXAgg')
from matplotlib.figure import Figure
from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg as FigureCanvas
import matplotlib.pyplot as plt

from communication import ServerCommunicator

# --- Configuration du Logging ---
if not os.path.exists("logs"):
    os.makedirs("logs")
log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
log_handler = TimedRotatingFileHandler("logs/gui.log", when="midnight", interval=1, backupCount=7)
log_handler.setFormatter(log_formatter)
logger = logging.getLogger()
logger.addHandler(log_handler)
logger.setLevel(logging.INFO)

class PYNQScopeGUI(wx.Frame):
    """Main window for the PYNQ Scope GUI."""

    def __init__(self):
        """Initializes the GUI."""
        super().__init__(None, title="PYNQ Scope GUI", size=(800, 600))

        self.panel = wx.Panel(self)
        self.main_sizer = wx.BoxSizer(wx.VERTICAL)
        self.panel.SetSizer(self.main_sizer)

        # Buffers and plot curves for 8 channels
        self.plot_buffers = [np.zeros(1000, dtype=np.int16) for _ in range(8)]
        self.lines = []
        self.channel_colors = ['y', 'b', 'g', 'r', 'c', 'm', 'k', 'tab:orange'] # wx/mpl colors
        
        # Helper to map mpl color codes to wx colors for dialogs wasn't strictly necessary if we stick to mpl colors for plotting
        # but for the color picker we might need conversion. For now, simplified to standard mpl colors.
        
        self.config = {}

        self._load_config_values()
        self.create_widgets()
        self._apply_config_to_widgets()

        self.communicator = ServerCommunicator(self.config.get("server_ip"))
        self.worker_thread = None
        
        self.last_update_time = time.time()
        self.chunk_count = 0
        self.data_amount = 0
        
        self.is_recording = False
        self.csv_file = None
        self.csv_writer = None
        
        self.Bind(wx.EVT_CLOSE, self.on_close)
        
        logger.info("GUI initialized.")

    def create_widgets(self):
        """Creates and arranges the widgets in the GUI."""
        
        # Status Label
        self.status_label = wx.StaticText(self.panel, label="Server Status: Disconnected")
        self.status_label.SetForegroundColour(wx.RED)
        self.main_sizer.Add(self.status_label, 0, wx.ALL, 5)

        # Plot Widget
        self.figure = Figure()
        self.axes = self.figure.add_subplot(111)
        self.axes.set_ylim(-32768, 32767) # Assuming int16
        self.axes.set_xlim(0, 1000)
        
        self.canvas = FigureCanvas(self.panel, -1, self.figure)
        self.main_sizer.Add(self.canvas, 1, wx.EXPAND | wx.ALL, 5)

        # Create plot curves for each channel
        for i in range(8):
            line, = self.axes.plot(self.plot_buffers[i], color=self.channel_colors[i], label=f"Channel {i}")
            self.lines.append(line)
        self.axes.legend(loc='upper right', fontsize='small')

        # Channels Controls
        self.channel_checkboxes = []
        channels_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        for i in range(8):
            v_sizer = wx.BoxSizer(wx.VERTICAL)
            checkbox = wx.CheckBox(self.panel, label=f"Ch {i}")
            checkbox.SetValue(True)
            # Bind event using a closure to capture 'i'
            checkbox.Bind(wx.EVT_CHECKBOX, lambda event, idx=i: self.update_plot_visibility(event, idx))
            self.channel_checkboxes.append(checkbox)
            v_sizer.Add(checkbox, 0, wx.ALIGN_CENTER)

            color_button = wx.Button(self.panel, label="Color", size=(50, -1))
            color_button.Bind(wx.EVT_BUTTON, lambda event, idx=i: self.open_color_dialog(event, idx))
            v_sizer.Add(color_button, 0, wx.ALIGN_CENTER)
            
            channels_sizer.Add(v_sizer, 1, wx.EXPAND | wx.ALL, 2)
            
        self.main_sizer.Add(channels_sizer, 0, wx.EXPAND | wx.ALL, 5)

        # Performance Metrics
        perf_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.refresh_rate_label = wx.StaticText(self.panel, label="Refresh Rate: 0 Hz")
        self.bandwidth_label = wx.StaticText(self.panel, label="Bandwidth: 0 B/s")
        perf_sizer.Add(self.refresh_rate_label, 1, wx.ALL, 5)
        perf_sizer.Add(self.bandwidth_label, 1, wx.ALL, 5)
        self.main_sizer.Add(perf_sizer, 0, wx.EXPAND)

        # Controls
        controls_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.start_stop_button = wx.ToggleButton(self.panel, label="Start")
        self.start_stop_button.Bind(wx.EVT_TOGGLEBUTTON, self.toggle_acquisition)
        
        self.record_button = wx.ToggleButton(self.panel, label="Record")
        self.record_button.Bind(wx.EVT_TOGGLEBUTTON, self.toggle_recording)
        
        self.save_button = wx.Button(self.panel, label="Save to CSV")
        self.save_button.Bind(wx.EVT_BUTTON, self.save_to_csv)

        controls_sizer.Add(self.start_stop_button, 0, wx.ALL, 5)
        controls_sizer.Add(self.record_button, 0, wx.ALL, 5)
        controls_sizer.Add(self.save_button, 0, wx.ALL, 5)
        self.main_sizer.Add(controls_sizer, 0, wx.EXPAND)

        # Acquisition Mode
        acq_mode_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.auto_mode_radio = wx.RadioButton(self.panel, label="Auto", style=wx.RB_GROUP)
        self.timed_mode_radio = wx.RadioButton(self.panel, label="Timed (s)")
        self.timed_duration_input = wx.TextCtrl(self.panel, value="10")
        self.timed_duration_input.Enable(False)
        
        self.Bind(wx.EVT_RADIOBUTTON, self.on_mode_change, self.auto_mode_radio)
        self.Bind(wx.EVT_RADIOBUTTON, self.on_mode_change, self.timed_mode_radio)

        acq_mode_sizer.Add(self.auto_mode_radio, 0, wx.ALL, 5)
        acq_mode_sizer.Add(self.timed_mode_radio, 0, wx.ALL, 5)
        acq_mode_sizer.Add(self.timed_duration_input, 0, wx.ALL, 5)
        self.main_sizer.Add(acq_mode_sizer, 0, wx.EXPAND)

        # Configuration
        config_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Server IP
        row1 = wx.BoxSizer(wx.HORIZONTAL)
        row1.Add(wx.StaticText(self.panel, label="Server IP:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        self.server_ip_input = wx.TextCtrl(self.panel)
        row1.Add(self.server_ip_input, 1, wx.EXPAND)
        config_sizer.Add(row1, 0, wx.EXPAND | wx.ALL, 2)
        
        # Data Folder
        row2 = wx.BoxSizer(wx.HORIZONTAL)
        row2.Add(wx.StaticText(self.panel, label="Data Folder:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        self.data_folder_input = wx.TextCtrl(self.panel)
        row2.Add(self.data_folder_input, 1, wx.EXPAND)
        config_sizer.Add(row2, 0, wx.EXPAND | wx.ALL, 2)
        
        # Rate
        row3 = wx.BoxSizer(wx.HORIZONTAL)
        row3.Add(wx.StaticText(self.panel, label="Rate:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        self.rate_input = wx.TextCtrl(self.panel)
        row3.Add(self.rate_input, 1, wx.EXPAND)
        config_sizer.Add(row3, 0, wx.EXPAND | wx.ALL, 2)

        self.main_sizer.Add(config_sizer, 0, wx.EXPAND | wx.ALL, 5)
        
        self.panel.Layout()
        logger.info("Widgets created.")

    def on_mode_change(self, event):
        self.timed_duration_input.Enable(self.timed_mode_radio.GetValue())

    def _load_config_values(self):
        """Loads configuration from config.yml into an instance variable."""
        try:
            with open("config.yml", "r") as f:
                self.config = yaml.safe_load(f)
                self.channel_colors = self.config.get("channel_colors", self.channel_colors)
                logger.info("Configuration loaded from config.yml")
        except FileNotFoundError:
            logger.warning("config.yml not found, using default configuration.")
            self.config = {
                "server_ip": "127.0.0.1:8000",
                "data_folder": "./data",
                "rate": 1000,
                "channel_colors": self.channel_colors
            }

    def _apply_config_to_widgets(self):
        """Applies the loaded configuration values to the UI widgets."""
        self.server_ip_input.SetValue(self.config.get("server_ip", "127.0.0.1:8000"))
        self.data_folder_input.SetValue(self.config.get("data_folder", "./data"))
        self.rate_input.SetValue(str(self.config.get("rate", 1000)))
        
        # Update plot colors
        for i, line in enumerate(self.lines):
            line.set_color(self.channel_colors[i])
        self.canvas.draw()

    def open_color_dialog(self, event, channel_index):
        """Opens a color dialog to select a color for the channel."""
        dlg = wx.ColourDialog(self)
        if dlg.ShowModal() == wx.ID_OK:
            color = dlg.GetColourData().GetColour()
            # Convert wx.Colour to hex #RRGGBB
            hex_color = f"#{color.Red():02x}{color.Green():02x}{color.Blue():02x}"
            self.channel_colors[channel_index] = hex_color
            self.lines[channel_index].set_color(hex_color)
            self.canvas.draw()
            logger.info(f"Channel {channel_index} color changed to {hex_color}")
        dlg.Destroy()

    def save_config(self):
        """Saves the current configuration to config.yml."""
        try:
            rate = int(self.rate_input.GetValue())
            config = {
                "server_ip": self.server_ip_input.GetValue(),
                "data_folder": self.data_folder_input.GetValue(),
                "rate": rate,
                "channel_colors": self.channel_colors
            }
            with open("config.yml", "w") as f:
                yaml.dump(config, f)
            logger.info("Configuration saved to config.yml")
        except ValueError:
            self.show_error_message("Invalid Rate", "The rate must be an integer.")
            logger.error("Failed to save config: invalid rate value.")

    def show_error_message(self, title, message):
        """Displays an error message in a message box."""
        wx.CallAfter(wx.MessageBox, message, title, wx.OK | wx.ICON_ERROR)

    def update_status_label(self, is_connected, message):
        """Updates the status label based on the connection status."""
        def _update():
            label_text = f"Server Status: {message}"
            self.status_label.SetLabel(label_text)
            if is_connected:
                self.status_label.SetForegroundColour(wx.GREEN)
            else:
                self.status_label.SetForegroundColour(wx.RED)
            self.status_label.Refresh()
        wx.CallAfter(_update)

    def toggle_acquisition(self, event):
        if self.start_stop_button.GetValue():
            self.start_acquisition()
        else:
            self.stop_acquisition()

    def start_acquisition(self):
        try:
            self.communicator.server_ip = self.server_ip_input.GetValue()

            mode = "auto"
            duration = 0
            if self.timed_mode_radio.GetValue():
                mode = "timed"
                duration = int(self.timed_duration_input.GetValue())

            rate = int(self.rate_input.GetValue())

            self.worker_thread = WorkerThread(self.communicator, mode, duration, rate, self.handle_data_callback, self.update_status_label)
            self.worker_thread.start()
            self.start_stop_button.SetLabel("Stop")
            logger.info("Acquisition started.")
            
        except Exception as e:
            logger.error(f"Failed to start acquisition: {e}")
            self.show_error_message("Failed to start acquisition", str(e))
            self.start_stop_button.SetValue(False)

    def stop_acquisition(self):
        if self.worker_thread:
            self.worker_thread.stop()
            self.worker_thread.join()
        
        self.update_status_label(False, "Disconnected")
        
        if self.is_recording:
            self.toggle_recording(None)
            
        self.start_stop_button.SetLabel("Start")
        self.start_stop_button.SetValue(False)
        logger.info("Acquisition stopped.")

    def handle_data_callback(self, data_chunk):
        wx.CallAfter(self.handle_data, data_chunk)

    def handle_data(self, data_chunk):
        num_channels, chunk_size = data_chunk.shape
        for i in range(num_channels):
            self.update_plot(i, data_chunk[i])
        
        self.canvas.draw()
            
        if self.is_recording and self.csv_writer:
            # Transpose and write data for CSV recording
            self.csv_writer.writerows(data_chunk.T)

    def toggle_recording(self, event):
        try:
            if not self.is_recording: # Start recording
                self.is_recording = True
                self.record_button.SetLabel("Stop Recording")
                self.record_button.SetValue(True)
                folder = self.data_folder_input.GetValue()
                if not os.path.exists(folder):
                    os.makedirs(folder)
                filename = f"record_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                filepath = os.path.join(folder, filename)
                self.csv_file = open(filepath, "w", newline="")
                self.csv_writer = csv.writer(self.csv_file)
                # Write header for CSV
                self.csv_writer.writerow([f"Channel {i}" for i in range(8)])
                logger.info(f"Recording started, saving to {filepath}")
            else: # Stop recording
                self.is_recording = False
                self.record_button.SetLabel("Record")
                self.record_button.SetValue(False)
                if self.csv_file:
                    self.csv_file.close()
                    self.csv_file = None
                    self.csv_writer = None
                logger.info("Recording stopped.")
        except Exception as e:
            logger.error(f"Failed to toggle recording: {e}")
            self.show_error_message("Failed to toggle recording", str(e))

    def update_plot_visibility(self, event, channel_index):
        line = self.lines[channel_index]
        line.set_visible(self.channel_checkboxes[channel_index].GetValue())
        self.canvas.draw()

    def update_plot(self, channel_index, data_chunk):
        # Update plot buffer for the specific channel
        self.plot_buffers[channel_index] = np.roll(self.plot_buffers[channel_index], -len(data_chunk))
        self.plot_buffers[channel_index][-len(data_chunk):] = data_chunk
        self.lines[channel_index].set_ydata(self.plot_buffers[channel_index])
        
        # Update performance metrics
        self.chunk_count += 1
        self.data_amount += len(data_chunk) * 2 # 2 bytes per sample
        current_time = time.time()
        elapsed_time = current_time - self.last_update_time
        if elapsed_time > 1:
            refresh_rate = self.chunk_count / elapsed_time
            bandwidth = self.data_amount / elapsed_time / 1024  # Convert to kB/s
            self.refresh_rate_label.SetLabel(f"Refresh Rate: {refresh_rate:.2f} Hz")
            self.bandwidth_label.SetLabel(f"Bandwidth: {bandwidth:.2f} kB/s")
            self.chunk_count = 0
            self.data_amount = 0
            self.last_update_time = current_time

    def on_close(self, event):
        self.save_config()
        if self.worker_thread and self.worker_thread.is_alive():
             self.stop_acquisition()
        logger.info("GUI closed.")
        self.Destroy()

    def save_to_csv(self, event):
        # Run async in a separate thread to avoid blocking UI
        threading.Thread(target=lambda: asyncio.run(self.communicator.control_api("save_to_csv", is_config=True))).start()

class WorkerThread(threading.Thread):
    def __init__(self, communicator, mode="auto", duration=0, rate=1000, data_callback=None, status_callback=None):
        super().__init__()
        self.communicator = communicator
        self.mode = mode
        self.duration = duration
        self.rate = rate
        self.data_callback = data_callback
        self.status_callback = status_callback
        self.loop = asyncio.new_event_loop()
        self._stop_event = threading.Event()

    def run(self):
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(self.run_async())
        finally:
            self.loop.close()

    async def run_async(self):
        try:
            start_response = await self.communicator.control_api("start", params={"mode": self.mode, "duration": self.duration, "rate": self.rate})
            if not start_response:
                if self.status_callback: self.status_callback(False, "Failed to start acquisition")
                return

            if await self.communicator.connect():
                if self.status_callback: self.status_callback(True, "Connected")
                await self.communicator.data_receiver(self.handle_data_bridge)
            else:
                if self.status_callback: self.status_callback(False, "Connection failed")

            # Final status update after disconnection or end of acquisition
            status = await self.communicator.get_status()
            if status:
                running_status = "Running" if status.get("running") else "Stopped"
                if self.status_callback: self.status_callback(False, f"Disconnected ({running_status})")
            else:
                if self.status_callback: self.status_callback(False, "Disconnected")
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"WorkerThread Error: {e}")
            if self.status_callback: self.status_callback(False, f"Error: {e}")

    def stop(self):
        self._stop_event.set()
        self.communicator.stop_event.set()
        if self.loop.is_running():
            self.loop.call_soon_threadsafe(self._async_stop)

    def _async_stop(self):
        asyncio.create_task(self.communicator.control_api("stop"))
        asyncio.create_task(self.communicator.disconnect())
        # self.loop.stop() # Don't stop loop immediately, let tasks finish

    def handle_data_bridge(self, data):
        if self.data_callback:
            self.data_callback(data)

if __name__ == "__main__":
    app = wx.App()
    frame = PYNQScopeGUI()
    frame.Show()
    app.MainLoop()
