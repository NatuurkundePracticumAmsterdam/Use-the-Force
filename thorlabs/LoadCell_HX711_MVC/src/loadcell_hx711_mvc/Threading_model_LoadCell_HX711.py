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
    """Worker that continuously reads and emits load cell measurements.

    Signals:
        measurement_received (float, bool, bool): Emitted for each
            measurement, providing the measured force and the states of
            I/O port 1 and I/O port 2, respectively.
        finished (): Emitted when the measurement loop has finished and
            the worker is ready to be cleaned up.
    """

    measurement_received = Signal(float, bool, bool)
    finished = Signal()

    def __init__(self, device):
        """Initialize the measurement worker.

        Args:
            device (ArduinoHX711Device): The Arduino device used to acquire
                force measurements and read the stage I/O states.
        """
        super().__init__()
        self.device = device
        self.running = False

    @Slot()
    def run(self):
        """Run continuous measurement until a stop is requested.

        Starts measurement on the Arduino, repeatedly reads measurements
        while the worker is running, and emits each measurement through
        the measurement_received signal.

        When the loop finishes, stops measurement on the Arduino, emits
        the finished signal, and requests the worker's thread to quit.

        Returns:
            None
        """

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
        """Request the worker to stop acquiring measurements.

        Sets the running flag to False so that the measurement loop can
        terminate after the current iteration.

        Returns:
            None
        """
        self.running = False


class MjolnirExperiment:
    """Manage force measurements using the Thorlabs Mjolnir setup."""

    def __init__(self, port_name):
        """Initialize the experiment and connect to the Arduino.

        Establishes communication with the Arduino and retrieves its
        firmware identification string.

        Args:
            port_name (str): VISA resource name of the connected Arduino's
                serial port.
        """
        self.device = ArduinoHX711Device(port_name)

        self.device_identification = self.device.get_identification()

        # To implement threading:
        self.live_thread = None
        self.live_worker = None

    def close(self):
        """Close the connection to the Arduino.

        Returns:
            None
        """
        self.device.close()

    def tare(self):
        """Tare the load cell.

        Returns:
            String: Confirmation that tare was completed successfully.
        """
        return self.device.tare()

    def calibrate(self, reference_force):
        """Calibrate the load cell using a reference force.

        Args:
            reference_force (float): Reference force applied to the load
                cell, expressed in newtons for Mjolnir/Use the force experiment.

        Returns:
            str: The response returned by the Arduino after the calibration
                command.
        """
        return self.device.calibrate(reference_force)

    def take_single_measurement(self):
        """Acquire a single force measurement and read the stage I/O states.

        Starts continuous acquisition, reads the next available measurement,
        and then stops acquisition.

        Returns:
            tuple[float, bool, bool]: The measured force and the states of
                I/O port 1 and I/O port 2, respectively.
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
        """Acquire individual force measurements over a fixed duration.

        Reads measurements from the Arduino's continuous data stream and
        records the elapsed time, measured force, and states of both stage
        I/O ports for each measurement.

        Args:
            duration (float): Measurement duration in seconds.

        Returns:
            tuple[numpy.ndarray, numpy.ndarray, numpy.ndarray, numpy.ndarray]:
                Four arrays containing, respectively, the elapsed times
                in seconds, measured forces, Boolean readings from I/O
                port 1, and Boolean readings from I/O port 2.
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
        """Create and start a worker for live measurement in a separate thread.

        Creates a QThread and a LiveMeasurementWorker, moves the worker to
        the new thread, and connects the thread's started signal to the
        worker's run method.

        Returns:
            LiveMeasurementWorker: The worker responsible for acquiring
                measurements and emitting measurement_received signals.

        Note:
            This method sets up the thread and its signal connections.
            The thread starts when its start() method is called.
        """
        self.live_thread = QThread()
        self.live_worker = LiveMeasurementWorker(self.device)

        self.live_worker.moveToThread(self.live_thread)

        self.live_thread.started.connect(self.live_worker.run)

        self.live_worker.finished.connect(self.live_worker.deleteLater)
        self.live_thread.finished.connect(self.live_thread.deleteLater)

        return self.live_worker

    # Implemented for threading:
    def stop_live_measurement(self):
        """Request the live measurement worker to stop and wait for its thread.

        Requests the worker to terminate its measurement loop, waits for
        the thread to finish, and resets the worker and thread references.

        Returns:
            None
        """

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
