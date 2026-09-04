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

    def tare(self):
        """Tare the load cell.

        Returns:
            String: Confirmation that tare was completed successfully.
        """
        return self.device.tare()

    def calibrate(self, reference_force):
        """Calibrate the load cell using a reference mass. Input is required to be in NEWTON.

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
        single_measurement_err = 0

        return single_measurement, single_measurement_err

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

    def measure_over_time(
        self, duration, interval=0.1, number_of_measurements=10
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
            current_time = time.time() - start_time

            force, uncertainty = self.take_average_measurement(
                number_of_measurements
            )  # At this timestamp: compute average force

            times.append(current_time)
            forces.append(force)
            uncertainties.append(uncertainty)

            time.sleep(interval)  # go to next timestamp

        return (
            np.array(times),
            np.array(forces),
            np.array(uncertainties),
        )

    def start_live_measurement(self):
        pass

    def stop_live_measurement(self):
        pass


if __name__ == "__main__":
    model_list_resources()

    experiment = MjolnirExperiment("ASRL/dev/cu.usbmodem1101::INSTR")

    # Pen cap mass: 2.277 g; full red pen mass: 8.208 g; blue pen: 6.479 g; thin wire: 0.338 g (quick: g to N -> mass/1000 * 9.81)
    pen_cap_mass = 2.277  # grams
    reference_force = pen_cap_mass / 1000.0 * 9.81

    print(experiment.take_single_measurement())
    print(experiment.take_average_measurement(20))

    experiment.tare()

    print(experiment.take_single_measurement())
    print(experiment.take_average_measurement(20))

    print("Place the reference mass on the load cell")
    input("Press Enter when the mass is in its place ...")

    experiment.calibrate(reference_force)

    print(experiment.take_single_measurement())
    print(experiment.take_average_measurement(20))

    input("Now we can start a time measurement. Press Enter when you are ready")

    times, forces, uncertainties = experiment.measure_over_time(10)

    print(times)
    print(forces)
    print(uncertainties)
