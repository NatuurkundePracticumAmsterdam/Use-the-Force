class Logging():
    def __init__(self, filename: str = '', NeverCloseFile: bool = False, extension: str = ".csv") -> None:
        """
        Class to log the data from the force sensor

        Allows for multiple measurements to be taken with the files increasing the `_i` identifier.
        """
        self.filename: str = filename
        self.full_filename: str = str
        self.HAND = 0
        self.NeverCloseFile: bool = NeverCloseFile
        self.extension: str = extension

    def createLog(self, ext='.csv') -> None:
        """
        Creates a new file for logging.
        """

        # Check for a file that does not exist yet.
        i = 0
        self.full_filename = "DATA/" + self.filename + "_" + str(i) + ext
        while True:
            try:
                f = open(self.full_filename, 'r')
                f.close()
                i += 1
                self.full_filename = "DATA/" + \
                    self.filename + "_" + str(i) + ext
            except:
                break

        # Create this file.
        self.HAND = open(self.full_filename, 'w+')

        if not self.NeverCloseFile:
            self.HAND.close()


    def createLogGUI(self, ext='.csv') -> None:
        """
        Creates a new file for logging, GUI variant.
        """

        # Check for a file that does not exist yet.
        self.full_filename = self.filename

        # Create this file.
        self.HAND = open(self.full_filename, 'w+')
        self.HAND.close()
        if self.NeverCloseFile:
            self.HAND = open(self.full_filename, 'a+')


    def replaceFile(self, data):
        self.HAND = open(self.full_filename, "w+t")
        self.NeverCloseFile = True
        self.writeLogFull(data=data)
        self.NeverCloseFile = False
        self.HAND.close()


    ### ===LOGGING FUNCTION===###
    # Puts the values in the given list into the opened log file.
    def writeLog(self, data) -> None:

        # Open file
        if not self.NeverCloseFile:
            self.HAND = open(self.full_filename, 'a+')

        # Write data
        for i, d in enumerate(data):
            if i == 0:
                txt = str(d)
            else:
                txt = str(round(d, 8))
                self.HAND.write(',')
                
            self.HAND.write(txt)
        self.HAND.write("\n")

        # Close file
        if not self.NeverCloseFile:
            self.HAND.close()
        
    def writeLogFull(self, data) -> None:

        # Open file
        if not self.NeverCloseFile:
            self.HAND = open(self.full_filename, 'a+')

        # Write data
        for d, F in zip(data[0], data[1]):
            self.HAND.write(str(round(d, 8))+","+str(round(F, 8))+"\n")
        # Close file
        if not self.NeverCloseFile:
            self.HAND.close()

    ### ===READ LOG===###

    def readLog(self, *, filename: str | None = None) -> list[list[float], list[float]]:
        if filename == None:
            filename = self.filename
        
        if self.NeverCloseFile and filename != None:
            file = self.HAND
        else:
            file = open(filename, "r")

        data = [[],[]]
        for line in file:
            t, F = line.strip().split(",")
            data[0].append(float(t))
            data[1].append(float(F))

        file.close()
        return data



    
    ### ===MANUAL CLOSING FUNCTION===###
    # Closes file, irregardless of whether 'NeverCloseFile' is True.

    def closeFile(self) -> None:
        if self.NeverCloseFile:
            self.HAND.close()
        else:
            pass  # file should be closed already
