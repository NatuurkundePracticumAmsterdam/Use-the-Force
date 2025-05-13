from time import perf_counter_ns, sleep
import serial

# TODO: add all new commands...

__all__ = [
    "ForceSensor",
    "Commands"
]

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
        
        cmd = Commands(self.ser)

    def connectPort(self, PortName: str, baudrate: int = 115200, timeout: float | None = 2.) -> serial.Serial:
        return serial.Serial(port=PortName, baudrate=baudrate, timeout=timeout)

    def reGauge(self, reads: int = 10, skips: int = 3) -> int:
        """
        !!!IT'S IMPORTANT NOT TO HAVE ANY FORCE ON THE SENSOR WHEN CALLING THIS FUNCTION!!!
        
        Updates the GaugeValue by taking the average of `reads` values.
        
        :param reads: amount of readings
        :type reads: int
        :param skips: initial lines to skip (and clear old values)
        :type skips: int

        :returns: Gauge value
        :rtype: int
        """
        self.ser.reset_input_buffer()
        skips: list[float] = [self.cmd.SR() for i in range(skips)]
        read_values: list[float] = [self.cmd.SR() for i in range(reads)]
        self.GaugeValue = int(sum(read_values)/reads)
        return self.GaugeValue
    
    def updateNpC(self, force: float, reads: int = 10) -> float:
        """Updates Newton per Count

        Args:
            force (float): Applied known force
            reads (int): Times to read load cell and take average
        
        Returns:
            float: Newton per Count
        """
        read_values: list[float] = [self.cmd.SR() for i in range(reads)]
        self.NewtonPerCount = force/int(sum(read_values)/reads)
        return self.NewtonPerCount

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


