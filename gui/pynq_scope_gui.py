import sys
import asyncio
import time
import csv
import os
from datetime import datetime
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QLineEdit, QSlider
from PyQt6.QtCore import Qt, QThread, pyqtSignal
import yaml
import numpy as np
import pyqtgraph as pg
from communication import ServerCommunicator

class PYNQScopeGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PYNQ Scope GUI")
        self.setGeometry(100, 100, 800, 600)

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)

        self.create_widgets()
        self.load_config()

        self.communicator = ServerCommunicator(self.server_ip_input.text())
        self.worker_thread = None
        
        # Data buffer for plotting
        self.plot_buffer = np.zeros(1000, dtype=np.int16)
        self.last_update_time = time.time()
        self.chunk_count = 0
        self.data_amount = 0
        
        # Recording state
        self.is_recording = False
        self.csv_file = None
        self.csv_writer = None

    def create_widgets(self):
        # Server status indicator
        self.status_label = QLabel("Server Status: Disconnected")
        self.status_label.setStyleSheet("color: red")
        self.layout.addWidget(self.status_label)
        
        # Oscilloscope plot
        self.plot_widget = pg.PlotWidget()
        self.layout.addWidget(self.plot_widget)
        self.plot_curve = self.plot_widget.plot(pen='y')

        # Performance metrics
        self.perf_layout = QHBoxLayout()
        self.refresh_rate_label = QLabel("Refresh Rate: 0 Hz")
        self.bandwidth_label = QLabel("Bandwidth: 0 B/s")
        self.perf_layout.addWidget(self.refresh_rate_label)
        self.perf_layout.addWidget(self.bandwidth_label)
        self.layout.addLayout(self.perf_layout)

        # Control buttons
        self.controls_layout = QHBoxLayout()
        self.start_button = QPushButton("Start")
        self.start_button.clicked.connect(self.start_acquisition)
        self.stop_button = QPushButton("Stop")
        self.stop_button.clicked.connect(self.stop_acquisition)
        self.record_button = QPushButton("Record")
        self.record_button.setCheckable(True)
        self.record_button.clicked.connect(self.toggle_recording)
        self.controls_layout.addWidget(self.start_button)
        self.controls_layout.addWidget(self.stop_button)
        self.controls_layout.addWidget(self.record_button)
        self.layout.addLayout(self.controls_layout)

        # Configuration settings
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

    def update_rate_label(self, value):
        self.rate_value_label.setText(str(value))

    def load_config(self):
        try:
            with open("config.yml", "r") as f:
                config = yaml.safe_load(f)
                self.server_ip_input.setText(config.get("server_ip", "127.0.0.1:8000"))
                self.data_folder_input.setText(config.get("data_folder", "./data"))
                self.rate_slider.setValue(config.get("rate", 1000))
        except FileNotFoundError:
            self.server_ip_input.setText("127.0.0.1:8000")
            self.data_folder_input.setText("./data")
            self.rate_slider.setValue(1000)

    def save_config(self):
        config = {
            "server_ip": self.server_ip_input.text(),
            "data_folder": self.data_folder_input.text(),
            "rate": self.rate_slider.value()
        }
        with open("config.yml", "w") as f:
            yaml.dump(config, f)

    def start_acquisition(self):
        self.communicator.server_ip = self.server_ip_input.text()
        self.worker_thread = WorkerThread(self.communicator)
        self.worker_thread.data_received.connect(self.handle_data)
        self.worker_thread.start()
        self.status_label.setText("Server Status: Connected")
        self.status_label.setStyleSheet("color: green")

    def stop_acquisition(self):
        if self.worker_thread:
            self.worker_thread.stop()
            self.worker_thread.wait()
        self.status_label.setText("Server Status: Disconnected")
        self.status_label.setStyleSheet("color: red")
        if self.is_recording:
            self.toggle_recording()

    def handle_data(self, data_chunk):
        self.update_plot(data_chunk)
        if self.is_recording:
            self.csv_writer.writerows(data_chunk.reshape(-1, 1))

    def toggle_recording(self):
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
        else:
            self.is_recording = False
            self.record_button.setText("Record")
            self.record_button.setChecked(False)
            if self.csv_file:
                self.csv_file.close()
                self.csv_file = None
                self.csv_writer = None

    def update_plot(self, data_chunk):
        # Update plot buffer
        self.plot_buffer = np.roll(self.plot_buffer, -len(data_chunk))
        self.plot_buffer[-len(data_chunk):] = data_chunk
        self.plot_curve.setData(self.plot_buffer)
        
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
        super().closeEvent(event)

class WorkerThread(QThread):
    data_received = pyqtSignal(np.ndarray)

    def __init__(self, communicator):
        super().__init__()
        self.communicator = communicator

    def run(self):
        asyncio.run(self.run_async())

    async def run_async(self):
        await self.communicator.control_api("start")
        if await self.communicator.connect():
            await self.communicator.data_receiver(self.handle_data)

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
