import pyvisa

rm = pyvisa.ResourceManager("@py")  # instance of resource manager


def list_resources():  # Function used to print out all available ports
    """List all resources connected to the local machine. Used to see all available ports.

    Returns:
       String: list of all resources and devices connected to local machine.
    """
    return rm.list_resources()


class ArduinoHX711Device:
    """Interface for an Arduino connected to an HX711 load cell."""

    def __init__(self, port_name):
        """Initialize Arduino device and start pyvisa communication with device.

        Args:
            port_name (str): usb port with Arduino attached, e.g. "ASRL/dev/cu.usbmodem101::INSTR".
        """
        self.device = rm.open_resource(
            port_name, read_termination="\r\n", write_termination="\n"
        )

        self.device.baud_rate = 57600  # Set the baud rate -> the speed at which the serial communication happens. The firmware has this at 57600
        self.device.timeout = 5000

    def close(self):
        """Close the connection to the Arduino."""
        if self.device is not None:
            self.device.close()  # Use the pyvisa close() method
            self.device = None

    def wait_until_ready(self):
        """Wait until the Arduino reports that it is ready.

        Reads and prints messages from the Arduino until the "READY"
        message is received.

        Returns:
            None
        """
        while True:
            message = self.device.read()
            print(f"Arduino: {message}")
            if message == "READY":
                break

    def get_identification(self):
        """Request the Arduino's firmware identification string.

        Returns:
            str: The identification string returned by the firmware.
        """
        return self.device.query("*IDN?")

    def tare(self):
        """Tare the load cell.

        Returns:
            str: The response returned by the Arduino after the tare
                command.
        """
        self.device.write("TARE")
        response = self.device.read()
        return response

    def calibrate(self, reference_mass):
        """Calibrate the load cell using a reference mass.

        Args:
            reference_mass (float): Mass of the reference object, expressed
                in the unit expected by the Arduino firmware. In the case of the Mjolnir experiment, use N.

        Returns:
            str: The response returned by the Arduino after the calibration
                command.

        Note:
            The units of subsequent measurements depend on how the firmware
            interprets the reference value. For force measurements in
            newtons, the reference value should be expressed in newtons if
            required by the firmware's calibration procedure.
        """

        self.device.write(f"CALIBRATE {reference_mass}")
        response = self.device.read()
        return response

    # Meausring using continuous readout:
    def measure(self):
        """Read the next measurement from the continuous data stream.

        Returns:
            tuple[float, bool, bool]: The measured force and the states of
                the two stage I/O ports, respectively.
        """
        return self.read_measurement()

    # Implemented continuous readout:
    def start_measurement(self):
        """Start continuous measurement on the Arduino.

        Returns:
            str: The response returned by the Arduino after the start
                command.
        """
        self.device.write("START")  # Give command to turn on "measuring" state
        response = self.device.read()
        return response

    def stop_measurement(self):
        """Stop continuous measurement on the Arduino.

        Waits until the Arduino reports that the measuring state has stopped.

        Returns:
            str: The confirmation message returned by the Arduino.
        """
        self.device.write("STOP")  # Give command to turn off "measuring" state

        while (
            True
        ):  # True never becomes <<not true>>, so this is essentially an infinite loop
            response = self.device.read()
            if response == "MEASURING STATE STOPPED":
                return response  # We can force the infinite loop to stop through this return statement

    # Method to read measurements using a continuous output architecture
    def read_measurement(self):
        """Read the next measurement from the continuous data stream.

        Reads messages from the Arduino until a data message is received.
        The data message is expected to contain the measured force and the
        states of the two stage I/O ports.

        Returns:
            tuple[float, bool, bool]: The measured force and the states of
                I/O port 1 and I/O port 2, respectively.
        """
        while True:
            response = self.device.read()

            if response.startswith(
                "DATA,"  # If the response that we get back from the Aruino starts with "DATA,", then we can exit the while loop, because we have found the (single) measurement that we wanted
            ):  # Need to have this condition for in case the Arduino returns something that isn't data (like info about taring or calibrating). We only want to read data here.
                # In order for the Arduino to read anything with "DATA,", it does neet to be in the MEASURING state, so make sure that you have starteed this before trying to read a measurement

                values = response.split(",")

                force = float(values[1])  # This should be the force readout
                # This should be the translation stage I/O (1 or 0):
                io_port_1_reading = bool(int(values[2]))
                io_port_2_reading = bool(int(values[3]))

                return force, io_port_1_reading, io_port_2_reading


if __name__ == "__main__":
    print(list_resources())

    my_load_cell = ArduinoHX711Device("ASRL/dev/cu.usbmodem1101::INSTR")

    my_load_cell.close()
