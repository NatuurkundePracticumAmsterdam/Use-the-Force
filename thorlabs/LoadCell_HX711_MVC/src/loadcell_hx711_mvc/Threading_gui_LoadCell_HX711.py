import csv
import sys
from importlib.metadata import version

import pyqtgraph as pg
from PySide6 import QtWidgets
from PySide6.QtCore import QLocale, Slot
from PySide6.QtWidgets import QInputDialog, QMessageBox

# Allow this script to be run either as a package via "Mjolnir"
# or directly with "python gui_LoadCell_HX711.py".
try:
    from .Threading_ui_Mjolnir_designer import Ui_MainWindow
except ImportError:
    from Threading_ui_Mjolnir_designer import Ui_MainWindow

MJOLNIR_VERSION = version("loadcell-hx711-mvc")

# Needed for threading:
import time

from loadcell_hx711_mvc.Threading_model_LoadCell_HX711 import (
    MjolnirExperiment,
    model_list_resources,
)

# PyQtGraph global options
pg.setConfigOption("background", "w")
pg.setConfigOption("foreground", "k")


class UserInterface(QtWidgets.QMainWindow):
    def __init__(self):
        """Initialize the Mjolnir graphical user interface.
        Set up the user interface, initialize the measurement state, configure
        the plot, populate the device selector, and connect the GUI controls to
        their corresponding methods.
        Initially, no device is connected and measurement-dependent controls
        are disabled."""
        super().__init__()

        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        self.experiment = None  # No experiment has been created yet, you have to connect to a device first. Setting this to None now prevents some problems down the line
        self.connected_device = None  # Keep track of what is connected
        # For the plot that will be made eventually:
        self.times = []
        self.forces = []
        self.io_port_1_readings = []
        self.io_port_2_readings = []

        # To keep track of whether you have a measurement that you are about to override:
        self.has_live_measurement = False  # You do not have any measurement when you open the app for the first time

        # Show an empty plot initially, but have some units and formatting ready
        self.ui.plot_widget.setLabel("bottom", "Time", units="s")
        self.ui.plot_widget.setLabel("left", "Force", units="N")
        self.ui.plot_widget.setTitle("Force vs. Time")

        self.ui.plot_widget.showGrid(x=True, y=True)

        # Show firmware label at the bottom
        self.ui.FirmwareLabel.setText(
            f"Use-the-force Mjolnir {MJOLNIR_VERSION} | No device connected"
        )

        # Add a functionality to the exit button
        self.ui.ExitButton.clicked.connect(self.close)

        # Additional button to refresh all devices: allows you to connect to a device that wasn't plugged in yet (without having to close the gui!)
        self.ui.RefreshDevicesButton.clicked.connect(self.refresh_devices)

        # List resources button:
        # Get all available resources:
        resources = model_list_resources()
        # Fill up the "choose device" menu:
        # Just a filler before you actually select anything (this will be index 0) -> helps with making sure you close a device in use if you switch to a new device
        self.ui.DeviceSelectorBox.addItem("Select device...")
        # Add all real options into the "select device" box
        for resource in resources:
            self.ui.DeviceSelectorBox.addItem(resource)

        # Device selection -- If the index of the DeviceSelectorBox changes (i.e. if you have changed/selected a device), you call the device_selected method
        self.ui.DeviceSelectorBox.currentIndexChanged.connect(self.device_selected)

        # Don't make the Tare, Calibrate, or Quick Read buttons clickable until you have connected to a port
        self.ui.TareButton.setEnabled(False)
        self.ui.CalibrateButton.setEnabled(False)
        self.ui.QuickReadButton.setEnabled(False)
        # Also make the "start measurement", show, and save plots unavailable until you have actually calibrated:
        self.ui.RunButton.setEnabled(False)
        # Also make the "stop measurement" button not show up:
        self.ui.StopButton.setEnabled(False)
        # Don't have the "save plot" button pop up until you have finished running a long measurement:
        self.ui.SaveButton.setEnabled(False)
        # Don't have the "reset view" button pop up until you created a plot:
        self.ui.ResetViewButton.setEnabled(False)
        self.ui.ClearPlot.setEnabled(False)

        # Once tare becomes clickable, it has this feature:
        self.ui.TareButton.clicked.connect(self.tare)

        # Once Quick Read becomes clickable, it has this feature:
        self.ui.QuickReadButton.clicked.connect(self.quick_measure)

        # Once calibrate becomes clickable, it has this feature:
        self.ui.CalibrateButton.clicked.connect(self.calibrate)

        # Clear plots:
        self.ui.ClearPlot.clicked.connect(self.pressed_clear)

        # Once you have calibrated, you can run a long measurement (threading version):
        self.ui.RunButton.clicked.connect(self.start_live_measurement)
        # Once you have run a measurement, you can also stop:
        self.ui.StopButton.clicked.connect(self.stop_live_measurement)

        # # Once a long measurement has been done, you can draw your plot:
        # self.ui.ShowButton.clicked.connect(self.show_plot)

        # Once you have made a nice plot, you can save it:
        self.ui.SaveButton.clicked.connect(self.save_data)

        # Extra button just for fun: reset view for in case you get lost after zooming:
        self.ui.ResetViewButton.clicked.connect(self.reset_view)

    # Implemented the following method for threading:
    @Slot(float, bool, bool)
    def receive_live_measurement(self, force, io_port_1_reading, io_port_2_reading):
        """Receive and store a live measurement and update the plot.

        Args:
        force (float): Measured force.
        io_port_1_reading (bool): State of stage I/O port 1.
        io_port_2_reading (bool): State of stage I/O port 2.

        The elapsed measurement time is calculated relative to the start of
        the measurement. The time, force, and I/O readings are stored, and
        the plot is refreshed."""

        # Update the status: you now have live measurements
        self.has_live_measurement = True

        current_time = time.perf_counter() - self.measurement_start_time

        self.times.append(current_time)
        self.forces.append(force)
        self.io_port_1_readings.append(io_port_1_reading)
        self.io_port_2_readings.append(io_port_2_reading)

        self.show_plot()

    # Implemented for threading:
    @Slot()
    def start_live_measurement(self):
        """Start continuous live measurement in a separate thread.

        If previous measurement data exist, ask the user to confirm before
        overwriting them. Reset the stored data, create the measurement worker,
        connect its measurement signal to the GUI, and start the worker thread.

        Disable controls that should not be used during acquisition and enable
        the stop button.

        Returns:
                None"""

        if self.has_live_measurement:
            reply = QMessageBox.question(
                self,
                "Start new measurement?",
                "Warning: you are about to start a new measurement. "
                "Any previous measurement currently shown will be overwritten. "
                "Would you like to continue?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )

            if reply != QMessageBox.Yes:
                return

        # Reset all previous measurements
        self.times = []
        self.forces = []
        self.io_port_1_readings = []
        self.io_port_2_readings = []

        self.measurement_start_time = time.perf_counter()

        self.live_worker = self.experiment.start_live_measurement()

        self.live_worker.measurement_received.connect(self.receive_live_measurement)

        self.experiment.live_thread.start()

        self.ui.RunButton.setEnabled(False)
        self.ui.TareButton.setEnabled(False)
        self.ui.CalibrateButton.setEnabled(False)
        self.ui.StopButton.setEnabled(True)  # Make the "stop button" available
        self.ui.ClearPlot.setEnabled(False)
        self.ui.ResetViewButton.setEnabled(False)
        self.ui.SaveButton.setEnabled(False)
        self.ui.QuickReadButton.setEnabled(False)

    # Implemented for threading:
    @Slot()
    def stop_live_measurement(self):
        """Stop live measurement and restore the relevant GUI controls.

        Wait for the measurement worker and its thread to finish, then re-enable
        the controls that can be used after acquisition.

        Returns:
        None"""
        self.experiment.stop_live_measurement()
        self.ui.RunButton.setEnabled(True)
        self.ui.StopButton.setEnabled(False)
        self.ui.TareButton.setEnabled(True)
        self.ui.CalibrateButton.setEnabled(True)
        self.ui.ResetViewButton.setEnabled(True)
        self.ui.ClearPlot.setEnabled(True)
        self.ui.SaveButton.setEnabled(True)
        self.ui.QuickReadButton.setEnabled(True)

    @Slot()
    def refresh_devices(self):
        """Refresh the list of available Arduino devices.

        Update the device selector with the currently available VISA resources.
        Preserve the current selection if the connected device remains available.

        If the connected device is no longer available, close its connection,
        reset the GUI state, and clear the stored measurement data.

        Returns:
        None"""
        # A method that allows the user to look for new devices that weren't plugged in when the GUI was started up:
        resources = model_list_resources()

        # Define what we're currently connected to (if anything)
        current_device = self.ui.DeviceSelectorBox.currentText()

        # Need to now make sure that if we find a new device, that we don't end up triggering the DeviceSelectorBox "index changed" signal.
        # This blocks signals that might be triggered by editing the list in the DeviceSelectorBox:
        self.ui.DeviceSelectorBox.blockSignals(True)

        # If we were connected to a device, but it is no longer available,
        # close the old connection and reset the GUI.
        # if self.experiment is not None means that an instance of MjolnirExperiment was made at some point. It could be that, at some point, it was plugged out, and so it cannot be found in the resource list anymore. In that case:
        if self.experiment is not None and current_device not in resources:
            self.experiment.stop_live_measurement()
            self.experiment.close()  # Close the connection that you had
            self.experiment = None  # Set the experiment state to None (because we are _not_ connected to anything right now)
            self.connected_device = None

            self.ui.FirmwareLabel.setText(
                f"Use-the-force Mjolnir {MJOLNIR_VERSION} | No device connected"
            )

            # Reset all buttons:
            self.ui.TareButton.setEnabled(False)
            self.ui.QuickReadButton.setEnabled(False)
            self.ui.CalibrateButton.setEnabled(False)
            self.ui.RunButton.setEnabled(False)
            self.ui.StopButton.setEnabled(False)  # New button for threading
            self.ui.SaveButton.setEnabled(False)
            self.ui.ResetViewButton.setEnabled(False)

            # Reset any measurements that may have happened
            self.times = []
            self.forces = []
            self.io_port_1_readings = []
            self.io_port_2_readings = []

            self.has_live_measurement = False
            self.ui.plot_widget.clear()

        # Now to update the list:
        # Empty out the box and remove all possible selections:
        self.ui.DeviceSelectorBox.clear()
        # Now manually add the first "Select device..." option in again"
        self.ui.DeviceSelectorBox.addItem("Select device...")

        # Now add all resources into the list again
        for resource in resources:
            self.ui.DeviceSelectorBox.addItem(resource)

        # If you were already connected to a device when clicking "refresh", this makes sure you stay connected (visually, at least)
        if current_device in resources:
            self.ui.DeviceSelectorBox.setCurrentText(current_device)
        else:
            self.ui.DeviceSelectorBox.setCurrentIndex(0)

        # Now that all devices (and potentially a new device!) have been added to the list, we can unblock the signals and let the trigger work as intended:
        self.ui.DeviceSelectorBox.blockSignals(False)

    def closeEvent(self, event):  # closeEvent is a special Qt event-handler method
        """Handle the window-close event.

        Stop any live measurement, close the Arduino connection if a device is
        connected, and accept the close event.

        Args:
        event (QCloseEvent): Qt close event triggered when the window closes.

        Returns:
        None"""
        if self.experiment is not None:
            # If you have triggered closeEvent, and you _do_ currently have a device connected, you will close the connection to the device
            self.experiment.stop_live_measurement()  # Implemented for threading
            self.experiment.close()

        event.accept()

    @Slot()
    def reset_view(self):
        """Reset the plot axes to automatically fit the displayed data.

        Returns:
        None"""
        # Reset the axes to what they were initially:
        self.ui.plot_widget.autoRange()

    @Slot()
    def save_data(self):
        """Save the current measurement data to a CSV file.

        Ask the user for an optional comment and a destination filename.
        If the user cancels either dialog, do not save the file.

        Ensure that the filename has a .csv extension and write the comment,
        column headers, elapsed times, measured forces, and both stage I/O
        readings to the file.

        Returns:
        None"""

        # Ask the user for an optional comment to include in the CSV.
        comment, accepted = QInputDialog.getText(
            self,
            "Measurement comments",
            "Enter an optional comment for this measurement: (leave blank if you don't want to write anything)",
        )
        if not accepted:
            return

        filename, _ = (
            QtWidgets.QFileDialog.getSaveFileName(  # this getSaveFileName returns two things, a filename and a filter. We don't need the filter for anything, so just assign that to a throwaway variable underscore (_)
                self,
                "Save measurement",
                "",
                "CSV files (*.csv)",
            )
        )  # The user will get a pop up box that allows them to select where they want to save the csv

        if filename:  # Very important, because if the user decides to close the window, you might get an issue because it will try to save with no filename
            if not filename.lower().endswith(
                ".csv"
            ):  # Automatically puts .csv into the filename if the user had not done that themselves already
                filename += ".csv"

            with open(filename, "w", newline="", encoding="utf-8") as csvfile:
                writer = csv.writer(csvfile)

                # Write the optional comment as the first row.
                writer.writerow([comment])

                # Four columns: time, force, moving (yes/no) (per IO port)
                writer.writerow(
                    ["Time_s", "Force_N", "IO_port_1_reading", "IO_port_2_reading"]
                )

                for time_s, force_n, io_port_1, io_port_2 in zip(
                    self.times,
                    self.forces,
                    self.io_port_1_readings,
                    self.io_port_2_readings,
                ):
                    writer.writerow([time_s, force_n, io_port_1, io_port_2])

    @Slot()
    def show_plot(self):
        """Update the plot with the stored force measurements.

        Display force as a function of elapsed time using individual data
        points, clear the previous plot contents, and automatically adjust
        the axes to fit the data.

        Returns:
        None"""

        self.ui.plot_widget.clear()

        # Plot dots:
        self.ui.plot_widget.plot(
            self.times,
            self.forces,
            pen=None,
            symbol="o",
            symbolSize=8,
            symbolBrush="b",
        )

        # Set the axes to the automatically determined range
        self.ui.plot_widget.autoRange()

    # This activates once you click a port in the "select device" dropdown menu
    @Slot()
    def device_selected(self):
        """Handle changes to the selected Arduino device.

        Connect to the newly selected device or disconnect from the current
        device if the placeholder option is selected. If a measurement exists,
        ask the user to confirm before discarding it when switching or
        disconnecting.

        Update the firmware label, clear measurement data when appropriate,
        and enable or disable controls according to the connection state.

        Returns:
        None"""

        # If "Select device..." is selected
        if self.ui.DeviceSelectorBox.currentIndex() == 0:
            if self.experiment is not None:
                # Warn if there is measurement data that would be deleted
                if self.has_live_measurement:
                    reply = QMessageBox.question(
                        self,
                        "Disconnect device?",
                        "Warning: disconnecting the device will delete the current "
                        "measurement from the application. Would you like to continue?",
                        QMessageBox.Yes | QMessageBox.No,
                        QMessageBox.No,
                    )

                    if reply != QMessageBox.Yes:
                        # Restore the currently connected device
                        self.ui.DeviceSelectorBox.blockSignals(True)
                        self.ui.DeviceSelectorBox.setCurrentText(self.connected_device)
                        self.ui.DeviceSelectorBox.blockSignals(False)
                        return

                self.experiment.stop_live_measurement()
                self.experiment.close()
                self.experiment = None
                self.connected_device = None

            self.ui.FirmwareLabel.setText(
                f"Use-the-force Mjolnir {MJOLNIR_VERSION} | No device connected"
            )

            # Reset all buttons
            self.ui.TareButton.setEnabled(False)
            self.ui.QuickReadButton.setEnabled(False)
            self.ui.CalibrateButton.setEnabled(False)
            self.ui.RunButton.setEnabled(False)
            self.ui.StopButton.setEnabled(False)
            self.ui.SaveButton.setEnabled(False)
            self.ui.ResetViewButton.setEnabled(False)

            # Reset measurement data
            self.times = []
            self.forces = []
            self.io_port_1_readings = []
            self.io_port_2_readings = []
            self.has_live_measurement = False

            return

        # A real device has been selected.
        # If another device is already connected, ask before switching.
        if self.experiment is not None:
            if self.has_live_measurement:
                reply = QMessageBox.question(
                    self,
                    "Change device?",
                    "Warning: changing the connected device will delete the current "
                    "measurement from the application. Would you like to continue?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No,
                )

                if reply != QMessageBox.Yes:
                    # Restore the currently connected device
                    self.ui.DeviceSelectorBox.blockSignals(True)
                    self.ui.DeviceSelectorBox.setCurrentText(self.connected_device)
                    self.ui.DeviceSelectorBox.blockSignals(False)
                    return

            self.experiment.stop_live_measurement()
            self.experiment.close()
            self.experiment = None
            self.connected_device = None

            # Reset all buttons
            self.ui.TareButton.setEnabled(False)
            self.ui.QuickReadButton.setEnabled(False)
            self.ui.CalibrateButton.setEnabled(False)
            self.ui.RunButton.setEnabled(False)
            self.ui.StopButton.setEnabled(False)
            self.ui.SaveButton.setEnabled(False)
            self.ui.ResetViewButton.setEnabled(False)

            # Reset measurement data
            self.times = []
            self.forces = []
            self.io_port_1_readings = []
            self.io_port_2_readings = []
            self.has_live_measurement = False
            self.ui.plot_widget.clear()

        # Connect to the newly selected device
        portname = self.ui.DeviceSelectorBox.currentText()

        self.experiment = MjolnirExperiment(portname)

        # Remember which device is currently connected
        self.connected_device = portname

        # Show the firmware version
        self.ui.FirmwareLabel.setText(
            f"Use-the-force Mjolnir {MJOLNIR_VERSION} | "
            f"{self.experiment.device_identification}"
        )

        # Make the device-specific buttons available
        self.ui.TareButton.setEnabled(True)
        self.ui.QuickReadButton.setEnabled(True)
        self.ui.CalibrateButton.setEnabled(True)

        # Confirm successful connection
        QtWidgets.QMessageBox.information(
            self,
            "Connect device complete",
            "You have successfully connected to a device. Happy measuring!",
        )

    @Slot()
    def pressed_clear(self):
        """Clear the current measurement and its plot.

        If measurement data exist, ask the user to confirm before deleting
        them. If confirmed, clear the stored times, forces, and I/O readings,
        reset the measurement state, and disable controls that require
        measurement data.

        Returns:
        None"""

        if self.has_live_measurement:
            reply = QMessageBox.question(
                self,
                "Clear measurement?",
                "Warning: clearing the plot will delete the current measurement "
                "from the application. Would you like to continue?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )

            if reply != QMessageBox.Yes:
                return

        # Clear all measurement data
        self.times = []
        self.forces = []
        self.io_port_1_readings = []
        self.io_port_2_readings = []

        # There is no longer a measurement to overwrite
        self.has_live_measurement = False

        self.ui.plot_widget.clear()
        self.ui.ResetViewButton.setEnabled(False)
        # Disable the ability to save if you can't see the plot:
        self.ui.SaveButton.setEnabled(False)
        # This is mainly implemented because a user might forget what they are storing, and therefore confuse measurements. Better to be able to see what you're saving before you actually save it

    @Slot()
    def tare(self):
        """Tare the load cell and notify the user when the operation finishes.

        Returns:
        None"""
        self.experiment.tare()

        # Have a little dialog box pop up when the tare has completed successfully:
        QtWidgets.QMessageBox.information(
            self,
            "Tare complete",
            "Tare completed successfully.",
        )

    @Slot()
    def quick_measure(self):
        """Acquire a single force measurement and display the result.

        Read the next available measurement from the load cell and display
        the measured force in the quick-read output box.

        Returns:
        None"""
        result, io_port_1_reading, io_port_2_reading = (
            self.experiment.take_single_measurement()
        )
        self.ui.QuickReadOutputBox.setValue(result)

    @Slot()
    def calibrate(self):
        """Calibrate the load cell using a reference force.

        Prompt the user to enter the known force exerted by a
        reference object, expressed in newtons. Send the value to the experiment
        for calibration.

        If calibration succeeds, display the reference force and enable
        continuous measurement. Otherwise, display a warning.

        Returns:
        None"""

        # Make a dialog box that pops up when you click calibrate
        dialog = QInputDialog(self)
        dialog.setDoubleRange(0.0, 1000000.0)  # Some arbitrary range
        # Allow users to type up to 6 decimals, though the load cell definitely does not have this sensitivty. Better to keep it at much fewer decimals than 6:
        dialog.setDoubleDecimals(6)
        dialog.setWindowTitle("Calibration")
        dialog.setLabelText(
            "Place a reference load on the sensor and enter the reference force in Newton:"
        )
        dialog.setInputMode(QInputDialog.DoubleInput)
        dialog.setDoubleValue(0.0)  # Default value in input box

        # Make it so that decimals are separated using a dot instead of a comma! Important for (language) consistency:
        dialog.setLocale(QLocale(QLocale.English, QLocale.UnitedStates))

        if dialog.exec():
            reference_force = dialog.doubleValue()

            response = self.experiment.calibrate(reference_force)

            # If calibration is successful, the Arduino print out "CALIBRATION COMPLETE" onto Serial Monitor. Can use this confirmation here as well
            # Use strip() to make sure that any trailing newlines or spaces do not cause problems
            if response.strip() == "CALIBRATION COMPLETE":
                # If calibration was successful, display the value that was used to calibrate:
                self.ui.ReferenceValueBox.setValue(reference_force)
                # Now enable the run button so the user can run a long measurement:
                self.ui.RunButton.setEnabled(True)
                self.ui.StopButton.setEnabled(False)
                # Pop up message saying you have successfully connected to a device
                QtWidgets.QMessageBox.information(
                    self,
                    "Calibration complete",
                    "You have successfully Calibrated the device. You can now perform long measurements.",
                )

            # If the calibration failed for whatever reason, return a warning message
            else:
                QtWidgets.QMessageBox.warning(
                    self,
                    "Calibration failed",
                    "The load cell could not be calibrated.",
                )


def main():
    """Launch the Mjolnir graphical user interface.

    Create the Qt application, initialize and display the main window,
    and start the application's event loop.

    Returns:
    None"""
    app = QtWidgets.QApplication(sys.argv)
    ui = UserInterface()
    ui.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
