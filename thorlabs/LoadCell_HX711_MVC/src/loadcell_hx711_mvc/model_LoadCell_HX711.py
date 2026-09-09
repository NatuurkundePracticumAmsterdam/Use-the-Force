import time

import numpy as np

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


class MjolnirExperiment:
    """Used to carry out force measurements using the Thorlabs Mjolnir setup."""

    def __init__(self, port_name):
        """Initialize the experiment. It connects to the Arduino device and starts communication.

        Args:
            port_name (string): port name of the connected Arduino device
        """
        self.device = ArduinoHX711Device(port_name)

        self.device_identification = self.device.get_identification()

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

        Returns:
            single_measurement (float): Force measured by the load cell.
            single_measurement_err (float): Statistical uncertainty. This is returned as 0 because no repeated measurements are available to estimate the statistical uncertainty.
        """

        single_measurement = self.device.measure()
        # single_measurement_err = 0

        return single_measurement  # , single_measurement_err

    def take_average_measurement(
        self, number_of_measurements=2
    ):  # Have at least two measurements, since to average and get a meaningful uncertainty you need at least two measurements
        """Iteratively perform many measurements over the same force. This method computes the average of that measurement, and additionally includes an uncertainty on that measurement determined by err = std / sqrt(N).

        Args:
            number_of_measurements (int, optional): The number of measurements you want to average over. The more, the better the uncertainty. Defaults to 2.

        Returns:
            average_measured_force (float): Average measured force.
            average_measured_force_err (float): Uncertainty on average measured force.
        """

        if number_of_measurements < 2:
            raise ValueError(
                "At least two measurements are required to take a meaningful average."
            )

        measurement_list = []

        for i in range(
            number_of_measurements
        ):  # Carry out measurement multiple times and store in a list
            measurement_list.append(self.device.measure())

        average_measured_force = np.mean(
            measurement_list
        )  # Take the average of multiple readings
        standard_deviation = np.std(
            measurement_list, ddof=1
        )  # Use N-1 because the sample mean is estimated from the measurements, leaving N-1 independent deviations.
        average_measured_force_err = (
            standard_deviation
            / np.sqrt(
                number_of_measurements  # Uncertainty on average: std_dev / sqrt(N), where N is number of measurements
            )
        )

        return average_measured_force, average_measured_force_err

    def measure_over_time_with_uncertainty(
        self, duration, interval=0.01, number_of_measurements=10
    ):  # This method can be used by the CLI. Here you have to define a fixed duration, so you cannot "start" and "stop" a measurement live.
        """Take repeated averaged force measurements over a fixed duration.

        Args:
            duration (float): Total measurement duration in seconds.
            interval (float, optional): Time between measurements in seconds.
                Defaults to 0.1.
            number_of_measurements (int, optional): Number of measurements
                used to calculate each average. Defaults to 10.

        Returns:
            times (numpy.ndarray): Measurement times in seconds.
            forces (numpy.ndarray): Average measured forces in newtons.
            uncertainties (numpy.ndarray): Statistical uncertainties in newtons.
        """
        times = []
        forces = []
        uncertainties = []

        start_time = time.time()

        while time.time() - start_time < duration:
            force, uncertainty = self.take_average_measurement(
                number_of_measurements
            )  # At this timestamp: compute average force
            current_time = time.time() - start_time
            times.append(current_time)
            forces.append(force)
            uncertainties.append(uncertainty)

            time.sleep(interval)  # go to next timestamp
        return (
            np.array(times),
            np.array(forces),
            np.array(uncertainties),
        )

    def measure_over_time_with_single_measurements(self, duration, interval=0.01):
        times = []
        forces = []

        start_time = time.perf_counter()
        next_measurement_time = start_time

        while True:
            # Wait until the scheduled measurement time -- This is to make sure that each force/time measurement is approximately evenly spaced in time
            while time.perf_counter() < next_measurement_time:
                time.sleep(0.001)

            # Take the measurement
            force = self.take_single_measurement()

            # Record the actual measurement time
            current_time = time.perf_counter() - start_time

            times.append(current_time)
            forces.append(force)

            # Schedule the next measurement: this ensures that measurement don't pile up or lag behind too much -> keep in mind that there will be a slight fluctuation between time steps! See test results below in execution block
            next_measurement_time += interval

            # Stop after the requested duration
            if current_time >= duration:
                break

        return np.array(times), np.array(forces)

    def start_live_measurement(self):
        pass

    def stop_live_measurement(self):
        pass


if __name__ == "__main__":
    model_list_resources()

    experiment = MjolnirExperiment("ASRL/dev/cu.usbmodem1101::INSTR")

    # Some tests to see how fast the communication is happening and what the sampling rate is:
    times, forces = experiment.measure_over_time_with_single_measurements(
        duration=10, interval=0.01
    )

    # We have run a measurement for 10 seconds, choosing an interval of 0.01 seconds per measurement. This means that we should be conducting 1000 measurements in total -> sampling rate of 100 Hz
    print("Sampling experiments: ")
    print(
        f"Number of measurements: {len(times)}"
    )  # This is how many measurements were actually performed
    print(
        f"Effective sampling rate: {len(times) / times[-1]:.1f} Hz"
    )  # This is the effective sampling rate. If this is actually 100 Hz, this is a good sign -> Note, this is NOT the HX711 sampling rate, this is only the effective sampling rate that we get when we run everything in python

    # Check spacing in time: do we measure at equal time intervals?
    dt = np.diff(times)
    print(
        f"Mean dt: {np.mean(dt):.4f} s"
    )  # On average, there should be 0.01 seconds between each measurement
    print(
        f"Median dt: {np.median(dt):.4f} s"
    )  # The median will tell us a bit more about the distribution between measurements (in time) -> For me, this returned a median of 0.008 seconds -> this means that there is a slight shift
    print(
        f"Minimum dt: {np.min(dt):.4f} s"
    )  # How big is the fluctuation in time? For me, min time between time measurements was 0.0078 (slightly shorter than we want)
    print(
        f"Maximum dt: {np.max(dt):.4f} s"
    )  # Max time between time measuremenst was 0.0125 seconds (slightly longer than we want)
    # So it seems, from this test, that we have a time uncertainty of the order of 0.002 seconds, if we have timesteps of 0.01 seconds. This uncertainty may be asymmetric (i.e. uncertainty of + 0.0025 and - 0.0022). I think this is acceptable for a timestep of 0.01 seconds

    print()
    print("See if successive force values are repeated")
    print(forces[:30])
