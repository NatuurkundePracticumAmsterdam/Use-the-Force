from time import perf_counter_ns, sleep
import serial

# TODO: add all new commands...

class ForceSensor():
    def __init__(self, 
                 PortName: str = "/dev/ttyACM0", 
                 GaugeValue: int = 0, 
                 NewtonPerVolt: float = 1., 
                 WarningOn: bool = True, 
                 MaxNewton: int | float = 5, 
                 **kwargs
                 ) -> None:
        """
        Opens up the serial port, checks the gauge value and makes sure data is available.

        (PySerial library has to be installed on the computer, see requirements.txt)
        """
        ####### SOME PARAMETERS AND STUFF ######

        # The 'zero' volt value. Determined automatically each time.
        self.GaugeValue: int = GaugeValue
        self.NewtonPerCount: float = NewtonPerVolt
        # self.NewtonPerVolt = 1  # value I set for calibration
        self.WarningOn: bool = WarningOn  # >MaxNewton is dangerous for sensor.
        self.MaxNewton: int | float = MaxNewton

        self.encoding: str = str(kwargs.pop('encoding', "UTF-8"))

        self.baudrate: int = int(kwargs.pop('baudrate', 115200))
        self.timeout: float = float(kwargs.pop('timeout', 5.))

        # 150/1000 # base delay of the M5Din Meter to send a response [seconds]
        self.stdDelay: float = 0.
        self.cmdStart: str = str(kwargs.pop('cmdStart', "#"))
        self.cmdEnd: str = str(kwargs.pop('cmdEnd', ";"))
        self.currentReads: list[list[float]] = [[], []]

        self.minPos: int = int(kwargs.pop('minPos', 1))  # [mm]
        self.maxPos: int = int(kwargs.pop('maxPos', 46))  # [mm]

        self.T0: int = perf_counter_ns()

        self.PortName: str = PortName

        ####### PORT INIT ######
        # The 'COM'-port depends on which plug is used at the back of the computer.
        # To find the correct port: go to Windows Settings, Search for Device Manager,
        # and click the tab "Ports (COM&LPT)".s
        self.ser: serial.Serial = self.connectPort(
            self.PortName, baudrate=self.baudrate, timeout=self.timeout)

    def connectPort(self, PortName: str, baudrate: int = 115200, timeout: float | None = 2.) -> serial.Serial:
        return serial.Serial(port=PortName, baudrate=baudrate, timeout=timeout)

    def reGauge(self, reads: int = 10, skips: int = 3):
        """
        !!!IT'S IMPORTANT NOT TO HAVE ANY FORCE ON THE SENSOR WHEN CALLING THIS FUNCTION!!!
        
        Updates the GaugeValue by taking the average of `reads` values.
        
        :param reads: amount of readings
        :type reads: int
        :param skips: initial lines to skip (and clear old values)
        :type skips: int
        """
        self.ser.reset_input_buffer()
        skips: list[float] = [self.GetReading()[2] for i in range(skips)]
        read_values: list[float] = [self.GetReading()[2] for i in range(reads)]
        self.GaugeValue = int(sum(read_values)/reads)
        print("Self-gauged value: " + str(self.GaugeValue))

    def ForceFix(self, count: float) -> float:
        """Corrects the units given based on GaugeValue and NewtonPerCount

        Args:
            count (float): sensor count

        Returns:
            float: calibrated units
        """        
        # The output, with gauge, in calibrated units.
        return (count - self.GaugeValue) * self.NewtonPerCount

    def ClosePort(self) -> None:
        """
        Always close after use.
        """
        self.ser.close()

    def SP(self, position: int) -> None:
        """
        ### Set Position
        Sets the position of the steppermotor stage in milimeters.

        :param position: position to set from bottom [mm]
        :type position: int
        """
        if position <= self.maxPos and position >= self.minPos:
            self.ser.flush()
            self.ser.write(f"{self.cmdStart}SP {position}{self.cmdEnd}".encode())
            if self.stdDelay > 0:
                sleep(self.stdDelay)
            returnLine: str = self.ser.read_until().decode().strip()
            if returnLine.split(":")[0] == "[ERROR]":
                raise RuntimeError(returnLine)
        else:
            raise ValueError(f"Position {position} is out of range ({self.minPos}, {self.maxPos})")

    def GP(self) -> int:
        """
        ### Get Position
        Current position set in memory.

        :return: End position if moving, else current position in [mm]
        :rtype: int
        """
        self.ser.flush()
        self.ser.write(f"{self.cmdStart}GP{self.cmdEnd}".encode())
        if self.stdDelay > 0:
            sleep(self.stdDelay)
        returnLine: str = self.ser.read_until().decode().strip()
        if returnLine.split(":")[0] == "[ERROR]":
            raise RuntimeError(returnLine)
        else:
            try:
                return int(returnLine.split(": ")[-1])
            except ValueError as e:
                return e
    
    def SV(self, velocity: int) -> None:
        """
        ### Set Velocity
        Sets the velocity of the steppermotor stage in milimeters per second.

        :param velocity: velocity to set [mm/s]
        :type velocity: int
        """
        self.ser.flush()
        self.ser.write(f"{self.cmdStart}SV {velocity}{self.cmdEnd}".encode())
        if self.stdDelay > 0:
            sleep(self.stdDelay)
        returnLine: str = self.ser.read_until().decode().strip()
        if returnLine.split(":")[0] == "[ERROR]":
            raise RuntimeError(returnLine)

    def GV(self) -> int:
        """
        ### Get Velocity
        Returns the current velocity of the steppermotor stage in milimeters per second.

        :return: End velocity if moving, else current velocity [mm/s]
        :rtype: int
        """
        self.ser.flush()
        self.ser.write(f"{self.cmdStart}GV{self.cmdEnd}".encode())
        if self.stdDelay > 0:
            sleep(self.stdDelay)
        returnLine: str = self.ser.read_until().decode().strip()
        if returnLine.split(":")[0] == "[ERROR]":
            raise RuntimeError(returnLine)
        else:
            return int(returnLine.split(": ")[-1])

    def GM(self) -> str:
        """
        ### Get Mode
        Returns the current selected mode, calibrated or raw.

        :return: string with selected mode
        :rtype: str
        """
        self.ser.flush()
        self.ser.write(f"{self.cmdStart}GV{self.cmdEnd}".encode())
        if self.stdDelay > 0:
            sleep(self.stdDelay)
        returnLine: str = self.ser.read_until().decode().strip()
        if returnLine.split(":")[0] == "[ERROR]":
            raise RuntimeError(returnLine)
        else:
            return returnLine.split(" ")[-1]

    def TM(self) -> None:
        """
        ### Toggle Mode
        Toggles between the two modes, calibrated or raw.
        """
        self.ser.flush()
        self.ser.write(f"{self.cmdStart}TM{self.cmdEnd}".encode())
        if self.stdDelay > 0:
            sleep(self.stdDelay)
        returnLine: str = self.ser.read_until().decode().strip()
        if returnLine.split(":")[0] == "[ERROR]":
            raise RuntimeError(returnLine)

    def SR(self) -> float:
        """
        ### Single Read
        Reads the force a single time.

        :return: read force
        :rtype: float
        """
        self.ser.flush()
        self.ser.write(f"{self.cmdStart}SR{self.cmdEnd}".encode())
        if self.stdDelay > 0:
            sleep(self.stdDelay)
        returnLine: str = self.ser.read_until().decode().strip()
        if returnLine.split(":")[0] == "[ERROR]":
            raise RuntimeError(returnLine)
        else:
            return float(returnLine.split(": ")[-1])

    def CR(self, nReads: int, iReads: int) -> list[list]:
        """
        ### Continuous Reading
        Reads nReads times the force with an iReads interval inbetween.

        :param nReads: number of lines to read
        :type nReads: int
        :param iReads: interval inbetween lines [ms]
        :type iReads: int

        :return: [[time], [force]]
        :rtype: list[list[int], list[float]]
        """
        self.ser.flush()
        self.ser.write(
            f"{self.cmdStart}CR {nReads},{iReads}{self.cmdEnd}".encode())
        sleep(self.stdDelay + iReads/1000)
        returnLine: str = self.ser.read_until().decode().strip()
        if returnLine.split(":")[0] == "[ERROR]":
            raise RuntimeError(returnLine)
        else:
            time, force = returnLine.split(": ")[-1].split(";")
            time = int(time)
            force = float(force)
            del self.currentReads
            self.currentReads = [[time], [force]]

            for i in range(nReads):
                returnLine = self.ser.read_until().decode().strip()
                if returnLine.split(":")[0] == "[ERROR]":
                    raise RuntimeError(returnLine)
                else:
                    time, force = returnLine.split(": ")[-1].split(",")
                    time = int(time)
                    force = float(force)
                    self.currentReads[0].append(time)
                    self.currentReads[1].append(force)
            return self.currentReads

    def HM(self) -> None:
        """
        ### Home
        Homes the steppermotor stage to the endstop.
        The endstop is a physical switch that stops the motor when it is pressed.
        Afterwards goes up to a set position inside the firmware.
        """
        self.ser.flush()
        self.ser.write(f"{self.cmdStart}HM{self.cmdEnd}".encode())
        if self.stdDelay > 0:
            sleep(self.stdDelay)
        returnLine: str = self.ser.read_until().decode().strip()
        if returnLine.split(":")[0] == "[ERROR]":
            raise RuntimeError(returnLine)

    def TR(self) -> None:
        """
        ### Tare

        Tares the display values by setting current reading as offset.
        Does not affect readings.
        """
        self.ser.flush()
        self.ser.write(f"{self.cmdStart}TR{self.cmdEnd}".encode())
        if self.stdDelay > 0:
            sleep(self.stdDelay)
        returnLine: str = self.ser.read_until().decode().strip()
        if returnLine.split(":")[0] == "[ERROR]":
            raise RuntimeError(returnLine)

    def SF(self, calibrationForce: float) -> None:
        """
        ### Set Force

        Changes the display calibration, does not affect readings.
        Internally the force is stored as a float, so it is recommended to use a unit corresponding to the measurement range as to avoid floating point errors.

        :param calibrationForce: current force on the loadcell
        :type calibrationForce: float
        """
        self.ser.flush()
        self.ser.write(
            f"{self.cmdStart}SF {calibrationForce}{self.cmdEnd}".encode())
        if self.stdDelay > 0:
            sleep(self.stdDelay)
        returnLine: str = self.ser.read_until().decode().strip()
        if returnLine.split(":")[0] == "[ERROR]":
            raise RuntimeError(returnLine)
    
    def DC(self, enable: bool = True) -> None:
        """
        ### Display Commands
        
        Enables or disables the display of commands on the sensor.

        :param enable: If commands should be displayed on sensor.
        :type enable: bool
        :value enable: True
        """

        self.ser.flush()
        if not enable:
            self.ser.write(f"{self.cmdStart}DC false{self.cmdEnd}".encode())
        else:
            self.ser.write(f"{self.cmdStart}DC{self.cmdEnd}".encode())
            
        returnLine: str = self.ser.read_until().decode().strip()
        if returnLine.split(":")[0] == "[ERROR]":
            self.errorMessage = ["RuntimeError", "RuntimeError", returnLine]
            self.errorSignal.emit()