class Commands():
    def __init__(self, serialConnection: serial.Serial, **kwargs) -> None:
        """Class containing all available commands.

        Args:
            serialConnection (serial.Serial): serial connection to sensor
            stdDelay (float): standard delay between sending a message and reading
        """
        self.serialConnection: serial.Serial = serialConnection
        self.stdDelay: float = float(kwargs.pop("stdDelay", 0.))

        self.cmdStart: str = "#"
        self.cmdArgSep: str = ","
        self.cmdEnd: str = ";"

        self.minPos: int = 1
        self.maxPos: int = 46
    
    def __call__(self, serialConnection: serial.Serial) -> None:
        """Change serial connection

        Args:
            serialConnection (serial.Serial): new serial connection
        """
        self.serialConnection = serialConnection

    def customCmd(self, cmd: str, *args) -> str:
        """Custom command

        Args:
            cmd (str): command to send
            args (tuple): additional arguments for the command

        Returns:
            str: return line
        """
        self.serialConnection.flush()
        cmdStr = f"{self.cmdStart}{cmd}"
        if len(args) != 0:
            cmdStr += f"{args[0]}"
            if len(args)-1 != 0:
                for argument in args[1:]:
                    cmdStr += f"{self.cmdArgSep}{argument}"
        cmdStr += f"{self.cmdEnd}"
        self.serialConnection.write(cmdStr.encode())
        if self.stdDelay > 0:
            sleep(self.stdDelay)
        return self.serialConnection.read_until().decode().strip()

    ########################
    # 0 Arguments Commands #
    ########################
    def AB(self) -> None:
        """
        ### Abort Continous Reading
        
        Aborts the continous reading.
        
        :raises RunTimeError: If sensor encounters an error.
        """
        self.serialConnection.flush()
        self.serialConnection.write(f"{self.cmdStart}AB{self.cmdEnd}".encode())
        if self.stdDelay > 0:
            sleep(self.stdDelay)
        returnLine: str = self.serialConnection.read_until().decode().strip()
        if returnLine.split(":")[0] == "[ERROR]":
            raise RuntimeError(returnLine)
    
    def CM(self) -> None:
        """
        ### Count Maximum
        
        Sets the currently read load as the maximum amount of force that is allowed.
        Will immediatly send out the abort message if load remains.
        
        This count is saved on the sensor.
        
        :raises RunTimeError: If sensor encounters an error.
        """
        self.serialConnection.flush()
        self.serialConnection.write(f"{self.cmdStart}CM{self.cmdEnd}".encode())
        if self.stdDelay > 0:
            sleep(self.stdDelay)
        returnLine: str = self.serialConnection.read_until().decode().strip()
        if returnLine.split(":")[0] == "[ERROR]":
            raise RuntimeError(returnLine)
    
    def CZ(self) -> None:
        """
        ### Count Zero
        
        Tares the internal value count of the sensor, which is used to check the maximum force.\\
        Uses current load on the sensor as internal zero.
        
        This count is saved on the sensor. 
        
        :raises RunTimeError: If sensor encounters an error.
        """
        self.serialConnection.flush()
        self.serialConnection.write(f"{self.cmdStart}CZ{self.cmdEnd}".encode())
        if self.stdDelay > 0:
            sleep(self.stdDelay)
        returnLine: str = self.serialConnection.read_until().decode().strip()
        if returnLine.split(":")[0] == "[ERROR]":
            raise RuntimeError(returnLine)

    def GP(self) -> int:
        """
        ### Get Position
        Current position set in memory.

        :return: End position if moving, else current position in [mm]
        :rtype: int
        
        :raises RunTimeError: If sensor encounters an error.
        """
        self.serialConnection.flush()
        self.serialConnection.write(f"{self.cmdStart}GP{self.cmdEnd}".encode())
        if self.stdDelay > 0:
            sleep(self.stdDelay)
        returnLine: str = self.serialConnection.read_until().decode().strip()
        if returnLine.split(":")[0] == "[ERROR]":
            raise RuntimeError(returnLine)
        else:
            try:
                return int(returnLine.split(": ")[-1])
            except ValueError as e:
                return e
    
    def GV(self) -> int:
        """
        ### Get Velocity
        Returns the current velocity of the steppermotor stage in milimeters per second.

        :return: End velocity if moving, else current velocity [mm/s]
        :rtype: int
        
        :raises RunTimeError: If sensor encounters an error.
        """
        self.serialConnection.flush()
        self.serialConnection.write(f"{self.cmdStart}GV{self.cmdEnd}".encode())
        if self.stdDelay > 0:
            sleep(self.stdDelay)
        returnLine: str = self.serialConnection.read_until().decode().strip()
        if returnLine.split(":")[0] == "[ERROR]":
            raise RuntimeError(returnLine)
        else:
            return int(returnLine.split(": ")[-1])
    
    def HE(self) -> ...:
        """
        ### Help

        Help command internally, not implemented here.
        
        :raises NotImplementedError: Not Implemented
        :raises RunTimeError: If sensor encounters an error.
        """
        raise NotImplementedError
    
    def HM(self) -> None:
        """
        ### Home
        Homes the steppermotor stage to the endstop.
        The endstop is a physical switch that stops the motor when it is pressed.
        Afterwards goes up to a set position inside the firmware.
        
        :raises RunTimeError: If sensor encounters an error.
        """
        self.serialConnection.flush()
        self.serialConnection.write(f"{self.cmdStart}HM{self.cmdEnd}".encode())
        if self.stdDelay > 0:
            sleep(self.stdDelay)
        returnLine: str = self.serialConnection.read_until().decode().strip()
        if returnLine.split(":")[0] == "[ERROR]":
            raise RuntimeError(returnLine)
        
    def ID(self) -> str:
        """
        ### Motor ID
        
        Returns the ID that is set for the motor stage.

        :returns: Motor ID
        :rtype: str

        :raises RunTimeError: If sensor encounters an error.
        """
        self.serialConnection.flush()
        self.serialConnection.write(f"{self.cmdStart}ID{self.cmdEnd}".encode())
        if self.stdDelay > 0:
            sleep(self.stdDelay)
        returnLine: str = self.serialConnection.read_until().decode().strip()
        if returnLine.split(":")[0] == "[ERROR]":
            raise RuntimeError(returnLine)
        else:
            return returnLine
        
    def SR(self) -> float:
        """
        ### Single Read
        Reads the force a single time.

        :return: read force
        :rtype: float
        
        :raises RunTimeError: If sensor encounters an error.
        """
        self.serialConnection.flush()
        self.serialConnection.write(f"{self.cmdStart}SR{self.cmdEnd}".encode())
        if self.stdDelay > 0:
            sleep(self.stdDelay)
        returnLine: str = self.serialConnection.read_until().decode().strip()
        if returnLine.split(":")[0] == "[ERROR]":
            raise RuntimeError(returnLine)
        else:
            return float(returnLine.split(": ")[-1])
    
    def ST(self) -> None:
        """
        ### Force Stop
        
        Forces the motor to stop during movement.
        Will need to home afterwards.
        ### WARNING: DOES NOT WORK DURING HOME
        
        :raises RunTimeError: If sensor encounters an error.
        """
        self.serialConnection.flush()
        self.serialConnection.write(f"{self.cmdStart}ST{self.cmdEnd}".encode())
        if self.stdDelay > 0:
            sleep(self.stdDelay)
        returnLine: str = self.serialConnection.read_until().decode().strip()
        if returnLine.split(":")[0] == "[ERROR]":
            raise RuntimeError(returnLine)
    
    def TR(self) -> None:
        """
        ### Tare

        Tares the display values by setting current reading as offset.
        Does not affect readings.
        
        :raises RunTimeError: If sensor encounters an error.
        """
        self.serialConnection.flush()
        self.serialConnection.write(f"{self.cmdStart}TR{self.cmdEnd}".encode())
        if self.stdDelay > 0:
            sleep(self.stdDelay)
        returnLine: str = self.serialConnection.read_until().decode().strip()
        if returnLine.split(":")[0] == "[ERROR]":
            raise RuntimeError(returnLine)
    
    def VR(self) -> str:
        """
        ### Version
        
        Returns current running firmware version of the sensor.

        :returns: Firmware Version
        :rtype: str
        
        :raises RunTimeError: If sensor encounters an error.
        """
        self.serialConnection.flush()
        self.serialConnection.write(f"{self.cmdStart}VR{self.cmdEnd}".encode())
        if self.stdDelay > 0:
            sleep(self.stdDelay)
        returnLine: str = self.serialConnection.read_until().decode().strip()
        if returnLine.split(":")[0] == "[ERROR]":
            raise RuntimeError(returnLine)
        else:
            return returnLine
    
    #######################
    # 1 Argument Commands #
    #######################
    def DC(self, enable: bool = True) -> None:
        """
        ### Display Commands
        
        Enables or disables the display of commands on the sensor.

        :param enable: If commands should be displayed on sensor. Default: True
        :type enable: bool

        :raises RunTimeError: If sensor encounters an error.
        """
        self.serialConnection.flush()
        if not enable:
            self.serialConnection.write(f"{self.cmdStart}DC false{self.cmdEnd}".encode())
        else:
            self.serialConnection.write(f"{self.cmdStart}DC{self.cmdEnd}".encode())
            
        returnLine: str = self.serialConnection.read_until().decode().strip()
        if returnLine.split(":")[0] == "[ERROR]":
            raise RuntimeError(returnLine)

    def SF(self, calibrationForce: float) -> None:
        """
        ### Set Force

        Changes the display calibration, does not affect readings.
        Internally the force is stored as a float, so it is recommended to use a unit corresponding to the measurement range as to avoid floating point errors.

        :param calibrationForce: current force on the loadcell
        :type calibrationForce: float

        :raises RunTimeError: If sensor encounters an error.
        """
        self.serialConnection.flush()
        self.serialConnection.write(
            f"{self.cmdStart}SF {calibrationForce}{self.cmdEnd}".encode())
        if self.stdDelay > 0:
            sleep(self.stdDelay)
        returnLine: str = self.serialConnection.read_until().decode().strip()
        if returnLine.split(":")[0] == "[ERROR]":
            raise RuntimeError(returnLine)


    def SP(self, position: int) -> None:
        """
        ### Set Position
        Sets the position of the steppermotor stage in milimeters.

        :param position: position to set from bottom [mm]
        :type position: int

        :raises RunTimeError: If sensor encounters an error.
        """
        if position <= self.maxPos and position >= self.minPos:
            self.serialConnection.flush()
            self.serialConnection.write(f"{self.cmdStart}SP{position}{self.cmdEnd}".encode())
            if self.stdDelay > 0:
                sleep(self.stdDelay)
            returnLine: str = self.serialConnection.read_until().decode().strip()
            if returnLine.split(":")[0] == "[ERROR]":
                raise RuntimeError(returnLine)
        else:
            raise ValueError(f"Position {position} is out of range ({self.minPos}, {self.maxPos})")
    
    def SV(self, velocity: int) -> None:
        """
        ### Set Velocity
        Sets the velocity of the steppermotor stage in milimeters per second.

        :param velocity: velocity to set [mm/s]
        :type velocity: int

        :raises RunTimeError: If sensor encounters an error.
        """
        self.serialConnection.flush()
        self.serialConnection.write(f"{self.cmdStart}SV{velocity}{self.cmdEnd}".encode())
        if self.stdDelay > 0:
            sleep(self.stdDelay)
        returnLine: str = self.serialConnection.read_until().decode().strip()
        if returnLine.split(":")[0] == "[ERROR]":
            raise RuntimeError(returnLine)
        
    def UL(self, lineHeight: int) -> None:
        """
        ### Update Text Line Height

        Changes the line height set in the sensor.

        :param lineHeight: current force on the loadcell
        :type lineHeight: int

        :raises RunTimeError: If sensor encounters an error.
        """
        self.serialConnection.flush()
        self.serialConnection.write(
            f"{self.cmdStart}UL{lineHeight}{self.cmdEnd}".encode())
        if self.stdDelay > 0:
            sleep(self.stdDelay)
        returnLine: str = self.serialConnection.read_until().decode().strip()
        if returnLine.split(":")[0] == "[ERROR]":
            raise RuntimeError(returnLine)
        
    def UU(self, unit: str) -> None:
        """
        ### Update Unit Displayed

        Changes the unit displayed on the interface.

        :param unit: new unit, max 8 chars.
        :type unit: str

        :raises RunTimeError: If sensor encounters an error.
        """
        self.serialConnection.flush()
        self.serialConnection.write(
            f"{self.cmdStart}UU{unit}{self.cmdEnd}".encode())
        if self.stdDelay > 0:
            sleep(self.stdDelay)
        returnLine: str = self.serialConnection.read_until().decode().strip()
        if returnLine.split(":")[0] == "[ERROR]":
            raise RuntimeError(returnLine)
        
    def UX(self, xOffset: int) -> None:
        """
        ### Update display x offset

        Updates the x offset of the display.

        :param xOffset: new offset
        :type xOffset: int

        :raises RunTimeError: If sensor encounters an error.
        """
        self.serialConnection.flush()
        self.serialConnection.write(
            f"{self.cmdStart}UX{xOffset}{self.cmdEnd}".encode())
        if self.stdDelay > 0:
            sleep(self.stdDelay)
        returnLine: str = self.serialConnection.read_until().decode().strip()
        if returnLine.split(":")[0] == "[ERROR]":
            raise RuntimeError(returnLine)
        
    def UY(self, yOffset: int) -> None:
        """
        ### Update display y offset

        Updates the y offset of the display.

        :param yOffset: new offset
        :type yOffset: int

        :raises RunTimeError: If sensor encounters an error.
        """
        self.serialConnection.flush()
        self.serialConnection.write(
            f"{self.cmdStart}UY{yOffset}{self.cmdEnd}".encode())
        if self.stdDelay > 0:
            sleep(self.stdDelay)
        returnLine: str = self.serialConnection.read_until().decode().strip()
        if returnLine.split(":")[0] == "[ERROR]":
            raise RuntimeError(returnLine)
        
    
    ########################
    # 2 Arguments Commands #
    ########################
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

        :raises RunTimeError: If sensor encounters an error.
        """
        self.serialConnection.flush()
        self.serialConnection.write(
            f"{self.cmdStart}CR {nReads}{self.cmdArgSep}{iReads}{self.cmdEnd}".encode())
        sleep(self.stdDelay + iReads/1000)
        returnLine: str = self.serialConnection.read_until().decode().strip()
        if returnLine.split(":")[0] == "[ERROR]":
            raise RuntimeError(returnLine)
        else:
            time, force = returnLine.split(": ")[-1].split(";")
            time = int(time)
            force = float(force)
            currentReads = [[time], [force]]

            for i in range(nReads):
                returnLine = self.serialConnection.read_until().decode().strip()
                if returnLine.split(":")[0] == "[ERROR]":
                    raise RuntimeError(returnLine)
                else:
                    time, force = returnLine.split(": ")[-1].split(",")
                    time = int(time)
                    force = float(force)
                    currentReads[0].append(time)
                    currentReads[1].append(force)
            return currentReads