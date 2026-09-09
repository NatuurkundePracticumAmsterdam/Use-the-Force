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
        """Average a number of consecutive measurements.

        Args:
            number_of_measurements (int): Number of consecutive measurements
                used to calculate the average.

        Returns:
            average_measured_force (float): Average measured force.
            average_measured_force_err (float): Standard uncertainty on the mean.
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

    # def measure_over_time_with_uncertainty(
    #     self, duration, interval=0.01, number_of_measurements=10
    # ):  # This method can be used by the CLI. Here you have to define a fixed duration, so you cannot "start" and "stop" a measurement live.
    #     """Take repeated averaged force measurements over a fixed duration.

    #     Args:
    #         duration (float): Total measurement duration in seconds.
    #         interval (float, optional): Time between measurements in seconds.
    #             Defaults to 0.1.
    #         number_of_measurements (int, optional): Number of measurements
    #             used to calculate each average. Defaults to 10.

    #     Returns:
    #         times (numpy.ndarray): Measurement times in seconds.
    #         forces (numpy.ndarray): Average measured forces in newtons.
    #         uncertainties (numpy.ndarray): Statistical uncertainties in newtons.
    #     """
    #     times = []
    #     forces = []
    #     uncertainties = []

    #     start_time = time.time()

    #     while time.time() - start_time < duration:
    #         force, uncertainty = self.take_average_measurement(
    #             number_of_measurements
    #         )  # At this timestamp: compute average force
    #         current_time = time.time() - start_time
    #         times.append(current_time)
    #         forces.append(force)
    #         uncertainties.append(uncertainty)

    #         time.sleep(interval)  # go to next timestamp
    #     return (
    #         np.array(times),
    #         np.array(forces),
    #         np.array(uncertainties),
    #     )

    # def measure_over_time_with_average_measurements( # -> This method is now OBSOLETE with the implementation of continuous output architecture. See updated method below
    #     self, duration, interval=0.1, number_of_measurements=4
    # ):
    #     """Measure a force over time using averaged measurements. At each timestamp, the force is measured repeatedly and subsequently averaged. The uncertainty on this measured average is std / sqrt(N), where N is the number of measurements per timestamp.

    #     Args:
    #         duration (float): The time duration of the total measurement in seconds.
    #         interval (float, optional): The time interval between single measurements.
    #         number_of_measurements (int, optional): Number of measurements you want to take before averaging. Defaults to 4.

    #     Returns:
    #         times (numpy array of floats): An array of timestamps (in s).
    #         forces (numpy array of floats): An array of average forces per timestamp (in N)
    #         uncertainies (numpy array of floats): An array of uncertainties on the average forces (in N).
    #     """
    #     times = []
    #     forces = []
    #     uncertainties = []

    #     start_time = time.perf_counter()
    #     next_measurement_time = start_time

    #     while True:
    #         # Wait until the scheduled measurement time
    #         while time.perf_counter() < next_measurement_time:
    #             time.sleep(0.001)

    #         # Take several measurements and calculate their average
    #         force, uncertainty = self.take_average_measurement(number_of_measurements)

    #         # Record the actual time
    #         current_time = time.perf_counter() - start_time

    #         times.append(current_time)
    #         forces.append(force)
    #         uncertainties.append(uncertainty)

    #         # Schedule the next averaged measurement
    #         next_measurement_time += interval

    #         if current_time >= duration:
    #             break

    #     return (
    #         np.array(times),
    #         np.array(forces),
    #         np.array(uncertainties),
    #     )

    def measure_over_time_with_average_measurements(
        self, duration, number_of_measurements=4
    ):
        """Measure a force over time using consecutive averaged measurements.

        The Arduino continuously acquires measurements from the HX711.
        Consecutive measurements are grouped into sets and averaged.

        Args:
            duration (float): Total measurement duration in seconds.
            number_of_measurements (int): Number of consecutive measurements
                used to calculate each average.

        Returns:
            times (numpy.ndarray): Timestamps in seconds.
            forces (numpy.ndarray): Average measured forces.
            uncertainties (numpy.ndarray): Standard uncertainties on the mean.
        """

        times = []
        forces = []
        uncertainties = []

        # Start the continuous stream of measurements.
        self.device.start_measurement()

        start_time = time.perf_counter()

        while True:
            # Take several consecutive measurements and calculate their average.
            force, uncertainty = self.take_average_measurement(number_of_measurements)

            # Record the time at which the average was completed.
            current_time = time.perf_counter() - start_time

            times.append(current_time)
            forces.append(force)
            uncertainties.append(uncertainty)

            if current_time >= duration:
                break

        # Stop the continuous stream of measurements.
        self.device.stop_measurement()

        return (
            np.array(times),
            np.array(forces),
            np.array(uncertainties),
        )

    # def test_average_measurement_time(
    #     self, number_of_measurements_list=(1, 2, 4, 5, 8, 10), repetitions=50
    # ):
    #     """Diagnostic method to see how long it takes to take average measurements

    #     Args:
    #         number_of_measurements_list (tuple, optional): A list specifying how many measurements to take before computing an average. Defaults to (1, 2, 4, 5, 8, 10).
    #         repetitions (int, optional): How many times to repeat the test for each number of measurements for an average. This helps give a distribution of how long it will take to compute an average. Defaults to 20.
    #     """
    #     for n in number_of_measurements_list:
    #         durations = []

    #         for _ in range(repetitions):
    #             start_time = time.perf_counter()

    #             if n == 1:
    #                 self.take_single_measurement()
    #             else:
    #                 self.take_average_measurement(n)

    #             elapsed_time = time.perf_counter() - start_time
    #             durations.append(elapsed_time)

    #         print(
    #             f"N = {n:2d}: "
    #             f"mean = {np.mean(durations):.4f} s ({1 / np.mean(durations):.1f} Hz), "
    #             f"min = {np.min(durations):.4f} s, "
    #             f"max = {np.max(durations):.4f} s"
    #         )

    # def measure_over_time_with_single_measurements(self, duration, interval=0.01): # -> This version is OBSOLETE now that we have implemented continuous output architecture. See updated method below.
    #     """Measure a force over time using single measurements. This method repeatedly measures the load on the load cell for a fixed duration of time, with a specific time interval between measurements.

    #     Args:
    #         duration (float): The time duration of the total measurement in seconds.
    #         interval (float, optional): The time interval between single measurements. Defaults to 0.01.

    #     Returns:
    #         times (numpy array of floats): Timestamps (in seconds) at which each single measurement was performed.
    #         foreces (numpy array of floats): array of forces (in Newtons) for each measurement in the series.
    #     """
    #     times = []
    #     forces = []

    #     start_time = time.perf_counter()
    #     next_measurement_time = start_time

    #     while True:
    #         # Wait until the scheduled measurement time -- This is to make sure that each force/time measurement is approximately evenly spaced in time
    #         while time.perf_counter() < next_measurement_time:
    #             time.sleep(0.001)

    #         # Take the measurement
    #         force = self.take_single_measurement()

    #         # Record the actual measurement time
    #         current_time = time.perf_counter() - start_time

    #         times.append(current_time)
    #         forces.append(force)

    #         # Schedule the next measurement: this ensures that measurement don't pile up or lag behind too much -> keep in mind that there will be a slight fluctuation between time steps! See test results below in execution block
    #         next_measurement_time += interval

    #         # Stop after the requested duration
    #         if current_time >= duration:
    #             break

    #     return np.array(times), np.array(forces)

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

        # Start the continuous stream of outputs:
        self.device.start_measurement()

        start_time = time.perf_counter()

        while True:
            force = self.take_single_measurement()

            current_time = time.perf_counter() - start_time

            times.append(current_time)
            forces.append(force)

            if current_time >= duration:
                break

        # Stop the continuous stream of outputs:
        self.device.stop_measurement()

        return np.array(times), np.array(forces)

    def start_live_measurement(self):
        """Feature still being developed: will be implemented when threading has been incorporated into the software."""
        pass

    def stop_live_measurement(self):
        """Feature still being developed: will be implemented when threading has been incorporated into the software."""
        pass


