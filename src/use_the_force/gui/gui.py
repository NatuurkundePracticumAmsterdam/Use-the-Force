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
from serial.tools import list_ports  # type: ignore
from .main_ui import Ui_MainWindow
from .error_ui import Ui_errorWindow

from ..logging import Logging


class UserInterface(QtWidgets.QMainWindow):
    def __init__(self) -> None:
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
        self.sensor = ForceSensorGUI(ui=self.ui)
        self.sensor.errorSignal.connect(self.error)

        self.plotTimer = QTimer()
        self.plotTimer.timeout.connect(self.updatePlot)

        self.mainLogWorker = mainLogWorker(self)
        self.mainLogWorker.startSignal.connect(self.startPlotTimer)
        self.mainLogWorker.endSignal.connect(self.stopPlotTimer)

        self.saveToLog = saveToLog(self)
        self.saveToLog.startSignal.connect(self.saveStart)
        self.saveToLog.endSignal.connect(self.saveEnd)

        self.singleReadWorker = singleReadWorker(self)
        # self.singleReadWorker.startSignal.connect()
        self.singleReadWorker.endSignal.connect(self.singleReadEnd)

        self.thread_pool = QThreadPool.globalInstance()

        ############################
        # CHANGE IN NEXT UI UPDATE #
        ############################
        # TODO: add screen for movement options and movement cycles.
        self.ui.setVelocity.setValue(60)  # 1mm/s
        self.ui.timeLabel.setVisible(False)  # REMOVE
        self.ui.setTime.setVisible(False)  # REMOVE
        self.ui.timeLabel.setEnabled(False)
        self.ui.setTime.setEnabled(False)
        self.ui.setLineSkipsMDM.setValue(3)
        print(type(self.ui.setTime))

    def enableElement(self, *elements) -> None:
        """
        Enables the specified GUI elements.
        """
        [element.setEnabled(True) for element in elements]

    def disableElement(self, *elements) -> None:
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
        self.disableElement(
            self.ui.setNewtonPerCount,
            self.ui.setGaugeValue,
            self.ui.butRecord,
            self.ui.butReGauge,
            self.ui.butSingleRead
        )

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
            self.ui.butConnect
        )
        self.disableElement(self.ui.setPortName)
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
        if self.ui.butConnect.isChecked():
            self.butConnect()

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
            labelTxt=kwargs.pop("label2txt", self.ui.xLabel.text())
        )

        self.ui.yLabel.textChanged.connect(self.updatePlotYLabel)
        self.ui.xLabel.textChanged.connect(self.updatePlotXLabel)

        self.ui.xLimSlider.sliderMoved.connect(self.xLimSlider)
        self.ui.xLimSet.textChanged.connect(self.xLimSet)

        self.ui.graph1.setTitle(self.ui.title.text(), color=(255, 255, 255))
        self.ui.title.textChanged.connect(self.updatePlotTitle)

    def updatePlot(self) -> None:
        """
        Updates the plot
        """
        self.ui.graph1.plot(
            *self.data[-2:],
        )

        if len(self.data[-2]) > 0:
            self.ui.xLimSlider.setMinimum(-1*(int(self.data[-2][-1])+1))
            try:
                self.xLim = float(self.ui.xLimSet.text())
                if -1*self.xLim < self.data[-2][-1] and (self.xLim != float(0)):
                    self.ui.graph1.setXRange(
                        self.data[-2][-1]+self.xLim, self.data[-2][-1])
                    i = bisect.bisect_left(
                        self.data[-2], self.data[-2][-1]+self.xLim)
                    self.ui.graph1.setYRange(
                        min(self.data[-1][i:]), max(self.data[-1][i:]))

                elif self.xLim == float(0):
                    self.ui.graph1.setXRange(0, self.data[-2][-1])
                    self.ui.graph1.setYRange(
                        min(self.data[-1]), max(self.data[-1]))

            except:
                self.ui.graph1.setXRange(0, self.data[-2][-1])
                self.ui.graph1.setYRange(
                    min(self.data[-1]), max(self.data[-1]))

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

        if self.butConnectToggle:
            self.butConnectToggle = False

            self.startsensorDisonnect = threading.Thread(
                target=self.sensorDisconnect)
            self.startsensorDisonnect.start()
            self.ui.setPortName.setEnabled(True)

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
                    self.error(
                        ["Port not found", f"Port: {self.ui.setPortName.text().upper()} was not detected!", "Available ports:\n" + '\n'.join([port.device for port in list_ports.comports()])])
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
        if self.sensor.SR() == 0.:
            self.sensor.ClosePort()
            self.resetConnectUI()
            return

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
                if len(self.data[1]) > 0:
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

            self.measurementLog.closeFile()
            del self.measurementLog

            self.ui.butFileGraphImport.setChecked(True)
            self.ui.butFileGraphImport.setText("-")
            self.ui.butFile.setText("-")
            self.butClear()

            self.enableElement(
                self.ui.butFile,
                self.ui.butClear,
                self.ui.butSwitchManual
            )

        else:
            self.fileGraphOpen = True

            self.disableElement(self.ui.butSwitchManual)

            self.filePathGraph, _ = QtWidgets.QFileDialog.getOpenFileName(
                filter="CSV files (*.csv)")

            if self.filePathGraph != "":
                self.measurementLog = Logging(self.filePathGraph)
                self.ui.butFileGraphImport.setChecked(True)
                self.ui.butFileGraphImport.setText(
                    *self.filePathGraph.split("/")[-1].split(".")[:-1])
                self.ui.butFile.setText(
                    f"Close File: {''.join(*self.filePathGraph.split('/')[-1].split('.')[:-1])}")

                self.disableElement(
                    self.ui.butFile,
                    self.ui.butRecord,
                    self.ui.butClear
                )

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
        if self.recording and self.threadReachedEnd:
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

        elif self.recording:
            self.butForceStop()

        else:
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
                self.ui.butFileGraphImport,
                self.ui.butSwitchManual
            )

            self.sensor.ser.reset_input_buffer()
            self.butClear()

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
        if not self.fileOpen:
            self.ui.butFileGraphImport.setEnabled(True)
        else:
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

        for i in range(3):
            self.ui.butReGauge.setText(f"Taring in {i+1}")
            sleep(1)

        self.ui.butReGauge.setText("...")
        self.sensor.reGauge()
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

        else:
            self.butFile()
            # Cancelling file selecting gives a 0 length string
            if self.filePath != "":
                self.disableElement(self.ui.butSave)
                self.thread_pool.start(self.saveToLog.run)

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
        self.thread_pool.start(self.singleReadWorker.run)

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
            self.singleReadSkips = int(self.ui.setLineSkipsMDM.text())
        except ValueError:
            pass

    def singleReadLinesForcesUpdate(self) -> None:
        """
        Changes the value of singleReadForces when textbox is changed
        """
        try:
            self.singleReadForces = int(self.ui.setLineReadsMDM.text())
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
        self.thread_pool.start(self.singleReadWorker.run)

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
                self.ui.logOptions,
                self.ui.graphOptions,
                self.ui.butClear
            )
            if self.butConnectToggle and self.homed:
                self.enableElement(self.ui.butRecord)

            # MDM
            self.disableElement(self.ui.MDM.setEnabled)

        else:
            self.MDMActive = True

            # visibility
            self.ui.centerGraph.setVisible(False)
            self.ui.MDM.setVisible(True)

            # main ui buttons
            self.disableElement(
                self.ui.logOptions,
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

    def setNewtonPerCount(self) -> None:
        """
        Changes the value of NewtonPerCount when textbox is changed

        Allows for changing the value while still getting live data
        """
        try:
            self.sensor.NewtonPerCount = float(
                self.ui.setNewtonPerCount.value())
        except:
            pass

    def butMove(self) -> None:
        self.sensor.SP(self.ui.setPosition.value())

    def butUpdateVelocity(self) -> None:
        self.velocity = int(self.ui.setVelocity.value())
        self.sensor.SV(self.velocity)

    def butHome(self) -> None:
        self.butUpdateVelocity()
        self.sensor.HM()
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

        self.sensor.ST()


class mainLogWorker(QObject, QRunnable):
    startSignal = Signal()
    endSignal = Signal()
    errorSignal = Signal()

    def __init__(self, callerSelf: UserInterface) -> None:
        super().__init__()
        self.callerSelf: UserInterface = callerSelf
        self.logLess = bool()

    def run(self) -> None:
        if not self.logLess:
            self.callerSelf.data = self.callerSelf.measurementLog.readLog(
                filename=self.callerSelf.filePath)

        # mm/s speed of stage
        trueVelocity: float = (5*self.callerSelf.velocity)/300

        currentPos: int = self.callerSelf.sensor.GP()
        startPos: int = self.callerSelf.ui.setStartPos.value()
        endPos: int = self.callerSelf.ui.setEndPos.value()

        travelTime: float = abs(endPos-startPos)/trueVelocity
        measurementTime: float = travelTime

        if currentPos != startPos:
            self.callerSelf.sensor.SP(startPos)
            # wait until the stage has reached the start position
            sleep(abs(startPos - currentPos) * trueVelocity+0.5)

        self.startSignal.emit()

        time: float = 0.
        self.callerSelf.sensor.T0 = perf_counter_ns()

        # start movement
        self.callerSelf.sensor.SP(endPos)

        while (time < measurementTime) and self.callerSelf.recording:
            try:
                time = round(
                    (perf_counter_ns() - self.callerSelf.sensor.T0)/1e9, 8)
                Position = trueVelocity*time
                Force = self.callerSelf.sensor.ForceFix(
                    self.callerSelf.sensor.SR())
                self.callerSelf.data[0].append(time)
                self.callerSelf.data[1].append(Position)
                self.callerSelf.data[2].append(Force)

                if not self.logLess:
                    # logs: t[s], s[m], F[mN]
                    self.callerSelf.measurementLog.writeLog(
                        [time, Position, Force])

            except ValueError:
                # I know this isn't the best way to deal with it, but it works fine (for now)
                pass

        self.endSignal.emit()

        if self.callerSelf.recording:
            self.callerSelf.threadReachedEnd = True
            self.callerSelf.butRecord()

        if self.logLess:
            # self.callerSelf.unsavedData = self.callerSelf.data
            self.callerSelf.enableElement(self.callerSelf.ui.butSave)


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

    def __init__(self, callerSelf: UserInterface) -> None:
        super().__init__()
        self.callerSelf: UserInterface = callerSelf

    def run(self) -> None:
        self.startSignal.emit()
        _skip: list[float] = [self.callerSelf.sensor.ForceFix(self.callerSelf.sensor.SR())
                              for i in range(self.callerSelf.singleReadSkips)]
        forces: list[float] = [self.callerSelf.sensor.ForceFix(
            self.callerSelf.sensor.SR()) for i in range(self.callerSelf.singleReadForces)]
        self.callerSelf.singleReadForce = round(
            sum(forces)/self.callerSelf.singleReadForces,
            ndigits=8
        )
        self.endSignal.emit()


class ForceSensorGUI(QObject, QRunnable):
    errorSignal = Signal()

    def __init__(self, ui: Ui_MainWindow) -> None:
        super().__init__()
        self.ui: Ui_MainWindow = ui
        self.failed: bool = False

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

        self.gaugeRound: int = kwargs.pop("gaugeLines", 6)
        self.gaugeLines: int = kwargs.pop("gaugeLines", 10)
        self.gaugeSkipLines: int = kwargs.pop("gaugeSkipLines", 3)
        self.cmdStart: str = kwargs.pop("cmdStart", "#")
        self.cmdEnd: str = kwargs.pop("cmdEnd", ";")

        self.T0 = perf_counter_ns()

        self.PortName: str = self.ui.setPortName.text().upper()

        ####### PORT INIT ######
        # The 'COM'-port depends on which plug is used at the back of the computer.
        # To find the correct port: go to Windows Settings, Search for Device Manager,
        # and click the tab "Ports (COM&LPT)".
        try:
            self.ser = serial.Serial(self.PortName,
                                     baudrate=self.baudrate,
                                     timeout=self.timeout
                                     )
        except Exception as e:
            self.failed = True
            self.ui.errorMessage = [
                e.__class__.__name__, e.args[0]+"\n\nCheck if Port is not already in use."]
            self.errorSignal.emit()

    def reGauge(self) -> None:
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
            return 0.
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
        if not (returnLine.split(":")[0] == "[ERROR]" and returnLine.split(":")[1] == " movement aborted, home to unlock"):
            self.ui.errorMessage = ["RuntimeError", "RuntimeError", returnLine]
            self.errorSignal.emit()
        elif returnLine.split(":")[0] == "[ERROR]":
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
        returnLine: str = self.ser.read_until().decode().strip()
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
        returnLine: str = self.ser.read_until().decode().strip()
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
        returnLine: str = self.ser.read_until().decode().strip()
        if returnLine.split(":")[0] == "[ERROR]":
            self.errorMessage = ["RuntimeError", "RuntimeError", returnLine]
            self.errorSignal.emit()

    def GP(self) -> int:
        """
        ### Get Position
        Current position set in memory.

        :return: End position if moving, else current position in [mm]
        :rtype: int
        """
        self.ser.flush()
        self.ser.write(f"{self.cmdStart}GP{self.cmdEnd}".encode())
        # if self.stdDelay > 0:
        #     sleep(self.stdDelay)
        returnLine: str = self.ser.read_until().decode().strip()
        if returnLine.split(":")[0] == "[ERROR]":
            self.errorMessage = ["RuntimeError", "RuntimeError", returnLine]
            self.errorSignal.emit()
            return 0
        else:
            try:
                return int(returnLine.split(": ")[-1])
            except Exception as e:
                self.ui.errorMessage = [e.__class__.__name__, e.args[0]]
                self.errorSignal.emit()
                return 0


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
