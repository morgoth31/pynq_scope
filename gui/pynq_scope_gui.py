import sys
import asyncio
import time
import csv
import os
import logging
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QLineEdit, QSlider, QMessageBox, QCheckBox, QRadioButton, QColorDialog
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor
import yaml
import numpy as np
import pyqtgraph as pg
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

class PYNQScopeGUI(QMainWindow):
    """Main window for the PYNQ Scope GUI."""

    def __init__(self):
        """Initializes the GUI."""
        super().__init__()
        self.setWindowTitle("PYNQ Scope GUI")
        self.setGeometry(100, 100, 800, 600)

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)

        # Buffers and plot curves for 8 channels
        self.plot_buffers = [np.zeros(1000, dtype=np.int16) for _ in range(8)]
        self.plot_curves = []
        self.channel_colors = ['y', 'b', 'g', 'r', 'c', 'm', 'w', 'k'] # Default colors
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
        logger.info("GUI initialized.")

    def create_widgets(self):
        """Creates and arranges the widgets in the GUI."""
        self.status_label = QLabel("Server Status: Disconnected")
        self.status_label.setStyleSheet("color: red")
        self.layout.addWidget(self.status_label)
        
        self.plot_widget = pg.PlotWidget()
        self.layout.addWidget(self.plot_widget)

        # Create plot curves for each channel
        for i in range(8):
            curve = self.plot_widget.plot(pen=self.channel_colors[i], name=f"Channel {i}")
            self.plot_curves.append(curve)

        self.channel_checkboxes = []
        self.channels_layout = QHBoxLayout()
        for i in range(8):
            checkbox = QCheckBox(f"Channel {i}")
            checkbox.setChecked(True)
            checkbox.stateChanged.connect(self.update_plot_visibility)
            self.channel_checkboxes.append(checkbox)
            self.channels_layout.addWidget(checkbox)

            color_button = QPushButton("Color")
            color_button.clicked.connect(lambda _, ch=i: self.open_color_dialog(ch))
            self.channels_layout.addWidget(color_button)
        self.layout.addLayout(self.channels_layout)

        self.perf_layout = QHBoxLayout()
        self.refresh_rate_label = QLabel("Refresh Rate: 0 Hz")
        self.bandwidth_label = QLabel("Bandwidth: 0 B/s")
        self.perf_layout.addWidget(self.refresh_rate_label)
        self.perf_layout.addWidget(self.bandwidth_label)
        self.layout.addLayout(self.perf_layout)

        self.controls_layout = QHBoxLayout()
        self.start_stop_button = QPushButton("Start")
        self.start_stop_button.setCheckable(True)
        self.start_stop_button.clicked.connect(self.toggle_acquisition)
        self.record_button = QPushButton("Record")
        self.record_button.setCheckable(True)
        self.record_button.clicked.connect(self.toggle_recording)

        self.save_button = QPushButton("Save to CSV")
        self.save_button.clicked.connect(self.save_to_csv)

        self.controls_layout.addWidget(self.start_stop_button)
        self.controls_layout.addWidget(self.record_button)
        self.controls_layout.addWidget(self.save_button)
        self.layout.addLayout(self.controls_layout)

        self.acquisition_mode_layout = QHBoxLayout()
        self.auto_mode_radio = QRadioButton("Auto")
        self.auto_mode_radio.setChecked(True)
        self.timed_mode_radio = QRadioButton("Timed (s)")
        self.timed_duration_input = QLineEdit("10")
        self.timed_duration_input.setEnabled(False)
        self.timed_mode_radio.toggled.connect(self.timed_duration_input.setEnabled)

        self.acquisition_mode_layout.addWidget(self.auto_mode_radio)
        self.acquisition_mode_layout.addWidget(self.timed_mode_radio)
        self.acquisition_mode_layout.addWidget(self.timed_duration_input)
        self.layout.addLayout(self.acquisition_mode_layout)

        self.config_layout = QVBoxLayout()
        
        self.server_ip_label = QLabel("Server IP:")
        self.server_ip_input = QLineEdit()
        self.config_layout.addWidget(self.server_ip_label)
        self.config_layout.addWidget(self.server_ip_input)
        
        self.data_folder_label = QLabel("Data Folder:")
        self.data_folder_input = QLineEdit()
        self.config_layout.addWidget(self.data_folder_label)
        self.config_layout.addWidget(self.data_folder_input)

        self.rate_label = QLabel("Rate:")
        self.rate_input = QLineEdit()
        self.config_layout.addWidget(self.rate_label)
        self.config_layout.addWidget(self.rate_input)
        
        self.layout.addLayout(self.config_layout)
        logger.info("Widgets created.")

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
        self.server_ip_input.setText(self.config.get("server_ip", "127.0.0.1:8000"))
        self.data_folder_input.setText(self.config.get("data_folder", "./data"))
        self.rate_input.setText(str(self.config.get("rate", 1000)))

    def open_color_dialog(self, channel_index):
        """Opens a color dialog to select a color for the channel."""
        color = QColorDialog.getColor()
        if color.isValid():
            self.channel_colors[channel_index] = color.name()
            self.plot_curves[channel_index].setPen(self.channel_colors[channel_index])
            logger.info(f"Channel {channel_index} color changed to {color.name()}")

    def save_config(self):
        """Saves the current configuration to config.yml."""
        try:
            rate = int(self.rate_input.text())
            config = {
                "server_ip": self.server_ip_input.text(),
                "data_folder": self.data_folder_input.text(),
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
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Icon.Critical)
        msg_box.setText(title)
        msg_box.setInformativeText(message)
        msg_box.setWindowTitle("Error")
        msg_box.exec()

    def update_status_label(self, is_connected, message):
        """Updates the status label based on the connection status."""
        if is_connected:
            self.status_label.setText(f"Server Status: {message}")
            self.status_label.setStyleSheet("color: green")
        else:
            self.status_label.setText(f"Server Status: {message}")
            self.status_label.setStyleSheet("color: red")

    def toggle_acquisition(self):
        if self.start_stop_button.isChecked():
            self.start_acquisition()
        else:
            self.stop_acquisition()

    def start_acquisition(self):
        try:
            self.communicator.server_ip = self.server_ip_input.text()

            mode = "auto"
            duration = 0
            if self.timed_mode_radio.isChecked():
                mode = "timed"
                duration = int(self.timed_duration_input.text())

            rate = int(self.rate_input.text())

            self.worker_thread = WorkerThread(self.communicator, mode, duration, rate)
            self.worker_thread.data_received.connect(self.handle_data)
            self.worker_thread.connection_status.connect(self.update_status_label)
            self.worker_thread.start()
            self.start_stop_button.setText("Stop")
            logger.info("Acquisition started.")
        except Exception as e:
            logger.error(f"Failed to start acquisition: {e}")
            self.show_error_message("Failed to start acquisition", str(e))
            self.start_stop_button.setChecked(False)

    def stop_acquisition(self):
        if self.worker_thread:
            self.worker_thread.stop()
            self.worker_thread.wait()
        self.status_label.setText("Server Status: Disconnected")
        self.status_label.setStyleSheet("color: red")
        if self.is_recording:
            self.toggle_recording()
        self.start_stop_button.setText("Start")
        self.start_stop_button.setChecked(False)
        logger.info("Acquisition stopped.")

    def handle_data(self, data_chunk):
        num_channels, chunk_size = data_chunk.shape
        for i in range(num_channels):
            self.update_plot(i, data_chunk[i])

        if self.is_recording:
            # Transpose and write data for CSV recording
            self.csv_writer.writerows(data_chunk.T)

    def toggle_recording(self):
        try:
            if not self.is_recording:
                self.is_recording = True
                self.record_button.setText("Stop Recording")
                folder = self.data_folder_input.text()
                if not os.path.exists(folder):
                    os.makedirs(folder)
                filename = f"record_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                filepath = os.path.join(folder, filename)
                self.csv_file = open(filepath, "w", newline="")
                self.csv_writer = csv.writer(self.csv_file)
                # Write header for CSV
                self.csv_writer.writerow([f"Channel {i}" for i in range(8)])
                logger.info(f"Recording started, saving to {filepath}")
            else:
                self.is_recording = False
                self.record_button.setText("Record")
                self.record_button.setChecked(False)
                if self.csv_file:
                    self.csv_file.close()
                    self.csv_file = None
                logger.info("Recording stopped.")
        except Exception as e:
            logger.error(f"Failed to toggle recording: {e}")
            self.show_error_message("Failed to toggle recording", str(e))

    def update_plot_visibility(self):
        for i, checkbox in enumerate(self.channel_checkboxes):
            if checkbox.isChecked():
                self.plot_curves[i].show()
            else:
                self.plot_curves[i].hide()

    def update_plot(self, channel_index, data_chunk):
        # Update plot buffer for the specific channel
        self.plot_buffers[channel_index] = np.roll(self.plot_buffers[channel_index], -len(data_chunk))
        self.plot_buffers[channel_index][-len(data_chunk):] = data_chunk
        self.plot_curves[channel_index].setData(self.plot_buffers[channel_index])
        
        # Update performance metrics
        self.chunk_count += 1
        self.data_amount += len(data_chunk) * 2 # 2 bytes per sample
        current_time = time.time()
        elapsed_time = current_time - self.last_update_time
        if elapsed_time > 1:
            refresh_rate = self.chunk_count / elapsed_time
            bandwidth = self.data_amount / elapsed_time / 1024  # Convert to kB/s
            self.refresh_rate_label.setText(f"Refresh Rate: {refresh_rate:.2f} Hz")
            self.bandwidth_label.setText(f"Bandwidth: {bandwidth:.2f} kB/s")
            self.chunk_count = 0
            self.data_amount = 0
            self.last_update_time = current_time

    def closeEvent(self, event):
        self.save_config()
        self.stop_acquisition()
        logger.info("GUI closed.")
        super().closeEvent(event)

    def save_to_csv(self):
        asyncio.run(self.communicator.control_api("save_to_csv", is_config=True))

