from .forceSensor import ForceSensor

class commands(ForceSensor):
    def __init__(self):
        self.cmdStart: str = "#"
        self.cmdEnd: str = ";"

    def SP(self, position: int) -> str:
        """
        Sets the position of the steppermotor stage in milimeters.
        
        :param position: position to set from bottom [mm]
        :type position: int
        """
        self.ser.write(f"{self.cmdStart}SR {position}{self.cmdEnd}")
        returnLine = self.ser.readline().strip()
        if returnLine.split(":")[0] == "[ERROR]":
            return "[ERROR]"
    
    def GP(self) -> int | str:
        """
        Current position set in memory.
        
        :return: End position if moving, else current position in [mm]
        :rtype: int
        """
        self.ser.write(f"{self.cmdStart}GP{self.cmdEnd}")
        returnLine = self.ser.readline().strip()
        if returnLine.split(":")[0] == "[ERROR]":
            return "[ERROR]"
        else:
            try:
                return int(returnLine.split(": ")[-1])
            except ValueError as e:
                return e
    
    def SV(self, velocity: int) -> str:
        """
        Sets the velocity of the steppermotor stage in milimeters per second.
        
        :param velocity: velocity to set [mm/s]
        :type velocity: int
        """
        self.ser.write(f"{self.cmdStart}SV {velocity}{self.cmdEnd}")
        returnLine = self.ser.readline().strip()
        if returnLine.split(":")[0] == "[ERROR]":
            return "[ERROR]"

    def GV(self) -> int | str:
        """
        Current velocity set in memory.
        
        :return: End velocity if moving, else current velocity [mm/s]
        :rtype: int
        """
        self.ser.write(f"{self.cmdStart}GV{self.cmdEnd}")
        returnLine = self.ser.readline().strip()
        if returnLine.split(":")[0] == "[ERROR]":
            return "[ERROR]"
        else:
            try:
                return int(returnLine.split(": ")[-1])
            except ValueError as e:
                return e
            
    def GM(self) -> str:
        """
        Returns the current selected mode, calibrated or raw.

        :return: string with selected mode
        :rtype: str
        """
        self.ser.write(f"{self.cmdStart}GV{self.cmdEnd}")
        returnLine = self.ser.readline().strip()
        if returnLine.split(":")[0] == "[ERROR]":
            return "[ERROR]"
        else:
            try:
                return returnLine.split(" ")[-1]
            except ValueError as e:
                return e
        

    def TM(self) -> None | str:
        """
        Toggles between the two modes, calibrated or raw.
        """
        self.ser.write(f"{self.cmdStart}TM{self.cmdEnd}")
        returnLine = self.ser.readline().strip()
        if returnLine.split(":")[0] == "[ERROR]":
            return "[ERROR]"
        
    def SR(self) -> float | str:
        """
        Reads the force a single time.

        :return: read force
        :rtype: float
        """
        self.ser.write(f"{self.cmdStart}SR{self.cmdEnd}")
        returnLine = self.ser.readline().strip()
        if returnLine.split(":")[0] == "[ERROR]":
            return "[ERROR]"

    def CR(self, nReads: int, iReads: int) -> list[float] | str:
        """
        Continuous reading of the force.
        
        :param nReads: number of lines to read
        :type nReads: int
        :param iReads: interval inbetween lines [ms]
        :type iReads: int

        :return: [time, force]
        :rtype: list[int, float]
        """
        self.ser.write(f"{self.cmdStart}CR {nReads},{iReads}{self.cmdEnd}")
        returnLine = self.ser.readline().strip()
        if returnLine.split(":")[0] == "[ERROR]":
            return "[ERROR]"

    def HM(self) -> None | str:
        self.ser.write(f"{self.cmdStart}HM{self.cmdEnd}")
        returnLine = self.ser.readline().strip()
        if returnLine.split(":")[0] == "[ERROR]":
            return "[ERROR]"

    def TR(self) -> None | str:
        """
        Tares load cell values by setting current reading as offset.
        """
        self.ser.write(f"{self.cmdStart}TR{self.cmdEnd}")
        returnLine = self.ser.readline().strip()
        if returnLine.split(":")[0] == "[ERROR]":
            return "[ERROR]"

    def CL(self) -> None | str:
        self.ser.write(f"{self.cmdStart}TM{self.cmdEnd}")
        returnLine = self.ser.readline().strip()
        if returnLine.split(":")[0] == "[ERROR]":
            return "[ERROR]"

    def SF(self, calibrationForce: float) -> None | str:
        self.ser.write(f"{self.cmdStart}SV {calibrationForce}{self.cmdEnd}")
        returnLine = self.ser.readline().strip()
        if returnLine.split(":")[0] == "[ERROR]":
            return "[ERROR]"
        

    def SC(self) -> None | str:
        self.ser.write(f"{self.cmdStart}TM{self.cmdEnd}")
        returnLine = self.ser.readline().strip()
        if returnLine.split(":")[0] == "[ERROR]":
            return "[ERROR]"

    