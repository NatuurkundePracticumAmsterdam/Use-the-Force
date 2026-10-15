import time

import numpy as np
from PySide6.QtCore import (  # Import this as part of the threading implementation
    QObject,
    QThread,
    Signal,
    Slot,
)

from loadcell_hx711_mvc.controller_LoadCell_HX711 import (
    ArduinoHX711Device,
    list_resources,
)


def model_list_resources():
    """List all resources connected to the local machine. Used to see all available ports.

    Returns:
       String: list of all resources and devices connected to local machine.
    """
    return list_resources()


# A new "worker" class -- used to implement threading
class LiveMeasurementWorker(QObject):
    """Worker that continuously reads measurements from the load cell."""

    measurement_received = Signal(float, bool, bool)
    finished = Signal()

    def __init__(self, device):
        super().__init__()
        self.device = device
        self.running = False

    @Slot()
    def run(self):
        """Continuously read measurements until stopped."""

        self.running = True

        try:
            self.device.start_measurement()
            while self.running:
                force, io_port_1_reading, io_port_2_reading = self.device.measure()
                self.measurement_received.emit(
                    force, io_port_1_reading, io_port_2_reading
                )

        finally:
            self.device.stop_measurement()
            self.finished.emit()
            self.thread().quit()

    def stop(self):
        """Request the worker to stop measuring."""
        self.running = False


class MjolnirExperiment:
    """Used to carry out force measurements using the Thorlabs Mjolnir setup."""

    def __init__(self, port_name):
        """Initialize the experiment. It connects to the Arduino device and starts communication.

        Args:
            port_name (string): port name of the connected Arduino device
        """
        self.device = ArduinoHX711Device(port_name)

        self.device_identification = self.device.get_identification()

        # To implement threading:
        self.live_thread = None
        self.live_worker = None

    def close(self):
        """Close the connection to the Arduino."""
        self.device.close()

    def tare(self):
        """Tare the load cell.

        Returns:
            String: Confirmation that tare was completed successfully.
        """
        return self.device.tare()

    def calibrate(self, reference_force):
        """Calibrate the load cell using a reference object (force that the object exerts on the loading cell). Input is required to be in NEWTON.

        Args:
            reference_force (_float_): Force exerted on the load cell by the reference object. The unit used to calibrate the load cell is also the unit that all subsequent measurements return.

        Returns:
            String: Confirmation that calibration completed successfully."""
        return self.device.calibrate(reference_force)

    def take_single_measurement(self):
        """Take a single measurement by reading out the load cell + HX711 data.
            Starts continuous acquisition, reads the next available
            measurement, and then stops continuous acquisition.

        Returns:
            single_measurement (float): Force measured by the load cell.
            single_measurement_err (float): Statistical uncertainty. This is returned as 0 because no repeated measurements are available to estimate the statistical uncertainty.
        """
        self.device.start_measurement()

        try:
            single_measurement, io_port_1_reading, io_port_2_reading = (
                self.device.measure()
            )
        finally:
            self.device.stop_measurement()

        return single_measurement, io_port_1_reading, io_port_2_reading

    # New method implemented as part of continuous output architecture:
    def measure_over_time_with_single_measurements(self, duration):
        """Measure a force continuously for a fixed duration.

        The Arduino continuously acquires measurements from the HX711.
        This method reads each new measurement as it becomes available.

        Args:
            duration (float): Total measurement duration in seconds.

        Returns:
            times (numpy.ndarray): Measurement timestamps in seconds.
            forces (numpy.ndarray): Measured forces.
        """

        times = []
        forces = []
        io_port_1_readings = []
        io_port_2_readings = []

        # Start the continuous stream of outputs:
        self.device.start_measurement()

        try:
            start_time = time.perf_counter()

            while True:
                # Read the next measurement from the continuous stream
                force, io_port_1_reading, io_port_2_reading = self.device.measure()

                current_time = time.perf_counter() - start_time

                times.append(current_time)
                forces.append(force)
                io_port_1_readings.append(io_port_1_reading)
                io_port_2_readings.append(io_port_2_reading)

                if current_time >= duration:
                    break

        finally:  # Always just make sure that you stop the measurement, even if the stuff under the "try" did not work
            # Stop the continuous stream of outputs:
            self.device.stop_measurement()

        return (
            np.array(times),
            np.array(forces),
            np.array(io_port_1_readings),
            np.array(io_port_2_readings),
        )

    # Implemented for threading:
    def start_live_measurement(self):
        """Start continuous live measurement in a separate thread."""
        self.live_thread = QThread()
        self.live_worker = LiveMeasurementWorker(self.device)

        self.live_worker.moveToThread(self.live_thread)

        self.live_thread.started.connect(self.live_worker.run)

        self.live_worker.finished.connect(self.live_worker.deleteLater)
        self.live_thread.finished.connect(self.live_thread.deleteLater)

        return self.live_worker

    # Implemented for threading:
    def stop_live_measurement(self):
        """Stop the live measurement worker and wait for its thread to finish."""

        if self.live_worker is not None:
            self.live_worker.stop()

        # Make sure that you also wait for the worker to have stopped before you do anything else:
        if self.live_thread is not None:
            self.live_thread.wait()

        self.live_worker = None
        self.live_thread = None


if __name__ == "__main__":
    model_list_resources()

    experiment = MjolnirExperiment("ASRL/dev/cu.usbmodem1101::INSTR")