class WorkerThread(QThread):
    data_received = pyqtSignal(np.ndarray)
    connection_status = pyqtSignal(bool, str)

    def __init__(self, communicator, mode="auto", duration=0, rate=1000):
        super().__init__()
        self.communicator = communicator
        self.mode = mode
        self.duration = duration
        self.rate = rate
        self.loop = asyncio.new_event_loop()

    def run(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self.run_async())

    async def run_async(self):
        start_response = await self.communicator.control_api("start", params={"mode": self.mode, "duration": self.duration, "rate": self.rate})
        if not start_response:
            self.connection_status.emit(False, "Failed to start acquisition")
            return

        if await self.communicator.connect():
            self.connection_status.emit(True, "Connected")
            await self.communicator.data_receiver(self.handle_data)
        else:
            self.connection_status.emit(False, "Connection failed")

        # Final status update after disconnection or end of acquisition
        status = await self.communicator.get_status()
        if status:
            running_status = "Running" if status.get("running") else "Stopped"
            self.connection_status.emit(False, f"Disconnected ({running_status})")
        else:
            self.connection_status.emit(False, "Disconnected")

    def stop(self):
        self.communicator.stop_event.set()
        if self.loop.is_running():
            asyncio.run_coroutine_threadsafe(self.communicator.control_api("stop"), self.loop)
            asyncio.run_coroutine_threadsafe(self.communicator.disconnect(), self.loop)
        self.loop.call_soon_threadsafe(self.loop.stop)

    def handle_data(self, data):
        self.data_received.emit(data)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = PYNQScopeGUI()
    window.show()
    sys.exit(app.exec())
