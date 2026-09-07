import sys

import pyqtgraph as pg
from PySide6 import QtWidgets
from PySide6.QtCore import Slot
from ui_Mjolnir_designer import Ui_MainWindow

# PyQtGraph global options
pg.setConfigOption("background", "w")
pg.setConfigOption("foreground", "k")


class UserInterface(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()

        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        # Make a plot widget:
        self.plot_widet = pg.PlotWidget()


def main():
    app = QtWidgets.QApplication(sys.argv)
    ui = UserInterface()
    ui.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
