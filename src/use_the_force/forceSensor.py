from time import perf_counter_ns, sleep
import serial
class ForceSensor():
    def __init__(self, PortName: str = "/dev/ttyACM0", GaugeValue: int = 0, NewtonPerVolt: float = 0.0000154, WarningOn: bool = True, MaxNewton: int | float = 5, **kwargs) -> None:
        """
        Opens up the serial port, checks the gauge value and makes sure data is available.

        (PySerial library has to be installed on the computer, see requirements.txt)
        """
        ####### SOME PARAMETERS AND STUFF ######

        self.GaugeValue: int = GaugeValue  # The 'zero' volt value. Determined automatically each time.
        self.NewtonPerVolt: float = NewtonPerVolt
        # self.NewtonPerVolt = 1  # value I set for calibration
        self.WarningOn: bool = WarningOn  # >MaxNewton is dangerous for sensor.
        self.MaxNewton: int | float = MaxNewton

        self.encoding: str = kwargs.pop('encoding', "UTF-8")

        self.baudrate: int = kwargs.pop('baudrate', 115200)
        self.timeout: float = kwargs.pop('timeout', 2)

        self.stdDelay: float = 0 #150/1000 # base delay of the M5Din Meter to send a response [seconds]
        self.cmdStart: str = "#"
        self.cmdEnd: str = ";"
        self.currentReads = [[], []]

        self.T0 = perf_counter_ns()

        self.PortName: str = PortName
        
        ####### PORT INIT ######
        # The 'COM'-port depends on which plug is used at the back of the computer.
        # To find the correct port: go to Windows Settings, Search for Device Manager,
        # and click the tab "Ports (COM&LPT)".

        self.ser = self.connectPort(self.PortName, baudrate=self.baudrate, timeout=self.timeout)

        # Test whether we are receiving any data or not.
        # try: 
        #     line = self.ser.readline()
        #     decodedLine = line.decode(self.encoding)
        #     if decodedLine == "":
        #         raise RuntimeError("Loadsensor returns no data")

        #     if GaugeValue == 0:
        #         print("Communication with the LoadSensor established")
        #         self.reGauge()
        #     else:
        #         print("Communication with the LoadSensor established")
        #         print("Given gauged value: " + str(self.GaugeValue))
        
        # except UnicodeDecodeError:
        #     print("could not decode incoming data!")
        #     print("Connection maintained for debugging.")
        #     print("Data: ", line)
        #     print("Decoded: "+ str(line.decode(self.encoding, errors="replace")))
    
    def connectPort(self, PortName: str, baudrate: int = 115200, timeout: int = 2):
        return serial.Serial(PortName, baudrate=baudrate, timeout=timeout)


    def reGauge(self):
        """
        !!!IT'S IMPORTANT NOT TO HAVE ANY FORCE ON THE SENSOR WHEN CALLING THIS FUNCTION!!!
        """
        self.ser.reset_input_buffer()
        skips: list[float] = [self.GetReading()[2] for i in range(3) ]
        reads: list[float] = [self.GetReading()[2] for i in range(10)]
        self.GaugeValue = int(  sum(reads)/10  )
        print("Self-gauged value: " + str(self.GaugeValue))

    def GetReading(self) -> list[int, float, float]:
        """
        Reads a line of code, returns [ID, time, force]
        """
        #'readline()' gives a value from the serial connection in 'bytes'
        #'decode()'   turns 'bytes' into a 'string'
        #'float()'    turns 'string' into a floating point number.
        line: str = self.ser.readline().decode(self.encoding)
        self.ser.reset_input_buffer()
        ID, force = line.split(",")
        return [int(ID), float(perf_counter_ns()-self.T0), float(force)]

    def ForceFix(self, x: float) -> float:
        """
        Gets a single reading out of the LoadSensor.
        """
        
        # x: float = self.LineReading()[2]

        #I don't want old values to pile up, so I delete them all to get a fresh
        # reading every time.
        # self.ser.reset_input_buffer()

        #Warning if a high value is read (>5 Newton)
        if self.WarningOn:
            if abs( x * self.NewtonPerVolt ) > self.MaxNewton:
                print( "LOAD TOO HIGH FOR SENSOR" )
                print( "ABORT TO AVOID SENSOR DAMAGE" )

        #The output, with gauge, in mN
        return ( x - self.GaugeValue ) * self.NewtonPerVolt * 1000


    def ClosePort(self) -> None:
        """
        Always close after use.
        """
        self.ser.flush()
        self.ser.flushInput()
        self.ser.flushOutput()
        self.ser.close()
        print( "LoadSensor port is closed" )


    def TestSensor(self, lines: int = 100) -> None:
        """
        Opens the port and prints some values on screen.
        Primarily a debugging tool.

        Tests if the decoding is right and should show the decoded values after the "-->"
        """
        for i in range( lines ):
            line = self.ser.readline()
            decodedLine = line.decode(self.encoding, errors="replace")
            print(line, " --> ", decodedLine)
            print("Force: " + str(float(decodedLine.split(",")[1])) + " N")

    def SP(self, position: int) -> None:
        """
        ### Set Position
        Sets the position of the steppermotor stage in milimeters.
        
        :param position: position to set from bottom [mm]
        :type position: int
        """
        self.ser.flush()
        self.ser.flushInput()
        self.ser.flushOutput()
        self.ser.write(f"{self.cmdStart}SP {position}{self.cmdEnd}".encode())
        if self.stdDelay > 0:
            sleep(self.stdDelay)
        returnLine = self.ser.read_until().decode().strip()
        if returnLine.split(":")[0] == "[ERROR]":
            raise RuntimeError(returnLine)
    
    def GP(self) -> int:
        """
        ### Get Position
        Current position set in memory.
        
        :return: End position if moving, else current position in [mm]
        :rtype: int
        """
        self.ser.flush()
        self.ser.flushInput()
        self.ser.flushOutput()
        self.ser.write(f"{self.cmdStart}GP{self.cmdEnd}".encode())
        if self.stdDelay > 0:
            sleep(self.stdDelay)
        returnLine = self.ser.read_until().decode().strip()
        if returnLine.split(":")[0] == "[ERROR]":
            raise RuntimeError(returnLine)
        else:
            try:
                return int(returnLine.split(": ")[-1])
            except ValueError as e:
                return e
    
    def SV(self, velocity: int) -> str:
        """
        ### Set Velocity
        Sets the velocity of the steppermotor stage in milimeters per second.
        
        :param velocity: velocity to set [mm/s]
        :type velocity: int
        """
        self.ser.flush()
        self.ser.flushInput()
        self.ser.flushOutput()
        self.ser.write(f"{self.cmdStart}SV {velocity}{self.cmdEnd}".encode())
        if self.stdDelay > 0:
            sleep(self.stdDelay)
        returnLine = self.ser.read_until().decode().strip()
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
        self.ser.flushInput()
        self.ser.flushOutput()
        self.ser.write(f"{self.cmdStart}GV{self.cmdEnd}".encode())
        if self.stdDelay > 0:
            sleep(self.stdDelay)
        returnLine = self.ser.read_until().decode().strip()
        if returnLine.split(":")[0] == "[ERROR]":
            raise RuntimeError(returnLine)
        else:
            try:
                return int(returnLine.split(": ")[-1])
            except ValueError as e:
                return e
            
    def GM(self) -> str:
        """
        ### Get Mode
        Returns the current selected mode, calibrated or raw.

        :return: string with selected mode
        :rtype: str
        """
        self.ser.flush()
        self.ser.flushInput()
        self.ser.flushOutput()
        self.ser.write(f"{self.cmdStart}GV{self.cmdEnd}".encode())
        if self.stdDelay > 0:
            sleep(self.stdDelay)
        returnLine = self.ser.read_until().decode().strip()
        if returnLine.split(":")[0] == "[ERROR]":
            raise RuntimeError(returnLine)
        else:
            try:
                return returnLine.split(" ")[-1]
            except ValueError as e:
                return e
        

    def TM(self) -> None:
        """
        ### Toggle Mode
        Toggles between the two modes, calibrated or raw.
        """
        self.ser.flush()
        self.ser.flushInput()
        self.ser.flushOutput()
        self.ser.write(f"{self.cmdStart}TM{self.cmdEnd}".encode())
        if self.stdDelay > 0:
            sleep(self.stdDelay)
        returnLine = self.ser.read_until().decode().strip()
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
        self.ser.flushInput()
        self.ser.flushOutput()
        self.ser.write(f"{self.cmdStart}SR{self.cmdEnd}".encode())
        if self.stdDelay > 0:
            sleep(self.stdDelay)
        returnLine = self.ser.read_until().decode().strip()
        if returnLine.split(":")[0] == "[ERROR]":
            raise RuntimeError(returnLine)
        else:
            try:
                return float(returnLine.split(": ")[-1])
            except ValueError as e:
                return e

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
        self.ser.flushInput()
        self.ser.flushOutput()
        self.ser.write(f"{self.cmdStart}CR {nReads},{iReads}{self.cmdEnd}".encode())
        sleep(self.stdDelay + iReads/1000)
        self.ser.read_until("[TIME;VALUE]:")
        returnLine = self.ser.read_until().decode().strip()
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
        self.ser.flushInput()
        self.ser.flushOutput()
        self.ser.write(f"{self.cmdStart}HM{self.cmdEnd}".encode())
        if self.stdDelay > 0:
            sleep(self.stdDelay)
        returnLine = self.ser.read_until().decode().strip()
        if returnLine.split(":")[0] == "[ERROR]":
            raise RuntimeError(returnLine)

    def TR(self) -> None:
        """
        ### Tare

        Tares load cell values by setting current reading as offset.
        """
        self.ser.flush()
        self.ser.flushInput()
        self.ser.flushOutput()
        self.ser.write(f"{self.cmdStart}TR{self.cmdEnd}".encode())
        if self.stdDelay > 0:
            sleep(self.stdDelay)
        returnLine = self.ser.read_until().decode().strip()
        if returnLine.split(":")[0] == "[ERROR]":
            raise RuntimeError(returnLine)

    def CL(self) -> None:
        """
        ### Calibrate Loading

        Starts the callibration sequence by calling TR and throws away the set slope value.

        ## Make sure no force is applied to the sensor when calling this function!
        """
        self.ser.flush()
        self.ser.flushInput()
        self.ser.flushOutput()
        self.ser.write(f"{self.cmdStart}TM{self.cmdEnd}".encode())
        if self.stdDelay > 0:
            sleep(self.stdDelay)
        returnLine = self.ser.read_until().decode().strip()
        if returnLine.split(":")[0] == "[ERROR]":
            raise RuntimeError(returnLine)

    def SF(self, calibrationForce: float) -> None:
        """
        ### Set Force

        Only to be called when the sensor is in calibration mode.
        Since this is scaling force, units can be set in [mN] or any other prefix as well. 
        The ouput force will correspond with the unit set.

        Internally the force is stored as a float, so it is recommended to use a unit corresponding to the measurement range as to avoid floating point errors.

        :param calibrationForce: current force on the loadcell [N]
        :type calibrationForce: float
        """
        self.ser.flush()
        self.ser.flushInput()
        self.ser.flushOutput()
        self.ser.write(f"{self.cmdStart}SF {calibrationForce}{self.cmdEnd}".encode())
        if self.stdDelay > 0:
            sleep(self.stdDelay)
        returnLine = self.ser.read_until().decode().strip()
        if returnLine.split(":")[0] == "[ERROR]":
            raise RuntimeError(returnLine)
        

    def SC(self) -> None:
        """
        ### Save Configuration

        Saves the current calibration settings to flash memory and uses them on boot.
        """
        self.ser.flush()
        self.ser.flushInput()
        self.ser.flushOutput()
        self.ser.write(f"{self.cmdStart}SC{self.cmdEnd}".encode())
        if self.stdDelay > 0:
            sleep(self.stdDelay)
        returnLine = self.ser.read_until().decode().strip()
        if returnLine.split(":")[0] == "[ERROR]":
            raise RuntimeError(returnLine)
    

    def CC(self, iReads: int) -> list[list[int], list[float]]:
        """
        # DEBUG: only available in debug firmware.

        ### CR, but as a toggle.
        Will contiuously read until the command is sent again.
        
        :param iReads: interval inbetween reads [ms]
        :type iReads: int

        :return: [[time], [force]]
        :rtype: list[list[int], list[float]]
        """
        self.ser.flush()
        self.ser.flushInput()
        self.ser.flushOutput()
        self.ser.write(f"{self.cmdStart}CC {iReads}{self.cmdEnd}".encode())
        if self.stdDelay > 0:
            sleep(self.stdDelay)
        returnLine = self.ser.read_until().decode().strip()
        if returnLine.split(":")[0] == "[ERROR]":
            raise RuntimeError(returnLine)
