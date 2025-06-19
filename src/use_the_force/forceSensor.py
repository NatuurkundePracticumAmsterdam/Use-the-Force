from time import perf_counter_ns, sleep
import serial

__all__ = [
    "ForceSensor",
    "Commands"
]

class ForceSensor():
    def __init__(self, 
                 PortName: str | None = None, 
                 **kwargs
                 ) -> None:
        """
        Base class for the force sensor with almost all functionality.

        Use ForceSensor.cmds.\<command\>() for commands:
        >>> sensor = ForceSensor("COM0")
        >>> commands = sensor.cmds
        >>> commands.SR()
        411023

        :param PortName: Portname over which to establish the connection. If None, the this class has to be called again with the port name.
        :type PortName: str | None
        """
        # The 'zero' volt value. Determined automatically each time.
        self.tareValue: int = int(kwargs.pop('tareValue', 0))
        self.tareRound: int = int(kwargs.pop('tareRound', 0))
        self.loadPerCount: float = int(kwargs.pop('loadPerCount', 1.))

        self.minPos: int = int(kwargs.pop('minPos', 1))  # [mm]
        self.maxPos: int = int(kwargs.pop('maxPos', 46))  # [mm]

        self.T0: int = perf_counter_ns()

        ####### PORT INIT ######
        # The 'COM'-port depends on which plug is used at the back of the computer.
        # To find the correct port: go to Windows Settings, Search for Device Manager,
        # and click the tab "Ports (COM&LPT)".s
        self.ser: serial.Serial = serial.Serial(port=PortName, baudrate=115200, timeout=5, dsrdtr=False)
        self.ser.setRTS(False)
        self.ser.setDTR(False)

        self.cmds = Commands(self.ser)

        if PortName != None:
            self.PortName = PortName.upper()
            self.ser.setPort(self.PortName)
            self.ser.open()
    
    def __call__(self, PortName: str):
        """
        Open the serial connection if not already open.

        >>> sensor = ForceSensor()
        >>> sensor("COM0")

        :param PortName: Portname over which to establish the connection.
        :type PortName: str
        """
        if not self.ser.is_open:
            self.PortName = PortName.upper()
            self.ser.setPort(self.PortName)
            self.ser.open()
    
    def tare(self, reads: int = 30, skips: int = 3) -> int:
        """
        Updates and returns the tare value by taking the average of `reads` reads.
        
        :param reads: amount of readings
        :type reads: int
        :param skips: initial lines to skip (and clear old values)
        :type skips: int

        :returns: Tare value
        :rtype: int
        """
        self.ser.reset_input_buffer()
        self.ser.reset_output_buffer()
        skips: list[float] = [self.cmds.SR() for _ in range(skips)]
        read_values: list[float] = [self.cmds.SR() for _ in range(reads)]
        self.tareValue = round(sum(read_values)/reads, self.tareRound)
        return self.tareValue

    def updateLpC(self, load: float, reads: int = 10) -> float:
        """Updates and returns Load per Count

        :param load: Applied known load (Newton, gram, ...)
        :type load: float
        :param reads: Times to read load cell and take average
        :type reads: int

        :returns: Load per Count
        :rtype: float
        """
        read_values: list[float] = [self.cmd.SR() for i in range(reads)]
        self.loadPerCount = load/int(sum(read_values)/reads)
        return self.loadPerCount

    def ForceFix(self, count: float) -> float:
        """Corrects the units given based on tareValue and loadPerCount

        Args:
            count (float): sensor count

        Returns:
            float: calibrated units
        """        
        # The output, with gauge, in calibrated units.
        return (count - self.tareValue) * self.loadPerCount

    def ClosePort(self) -> None:
        """
        Always close after use.
        """
        self.ser.close()


