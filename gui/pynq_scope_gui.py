import sys
import asyncio
import time
import csv
import os
import logging
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QLineEdit, QSlider, QMessageBox, QCheckBox, QRadioButton
from PyQt6.QtCore import Qt, QThread, pyqtSignal
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
        self.channel_colors = ['y', 'b', 'g', 'r', 'c', 'm', 'w', 'k'] # Colors for each channel

        self.create_widgets()
        self.load_config()

        self.communicator = ServerCommunicator(self.server_ip_input.text())
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
        self.layout.addLayout(self.channels_layout)

        self.perf_layout = QHBoxLayout()
        self.refresh_rate_label = QLabel("Refresh Rate: 0 Hz")
        self.bandwidth_label = QLabel("Bandwidth: 0 B/s")
        self.perf_layout.addWidget(self.refresh_rate_label)
        self.perf_layout.addWidget(self.bandwidth_label)
        self.layout.addLayout(self.perf_layout)

        self.controls_layout = QHBoxLayout()
        self.start_button = QPushButton("Start")
        self.start_button.clicked.connect(self.start_acquisition)
        self.stop_button = QPushButton("Stop")
        self.stop_button.clicked.connect(self.stop_acquisition)
        self.record_button = QPushButton("Record")
        self.record_button.setCheckable(True)
        self.record_button.clicked.connect(self.toggle_recording)

        self.save_button = QPushButton("Save to CSV")
        self.save_button.clicked.connect(self.save_to_csv)

        self.controls_layout.addWidget(self.start_button)
        self.controls_layout.addWidget(self.stop_button)
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
        self.rate_slider = QSlider(Qt.Orientation.Horizontal)
        self.rate_slider.setRange(1, 10000)
        self.rate_slider.setValue(1000)
        self.rate_slider.valueChanged.connect(self.update_rate_label)
        self.rate_value_label = QLabel("1000")
        self.config_layout.addWidget(self.rate_label)
        self.config_layout.addWidget(self.rate_slider)
        self.config_layout.addWidget(self.rate_value_label)
        
        self.layout.addLayout(self.config_layout)
        logger.info("Widgets created.")

    def update_rate_label(self, value):
        """Updates the rate label when the slider is moved."""
        self.rate_value_label.setText(str(value))
        logger.debug(f"Rate slider updated to {value}")

    def load_config(self):
        """Loads the configuration from config.yml."""
        try:
            with open("config.yml", "r") as f:
                config = yaml.safe_load(f)
                self.server_ip_input.setText(config.get("server_ip", "127.0.0.1:8000"))
                self.data_folder_input.setText(config.get("data_folder", "./data"))
                self.rate_slider.setValue(config.get("rate", 1000))
                logger.info("Configuration loaded from config.yml")
        except FileNotFoundError:
            self.server_ip_input.setText("127.0.0.1:8000")
            self.data_folder_input.setText("./data")
            self.rate_slider.setValue(1000)
            logger.warning("config.yml not found, using default configuration.")

    def save_config(self):
        """Saves the current configuration to config.yml."""
        config = {
            "server_ip": self.server_ip_input.text(),
            "data_folder": self.data_folder_input.text(),
            "rate": self.rate_slider.value()
        }
        with open("config.yml", "w") as f:
            yaml.dump(config, f)
        logger.info("Configuration saved to config.yml")

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

    def start_acquisition(self):
        try:
            self.communicator.server_ip = self.server_ip_input.text()

            mode = "auto"
            duration = 0
            if self.timed_mode_radio.isChecked():
                mode = "timed"
                duration = int(self.timed_duration_input.text())

            self.worker_thread = WorkerThread(self.communicator, mode, duration)
            self.worker_thread.data_received.connect(self.handle_data)
            self.worker_thread.connection_status.connect(self.update_status_label)
            self.worker_thread.start()
            logger.info("Acquisition started.")
        except Exception as e:
            logger.error(f"Failed to start acquisition: {e}")
            self.show_error_message("Failed to start acquisition", str(e))

    def stop_acquisition(self):
        if self.worker_thread:
            self.worker_thread.stop()
            self.worker_thread.wait()
        self.status_label.setText("Server Status: Disconnected")
        self.status_label.setStyleSheet("color: red")
        if self.is_recording:
            self.toggle_recording()
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
            bandwidth = self.data_amount / elapsed_time
            self.refresh_rate_label.setText(f"Refresh Rate: {refresh_rate:.2f} Hz")
            self.bandwidth_label.setText(f"Bandwidth: {bandwidth:.2f} B/s")
            self.chunk_count = 0
            self.data_amount = 0
            self.last_update_time = current_time

    def closeEvent(self, event):
        self.save_config()
        self.stop_acquisition()
        logger.info("GUI closed.")
        super().closeEvent(event)

    def save_to_csv(self):
        asyncio.run(self.communicator.control_api("save_to_csv"))

class WorkerThread(QThread):
    data_received = pyqtSignal(np.ndarray)
    connection_status = pyqtSignal(bool, str)

    def __init__(self, communicator, mode="auto", duration=0):
        super().__init__()
        self.communicator = communicator
        self.mode = mode
        self.duration = duration

    def run(self):
        asyncio.run(self.run_async())

    async def run_async(self):
        await self.communicator.control_api("start", params={"mode": self.mode, "duration": self.duration})
        if await self.communicator.connect():
            status = await self.communicator.get_status()
            if status and status.get("running"):
                self.connection_status.emit(True, "Connected")
                await self.communicator.data_receiver(self.handle_data)
            else:
                self.connection_status.emit(False, "Server not running")
        else:
            self.connection_status.emit(False, "Connection failed")

    def stop(self):
        self.communicator.stop_event.set()
        asyncio.run(self.communicator.control_api("stop"))
        asyncio.run(self.communicator.disconnect())

    def handle_data(self, data):
        self.data_received.emit(data)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = PYNQScopeGUI()
    window.show()
    sys.exit(app.exec())
