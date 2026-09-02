import pyvisa

rm = pyvisa.ResourceManager("@py")  # instance of resource manager


def list_resources():  # Function used to print out all available ports
    return rm.list_resources()


class ArduinoHX711Device:
    """A class to create an Arduino-HX711 device."""

    def __init__(self, port_name="ASRL/dev/cu.usbmodem101::INSTR"):
        self.device = rm.open_resource(
            port_name, read_termination="\r\n", write_termination="\n"
        )

        self.device.baud_rate = 57600  # Set the baud rate -> the speed at which the serial communication happens. The firmware has this at 57600

    def get_identification(self):
        return self.device.query("*IDN?")


if __name__ == "__main__":
    print(list_resources())

    my_load_cell = ArduinoHX711Device("ASRL/dev/cu.usbmodem101::INSTR")

    print(my_load_cell.get_identification())