class Commands():
    def __init__(self, serialConnection: serial.Serial, **kwargs) -> None:
        """Class containing all available commands.

        For more explanation, see the firmware [GitHub](https://github.com/NatuurkundePracticumAmsterdam/use-the-force-firmware).

        :param serialConnection: serial connection to sensor
        :type serialConnection: Serial
        :param stdDelay: standard delay between sending a message and reading
        :type stdDelay: float
        """
        self.serialConnection: serial.Serial = serialConnection
        self.stdDelay: float = float(kwargs.pop("stdDelay", 0.))

        self.cmdStart: str = "#"
        self.cmdArgSep: str = ","
        self.cmdEnd: str = ";"

        self.minPos: int = 1
        self.maxPos: int = 46

        self.verMajor:int = 0
        self.verMinor:int = 0
        self.verPatch:int = 0
    
    def __call__(self, serialConnection: serial.Serial) -> None:
        """Change serial connection

        :param serialConnection: new serial connection
        :type serialConnection: Serial
        """
        self.serialConnection = serialConnection

    def _clearBuffer(self) -> None:
        """
        Clears the serial buffer.
        """
        self.serialConnection.flush()
        self.serialConnection.reset_input_buffer()
        self.serialConnection.reset_output_buffer()

    def customCmd(self, cmd: str, *args) -> str:
        """Custom command
        
        Sends a self written command to the sensor.
        For general use, this command should not be used, as it is not guaranteed to work with the firmware.

        :param cmd: command to send
        :type cmd: str
        :param args: additional arguments for the command
        :type args: tuple

        :returns: return line
        :rtype: str
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
        returnLine: str = self.serialConnection.read_until().decode().strip()
        if returnLine.split(":")[0] == "[ERROR]":
            raise RuntimeError(returnLine)
        return returnLine
    
    ########################
    # 0 Arguments Commands #
    ########################
    def AB(self) -> None:
        """
        ### Abort CR
        
        Aborts the continous reading.
        
        :raises RunTimeError: If sensor encounters an error.
        """
        self._clearBuffer()
        self.serialConnection.write(f"{self.cmdStart}AB{self.cmdEnd}".encode())
        if self.stdDelay > 0:
            sleep(self.stdDelay)
        returnLine: str = self.serialConnection.read_until().decode().strip()
        if returnLine.split(":")[0] == "[ERROR]":
            raise RuntimeError(returnLine)
    
    def CM(self) -> str:
        """
        ### Count Maximum
        
        Sets the currently read load as the maximum amount of force that is allowed.
        Will immediatly send out the abort message if load remains.
        
        This count is saved on the sensor.
        
        :raises RunTimeError: If sensor encounters an error.

        :returns: Returnline from sensor
        :rtype: str
        """
        self._clearBuffer()
        self.serialConnection.write(f"{self.cmdStart}CM{self.cmdEnd}".encode())
        if self.stdDelay > 0:
            sleep(self.stdDelay)
        returnLine: str = self.serialConnection.read_until().decode().strip()
        if returnLine.split(":")[0] == "[ERROR]":
            raise RuntimeError(returnLine)
        return returnLine
    
    def CZ(self) -> str:
        """
        ### Count Zero
        
        Tares the internal value count of the sensor, which is used to check the maximum force.\\
        Uses current load on the sensor as internal zero.
        
        This count is saved on the sensor. 
        
        :raises RunTimeError: If sensor encounters an error.

        :returns: Returnline from sensor
        :rtype: str
        """
        self._clearBuffer()
        self.serialConnection.write(f"{self.cmdStart}CZ{self.cmdEnd}".encode())
        if self.stdDelay > 0:
            sleep(self.stdDelay)
        returnLine: str = self.serialConnection.read_until().decode().strip()
        if returnLine.split(":")[0] == "[ERROR]":
            raise RuntimeError(returnLine)
        return returnLine

    def GP(self) -> int:
        """
        ### Get Position
        Current position set in memory.

        :return: End position if moving, else current position in [mm]
        :rtype: int
        
        :raises RunTimeError: If sensor encounters an error.
        """
        self._clearBuffer()
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
        self._clearBuffer()
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
        self._clearBuffer()
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
        self._clearBuffer()
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
        self._clearBuffer()
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
        self._clearBuffer()
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
        self._clearBuffer()
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
        self._clearBuffer()
        self.serialConnection.write(f"{self.cmdStart}VR{self.cmdEnd}".encode())
        if self.stdDelay > 0:
            sleep(self.stdDelay)
        returnLine: str = self.serialConnection.read_until().decode().strip()
        if returnLine.split(":")[0] == "[ERROR]":
            raise RuntimeError(returnLine)
        else:
            self.verMajor, self.verMinor, self.verPatch = map(int, returnLine.split(": ")[-1].split("."))
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
        self._clearBuffer()
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
        self._clearBuffer()
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
        self._clearBuffer()
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
        self._clearBuffer()
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
        self._clearBuffer()
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
        self._clearBuffer()
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
        self._clearBuffer()
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
        self._clearBuffer()
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
        self._clearBuffer()
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