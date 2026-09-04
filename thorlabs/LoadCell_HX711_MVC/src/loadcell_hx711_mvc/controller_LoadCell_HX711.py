# import time

import pyvisa

rm = pyvisa.ResourceManager("@py")  # instance of resource manager


def list_resources():  # Function used to print out all available ports
    """List all resources connected to the local machine. Used to see all available ports.

    Returns:
       String: list of all resources and devices connected to local machine.
    """
    return rm.list_resources()


class ArduinoHX711Device:
    """A class to create an Arduino-HX711 device."""

    def __init__(self, port_name="ASRL/dev/cu.usbmodem101::INSTR"):
        """Initialize Arduino device and start pyvisa communication with device.

        Args:
            port_name (str, optional): usb port with Arduino attached. Defaults to "ASRL/dev/cu.usbmodem101::INSTR".
        """
        self.device = rm.open_resource(
            port_name, read_termination="\r\n", write_termination="\n"
        )

        self.device.baud_rate = 57600  # Set the baud rate -> the speed at which the serial communication happens. The firmware has this at 57600
        self.device.timeout = 5000

        self.wait_until_ready()  # Call this method when the class is initialized to make sure that the Arduino does not receive commands before it has set itself up

    def wait_until_ready(self):
        """Method that waits until the Arduino has initialized (and tared) properly before python sends commands.

        Returns:
            Nothing.
        """
        while True:
            message = self.device.read()
            if message == "READY":
                break

    def get_identification(self):
        """Request firmware version of Thorlabs Mjolnir.

        Returns:
            String: Firmware version of connected device.
        """
        return self.device.query("*IDN?")

    def tare(self):
        """Tare the load cell.

        Returns:
            String: Confirmation that tare was completed successfully.
        """
        self.device.write("TARE")
        response = self.device.read()
        return response

    def calibrate(self, reference_mass):
        """Calibrate the load cell using a reference mass.

        Args:
            reference_mass (_float_): Mass of the reference object. The unit used to calibrate the load cell is also the unit that all subsequent measurements return.

        Returns:
            String: Confirmation that calibration completed successfully."""

        # print("Place the reference mass on the load cell")
        # input("Press Enter when the mass is in its place ...")

        self.device.write(f"CALIBRATE {reference_mass}")
        response = self.device.read()
        return response

    def measure(self):
        """Read out mass measurement.

        Returns:
            Float: Mass as measured by load cell. The units of this measurement are the same as the units that were used during calibration.
        """
        self.device.write("MEASURE?")
        response = self.device.read()
        return float(response)


if __name__ == "__main__":
    print(list_resources())

    # my_load_cell = ArduinoHX711Device("ASRL/dev/cu.usbmodem1101::INSTR")

    # print(my_load_cell.tare())
    # print(my_load_cell.measure())
    # # Pen cap mass: 2.277g g; full red pen mass: 8.208 g; blue pen: 6.479 g; thin wire: 0.338 g
    # print(my_load_cell.calibrate(2.277))

    # print(my_load_cell.measure())
