import sys
from time import perf_counter_ns, sleep
from PySide6 import QtWidgets
from PySide6.QtCore import Signal, QTimer, QObject, QRunnable, QThreadPool, Signal, Slot
from PySide6.QtGui import QCloseEvent
import pyqtgraph as pg
import threading
import bisect
import serial
import re
from serial.tools import list_ports # type: ignore
from .main_ui import Ui_MainWindow
from .error_ui import Ui_errorWindow

from ..logging import Logging


class UserInterface(QtWidgets.QMainWindow):
    def __init__(self):
        # roep de __init__() aan van de parent class
        super().__init__()

        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        # disable MDM until switched
        self.ui.MDM.setVisible(False)
        self.ui.MDM.setEnabled(False)
        # new variable for use later


        ###############
        # CONNECTIONS #
        ###############
        # Buttons
        self.ui.butConnect.pressed.connect(self.butConnect)
        self.ui.butFile.pressed.connect(self.butFile)
        self.ui.butReGauge.pressed.connect(self.butTare)
        self.ui.butRecord.pressed.connect(self.butRecord)
        self.ui.butClear.pressed.connect(self.butClear)
        self.ui.butSave.pressed.connect(self.butSave)
        self.ui.butFileGraphImport.pressed.connect(self.butFileGraph)
        self.ui.butSingleRead.pressed.connect(self.butSingleRead)
        self.ui.butSwitchManual.pressed.connect(self.butSwitchMDM)
        self.ui.butFileMDM.pressed.connect(self.butFileMDM)
        self.ui.butReadForceMDM.pressed.connect(self.readForceMDM)
        self.ui.butSwitchDirectionMDM.pressed.connect(self.switchDirectionMDM)
        self.ui.butDeletePreviousMDM.pressed.connect(self.butDeletePreviousMDM)
        self.ui.butMove.pressed.connect(self.butMove)
        self.ui.butUpdateVelocity.pressed.connect(self.butUpdateVelocity)
        self.ui.butHome.pressed.connect(self.butHome)
        self.ui.butForceStop.pressed.connect(self.butForceStop)

        # Text boxes
        self.ui.setNewtonPerCount.valueChanged.connect(self.setNewtonPerCount)
        self.ui.setPlotTimerInterval.textEdited.connect(
            self.updatePlotTimerInterval)
        self.ui.setLineReadsMDM.valueChanged.connect(
            self.singleReadLinesForcesUpdate)
        self.ui.setLineSkipsMDM.valueChanged.connect(
            self.singleReadSkipsUpdate)
        self.ui.setStepSizeMDM.valueChanged.connect(self.singleReadStepUpdate)
        self.ui.title_2.textChanged.connect(self.updatePlotMDMTitle)
        

        ###############
        # Check Ports #
        ###############
        ports = [port.device for port in list_ports.comports()]
        if len(ports) > 0:
            self.ui.setPortName.setText(ports[0])
        else:
            self.ui.setPortName.setText("No ports found")
        del ports

        ###################
        # INITIALIZE VARS #
        ###################
        self.measurementLog = None
        self.butConnectToggle: bool = False
        self.threadReachedEnd = False
        self.recording: bool = False
        self.fileGraphOpen: bool = False
        self.fileOpen: bool = False
        self.fileMDMOpen: bool = False
        self.readForceMDMToggle: bool = False
        self.switchDirectionMDMToggle: bool = False
        self.MDMActive: bool = False
        self.singleReadToggle: bool = False
        self.singleReadForce: float = float()
        self.singleReadForces: int = 10
        self.singleReadSkips: int = 10
        self.stepSizeMDM: float = 0.05
        self.txtLogMDM: str = str()
        self.reMDMMatch = re.compile(r"\[[A-Za-z0-9]+\]")
        self.data = [[], []]
        self.ui.errorMessage = []

        ###################
        # INITIALIZE PLOT #
        ###################
        self.plot(clrBg="default")
        self.plotMDM()

        # Plot timer interval in ms
        self.plotTimerInterval: int = 100

        ##################
        # MULTITHREADING #
        ##################
        self.sensor = ForceSensorGUI(ui=self.ui)
        self.sensor.errorSignal.connect(self.error)

        self.plotTimer = QTimer()
        self.plotTimer.timeout.connect(self.updatePlot)

        self.mainLogWorker = mainLogWorker(self)
        self.mainLogWorker.startSignal.connect(self.startPlotTimer)
        self.mainLogWorker.endSignal.connect(self.stopPlotTimer)

        self.saveToLog = saveToLog(self)
        self.saveToLog.startSignal.connect(self.startPlotTimer)
        self.saveToLog.endSignal.connect(self.stopPlotTimer)

        self.singleReadWorker = singleReadWorker(self)
        # self.singleReadWorker.startSignal.connect()
        self.singleReadWorker.endSignal.connect(self.singleReadEnd)

        self.thread_pool = QThreadPool.globalInstance()

        ############################
        # CHANGE IN NEXT UI UPDATE #
        ############################
        # TODO: add screen for movement options and movement cycles.
        self.ui.butMove.setEnabled(False)
        self.ui.butUpdateVelocity.setEnabled(False)
        self.ui.butHome.setCheckable(False)
        self.ui.setVelocity.setValue(100)
        self.ui.setNewtonPerCount.setValue(1.)

    def closeEvent(self, event: QCloseEvent) -> None:
        """
        Safely closes the program and ends certain threads

        Some threads can be set to run infinitly, but will now be closed
        """
        if self.recording:
            self.recording = False
        if self.ui.butConnect.isChecked():
            self.butConnect()

    def plot(self, **kwargs) -> None:
        """
        Plots the data on the central plot.

        :param data: list containing both x-axes and y-axes as `[x,y]`
        :type data: list[list, list]

        :param label1loc: location of first label, default: `"left"`
        :type label1loc: str
        :param label1txt: text of first label
        :type label1txt: str
        :param label2loc: location of second label, default: `"bottom"`
        :type label2loc: str
        :param label2txt: text of second label
        :type label2txt: str

        :param color: line color, default: `"r"`
        :type color: str
        :param linewidth: linewidth, default: `5`
        :type linewidth: int

        :param clrBg: color of the background, default: `"w"`
        :type clrBg: str
        :param clrFg: color of the foreground, default: `"k"`
        :type clrFg: str
        """

        pg.setConfigOption("foreground", kwargs.pop("clrFg", "k"))
        pg.setConfigOption("background", kwargs.pop("clrBg", "w"))
        # self.ui.graphMDM.setBackground(background=kwargs.pop("clrBg", "w"))
        self.ui.graph1.plot(
            *self.data,
            symbol=kwargs.pop("symbol", None),
            pen={
                "color": kwargs.pop("color", "r"),
                "width": kwargs.pop("linewidth", 5)
            }
        )

        self.updatePlotLabel(
            graph=self.ui.graph1,
            labelLoc=kwargs.pop("label1loc", "left"),
            labelTxt=kwargs.pop("label1txt", self.ui.yLabel.text())
        )

        self.updatePlotLabel(
            graph=self.ui.graph1,
            labelLoc=kwargs.pop("label2loc", "bottom"),
            labelTxt=kwargs.pop("label2txt", self.ui.xLabel.text())
        )

        self.ui.yLabel.textChanged.connect(self.updatePlotYLabel)
        self.ui.xLabel.textChanged.connect(self.updatePlotXLabel)

        self.ui.xLimSlider.sliderMoved.connect(self.xLimSlider)
        self.ui.xLimSet.textChanged.connect(self.xLimSet)

        self.ui.graph1.setTitle(self.ui.title.text(), color=(255,255,255))
        self.ui.title.textChanged.connect(self.updatePlotTitle)

    def updatePlot(self) -> None:
        """
        Updates the plot
        """
        self.ui.graph1.plot(
            *self.data,
        )

        if len(self.data[0]) > 0:
            self.ui.xLimSlider.setMinimum(-1*(int(self.data[0][-1])+1))
            try:
                self.xLim = float(self.ui.xLimSet.text())
                if -1*self.xLim < self.data[0][-1] and (self.xLim != float(0)):
                    self.ui.graph1.setXRange(
                        self.data[0][-1]+self.xLim, self.data[0][-1])
                    i = bisect.bisect_left(
                        self.data[0], self.data[0][-1]+self.xLim)
                    self.ui.graph1.setYRange(
                        min(self.data[1][i:]), max(self.data[1][i:]))

                elif self.xLim == float(0):
                    self.ui.graph1.setXRange(0, self.data[0][-1])
                    self.ui.graph1.setYRange(
                        min(self.data[1]), max(self.data[1]))

            except:
                self.ui.graph1.setXRange(0, self.data[0][-1])
                self.ui.graph1.setYRange(min(self.data[1]), max(self.data[1]))

    def updatePlotLabel(self, graph, labelLoc: str, labelTxt: str) -> None:
        """
        Updates the label

        :param graph: what graph to update
        :type PlotWidget:
        :param labelLoc: label location
        :type labelLoc: str
        :param labelTxt: label text
        :type labelTxt: str
        """
        graph.setLabel(
            labelLoc,
            labelTxt
        )

    def updatePlotYLabel(self) -> None:
        self.updatePlotLabel(graph=self.ui.graph1,
                             labelLoc="left", labelTxt=self.ui.yLabel.text())

    def updatePlotXLabel(self) -> None:
        self.updatePlotLabel(graph=self.ui.graph1,
                             labelLoc="bottom", labelTxt=self.ui.xLabel.text())

    def updatePlotTimerInterval(self) -> None:
        tmp = self.ui.setPlotTimerInterval.text()
        try:
            tmp = int(tmp)
            if tmp > 0:
                self.plotTimerInterval = tmp
                if hasattr(self, "plotTimer"):
                    self.plotTimer.setInterval(self.plotTimerInterval)

        except:
            pass

        del tmp

    def updatePlotTitle(self) -> None:
        self.ui.graph1.setTitle(self.ui.title.text(), color=(255,255,255))

    def startPlotTimer(self):
        """
        Start the QTimer in the main thread when the signal is emitted.
        """
        self.plotTimer.start()

    def stopPlotTimer(self):
        """
        Stop the QTimer
        """
        self.plotTimer.stop()

    def butConnect(self) -> None:
        """
        Function defining what to do when a button is pressed.

        - checks if butConnect isChecked()
        - Starts a thread to connect/ disconnect the sensor
        - Thread ends with re-enabling the button
        """
        # Gets enabled again at the end of the thread
        self.ui.butConnect.setEnabled(False)

        if self.butConnectToggle:
            self.butConnectToggle = False

            self.startsensorDisonnect = threading.Thread(
                target=self.sensorDisconnect)
            self.startsensorDisonnect.start()
            self.ui.setPortName.setEnabled(True)

        else:
            devices: list[str] = [port.device for port in list_ports.comports()]
            if self.ui.setPortName.text().upper() in devices:
                self.butConnectToggle = True
                self.ui.butFile.setEnabled(False)
                self.startsensorConnect = threading.Thread(
                    target=self.sensorConnect)
                self.startsensorConnect.start()
            else:
                if len(devices) > 0:
                    self.error(
                        ["Port not found", f"Port: {self.ui.setPortName.text().upper()} was not detected!", "Available ports:\n" + '\n'.join([port.device for port in list_ports.comports()])])
                else:
                    self.error(["Port not found", f"Port: {self.ui.setPortName.text().upper()} was not detected!", "Available ports:\nNo ports found!"])
                self.ui.butConnect.setText("Connect")
                self.ui.butConnect.setEnabled(True)
            del devices

    def sensorConnect(self) -> None:
        """
        Script to connect to the M5Din Meter

        If connection fails, will raise an error dialog with the error.
        """
        self.ui.butConnect.setText("Connecting...")
        self.sensor()
        # needs time or it will break
        # something to do with the M5Stick probably
        sleep(0.5)
        if self.sensor.SR() == 0.:
            self.sensor.ClosePort()
            self.ui.butConnect.setText("Connect")
            self.butConnectToggle = False
            self.ui.butConnect.setEnabled(True)
            return
        self.ui.butReGauge.setEnabled(True)
        self.ui.butConnect.setText("Connected")
        self.ui.butSingleRead.setEnabled(True)
        self.ui.butConnect.setChecked(True)
        self.ui.setPortName.setEnabled(False)
        if not self.MDMActive:
            self.ui.butRecord.setEnabled(True)
            if not self.fileOpen:
                self.butClear()
            self.ui.butFile.setEnabled(True)
        else:
            if self.fileMDMOpen:
                self.ui.butReadForceMDM.setEnabled(True)
        self.ui.setNewtonPerCount.setEnabled(True)
        self.ui.setGaugeValue.setEnabled(True)
        self.ui.butHome.setEnabled(True)
        self.ui.butForceStop.setEnabled(True)
        self.ui.butUpdateVelocity.setEnabled(True)
        self.ui.butConnect.setEnabled(True)

    def sensorDisconnect(self) -> None:
        """
        Script to safely disconnect the M5Din Meter

        Will first stop the recording, if running, with `butRecord()` function.
        """
        if self.recording:
            self.butRecord()
        self.ui.butRecord.setEnabled(False)
        self.ui.butReGauge.setEnabled(False)
        self.ui.butSingleRead.setEnabled(False)
        self.sensor.ClosePort()
        # Give some time to Windows/ M5Din Meter to fully disconnect
        sleep(0.5)
        self.ui.butConnect.setText("Connect")
        self.ui.butConnect.setEnabled(True)
        self.ui.butConnect.setChecked(False)
        self.ui.setNewtonPerCount.setEnabled(False)
        self.ui.setGaugeValue.setEnabled(False)
        del self.sensor

    @Slot(str, str, str)
    @Slot(str, str, None)
    def error(self) -> None:
        """
        Launches the error dialog.

        :param errorType: error type name, can be found with `Exception.__class__.__name__`
        :type errorType: str
        :param errorText: text why the error occured
        :type errorText: str
        """
        self.error_ui = ErrorInterface(*self.ui.errorMessage)
        self.error_ui.show()

    def butFile(self) -> None:
        """
        Function for what `butFile` has to do.

        What to do is based on if the button is in the `isChecked()` state. 
        - `if isChecked():` close file
        - `else:` opens dialog box to select/ create a .csv file
        """
        if self.fileOpen:
            self.fileOpen = False
            self.ui.butFile.setChecked(True)
            self.measurementLog.closeFile()
            del self.measurementLog
            self.ui.butFile.setText("-")
            self.butClear()
            self.ui.butFileGraphImport.setEnabled(True)
            self.ui.butFileGraphImport.setText("-")
            self.ui.butSwitchManual.setEnabled(True)

        else:
            self.fileOpen = True
            self.ui.butFile.setChecked(True)
            # if hasattr(self, 'filePath'):
            #     if self.filePath != "":
            #         self.oldFilepath = self.filePath
            self.filePath, _ = QtWidgets.QFileDialog.getSaveFileName(
                filter="CSV files (*.csv)")
            if self.filePath != "":
                self.measurementLog = Logging(self.filePath)
                self.measurementLog.createLogGUI()
                self.ui.butFile.setText(
                    *self.filePath.split("/")[-1].split(".")[:-1])
                self.ui.butFileGraphImport.setEnabled(False)
                self.ui.butFileGraphImport.setText(
                    f"Close File: {''.join(*self.filePath.split('/')[-1].split('.')[:-1])}")
                if len(self.data[0]) > 0:
                    self.ui.butSave.setEnabled(False)
                    self.thread_pool.start(self.saveToLog.run)
                self.ui.butSwitchManual.setEnabled(False)
            else:
                self.fileOpen = False
                self.ui.butFile.setText("-")
                self.ui.butFile.setChecked(False)

    def butFileGraph(self) -> None:
        """
        Function for what `butFileGraphImport` has to do.

        What to do is based on if the button is in the `isChecked()` state. 
        - `if isChecked():` close file and clear plot
        - `else:` opens dialog box to select a .csv file
        """
        if self.fileGraphOpen:
            self.fileGraphOpen = False
            self.ui.butFileGraphImport.setChecked(True)
            self.measurementLog.closeFile()
            del self.measurementLog
            self.ui.butFileGraphImport.setText("-")
            self.ui.butFile.setText("-")
            self.ui.butFile.setEnabled(True)
            if hasattr(self, "sensor"):
                self.ui.butRecord.setEnabled(True)
            self.ui.butClear.setEnabled(True)
            self.butClear()
            self.ui.butSwitchManual.setEnabled(True)

        else:
            self.fileGraphOpen = True
            self.ui.butSwitchManual.setEnabled(False)
            self.filePathGraph, _ = QtWidgets.QFileDialog.getOpenFileName(
                filter="CSV files (*.csv)")

            if self.filePathGraph != "":
                self.measurementLog = Logging(self.filePathGraph)
                self.ui.butFileGraphImport.setChecked(True)
                self.ui.butFileGraphImport.setText(
                    *self.filePathGraph.split("/")[-1].split(".")[:-1])
                self.ui.butFile.setText(
                    f"Close File: {''.join(*self.filePathGraph.split('/')[-1].split('.')[:-1])}")
                self.ui.butFile.setEnabled(False)
                self.ui.butRecord.setEnabled(False)
                self.ui.butClear.setEnabled(False)
                self.data = self.measurementLog.readLog()
                self.updatePlot()

            else:
                self.fileGraphOpen = False
                del self.filePathGraph
                self.ui.butFileGraphImport.setText("-")
                self.ui.butFileGraphImport.setChecked(False)

    def butRecord(self) -> None:
        """
        start button, disables/ enables most buttons and starts/ joins threads for the logging
        """
        if self.recording:
            self.recording = False
            self.ui.butRecord.setText("Start")
            self.ui.butRecord.setChecked(True)
            self.ui.butClear.setEnabled(True)
            self.ui.butFile.setEnabled(True)
            self.ui.butReGauge.setEnabled(True)
            self.ui.butSave.setEnabled(True)
            self.ui.butSingleRead.setEnabled(True)
            self.ui.butSwitchManual.setEnabled(True)
            # if not self.threadReachedEnd:
            #     if self.ui.butFile.text() != "-":
            #         self.startMainLog.join()
            #     else:
            #         self.startMainLogLess.join()

        else:
            self.recording = True
            self.threadReachedEnd = False
            self.ui.butRecord.setText("Stop")
            self.ui.butRecord.setChecked(True)
            self.ui.butClear.setEnabled(False)
            self.ui.butFile.setEnabled(False)
            self.ui.butReGauge.setEnabled(False)
            self.ui.butSave.setEnabled(False)
            self.ui.butSingleRead.setEnabled(False)
            self.ui.butFileGraphImport.setEnabled(False)
            self.ui.butSwitchManual.setEnabled(False)
            self.sensor.ser.reset_input_buffer()
            if self.ui.butFile.text() != "-":
                self.mainLogWorker.logLess = False
                self.thread_pool.start(self.mainLogWorker.run)

            else:
                self.mainLogWorker.logLess = True
                self.thread_pool.start(self.mainLogWorker.run)

    def butClear(self) -> None:
        """
        button that clears data in `self.data` and resets graph
        """
        del self.data
        self.data = [[], []]
        if self.MDMActive:
            self.graphMDM1.clear()
            self.graphMDM2.clear()
        else:
            self.ui.graph1.clear()
        if hasattr(self, "sensor"):
            self.sensor.ser.reset_input_buffer()
        self.ui.butSave.setEnabled(False)
        if not self.fileOpen:
            self.ui.butFileGraphImport.setEnabled(True)
        else:
            self.butFile()

    def butTare(self) -> None:
        """
        button for Taring values sent from the M5Din Meter

        starts a thread to count down, end of thread re-enables button
        """
        self.ui.butReGauge.setEnabled(False)
        self.ui.butConnect.setEnabled(False)
        self.ui.butRecord.setEnabled(False)
        self.ui.butSingleRead.setEnabled(False)
        th = threading.Thread(target=self.butTareActive)
        th.start()

    def butTareActive(self) -> None:
        """
        the actual Tare script
        """
        self.ui.butReGauge.setChecked(True)
        self.ui.butReGauge.setText("Taring in 3")
        sleep(1)
        self.ui.butReGauge.setText("Taring in 2")
        sleep(1)
        self.ui.butReGauge.setText("Taring in 1")
        sleep(1)
        self.ui.butReGauge.setText("...")
        self.sensor.reGauge()
        self.ui.butReGauge.setText("Tare")
        self.ui.butReGauge.setEnabled(True)
        self.ui.butConnect.setEnabled(True)
        if not self.MDMActive:
            self.ui.butRecord.setEnabled(True)
        self.ui.butReGauge.setChecked(False)
        self.ui.butSingleRead.setEnabled(True)

    def butSave(self) -> None:
        """
        Function for what `butSave` has to do.

        What to do is based on if `butFile` is in the `isChecked()` state. 
        - `if isChecked():` do nothing as it is already saved
        - `else:` open new file and write data
        """
        if self.ui.butFile.isChecked():
            # When a file is selected it will already
            # write to the file when it reads a line
            self.ui.butSave.setEnabled(False)

        else:
            self.butFile()
            # Cancelling file selecting gives a 0 length string
            if self.filePath != "":
                self.ui.butSave.setEnabled(False)
                self.thread_pool.start(self.saveToLog.run)

    def saveStart(self):
        self.ui.butSave.setText(f"Saving {len(self.data)}")

    def saveEnd(self):
        self.ui.butSave.setText("Save")
        self.butFile()

    def butSingleRead(self):
        self.singleReadToggle = True
        self.ui.butSingleRead.setEnabled(False)
        self.ui.butRecord.setEnabled(False)
        self.ui.butConnect.setEnabled(False)
        self.ui.butReGauge.setEnabled(False)
        self.thread_pool.start(self.singleReadWorker.run)

    def singleReadEnd(self):
        if self.MDMActive:
            self.ui.butSingleRead.setEnabled(True)
            if self.fileMDMOpen:
                self.ui.butReadForceMDM.setEnabled(True)
            if self.singleReadToggle:
                self.ui.butSingleRead.setText(
                    "{:.5f}".format(self.singleReadForce))
                self.singleReadToggle = False
            else:
                if self.readForceMDMToggle:
                    self.data[0].append(round(self.data[0][-1]+self.stepSizeMDM, len(str(self.stepSizeMDM).split(".")[-1])))
                    self.data[1].append(self.singleReadForce)

                    if re.search(self.reMDMMatch, self.ui.xLabel_2.text()) and  re.search(self.reMDMMatch, self.ui.yLabel_2.text()):
                        xUnit = self.ui.xLabel_2.text().split("[")[1].split("]")
                        yUnit = self.ui.yLabel_2.text().split("[")[1].split("]")
                        if len(xUnit) > 0 and len(yUnit) > 0:
                            self.txtLogMDM = self.txtLogMDM + f"\n{self.data[0][-1]} {xUnit[0]}, {self.data[1][-1]} {yUnit[0]}"
                    else:
                        self.txtLogMDM = self.txtLogMDM + f"\n{self.data[0][-1]}, {self.data[1][-1]}"
                    self.ui.plainTextEdit.setPlainText(self.txtLogMDM)
                    self.plainTextEditScrollbar = self.ui.plainTextEdit.verticalScrollBar()
                    self.plainTextEditScrollbar.setValue(self.plainTextEditScrollbar.maximum())
                else:
                    self.data[0].append(0.)
                    self.data[1].append(self.singleReadForce)
                    self.readForceMDMToggle = True
                    if re.search(self.reMDMMatch, self.ui.xLabel_2.text()) and  re.search(self.reMDMMatch, self.ui.yLabel_2.text()):
                        xUnit = self.ui.xLabel_2.text().split("[")[1].split("]")
                        yUnit = self.ui.yLabel_2.text().split("[")[1].split("]")
                        if len(xUnit) > 0 and len(yUnit) > 0:
                            self.txtLogMDM = self.txtLogMDM + f"{self.data[0][-1]} {xUnit[0]}, {self.data[1][-1]} {yUnit[0]}"
                    else:
                        self.txtLogMDM = self.txtLogMDM + f"{self.data[0][-1]}, {self.data[1][-1]}"
                    self.ui.plainTextEdit.setPlainText(self.txtLogMDM)
                    self.plainTextEditScrollbar = self.ui.plainTextEdit.verticalScrollBar()
                    self.plainTextEditScrollbar.setValue(self.plainTextEditScrollbar.maximum())
                self.ui.butSwitchDirectionMDM.setEnabled(True)

                self.measurementLog.writeLog([self.data[0][-1],self.data[1][-1]])
                self.updatePlotMDM()
                self.ui.butDeletePreviousMDM.setEnabled(True)
        else:
            self.ui.butSingleRead.setText(
                "{:.5f}".format(self.singleReadForce))
            self.ui.butSingleRead.setEnabled(True)
            self.ui.butRecord.setEnabled(True)
            self.singleReadToggle = False

        self.ui.butReGauge.setEnabled(True)
        self.ui.butConnect.setEnabled(True)

    def singleReadSkipsUpdate(self):
        try:
            self.singleReadSkips = int(self.ui.setLineSkipsMDM.text())
        except ValueError:
            pass

    def singleReadLinesForcesUpdate(self):
        try:
            self.singleReadForces = int(self.ui.setLineReadsMDM.text())
        except ValueError:
            pass

    def singleReadStepUpdate(self):
        try:
            self.stepSizeMDM = float(self.ui.setStepSizeMDM.text())
            if self.switchDirectionMDMToggle:
                self.stepSizeMDM = -1*self.stepSizeMDM
        except ValueError:
            pass

    def readForceMDM(self):        
        self.ui.butReadForceMDM.setEnabled(False)
        self.ui.butSwitchDirectionMDM.setEnabled(False)
        self.thread_pool.start(self.singleReadWorker.run)

    def switchDirectionMDM(self):
        self.measurementLog.closeFile()
        del self.measurementLog
        self.readForceMDMToggle = False
        self.ui.butDeletePreviousMDM.setEnabled(False)
        if self.switchDirectionMDMToggle:
            self.switchDirectionMDMToggle = False
            del self.txtLogMDM
            self.txtLogMDM = str()
            self.ui.plainTextEdit.clear()
            self.ui.butSwitchDirectionMDM.setText("Switch Direction")

            self.fileMDMOpen = False
            self.ui.butFileMDM.setChecked(False)
            self.ui.butFileMDM.setText("-")
            self.butClear()
            self.ui.butSwitchManual.setEnabled(True)
            self.ui.butConnect.setEnabled(True)
            self.ui.butReadForceMDM.setEnabled(False)
            self.ui.butSwitchDirectionMDM.setEnabled(False)
            
        else:
            self.switchDirectionMDMToggle = True
            self.ui.butSwitchDirectionMDM.setText("Stop")
            self.ui.butDeletePreviousMDM.setEnabled(False)

            self.measurementLog = Logging(
                "".join(self.filePath.split(".")[:-1])+"_out.csv")
            self.measurementLog.createLogGUI()

            self.stepSizeMDM = -1*self.stepSizeMDM
            if len(self.data[0]) > 0:
                self.switchForce: float = self.data[1][-1]
                self.switchDistance: float = self.data[0][-1]
                del self.data
            else:
                self.switchDistance = 0.
                self.switchForce = 0.

            self.data = [[self.switchDistance], [self.switchForce]]

            self.measurementLog.writeLog([self.data[0][-1],self.data[1][-1]])

            self.readForceMDMToggle = True
            del self.txtLogMDM
            self.txtLogMDM = str()
            if re.search(self.reMDMMatch, self.ui.xLabel_2.text()) and  re.search(self.reMDMMatch, self.ui.yLabel_2.text()):
                xUnit = self.ui.xLabel_2.text().split("[")[1].split("]")
                yUnit = self.ui.yLabel_2.text().split("[")[1].split("]")
                if len(xUnit) > 0 and len(yUnit) > 0:
                    self.txtLogMDM = self.txtLogMDM + f"{self.data[0][-1]} {xUnit[0]}, {self.data[1][-1]} {yUnit[0]}"
            else:
                self.txtLogMDM = self.txtLogMDM + f"{self.data[0][-1]}, {self.data[1][-1]}"
            self.ui.plainTextEdit.setPlainText(self.txtLogMDM)
            self.plainTextEditScrollbar = self.ui.plainTextEdit.verticalScrollBar()
            self.plainTextEditScrollbar.setValue(self.plainTextEditScrollbar.maximum())

    def butSwitchMDM(self):
        self.butClear()
        if self.MDMActive:
            self.MDMActive = False
            # visibility
            self.ui.centerGraph.setVisible(True)
            self.ui.MDM.setVisible(False)

            # main ui buttons
            self.ui.logOptions.setEnabled(True)
            self.ui.graphOptions.setEnabled(True)
            self.ui.butClear.setEnabled(True)
            if self.butConnectToggle:
                self.ui.butRecord.setEnabled(True)

            # MDM
            self.ui.MDM.setEnabled(False)

        else:
            self.MDMActive = True

            # visibility
            self.ui.centerGraph.setVisible(False)
            self.ui.MDM.setVisible(True)

            # main ui buttons
            self.ui.logOptions.setEnabled(False)
            self.ui.graphOptions.setEnabled(False)
            self.ui.butSave.setEnabled(False)
            self.ui.butClear.setEnabled(False)
            self.ui.butRecord.setEnabled(False)

            # MDM
            self.ui.MDM.setEnabled(True)

    def plotMDM(self, **kwargs):
        pg.setConfigOption("foreground", kwargs.pop("clrFg", "k"))
        pg.setConfigOption("background", kwargs.pop("clrBg", "w"))
        # self.ui.graphMDM.setBackground(background=kwargs.pop("clrBg", "w"))
        self.graphMDM1 = self.ui.graphMDM.plot(
            *self.data,
            name=kwargs.pop("nameIn","Approach"),
            symbol=kwargs.pop("symbolIn", None),
            pen=pg.mkPen({
                "color": kwargs.pop("colorIn", (0,0,255)),
                "width": kwargs.pop("linewidthIn", 5)
            })
        )
        self.graphMDM2 = self.ui.graphMDM.plot(
            *self.data,
            name=kwargs.pop("nameOut","Retraction"),
            symbol=kwargs.pop("symbolOut", None),
            pen=pg.mkPen({
                "color": kwargs.pop("colorOut", (255,127,0)),
                "width": kwargs.pop("linewidthOut", 5)
            })
        )
        self.ui.graphMDM.setLabel(
            kwargs.pop("labelyloc", "left"),
            kwargs.pop("labelytxt", self.ui.yLabel_2.text())
        )
        self.ui.graphMDM.setLabel(
            kwargs.pop("labelxloc", "bottom"),
            kwargs.pop("labelxtxt", self.ui.xLabel_2.text())
        )

        self.graphMDMLegend = self.ui.graphMDM.addLegend(offset=(1,1), labelTextColor=(255,255,255))
        self.graphMDMLegend.addItem(self.graphMDM1, name=self.graphMDM1.name())
        self.graphMDMLegend.addItem(self.graphMDM2, name=self.graphMDM2.name())

        self.ui.graphMDM.setTitle(self.ui.title_2.text(), color=(255,255,255))

        self.ui.yLabel_2.textChanged.connect(self.updatePlotMDMYLabel)
        self.ui.xLabel_2.textChanged.connect(self.updatePlotMDMXLabel)

    def updatePlotMDMTitle(self) -> None:
        self.ui.graphMDM.setTitle(self.ui.title_2.text(), color=(255,255,255))

    def updatePlotMDMYLabel(self) -> None:
        self.updatePlotLabel(graph=self.ui.graphMDM,
                             labelLoc="left", labelTxt=self.ui.yLabel_2.text())

    def updatePlotMDMXLabel(self) -> None:
        self.updatePlotLabel(graph=self.ui.graphMDM,
                             labelLoc="bottom", labelTxt=self.ui.xLabel_2.text())

    def updatePlotMDM(self) -> None:
        if self.switchDirectionMDMToggle:
            self.graphMDM2.setData(*self.data)
        else:
            self.graphMDM1.setData(*self.data)

    def butFileMDM(self) -> None:
        """
        Function for what `butFileMDM` has to do.

        - `if fileMDMOpen:` close file
        - `else:` opens dialog box to select/ create a .csv file
        """
        if self.fileMDMOpen:
            if not self.switchDirectionMDMToggle:
                self.switchDirectionMDM()
            else:
                self.ui.butDeletePreviousMDM.setEnabled(False)
            self.switchDirectionMDMToggle = False
            del self.txtLogMDM
            self.txtLogMDM = str()
            self.ui.plainTextEdit.clear()
            self.ui.butSwitchDirectionMDM.setText("Switch Direction")
            self.readForceMDMToggle = False

            self.fileMDMOpen = False
            self.ui.butFileMDM.setChecked(False)
            del self.measurementLog
            self.ui.butFileMDM.setText("-")
            self.butClear()
            self.ui.butSwitchManual.setEnabled(True)
            self.ui.butConnect.setEnabled(True)
            self.ui.butReadForceMDM.setEnabled(False)
            self.ui.butSwitchDirectionMDM.setEnabled(False)

        else:
            self.filePath, _ = QtWidgets.QFileDialog.getSaveFileName(
                filter="CSV files (*.csv)")
            if self.filePath != "":
                self.fileMDMOpen = True
                self.ui.butFileMDM.setChecked(True)
                self.measurementLog = Logging(
                    "".join(self.filePath.split(".")[:-1])+"_in.csv")
                self.measurementLog.createLogGUI()
                self.ui.butFileMDM.setText(
                    *self.filePath.split("/")[-1].split(".")[:-1])
                self.ui.butSwitchManual.setEnabled(False)
                if self.butConnectToggle:
                    self.ui.butReadForceMDM.setEnabled(True)
            else:
                self.ui.butFileMDM.setText("-")

    def butDeletePreviousMDM(self) -> None:
        """
        Deletes the previous value in self.data

        main use for when MDM hits other side in capillary bridge experiment, or when the capillary bridge gets broken without being noticed
        """
        # data changes
        self.data[0], self.data[1] = self.data[0][:-1], self.data[1][:-1]

        if len(self.data[0]) <= 1 and self.switchDirectionMDMToggle:
            self.ui.butDeletePreviousMDM.setEnabled(False)
            self.ui.butSwitchDirectionMDM.setEnabled(False)
        elif len(self.data[0]) <= 0:
            self.readForceMDMToggle = False
            self.ui.butDeletePreviousMDM.setEnabled(False)
            self.ui.butSwitchDirectionMDM.setEnabled(False)
        self.measurementLog.replaceFile(data=self.data)

        # text box changes
        self.txtLogMDM = str("\n").join(self.txtLogMDM.split("\n")[:-1])
        self.ui.plainTextEdit.setPlainText(self.txtLogMDM)
        self.plainTextEditScrollbar = self.ui.plainTextEdit.verticalScrollBar()
        self.plainTextEditScrollbar.setValue(self.plainTextEditScrollbar.maximum())

        self.updatePlotMDM()

    def xLimSlider(self) -> None:
        """
        Changes lineEdit text based on slider position
        """
        self.ui.xLimSet.setText(str(self.ui.xLimSlider.value()))

    def xLimSet(self) -> None:
        """
        Changes slider position
        """
        try:
            val = int(self.ui.xLimSet.text())
            if not val > 0:
                self.ui.xLimSlider.setValue(val)
            elif val < self.ui.xLimSlider.minimum():
                self.ui.xLimSlider.setValue(self.ui.xLimSlider.minimum())
            else:
                self.ui.xLimSlider.setValue(0)
        except:
            pass

    def setNewtonPerCount(self):
        """
        Changes the value of NewtonPerCount when textbox is changed

        Allows for changing the value while still getting live data
        """
        try:
            self.sensor.NewtonPerCount = float(self.ui.setNewtonPerCount.value())
        except:
            pass

    def butMove(self):
        self.sensor.SP(self.ui.setPosition.value())
    
    def butUpdateVelocity(self):
        self.sensor.SV(self.ui.setVelocity.value())

    def butHome(self):
        self.butUpdateVelocity()
        self.sensor.HM()
        self.ui.butMove.setEnabled(True)

    def butForceStop(self):
        self.sensor.ST()
        self.ui.butHome.setEnabled(True)
        self.ui.butMove.setEnabled(False)


