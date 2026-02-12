

import numpy as np
from pynq import Overlay
from pynq import allocate

class dmaAcquisition:
    """
    A class to control the PYNQ-based oscilloscope.
    """

    def __init__(self, overlay_path="base.bit"):
        """
        Initializes the PynqScope.

        Args:
            overlay_path (str): The path to the overlay bitstream file.
        """
        self.overlay = Overlay(overlay_path)
        self.dma = self.overlay.axi_dma_1
        self.dma_recv = self.dma.recvchannel
        self.rate_acquisition_reg = self.overlay.axi_rate_acquisition.channel1[0:32]
        self.packet_size_reg = self.overlay.axi_rate_acquisition.channel2[0:32]

    def acquire_data(self, rate_acquisition, packet_size):
        """
        Acquires data from the ADC.

        Args:
            rate_acquisition (int): The acquisition rate.
            packet_size (int): The size of the packet (up to 1023).

        Returns:
            tuple: A tuple containing 8 numpy arrays, one for each channel.
        """
        if not (0 <= packet_size <= 1023):
            raise ValueError("packet_size must be between 0 and 1023.")

        # Configure the FPGA
        self.rate_acquisition_reg.write(rate_acquisition)
        self.packet_size_reg.write(packet_size)

        # Set up DMA transfer
        data_size = packet_size * 8
        output_buffer = allocate(shape=(data_size,), dtype=np.int16)

        # Perform DMA transfer
        self.dma_recv.transfer(output_buffer)
        self.dma_recv.wait()

        # Demultiplex the data
        array_0 = output_buffer[0::8]
        array_1 = output_buffer[1::8]
        array_2 = output_buffer[2::8]
        array_3 = output_buffer[3::8]
        array_4 = output_buffer[4::8]
        array_5 = output_buffer[5::8]
        array_6 = output_buffer[6::8]
        array_7 = output_buffer[7::8]

        return array_0, array_1, array_2, array_3, array_4, array_5, array_6, array_7

    def write_data(self, rate_generation, packet_size):
            status = 0 
        return status