if __name__ == "__main__":
    model_list_resources()

    experiment = MjolnirExperiment("ASRL/dev/cu.usbmodem1101::INSTR")

    # Some tests to see how fast the communication is happening and what the sampling rate is:
    times, forces = experiment.measure_over_time_with_single_measurements(duration=10)

    # The Arduino/HX711 continuously acquires measurements.
    # Python reads each new measurement as it becomes available.
    # Therefore, the sampling rate is determined primarily by the HX711,
    # rather than by a Python-defined measurement interval.

    print("Sampling experiment: ")
    print(
        f"Number of measurements: {len(times)}"
    )  # Number of measurements actually received from the HX711

    print(
        f"Effective sampling rate: {len(times) / times[-1]:.1f} Hz"
    )  # Effective rate observed by Python

    # Check spacing in time: do we measure at equal time intervals?
    dt = np.diff(times)
    print(
        f"Mean dt: {np.mean(dt):.4f} s"
    )  # Mean time between consecutive measurements received from the Arduino
    print(
        f"Median dt: {np.median(dt):.4f} s"
    )  # The median will tell us a bit more about the distribution between measurements (in time)
    print(f"Minimum dt: {np.min(dt):.4f} s")  # How big is the fluctuation in time?
    print(f"Maximum dt: {np.max(dt):.4f} s")  # Max time between time measurements

    print()
    print("See if successive force values are repeated")
    print(forces[:30])

    # print()
    # print("Tests to see how long it takes to compute averages:")
    # experiment.test_average_measurement_time()

    print()
    # Tests to see how well we can average now with continuous output architecture:
    print("Tests to see how well averaging works now:")
    times, forces, uncertainties = (
        experiment.measure_over_time_with_average_measurements(
            duration=10,
            number_of_measurements=4,
        )
    )

    print("Averaging experiment:")
    print(f"Number of averaged measurements: {len(times)}")
    print(f"Effective rate: {len(times) / times[-1]:.1f} Hz")
    print(f"Mean dt: {np.mean(np.diff(times)):.4f} s")
    print(f"Median dt: {np.median(np.diff(times)):.4f} s")

    print()
    print("Forces:")
    print(forces)

    print()
    print("Uncertainties:")
    print(uncertainties)