class mainLogWorker(QObject, QRunnable):
    startSignal = Signal()
    endSignal = Signal()
    errorSignal = Signal()

    def __init__(self, callerSelf: UserInterface):
        super().__init__()
        self.callerSelf = callerSelf
        self.logLess = bool()

    def run(self):
        if not self.logLess:
            self.callerSelf.data = self.callerSelf.measurementLog.readLog(
                filename=self.callerSelf.filePath)

        # a time of `-1` will be seen as infinit and function will keep reading
        if float(self.callerSelf.ui.setTime.value()) >= 0. and float(self.callerSelf.ui.setTime.value()) != -1.:
            measurementTime = float(self.callerSelf.ui.setTime.text())
        else:
            measurementTime = -1
            self.callerSelf.ui.setTime.setValue(-1.)

        self.startSignal.emit()

        if len(self.callerSelf.data[0]) == 0:
            time: float = 0.
            self.callerSelf.sensor.T0 = perf_counter_ns()
        else:
            time: float = self.callerSelf.data[0][-1]
            self.callerSelf.sensor.T0 = perf_counter_ns() - int(time*1e9+0.5)
        while (time < measurementTime or measurementTime == -1) and self.callerSelf.recording:
            try:
                Force = self.callerSelf.sensor.ForceFix(self.callerSelf.sensor.SR())
                time = perf_counter_ns() - self.callerSelf.sensor.T0
                time = round(time/1e9, 8)
                self.callerSelf.data[0].append(time)
                self.callerSelf.data[1].append(Force)

                if not self.logLess:
                    # logs: t[s], F[mN]
                    self.callerSelf.measurementLog.writeLog([time, Force])

            except ValueError:
                # I know this isn't the best way to deal with it, but it works fine (for now)
                pass

        self.endSignal.emit()

        if self.callerSelf.recording:
            self.callerSelf.threadReachedEnd = True
            self.callerSelf.butRecord()

        if self.logLess:
            # self.callerSelf.unsavedData = self.callerSelf.data
            if not self.callerSelf.ui.butSave.isEnabled():
                self.callerSelf.ui.butSave.setEnabled(True)


