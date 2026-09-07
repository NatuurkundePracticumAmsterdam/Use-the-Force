# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'DesignerGuiMjolnir.ui'
##
## Created by: Qt User Interface Compiler version 6.11.2
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QCursor,
    QFont, QFontDatabase, QGradient, QIcon,
    QImage, QKeySequence, QLinearGradient, QPainter,
    QPalette, QPixmap, QRadialGradient, QTransform)
from PySide6.QtWidgets import (QAbstractSpinBox, QApplication, QComboBox, QDoubleSpinBox,
    QHBoxLayout, QLabel, QMainWindow, QMenuBar,
    QPushButton, QSizePolicy, QStatusBar, QVBoxLayout,
    QWidget)

from pyqtgraph import PlotWidget

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        if not MainWindow.objectName():
            MainWindow.setObjectName(u"MainWindow")
        MainWindow.resize(800, 600)
        self.centralwidget = QWidget(MainWindow)
        self.centralwidget.setObjectName(u"centralwidget")
        self.verticalLayout = QVBoxLayout(self.centralwidget)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.horizontalLayout_4 = QHBoxLayout()
        self.horizontalLayout_4.setObjectName(u"horizontalLayout_4")
        self.verticalLayout_3 = QVBoxLayout()
        self.verticalLayout_3.setObjectName(u"verticalLayout_3")
        self.DeviceSelectorBox = QComboBox(self.centralwidget)
        self.DeviceSelectorBox.setObjectName(u"DeviceSelectorBox")
        self.DeviceSelectorBox.setEditable(False)

        self.verticalLayout_3.addWidget(self.DeviceSelectorBox)

        self.TareButton = QPushButton(self.centralwidget)
        self.TareButton.setObjectName(u"TareButton")

        self.verticalLayout_3.addWidget(self.TareButton)

        self.CalibrateButton = QPushButton(self.centralwidget)
        self.CalibrateButton.setObjectName(u"CalibrateButton")

        self.verticalLayout_3.addWidget(self.CalibrateButton)

        self.QuickReadButton = QPushButton(self.centralwidget)
        self.QuickReadButton.setObjectName(u"QuickReadButton")

        self.verticalLayout_3.addWidget(self.QuickReadButton)

        self.QuickReadOutputBox = QDoubleSpinBox(self.centralwidget)
        self.QuickReadOutputBox.setObjectName(u"QuickReadOutputBox")
        self.QuickReadOutputBox.setLocale(QLocale(QLocale.English, QLocale.UnitedStates))
        self.QuickReadOutputBox.setFrame(False)
        self.QuickReadOutputBox.setReadOnly(True)
        self.QuickReadOutputBox.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)

        self.verticalLayout_3.addWidget(self.QuickReadOutputBox)


        self.horizontalLayout_4.addLayout(self.verticalLayout_3)

        self.plot_widget = PlotWidget(self.centralwidget)
        self.plot_widget.setObjectName(u"plot_widget")

        self.horizontalLayout_4.addWidget(self.plot_widget)


        self.verticalLayout.addLayout(self.horizontalLayout_4)

        self.horizontalLayout_3 = QHBoxLayout()
        self.horizontalLayout_3.setObjectName(u"horizontalLayout_3")
        self.LongMeasurementLabel = QLabel(self.centralwidget)
        self.LongMeasurementLabel.setObjectName(u"LongMeasurementLabel")

        self.horizontalLayout_3.addWidget(self.LongMeasurementLabel)

        self.MeasureDurationBox = QDoubleSpinBox(self.centralwidget)
        self.MeasureDurationBox.setObjectName(u"MeasureDurationBox")
        self.MeasureDurationBox.setLocale(QLocale(QLocale.English, QLocale.UnitedStates))
        self.MeasureDurationBox.setDecimals(4)
        self.MeasureDurationBox.setMaximum(10000.000000000000000)
        self.MeasureDurationBox.setSingleStep(1.000000000000000)

        self.horizontalLayout_3.addWidget(self.MeasureDurationBox)

        self.RunButton = QPushButton(self.centralwidget)
        self.RunButton.setObjectName(u"RunButton")

        self.horizontalLayout_3.addWidget(self.RunButton)


        self.verticalLayout.addLayout(self.horizontalLayout_3)

        self.horizontalLayout = QHBoxLayout()
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.ShowButton = QPushButton(self.centralwidget)
        self.ShowButton.setObjectName(u"ShowButton")

        self.horizontalLayout.addWidget(self.ShowButton)

        self.SaveButton = QPushButton(self.centralwidget)
        self.SaveButton.setObjectName(u"SaveButton")

        self.horizontalLayout.addWidget(self.SaveButton)

        self.ExitButton = QPushButton(self.centralwidget)
        self.ExitButton.setObjectName(u"ExitButton")

        self.horizontalLayout.addWidget(self.ExitButton)


        self.verticalLayout.addLayout(self.horizontalLayout)

        MainWindow.setCentralWidget(self.centralwidget)
        self.menubar = QMenuBar(MainWindow)
        self.menubar.setObjectName(u"menubar")
        self.menubar.setGeometry(QRect(0, 0, 800, 37))
        MainWindow.setMenuBar(self.menubar)
        self.statusbar = QStatusBar(MainWindow)
        self.statusbar.setObjectName(u"statusbar")
        MainWindow.setStatusBar(self.statusbar)

        self.retranslateUi(MainWindow)

        QMetaObject.connectSlotsByName(MainWindow)
    # setupUi

    def retranslateUi(self, MainWindow):
        MainWindow.setWindowTitle(QCoreApplication.translate("MainWindow", u"MainWindow", None))
        self.DeviceSelectorBox.setCurrentText("")
        self.DeviceSelectorBox.setPlaceholderText(QCoreApplication.translate("MainWindow", u"Device", None))
        self.TareButton.setText(QCoreApplication.translate("MainWindow", u"Tare", None))
        self.CalibrateButton.setText(QCoreApplication.translate("MainWindow", u"Calibrate", None))
        self.QuickReadButton.setText(QCoreApplication.translate("MainWindow", u"Quick Read", None))
        self.LongMeasurementLabel.setText(QCoreApplication.translate("MainWindow", u"Long measurement duration:", None))
        self.MeasureDurationBox.setSuffix(QCoreApplication.translate("MainWindow", u" seconds", None))
        self.RunButton.setText(QCoreApplication.translate("MainWindow", u"Run Long Measurement", None))
        self.ShowButton.setText(QCoreApplication.translate("MainWindow", u"Show Plot", None))
        self.SaveButton.setText(QCoreApplication.translate("MainWindow", u"Save Plot", None))
        self.ExitButton.setText(QCoreApplication.translate("MainWindow", u"Exit", None))
    # retranslateUi

