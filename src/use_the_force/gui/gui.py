import sys
from time import perf_counter_ns, sleep

from PySide6 import QtWidgets
from PySide6.QtCore import Signal, QTimer, QObject, QRunnable, QThreadPool, Signal, Slot, Qt
from PySide6.QtGui import QCloseEvent, QTextBlockFormat, QResizeEvent
import pyqtgraph as pg

import threading
import bisect
import serial
from serial.tools import list_ports  # type: ignore
import re

from .main_ui import Ui_MainWindow
from .error_ui import Ui_errorWindow
from ..forceSensor import Commands,ForceSensor
from ..logging import Logging

__all__ = [
    "UserInterface",
    "mainLogWorker",
    "saveToLog",
    "ForceSensorGUI",
    "ErrorInterface",
    "start"
]

class UserInterface(QtWidgets.QMainWindow):
    def __init__(self) -> None:
        # roep de __init__() aan van de parent class
        super().__init__()

        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        # disable MDM until switched
        self.ui.MDM.setVisible(False)
        self.ui.MDM.setEnabled(False)

        self.error_ui = ErrorInterface()

        ###########
        # BUTTONS #
        ###########
        self.ui.butConnect.pressed.connect(self.butConnect)
        self.ui.butFile.pressed.connect(self.butFile)
        self.ui.butReGauge.pressed.connect(self.butTare)
        self.ui.butRecord.pressed.connect(self.butRecord)
        self.ui.butClear.pressed.connect(self.butClear)
        self.ui.butSave.pressed.connect(self.butSave)
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
        self.ui.butTareDisplay.pressed.connect(self.butDisplayTare)
        self.ui.butSwapPositions.pressed.connect(self.swapPositions)

        # Text boxes and value boxes
        self.ui.setNewtonPerCount.valueChanged.connect(self.setLoadPerCount)
        self.ui.setPlotTimerInterval.textEdited.connect(
            self.updatePlotTimerInterval)
        self.ui.setLineReads.valueChanged.connect(
            self.singleReadLinesForcesUpdate)
        self.ui.setLineSkips.valueChanged.connect(
            self.singleReadSkipsUpdate)
        self.ui.setStepSizeMDM.valueChanged.connect(self.singleReadStepUpdate)
        self.ui.title_2.textChanged.connect(self.updatePlotMDMTitle)
        self.ui.setUnitDisplay.editingFinished.connect(self.updateUnitDisplay)

        ###############
        # Check Ports #
        ###############
        ports: list[str] = [port.device for port in list_ports.comports()]
        if len(ports) > 0:
            self.ui.setPortName.setText(ports[0])
        else:
            self.ui.setPortName.setText("No ports found")
        del ports

        ###################
        # INITIALIZE VARS #
        ###################
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
        self.homed: bool = False
        self.singleReadForce: float = float()
        self.singleReadForces: int = 10
        self.singleReadSkips: int = 10
        self.stepSizeMDM: float = 0.05
        self.plotIndexX = 1
        self.plotIndexY = 2
        self.velocity = int(self.ui.setVelocity.value())
        self.txtLogMDM: str = str()
        self.reMDMMatch: re.Pattern[str] = re.compile(r"\[[A-Za-z0-9]+\]")
        self.data: list[list[float]] = [[], [], []]
        setattr(self.ui, "errorMessage", [])

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
        self.sensor = ForceSensorGUI(caller=self)
        # self.cmds = Commands(self.sensor.ser)
        self.sensor.errorSignal.connect(self.error)

        self.plotTimer = QTimer()
        self.plotTimer.timeout.connect(self.updatePlot)

        self.mainLogWorker = mainLogWorker(self)
        self.mainLogWorker.startSignal.connect(self.startPlotTimer)
        self.mainLogWorker.endSignal.connect(self.stopPlotTimer)
        self.mainLogWorker.switchXAxisSignal.connect(self.switchToTime)
        # self.mainLogWorker.singleReadStartSignal.connect()
        self.mainLogWorker.singleReadEndSignal.connect(self.singleReadEnd)

        self.saveToLog = saveToLog(self)
        self.saveToLog.startSignal.connect(self.saveStart)
        self.saveToLog.endSignal.connect(self.saveEnd)

        self.thread_pool = QThreadPool.globalInstance()

        ############################
        # CHANGE IN NEXT UI UPDATE #
        ############################
        # TODO: add screen for movement options and movement cycles.
        # ^ Might never update this one ^
        self.ui.butSwapPositions.setEnabled(True)

    def enableElement(self, *elements: QtWidgets.QWidget) -> None:
        """
        Enables the specified GUI elements.
        """
        [element.setEnabled(True) for element in elements]

    def disableElement(self, *elements: QtWidgets.QWidget) -> None:
        """
        Disables the specified GUI elements.
        """
        [element.setEnabled(False) for element in elements]

    def resetConnectUI(self) -> None:
        """
        Resets the UI state for the connect button and related elements.
        """
        self.ui.butConnect.setText("Connect")
        self.ui.butConnect.setChecked(False)
        self.butConnectToggle = False
        self.homed = False
        self.enableElement(
            self.ui.butConnect,
            self.ui.setPortName
        )
        self.ui.setForceApplied.editingFinished.disconnect(self.butDisplayForce)
        self.disableElement(
            self.ui.setNewtonPerCount,
            self.ui.setGaugeValue,
            self.ui.butRecord,
            self.ui.butReGauge,
            self.ui.butSingleRead,
            self.ui.setUnitDisplay,
            self.ui.butTareDisplay,
            self.ui.setForceApplied
        )
        self.ui.toolBox.setItemText(self.ui.toolBox.indexOf(self.ui.sensorOptions), "Sensor")

    def setConnectedUI(self) -> None:
        """
        Updates the UI state for a successful connection.
        """
        self.ui.butConnect.setText("Connected")
        self.ui.butConnect.setChecked(True)
        self.enableElement(
            self.ui.butReGauge,
            self.ui.butSingleRead,
            self.ui.setNewtonPerCount,
            self.ui.setGaugeValue,
            self.ui.butHome,
            self.ui.butForceStop,
            self.ui.butUpdateVelocity,
            self.ui.butConnect,
            self.ui.setUnitDisplay,
            self.ui.butTareDisplay,
            self.ui.setForceApplied
        )
        self.disableElement(self.ui.setPortName)
        self.ui.setForceApplied.editingFinished.connect(self.butDisplayForce)
        if not self.MDMActive:
            if not self.fileOpen:
                self.butClear()
            self.enableElement(self.ui.butFile)
        elif self.fileMDMOpen:
            self.enableElement(self.ui.butReadForceMDM)

    def closeEvent(self, event: QCloseEvent) -> None:
        """
        Safely closes the program and ends certain threads

        Some threads can be set to run infinitly, but will now be closed
        """
        if self.recording:
            self.recording = False
        if self.butConnectToggle:
            self.butConnect()
        if not (self.fileOpen or self.MDMActive) and len(self.data[0])>0:
            self.ui.errorMessage = [
                "Unsaved Data", "Unsaved Data!", "You have unsaved data, quit anyways?"]
            if self.error() == 0: # 0 = Cancel
                event.ignore()
                self.butSave()

    def plot(self, **kwargs) -> None:
        """
        Plots the data on the central plot.

        :param data: list containing both x-axes and y-axes as `[...,x,y]`. `...` is ignored
        :type data: list[..., list, list]

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
            *self.data[-2:],
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
            labelTxt=kwargs.pop("label2txt", "Displacement [mm]")
        )

        self.ui.yLabel.textChanged.connect(self.updatePlotYLabel)

        self.ui.xLimSlider.sliderMoved.connect(self.xLimSlider)
        self.ui.xLimSet.textChanged.connect(self.xLimSet)

        self.ui.graph1.setTitle(self.ui.title.text(), color=(255, 255, 255))
        self.ui.title.textChanged.connect(self.updatePlotTitle)

    def updatePlot(self) -> None:
        """
        Updates the plot
        """
        self.ui.graph1.plot(
            self.data[self.plotIndexX], self.data[self.plotIndexY]
        )

        if len(self.data[self.plotIndexX]) > 0:
            self.ui.xLimSlider.setMinimum(-1*(int(self.data[self.plotIndexX][-1])+1))
            try:
                self.xLim = float(self.ui.xLimSet.text())
                if -1*self.xLim < self.data[self.plotIndexX][-1] and (self.xLim != float(0)):
                    self.ui.graph1.setXRange(
                        self.data[self.plotIndexX][-1]+self.xLim, self.data[self.plotIndexX][-1])
                    i = bisect.bisect_left(
                        self.data[self.plotIndexX], self.data[self.plotIndexX][-1]+self.xLim)
                    self.ui.graph1.setYRange(
                        min(self.data[self.plotIndexY][i:]), max(self.data[self.plotIndexY][i:]))

                elif self.xLim == float(0):
                    self.ui.graph1.setXRange(0, self.data[self.plotIndexX][-1])
                    self.ui.graph1.setYRange(
                        min(self.data[self.plotIndexY]), max(self.data[self.plotIndexY]))

            except:
                self.ui.graph1.setXRange(0, self.data[self.plotIndexX][-1])
                self.ui.graph1.setYRange(
                        min(self.data[self.plotIndexY]), max(self.data[self.plotIndexY]))

    def switchPlotIndexX(self, index: int) -> None:
        self.plotIndexX = index
        if index == 0:
            self.updatePlotLabel(
                graph=self.ui.graph1, 
                labelLoc="bottom", 
                labelTxt="Time [s]"
                )
        elif index == 1:
            self.updatePlotLabel(
                graph=self.ui.graph1, 
                labelLoc="bottom", 
                labelTxt="Displacement [mm]"
                )
    
    def switchPlotIndexY(self, index: int) -> None:
        self.plotIndexY = index

    def switchToTime(self) -> None:
        self.switchPlotIndexX(0)

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
        self.ui.graph1.setTitle(self.ui.title.text(), color=(255, 255, 255))

    def startPlotTimer(self) -> None:
        """
        Start the QTimer in the main thread when the signal is emitted.
        """
        self.plotTimer.start()

    def stopPlotTimer(self) -> None:
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

        # Disconnect
        if self.butConnectToggle:
            self.butConnectToggle = False

            self.startsensorDisonnect = threading.Thread(
                target=self.sensorDisconnect)
            self.startsensorDisonnect.start()
            self.ui.setPortName.setEnabled(True)

        # Connect
        else:
            devices: list[str] = [
                port.device for port in list_ports.comports()]
            if self.ui.setPortName.text().upper() in devices:
                self.butConnectToggle = True
                self.ui.butFile.setEnabled(False)
                self.startsensorConnect = threading.Thread(
                    target=self.sensorConnect)
                self.startsensorConnect.start()
            else:
                if len(devices) > 0:
                    self.ui.errorMessage = ["Port not found", f"Port: {self.ui.setPortName.text().upper()} was not detected!", "Available ports:\n" + '\n'.join([port.device for port in list_ports.comports()])]
                    self.error()
                else:
                    self.ui.errorMessage = [
                        "Port not found", f"Port: {self.ui.setPortName.text().upper()} was not detected!", "Available ports:\nNo ports found!"]
                    self.error()
                self.ui.butConnect.setText("Connect")
                self.ui.butConnect.setEnabled(True)
            del devices

    def sensorConnect(self) -> None:
        """
        Script to connect to the M5Din Meter.

        If connection fails, will raise an error dialog with the error.
        """
        self.ui.butConnect.setText("Connecting...")
        self.sensor()
        if self.sensor.failed:
            self.sensor.failed = False
            self.resetConnectUI()
            return

        # needs time or it will break
        sleep(0.5)
        try:
            vr = self.sensor.cmds.VR()
            if vr == '':
                raise RuntimeError("[ERROR]: Returned empty string.")
            else:
                self.ui.toolBox.setItemText(self.ui.toolBox.indexOf(self.ui.sensorOptions), "Sensor v:"+vr.split(":")[1][1:])
        except RuntimeError as e:
            self.sensor.ClosePort()
            self.resetConnectUI()
            self.ui.errorMessage = [
                                    "Connection Error", 
                                    "Connection Error", 
                                    "[ERROR]: Retrieved no data."
                                ]
            self.error()
            return

        pos = self.sensor.cmds.GP()
        vel = self.sensor.cmds.GV()
        self.ui.setVelocity.setValue(vel)
        self.velocity = vel
        if pos>=0 and pos<47:
            self.homed = True
            self.enableElement(
                self.ui.butRecord,
                self.ui.butMove
            )
            self.ui.setPosition.setValue(pos)
        
        self.setConnectedUI()

    def sensorDisconnect(self) -> None:
        """
        Script to safely disconnect the M5Din Meter.

        Will first stop the recording, if running, with `butRecord()` function.
        """
        if self.recording:
            self.butRecord()
        self.sensor.ClosePort()
        sleep(0.5)  # Give some time to Windows/M5Din Meter to fully disconnect
        self.resetConnectUI()

    @Slot(str, str, str)
    @Slot(str, str, None)
    def error(self) -> int:
        """
        Launches the error dialog.

        :param errorType: error type name, can be found with `Exception.__class__.__name__`
        :type errorType: str
        :param errorText: text why the error occured
        :type errorText: str

        :returns: Result of dialogue (button pressed), 1 for OK, 0 for Cancel
        :rtype: int
        """
        if len(self.ui.errorMessage) == 3:
            if self.ui.errorMessage[2] == "[ERROR]: movement aborted, home to unlock":
                if self.recording:
                    self.recording = False
                    self.ui.butRecord.setText("Start")
                    self.enableElement(
                        self.ui.butClear,
                        self.ui.butFile,
                        self.ui.butSave,
                        self.ui.butSwitchManual
                    )
                self.homed = False
                self.enableElement(self.ui.butHome)
                self.disableElement(
                    self.ui.butRecord,
                    self.ui.butMove
                )
            

        return self.error_ui(*self.ui.errorMessage)

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
            self.ui.butSwitchManual.setEnabled(True)

        else:
            self.fileOpen = True
            self.ui.butFile.setChecked(True)
            self.filePath, _ = QtWidgets.QFileDialog.getSaveFileName(
                filter="CSV files (*.csv)")
            # Cancel gives a 0 length string
            if self.filePath != "":
                self.measurementLog = Logging(self.filePath)
                self.measurementLog.createLogGUI()
                self.ui.butFile.setText(
                    *self.filePath.split("/")[-1].split(".")[:-1])
                if len(self.data[1]) > 0:
                    self.ui.butSave.setEnabled(False)
                    self.thread_pool.start(self.saveToLog.run)
                self.ui.butSwitchManual.setEnabled(False)
            else:
                self.fileOpen = False
                self.ui.butFile.setText("-")
                self.ui.butFile.setChecked(False)

    def butRecord(self) -> None:
        """
        start button, disables/ enables most buttons and starts/ joins threads for the logging
        """
        if self.recording:
            self.recording = False
            self.ui.butRecord.setText("Start")
            self.enableElement(
                self.ui.butClear,
                self.ui.butFile,
                self.ui.butReGauge,
                self.ui.butSave,
                self.ui.butSingleRead,
                self.ui.butSwitchManual,
                self.ui.butUpdateVelocity,
                self.ui.butHome
            )

            if not self.threadReachedEnd:
                pass # one day will be able to wait for motor to stop.

        else:
            if len(self.data[0])>0:
                if not self.fileOpen:
                    self.ui.errorMessage = [
                        "Unsaved Data", "Unsaved Data!", "You have unsaved data, do you wish to continue?"]
                    if self.error() == 0: # 0 = Cancel
                        self.butSave()
                        return
                self.butClear()

            self.recording = True
            self.threadReachedEnd = False
            self.ui.butRecord.setText("Stop")
            self.ui.butRecord.setChecked(True)

            self.disableElement(
                self.ui.butClear,
                self.ui.butFile,
                self.ui.butReGauge,
                self.ui.butSave,
                self.ui.butSingleRead,
                self.ui.butSwitchManual,
                self.ui.butUpdateVelocity,
                self.ui.butHome
            )

            self.sensor.ser.reset_input_buffer()
            

            if self.ui.setStartPos.value() == self.ui.setEndPos.value() and self.plotIndexX!=0 and self.ui.setTime.value()>0:
                self.switchPlotIndexX(0)
            elif self.plotIndexX!=1:
                self.switchPlotIndexX(1)

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
        self.data = [[], [], []]
        if self.MDMActive:
            self.graphMDM1.clear()
            self.graphMDM2.clear()
        else:
            self.ui.graph1.clear()
        if hasattr(self.sensor, "ser"):
            self.sensor.ser.reset_input_buffer()
        self.ui.butSave.setEnabled(False)
        if self.fileOpen:
            self.butFile()

    def butTare(self) -> None:
        """
        button for Taring values sent from the M5Din Meter

        starts a thread to count down, end of thread re-enables button
        """
        self.disableElement(
            self.ui.butReGauge,
            self.ui.butConnect,
            self.ui.butRecord,
            self.ui.butSingleRead
        )
        th = threading.Thread(target=self.butTareActive)
        th.start()

    def butTareActive(self) -> None:
        """
        the actual Tare script
        """
        self.ui.butReGauge.setChecked(True)

        i=3
        while i > 0:
            self.ui.butReGauge.setText(f"Taring in {i}")
            sleep(1)
            i -= 1

        self.ui.butReGauge.setText("...")
        GaugeValue = self.sensor.tare()
        self.ui.setGaugeValue.setValue(GaugeValue)
        self.sensor.tareValue = GaugeValue
        self.ui.butReGauge.setText("Tare")

        if (not self.MDMActive) and self.homed:
            self.enableElement(self.ui.butRecord)
        self.enableElement(
            self.ui.butReGauge,
            self.ui.butConnect,
            self.ui.butSingleRead
        )
        self.ui.butReGauge.setChecked(False)

    def butSave(self) -> None:
        """
        Function for what `butSave` has to do.

        What to do is based on if `butFile` is in the `isChecked()` state. 
        - `if isChecked():` do nothing as it is already saved
        - `else:` open new file and write data
        """
        if self.fileOpen:
            # When a file is selected it will already
            # write to the file when it reads a line
            self.disableElement(self.ui.butSave)
            self.ui.toolBox.setCurrentIndex(2)

        else:
            self.butFile()
            # Cancelling file selecting gives a 0 length string
            if self.filePath != "":
                self.disableElement(self.ui.butSave)
                self.ui.toolBox.setCurrentIndex(2)

    def saveStart(self) -> None:
        self.ui.butSave.setText("Saving...")

    def saveEnd(self) -> None:
        self.ui.butSave.setText("Save")

    def butSingleRead(self) -> None:
        self.singleReadToggle = True
        self.disableElement(
            self.ui.butSingleRead,
            self.ui.butRecord,
            self.ui.butConnect,
            self.ui.butReGauge
        )
        self.thread_pool.start(self.mainLogWorker.singleRead)

    def singleReadEnd(self) -> None:
        if self.MDMActive:

            if self.fileMDMOpen:
                self.enableElement(self.ui.butReadForceMDM)
            if self.singleReadToggle:
                self.ui.butSingleRead.setText(
                    "{:.5f}".format(self.singleReadForce))
                self.singleReadToggle = False
            else:
                if self.readForceMDMToggle:
                    self.data[0].append(0)
                    self.data[1].append(round(
                        self.data[1][-1]+self.stepSizeMDM, len(str(self.stepSizeMDM).split(".")[-1])))
                    self.data[2].append(self.singleReadForce)

                    if re.search(self.reMDMMatch, self.ui.xLabel_2.text()) and re.search(self.reMDMMatch, self.ui.yLabel_2.text()):
                        xUnit: list[str] = self.ui.xLabel_2.text().split(
                            "[")[-1].split("]")
                        yUnit: list[str] = self.ui.yLabel_2.text().split(
                            "[")[-1].split("]")
                        if len(xUnit) > 0 and len(yUnit) > 0:
                            self.txtLogMDM = self.txtLogMDM + \
                                f"\n{self.data[1][-1]} {xUnit[0]}, {self.data[2][-1]} {yUnit[0]}"
                        else:
                            self.txtLogMDM = self.txtLogMDM + \
                                f"\n{self.data[1][-1]}, {self.data[2][-1]}"
                    else:
                        self.txtLogMDM = self.txtLogMDM + \
                            f"\n{self.data[1][-1]}, {self.data[2][-1]}"
                    self.ui.plainTextEdit.setPlainText(self.txtLogMDM)
                    self.plainTextEditScrollbar = self.ui.plainTextEdit.verticalScrollBar()
                    self.plainTextEditScrollbar.setValue(
                        self.plainTextEditScrollbar.maximum())
                else:
                    self.data[0].append(0)
                    self.data[1].append(0.)
                    self.data[2].append(self.singleReadForce)
                    self.readForceMDMToggle = True
                    if re.search(self.reMDMMatch, self.ui.xLabel_2.text()) and re.search(self.reMDMMatch, self.ui.yLabel_2.text()):
                        xUnit: list[str] = self.ui.xLabel_2.text().split("[")[
                            1].split("]")
                        yUnit: list[str] = self.ui.yLabel_2.text().split("[")[
                            1].split("]")
                        if len(xUnit) > 0 and len(yUnit) > 0:
                            self.txtLogMDM = self.txtLogMDM + \
                                f"{self.data[1][-1]} {xUnit[0]}, {self.data[2][-1]} {yUnit[0]}"
                    else:
                        self.txtLogMDM = self.txtLogMDM + \
                            f"{self.data[1][-1]}, {self.data[2][-1]}"
                    self.ui.plainTextEdit.setPlainText(self.txtLogMDM)
                    self.plainTextEditScrollbar = self.ui.plainTextEdit.verticalScrollBar()
                    self.plainTextEditScrollbar.setValue(
                        self.plainTextEditScrollbar.maximum())

                self.enableElement(
                    self.ui.butSwitchDirectionMDM,
                    self.ui.butDeletePreviousMDM
                )

                self.measurementLog.writeLog(
                    [self.data[0][-1], self.data[1][-1], self.data[2][-1]])
                self.updatePlotMDM()
        else:
            self.ui.butSingleRead.setText(
                "{:.5f}".format(self.singleReadForce))
            if self.homed:
                self.ui.butRecord.setEnabled(True)
            self.singleReadToggle = False

        self.enableElement(
            self.ui.butSingleRead,
            self.ui.butReGauge,
            self.ui.butConnect
        )

    def singleReadSkipsUpdate(self) -> None:
        """
        Changes the value of singleReadSkips when textbox is changed
        """
        try:
            self.singleReadSkips = int(self.ui.setLineSkips.text())
        except ValueError:
            pass

    def singleReadLinesForcesUpdate(self) -> None:
        """
        Changes the value of singleReadForces when textbox is changed
        """
        try:
            self.singleReadForces = int(self.ui.setLineReads.text())
        except ValueError:
            pass

    def singleReadStepUpdate(self) -> None:
        """
        Changes the value of stepSizeMDM when textbox is changed
        """
        try:
            self.stepSizeMDM = float(self.ui.setStepSizeMDM.text())
            if self.switchDirectionMDMToggle:
                self.stepSizeMDM = -1*self.stepSizeMDM
        except ValueError:
            pass

    def readForceMDM(self) -> None:
        self.disableElement(
            self.ui.butReadForceMDM,
            self.ui.butSwitchDirectionMDM
        )
        self.thread_pool.start(self.mainLogWorker.singleRead)

    def switchDirectionMDM(self) -> None:
        self.measurementLog.closeFile()
        del self.measurementLog

        self.readForceMDMToggle = False
        self.enableElement(self.ui.butDeletePreviousMDM)

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
            self.enableElement(
                self.ui.butSwitchManual,
                self.ui.butConnect
            )
            self.disableElement(
                self.ui.butReadForceMDM,
                self.ui.butSwitchDirectionMDM
            )

        else:
            self.switchDirectionMDMToggle = True
            self.ui.butSwitchDirectionMDM.setText("Stop")

            self.measurementLog = Logging(
                "".join(self.filePath.split(".")[:-1])+"_out.csv")
            self.measurementLog.createLogGUI()

            self.stepSizeMDM = -self.stepSizeMDM
            if len(self.data[1]) > 0:
                self.switchDistance: float = self.data[1][-1]
                self.switchForce: float = self.data[2][-1]
            else:
                self.switchDistance, self.switchForce = 0., 0.
            del self.data

            self.data = [[0], [self.switchDistance], [self.switchForce]]

            self.measurementLog.writeLog([self.data[1][-1], self.data[2][-1]])

            self.readForceMDMToggle = True
            del self.txtLogMDM
            self.txtLogMDM = str()
            if re.search(self.reMDMMatch, self.ui.xLabel_2.text()) and re.search(self.reMDMMatch, self.ui.yLabel_2.text()):
                xUnit: list[str] = self.ui.xLabel_2.text().split("[")[
                    1].split("]")
                yUnit: list[str] = self.ui.yLabel_2.text().split("[")[
                    1].split("]")
                if len(xUnit) > 0 and len(yUnit) > 0:
                    self.txtLogMDM = self.txtLogMDM + \
                        f"{self.data[1][-1]} {xUnit[0]}, {self.data[2][-1]} {yUnit[0]}"
            else:
                self.txtLogMDM = self.txtLogMDM + \
                    f"{self.data[1][-1]}, {self.data[2][-1]}"
            self.ui.plainTextEdit.setPlainText(self.txtLogMDM)
            self.plainTextEditScrollbar = self.ui.plainTextEdit.verticalScrollBar()
            self.plainTextEditScrollbar.setValue(
                self.plainTextEditScrollbar.maximum())

    def butSwitchMDM(self) -> None:
        self.butClear()
        if self.MDMActive:
            self.MDMActive = False
            # visibility
            self.ui.centerGraph.setVisible(True)
            self.ui.MDM.setVisible(False)

            # main ui buttons
            self.enableElement(
                self.ui.graphOptions,
                self.ui.butClear
            )
            if self.butConnectToggle and self.homed:
                self.enableElement(self.ui.butRecord)

            # MDM
            self.disableElement(self.ui.MDM)

        else:
            self.MDMActive = True

            # visibility
            self.ui.centerGraph.setVisible(False)
            self.ui.MDM.setVisible(True)

            # main ui buttons
            self.disableElement(
                self.ui.graphOptions,
                self.ui.butSave,
                self.ui.butClear,
                self.ui.butRecord
            )

            # MDM
            self.ui.MDM.setEnabled(True)

    def plotMDM(self, **kwargs) -> None:
        pg.setConfigOption("foreground", kwargs.pop("clrFg", "k"))
        pg.setConfigOption("background", kwargs.pop("clrBg", "w"))
        # self.ui.graphMDM.setBackground(background=kwargs.pop("clrBg", "w"))
        self.graphMDM1 = self.ui.graphMDM.plot(
            *self.data[1:],
            name=kwargs.pop("nameIn", "Approach"),
            symbol=kwargs.pop("symbolIn", None),
            pen=pg.mkPen({
                "color": kwargs.pop("colorIn", (0, 0, 255)),
                "width": kwargs.pop("linewidthIn", 5)
            })
        )
        self.graphMDM2 = self.ui.graphMDM.plot(
            *self.data[1:],
            name=kwargs.pop("nameOut", "Retraction"),
            symbol=kwargs.pop("symbolOut", None),
            pen=pg.mkPen({
                "color": kwargs.pop("colorOut", (255, 127, 0)),
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

        self.graphMDMLegend = self.ui.graphMDM.addLegend(
            offset=(1, 1), labelTextColor=(255, 255, 255))
        self.graphMDMLegend.addItem(self.graphMDM1, name=self.graphMDM1.name())
        self.graphMDMLegend.addItem(self.graphMDM2, name=self.graphMDM2.name())

        self.ui.graphMDM.setTitle(
            self.ui.title_2.text(), color=(255, 255, 255))

        self.ui.yLabel_2.textChanged.connect(self.updatePlotMDMYLabel)
        self.ui.xLabel_2.textChanged.connect(self.updatePlotMDMXLabel)

    def updatePlotMDMTitle(self) -> None:
        self.ui.graphMDM.setTitle(
            self.ui.title_2.text(), color=(255, 255, 255))

    def updatePlotMDMYLabel(self) -> None:
        self.updatePlotLabel(graph=self.ui.graphMDM,
                             labelLoc="left", labelTxt=self.ui.yLabel_2.text())

    def updatePlotMDMXLabel(self) -> None:
        self.updatePlotLabel(graph=self.ui.graphMDM,
                             labelLoc="bottom", labelTxt=self.ui.xLabel_2.text())

    def updatePlotMDM(self) -> None:
        if self.switchDirectionMDMToggle:
            self.graphMDM2.setData(*self.data[1:])
        else:
            self.graphMDM1.setData(*self.data[1:])

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
                self.disableElement(self.ui.butSwitchDirectionMDM)
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
            self.enableElement(
                self.ui.butSwitchManual,
                self.ui.butConnect
            )
            self.disableElement(
                self.ui.butReadForceMDM,
                self.ui.butSwitchDirectionMDM
            )

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
        for i in range(len(self.data)):
            self.data[i] = self.data[i][:-1]

        # already switched and only 1 value left
        if len(self.data[1]) <= 1 and self.switchDirectionMDMToggle:
            self.disableElement(
                self.ui.butDeletePreviousMDM,
                self.ui.butSwitchDirectionMDM
            )
        # not switched and no values left
        elif len(self.data[1]) <= 0:
            self.readForceMDMToggle = False
            self.disableElement(
                self.ui.butDeletePreviousMDM,
                self.ui.butSwitchDirectionMDM
            )
        # there should be a better way to just
        # drop the last value, but this works for now
        # and does not seem to cause much trouble
        self.measurementLog.replaceFile(data=self.data)

        # text box changes
        self.txtLogMDM = str("\n").join(self.txtLogMDM.split("\n")[:-1])
        self.ui.plainTextEdit.setPlainText(self.txtLogMDM)
        self.plainTextEditScrollbar = self.ui.plainTextEdit.verticalScrollBar()
        self.plainTextEditScrollbar.setValue(
            self.plainTextEditScrollbar.maximum())

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

    def setLoadPerCount(self) -> None:
        """
        Changes the value of LoadPerCount when textbox is changed

        Allows for changing the value while still getting live data
        """
        try:
            self.sensor.loadPerCount = float(
                self.ui.setNewtonPerCount.value())
        except:
            pass

    def butMove(self) -> None:
        self.sensor.cmds.SP(self.ui.setPosition.value())

    def butUpdateVelocity(self) -> None:
        self.velocity = int(self.ui.setVelocity.value())
        self.sensor.cmds.SV(self.velocity)

    def butHome(self) -> None:
        self.ui.errorMessage = ["Home Warning", "Home Warning", "Make sure nothing is obstructing the path downwards.<br>The motor will not stop during homing!"]
        if self.error()==1:
            self.butUpdateVelocity()
            self.sensor.cmds.HM()
            self.homed = True
            self.enableElement(
                self.ui.butRecord,
                self.ui.butMove
            )

    def butForceStop(self) -> None:
        self.homed = False
        self.enableElement(self.ui.butHome)
        self.disableElement(
            self.ui.butRecord,
            self.ui.butMove
        )
        if self.recording:
            self.recording = False
            self.ui.butRecord.setText("Start")
            self.enableElement(
                self.ui.butClear,
                self.ui.butFile,
                self.ui.butReGauge,
                self.ui.butSave,
                self.ui.butSingleRead,
                self.ui.butSwitchManual
            )

        self.sensor.cmds.ST()

    def butDisplayTare(self) -> None:
        self.sensor.cmds.TR()

    def butDisplayForce(self) -> None:
        self.sensor.cmds.SF(float(self.ui.setForceApplied.value()))

    def updateUnitDisplay(self) -> None:
        if self.butConnectToggle:
            self.sensor.cmds.UU(str(self.ui.setUnitDisplay.text()))

    def swapPositions(self) -> None:
        startPos = self.ui.setStartPos.value()
        endPos = self.ui.setEndPos.value()
        self.ui.setStartPos.setValue(endPos)
        self.ui.setEndPos.setValue(startPos)


class mainLogWorker(QObject, QRunnable):
    startSignal = Signal()
    endSignal = Signal()
    errorSignal = Signal()
    switchXAxisSignal = Signal()
    singleReadStartSignal = Signal()
    singleReadEndSignal = Signal()

    def __init__(self, callerSelf: UserInterface) -> None:
        super().__init__()
        self.callerSelf: UserInterface = callerSelf
        self.logLess:bool = bool()
        self.singleReadForces: int = self.callerSelf.singleReadForces

    def run(self) -> None:
        # mm/s speed of stage
        trueVelocity: float = (self.callerSelf.velocity)/60

        currentPos: int = self.callerSelf.sensor.cmds.GP()
        startPos: int = self.callerSelf.ui.setStartPos.value()
        endPos: int = self.callerSelf.ui.setEndPos.value()
        Position: float = 0.

        travelTime: float = abs(endPos-startPos)/trueVelocity
        measurementTime: float = travelTime + self.callerSelf.ui.setTime.value()
        allowTimeSwitch = self.callerSelf.ui.setTime.value() != 0.
        if currentPos != startPos:
            self.callerSelf.sensor.cmds.SP(startPos)
            # wait until the stage has reached the start position
            sleep(abs(startPos - currentPos) / trueVelocity + 1)
        self.singleReadForces = self.callerSelf.singleReadForces
        
        _skip: list[float] = [self.callerSelf.sensor.cmds.SR()
                              for i in range(self.callerSelf.singleReadSkips)]

        self.startSignal.emit()
        self.callerSelf.sensor.cmds.DC(False)
        time = float(0.)
        self.callerSelf.sensor.T0 = perf_counter_ns()

        # start movement
        self.callerSelf.sensor.cmds.SP(endPos)

        while (time < measurementTime) and self.callerSelf.recording:
            try:
                time = round(
                    (perf_counter_ns() - self.callerSelf.sensor.T0)/1e9, 8)
                if time < travelTime:
                    Position = trueVelocity*time
                elif self.callerSelf.plotIndexX != 0 and allowTimeSwitch:
                        Position = float(abs(endPos-startPos))
                        self.switchXAxisSignal.emit()
                Force = self.read()
                self.callerSelf.data[0].append(time)
                self.callerSelf.data[1].append(Position)
                self.callerSelf.data[2].append(Force)
                if not self.logLess:
                    # logs: t[s], s[mm], F[mN]
                    self.callerSelf.measurementLog.writeLog(
                        [time, Position, Force])
                
                self.singleReadForces = self.callerSelf.singleReadForces

            except ValueError:
                # I know this isn't the best way to deal with it, but it works fine (for now)
                pass
        
        self.callerSelf.sensor.cmds.DC()
        self.endSignal.emit()

        if self.callerSelf.recording:
            self.callerSelf.threadReachedEnd = True
            self.callerSelf.butRecord()

        if self.logLess:
            # self.callerSelf.unsavedData = self.callerSelf.data
            self.callerSelf.enableElement(self.callerSelf.ui.butSave)
    
    def read(self) -> float:
        forces: list[float] = [self.callerSelf.sensor.ForceFix(
            self.callerSelf.sensor.cmds.SR()) for i in range(self.singleReadForces)]
        Force = round(
            sum(forces)/self.singleReadForces,
            ndigits=8
        )
        return Force


    def singleRead(self) -> None:
        self.singleReadStartSignal.emit()
        self.singleReadForces = self.callerSelf.singleReadForces
        _skip: list[float] = [self.callerSelf.sensor.ForceFix(self.callerSelf.sensor.cmds.SR())
                            for i in range(self.callerSelf.singleReadSkips)]
        self.callerSelf.singleReadForce = self.read()
        self.singleReadEndSignal.emit()


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


class ForceSensorGUI(ForceSensor, QObject, QRunnable):
    errorSignal = Signal()

    def __init__(self, caller: UserInterface, PortName: str | None = None, **kwargs) -> None:
        """
        Class that combines the ForceSensor class with GUI parts and multithreading.

        :param PortName: Portname over which to establish the connection. If None, the this class has to be called again with the port name.
        :type PortName: str | None
        """
        ForceSensor.__init__(self, PortName=PortName, kwargs=kwargs)
        QObject.__init__(self)
        QRunnable.__init__(self)
        
        self.caller: UserInterface = caller
        self.ui: Ui_MainWindow = caller.ui
        self.failed: bool = False

        if PortName != None:
            self.tareValue: float = float(self.ui.setGaugeValue.value())
            self.loadPerCount: float = float(self.ui.setNewtonPerCount.value())

            self.PortName: str = PortName.upper()

            try:
                self.ser.setPort(self.PortName)
                self.ser.open()
                self.ser.setRTS(False)
                self.ser.setDTR(False)
            except Exception as e:
                self.failed = True
                self.ui.errorMessage = [
                    e.__class__.__name__, e.args[0]+"\n\nCheck if Port is not already in use."]
                self.errorSignal.emit()

    def __call__(self, **kwargs) -> None:
        """
        Opens up the serial port, checks the gauge value and makes sure data is available.
        """
        self.tareValue: float = float(self.ui.setGaugeValue.value())
        self.loadPerCount: float = float(self.ui.setNewtonPerCount.value())

        self.PortName: str = self.ui.setPortName.text().upper()

        try:
            self.ser.setPort(self.PortName)
            self.ser.open()
            self.ser.setRTS(False)
            self.ser.setDTR(False)
        except Exception as e:
            self.failed = True
            self.ui.errorMessage = [
                e.__class__.__name__, e.args[0]+"\n\nCheck if Port is not already in use."]
            self.errorSignal.emit()


class ErrorInterface(QtWidgets.QDialog):
    def __init__(self) -> None:
        # roep de __init__() aan van de parent class
        super().__init__()

        self.ui = Ui_errorWindow()
        self.ui.setupUi(self)
        self.ui.ErrorText.setTextFormat(Qt.TextFormat.RichText)

    def __call__(self, windowTitle: str, errorText: str, additionalInfo: str | None = None) -> int:
        """
        Enabling the window with the different types.

        :param windowTitle: sets the window title
        :type windowTitle: str
        :param errorText: sets the short error text in the window
        :type errorText: str
        :param additionalInfo: sets the additional information in the window
        :type additionalInfo: str | None

        :return: returns the value of the button pressed, 1 for OK, 0 for Cancel
        :rtype: int
        """
        self.setWindowTitle(windowTitle)
        if additionalInfo is not None:
            self.ui.ErrorText.setText(f"""
<b>{errorText}</b><br>
<br>
{additionalInfo}
""")
        else:
            self.ui.ErrorText.setText(f"<b>{errorText}</b>")
        
        return self.exec()


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