class saveToLog(QObject, QRunnable):
    startSignal = Signal()
    endSignal = Signal()

    def __init__(self, callerSelf: UserInterface) -> None:
        super().__init__()
        self.callerSelf: UserInterface = callerSelf

    def run(self) -> None:
        self.startSignal.emit()
        self.callerSelf.measurementLog.writeLogFull(self.callerSelf.data)
        self.endSignal.emit()


class singleReadWorker(QObject, QRunnable):
    startSignal = Signal()
    endSignal = Signal()

    def __init__(self, callerSelf: UserInterface):
        super().__init__()
        self.callerSelf = callerSelf

    def run(self):
        self.startSignal.emit()
        _skip = [self.callerSelf.sensor.ForceFix(self.callerSelf.sensor.SR())
                 for i in range(0, self.callerSelf.singleReadSkips)]
        forces = [self.callerSelf.sensor.ForceFix(self.callerSelf.sensor.SR()) for i in range(0, self.callerSelf.singleReadForces)]
        self.callerSelf.singleReadForce = round(sum(
            forces)/self.callerSelf.singleReadForces,8)
        self.endSignal.emit()


class ForceSensorGUI(QObject, QRunnable):
    errorSignal = Signal()

    def __init__(self, ui) -> None:
        super().__init__()
        self.ui = ui

    def __call__(self, **kwargs) -> None:
        """
        Opens up the serial port, checks the gauge value and makes sure data is available.

        (PySerial library has to be installed on the computer)
        """
        ####### SOME PARAMETERS AND STUFF ######
        self.GaugeValue: float = float(self.ui.setGaugeValue.value())
        self.NewtonPerCount: float = float(self.ui.setNewtonPerCount.value())

        self.encoding: str = kwargs.pop('encoding', "UTF-8")

        self.baudrate: int = kwargs.pop('baudrate', 115200)
        self.timeout: float = kwargs.pop('timeout', 5.)

        self.gaugeRound: int = kwargs.pop("gaugeLines",6)
        self.gaugeLines: int = kwargs.pop("gaugeLines",10)
        self.gaugeSkipLines: int = kwargs.pop("gaugeSkipLines", 3)
        self.cmdStart: str = kwargs.pop("cmdStart", "#")
        self.cmdEnd: str = kwargs.pop("cmdEnd", ";")

        self.T0 = perf_counter_ns()

        self.PortName: str = self.ui.setPortName.text().upper()

        ####### PORT INIT ######
        # The 'COM'-port depends on which plug is used at the back of the computer.
        # To find the correct port: go to Windows Settings, Search for Device Manager,
        # and click the tab "Ports (COM&LPT)".
        self.ser = serial.Serial(self.PortName,
                                 baudrate=self.baudrate,
                                 timeout=self.timeout
                                 )

    def reGauge(self):
        """
        # !!!IT'S IMPORTANT NOT TO HAVE ANY FORCE ON THE SENSOR WHEN CALLING THIS FUNCTION!!!
        """
        skips: list[float] = [self.SR()
                              for i in range(self.gaugeSkipLines)]
        del skips
        reads: list[float] = [self.SR()
                              for i in range(self.gaugeLines)]
        self.GaugeValue = round(sum(reads)/self.gaugeLines, self.gaugeRound)
        self.ui.setGaugeValue.setValue(self.GaugeValue)

    def GetReading(self) -> list[int | float]:
        """
        # DEPRICATED: use `SR()` instead.
        Reads a line of the M5Din Meter

        :returns: singular read line as [ID, Force]
        :rtype: list[int, float]
        """
        # 'readline()' gives a value from the serial connection in 'bytes'
        # 'decode()'   turns 'bytes' into a 'string'
        # 'float()'    turns 'string' into a floating point number.
        while True:
            try:
                line: str = self.ser.readline().decode(self.encoding)
                self.ser.reset_input_buffer()
                ID, force = line.strip().split(",")
                return [float(perf_counter_ns()-self.T0), float(force)]
            except ValueError:
                pass

    def ForceFix(self, x: float) -> float:
        """
        Calculates the force based on `self.GaugeValue` and self.`NewtonPerCount`

        :param x: input value/ measured count
        :type x: float
        :returns: calculated force
        :rtype: float
        """
        # The output, with gauge, in mN
        return (x - self.GaugeValue) * self.NewtonPerCount

    def ClosePort(self) -> None:
        """
        Always close after use.
        """
        self.ser.close()

    def SR(self) -> float:
        """
        ### Single Read
        Reads the force a single time.

        :return: read force
        :rtype: float
        """
        self.ser.reset_input_buffer()
        self.ser.write(f"{self.cmdStart}SR{self.cmdEnd}".encode())
        # if self.stdDelay > 0:
        #     sleep(self.stdDelay)
        returnLine = self.ser.read_until().decode().strip()
        if returnLine.split(":")[0] == "[ERROR]":
            self.ui.errorMessage = ["RuntimeError", "RuntimeError", returnLine]
            self.errorSignal.emit()
        else:
            try:
                return float(returnLine.split(": ")[-1])
            except Exception as e:
                self.ui.errorMessage = [e.__class__.__name__, e.args[0]]
                self.errorSignal.emit()
                return 0.

        
    def ST(self) -> None:
        """
        ### Stops the Motor

        Stops the motor by simulating too much force. Needs to home after being called.
        """
        self.ser.flush()
        self.ser.write(f"{self.cmdStart}ST{self.cmdEnd}".encode())
        # if self.stdDelay > 0:
        #     sleep(self.stdDelay)
        returnLine: str = self.ser.read_until().decode().strip()
        if not(returnLine.split(":")[0] == "[ERROR]" and returnLine.split(":")[1]==" movement aborted, home to unlock"):
            self.ui.errorMessage = ["RuntimeError", "RuntimeError", returnLine]
            self.errorSignal.emit()
        returnLine: str = self.ser.read_until().decode().strip()
        if returnLine.split(":")[0] == "[ERROR]":
            self.ui.errorMessage = ["RuntimeError", "RuntimeError", returnLine]
            self.errorSignal.emit()

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
        # if self.stdDelay > 0:
        #     sleep(self.stdDelay)
        returnLine = self.ser.read_until().decode().strip()
        if returnLine.split(":")[0] == "[ERROR]":
            self.ui.errorMessage = ["RuntimeError", "RuntimeError", returnLine]
            self.errorSignal.emit()

    def SV(self, velocity: int) -> None:
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
        # if self.stdDelay > 0:
        #     sleep(self.stdDelay)
        returnLine = self.ser.read_until().decode().strip()
        if returnLine.split(":")[0] == "[ERROR]":
            self.errorMessage = ["RuntimeError", "RuntimeError", returnLine]
            self.errorSignal.emit()

    def HM(self) -> None:
        """
        ### Home
        Homes the steppermotor stage to the endstop.\\
        The endstop is a physical switch that stops the motor when it is pressed. (This is position 0)\\
        Afterwards goes up to a set position inside the firmware.
        """
        self.ser.flush()
        self.ser.write(f"{self.cmdStart}HM{self.cmdEnd}".encode())
        # if self.stdDelay > 0:
        #     sleep(self.stdDelay)
        returnLine: str = self.ser.read_until().decode().strip()
        if returnLine.split(":")[0] == "[ERROR]":
            self.errorMessage = ["RuntimeError", "RuntimeError", returnLine]
            self.errorSignal.emit()


class ErrorInterface(QtWidgets.QDialog):
    def __init__(self, errorType: str, errorText: str, additionalInfo: str | None = None) -> None:
        # roep de __init__() aan van de parent class
        super().__init__()

        self.ui = Ui_errorWindow()
        self.ui.setupUi(self)
        self.setWindowTitle(errorType)
        if additionalInfo is not None:
            self.ui.ErrorText.setText(f"{errorText}\n\n{additionalInfo}")
        else:
            self.ui.ErrorText.setText(errorText)


def start() -> None:
    """
    Basic main function that starts the GUI

    this function can be recreated to change values set in `UserInterface`

    Function:
    ```
    import sys
    from pyside6 import QtWidgets
    from use_the_force import gui
    def main() -> None:
        app = QtWidgets.QApplication(sys.argv)
        ui = gui.UserInterface()
        ui.show()
        ret = app.exec_()
        sys.exit(ret)
    ```
    """
    app = QtWidgets.QApplication(sys.argv)
    ui = UserInterface()
    ui.show()
    ret = app.exec_()
    sys.exit(ret)
