import csv
import sys
from importlib.metadata import version

import pyqtgraph as pg
from PySide6 import QtWidgets
from PySide6.QtCore import Slot
from PySide6.QtWidgets import QInputDialog

# Allow this script to be run either as a package via "Mjolnir"
# or directly with "python gui_LoadCell_HX711.py".
try:
    from .ui_Mjolnir_designer import Ui_MainWindow
except ImportError:
    from ui_Mjolnir_designer import Ui_MainWindow

MJOLNIR_VERSION = version("loadcell-hx711-mvc")

from loadcell_hx711_mvc.model_LoadCell_HX711 import (
    MjolnirExperiment,
    model_list_resources,
)

# PyQtGraph global options
pg.setConfigOption("background", "w")
pg.setConfigOption("foreground", "k")


class UserInterface(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()

        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        self.experiment = None  # No experiment has been created yet, you have to connect to a device first. Setting this to None now prevents some problems down the line
        # For the plot that will be made eventually:
        self.times = None
        self.forces = None

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
        # Also make the "run long measurement", show, and save plots unavailable until you have actually calibrated:
        self.ui.RunButton.setEnabled(False)
        # Don't have the "save plot" button pop up until you have finished running a long measurement:
        self.ui.SaveButton.setEnabled(False)
        # Don't have the "show plot" button pop up until you have created a plot:
        self.ui.ShowButton.setEnabled(False)
        # Don't have the "reset view" button pop up until you created a plot:
        self.ui.ResetViewButton.setEnabled(False)

        # Once tare becomes clickable, it has this feature:
        self.ui.TareButton.clicked.connect(self.tare)

        # Once Quick Read becomes clickable, it has this feature:
        self.ui.QuickReadButton.clicked.connect(self.quick_measure)

        # Once calibrate becomes clickable, it has this feature:
        self.ui.CalibrateButton.clicked.connect(self.calibrate)

        # Clear plots:
        self.ui.ClearPlot.clicked.connect(self.pressed_clear)

        # Once you have calibrated, you can run a long measurement:
        self.ui.RunButton.clicked.connect(self.run_measurement)

        # Once a long measurement has been done, you can draw your plot:
        self.ui.ShowButton.clicked.connect(self.show_plot)

        # Once you have made a nice plot, you can save it:
        self.ui.SaveButton.clicked.connect(self.save_data)

        # Extra button just for fun: reset view for in case you get lost after zooming:
        self.ui.ResetViewButton.clicked.connect(self.reset_view)

    @Slot()
    def refresh_devices(self):
        """Refresh the list of available devices."""
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
            self.experiment.close()  # Close the connection that you had
            self.experiment = None  # Set the experiment state to None (because we are _not_ connected to anything right now)

            self.ui.FirmwareLabel.setText(
                f"Use-the-force Mjolnir {MJOLNIR_VERSION} | No device connected"
            )

            # Reset all buttons:
            self.ui.TareButton.setEnabled(False)
            self.ui.QuickReadButton.setEnabled(False)
            self.ui.CalibrateButton.setEnabled(False)
            self.ui.RunButton.setEnabled(False)
            self.ui.SaveButton.setEnabled(False)
            self.ui.ShowButton.setEnabled(False)
            self.ui.ResetViewButton.setEnabled(False)

            # Reset any measurements that may have happened
            self.times = None
            self.forces = None

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
        """Close the Arduino connection when Mjolnir exits."""
        if self.experiment is not None:
            # If you have triggered closeEvent, and you _do_ currently have a device connected, you will close the connection to the device
            self.experiment.close()

        event.accept()

    @Slot()
    def reset_view(self):
        """For if you have zoomed around too much and don't know how to get back"""
        # Reset the axes to what they were initially:
        self.ui.plot_widget.autoRange()

    @Slot()
    def save_data(self):
        """Save the most recent measurement as a CSV file."""

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

                writer.writerow(["Time_s", "Force_N"])  # Two columns: time and force

                for time_s, force_n in zip(self.times, self.forces):
                    writer.writerow([time_s, force_n])

    @Slot()
    def show_plot(self):
        """Display the most recent force measurement as a function of time."""

        self.ui.plot_widget.clear()

        self.ui.plot_widget.plot(
            self.times,
            self.forces,
        )

        # Set the axes to the automatically determined range
        self.ui.plot_widget.autoRange()

        # If you have plotted something, you are allowed to save/reset the view:
        self.ui.SaveButton.setEnabled(True)
        self.ui.ResetViewButton.setEnabled(True)

    # This activates once you click a port in the "select device" dropdown menu
    @Slot()
    def device_selected(self):
        """After clicking "select a device", you actually connect to the Arduino and create an instance of MjolnirExperiment"""
        if self.ui.DeviceSelectorBox.currentIndex() == 0:
            # If index is 0, it means that you are still on "select device..." and have not selected anything yet
            if self.experiment is not None:
                # This happens if you had selected something earlier but then clicked on "select device..." again afterwards. You close your connection to the device
                self.experiment.close()
                self.experiment = None

            self.ui.FirmwareLabel.setText(
                f"Use-the-force Mjolnir {MJOLNIR_VERSION} | No device connected"
            )

            # Reset all buttons:
            self.ui.TareButton.setEnabled(False)
            self.ui.QuickReadButton.setEnabled(False)
            self.ui.CalibrateButton.setEnabled(False)
            self.ui.RunButton.setEnabled(False)
            self.ui.SaveButton.setEnabled(False)
            self.ui.ShowButton.setEnabled(False)
            self.ui.ResetViewButton.setEnabled(False)

            # Reset any measurements that may have happened
            self.times = None
            self.forces = None

            return

        # If another device is already connected, close its connection first:
        if self.experiment is not None:
            self.experiment.close()
            # Reset all buttons:
            self.ui.TareButton.setEnabled(False)
            self.ui.QuickReadButton.setEnabled(False)
            self.ui.CalibrateButton.setEnabled(False)
            self.ui.RunButton.setEnabled(False)
            self.ui.SaveButton.setEnabled(False)
            self.ui.ShowButton.setEnabled(False)
            self.ui.ResetViewButton.setEnabled(False)
            # Reset any measurements that may have happened
            self.times = None
            self.forces = None

        # Now we can read out the port of the new device and start a fresh connection, with no other (older) devices connected
        portname = self.ui.DeviceSelectorBox.currentText()

        # Create an instance of MjolnirExperiment (i.e.: connect to the Arduino)
        self.experiment = MjolnirExperiment(portname)

        # Print the firmware version in the label
        self.ui.FirmwareLabel.setText(
            f"Use-the-force Mjolnir {MJOLNIR_VERSION} | "
            f"{self.experiment.device_identification}"
        )

        # Make the Tare, Quick Read, and Calibrate buttons clickable
        self.ui.TareButton.setEnabled(True)
        self.ui.QuickReadButton.setEnabled(True)
        self.ui.CalibrateButton.setEnabled(True)

    @Slot()
    def run_measurement(self):
        """Perform a measurement over the requested duration.
        The input time duration is in seconds"""
        duration = self.ui.MeasureDurationBox.value()

        self.times, self.forces = (
            self.experiment.measure_over_time_with_single_measurements(duration)
        )

        # A measurement has now been completed, so the plot can be shown
        self.ui.ShowButton.setEnabled(True)

    @Slot()
    def pressed_clear(self):
        """Clear the displayed plot."""
        self.ui.plot_widget.clear()
        self.ui.ResetViewButton.setEnabled(False)
        # Disable the ability to save if you can't see the plot:
        self.ui.SaveButton.setEnabled(False)
        # This is mainly implemented because a user might forget what they are storing, and therefore confuse measurements. Better to be able to see what you're saving before you actually save it

    @Slot()
    def tare(self):
        """Tare the Arduino using the MjolnirExperiment class"""
        self.experiment.tare()

    @Slot()
    def quick_measure(self):
        """Perform a quick instantaneous measurement. The units returned by this are the same units as the calibration factor that was used"""
        result = self.experiment.take_single_measurement()
        self.ui.QuickReadOutputBox.setValue(result)

    @Slot()
    def calibrate(self):
        """Calibrate the sensor. You do this by placing an object with a known weight (gravitational force) onto the sensor and typing in the force of the reference object"""
        reference_force, ok = QInputDialog.getDouble(
            self,
            "Calibration",
            "Place a reference load on the sensor and enter the reference force in Newton:",
        )

        if ok:
            response = self.experiment.calibrate(reference_force)

            if (  # If calibration is successful, the Arduino print out "CALIBRATION COMPLETE" onto Serial Monitor. Can use this confirmation here as well
                response.strip()
                == "CALIBRATION COMPLETE"  # Can change this in controller so that it just returns something like "True" or something
            ):  # Using .strip() here to make sure that any trailing newlines do not cause problems
                # If calibration was successful, display the value used
                self.ui.ReferenceValueBox.setValue(reference_force)

                # Now that the calibration has happened successfully, the user can run a long measurement:
                self.ui.RunButton.setEnabled(True)
            else:  # This happens if calibration were to fail somehow
                QtWidgets.QMessageBox.warning(
                    self,
                    "Calibration failed",
                    "The load cell could not be calibrated.",
                )


def main():
    app = QtWidgets.QApplication(sys.argv)
    ui = UserInterface()
    ui.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
