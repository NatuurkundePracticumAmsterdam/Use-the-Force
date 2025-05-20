# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'error_ui.ui'
##
## Created by: Qt User Interface Compiler version 6.8.2
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
from PySide6.QtWidgets import (QAbstractButton, QApplication, QDialog, QDialogButtonBox,
    QLabel, QLayout, QSizePolicy, QVBoxLayout,
    QWidget)

__all__ = [
    "Ui_errorWindow"
]

class Ui_errorWindow(object):
    def setupUi(self, errorWindow):
        if not errorWindow.objectName():
            errorWindow.setObjectName(u"errorWindow")
        errorWindow.setWindowModality(Qt.WindowModality.WindowModal)
        
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(10)
        sizePolicy.setHeightForWidth(errorWindow.sizePolicy().hasHeightForWidth())
        errorWindow.setSizePolicy(sizePolicy)
        errorWindow.setMinimumSize(QSize(400, 100))
        errorWindow.setSizeIncrement(QSize(0, 20))
        errorWindow.setBaseSize(QSize(400, 100))
        errorWindow.setWindowOpacity(1.000000000000000)
        self.verticalLayoutWidget = QWidget(errorWindow)
        self.verticalLayoutWidget.setObjectName(u"verticalLayoutWidget")
        self.verticalLayoutWidget.setGeometry(QRect(-1, 9, 401, 92))
        self.verticalLayout = QVBoxLayout(self.verticalLayoutWidget)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        self.verticalLayout.setContentsMargins(10, 0, 10, 0)
        self.ErrorText = QLabel(self.verticalLayoutWidget)
        self.ErrorText.setObjectName(u"ErrorText")
        self.ErrorText.setEnabled(True)
        sizePolicy1 = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.ErrorText.sizePolicy().hasHeightForWidth())
        self.ErrorText.setSizePolicy(sizePolicy1)
        self.ErrorText.setSizeIncrement(QSize(0, 20))
        self.ErrorText.setTextFormat(Qt.TextFormat.RichText)
        self.ErrorText.setScaledContents(True)
        self.ErrorText.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ErrorText.setWordWrap(True)

        self.verticalLayout.addWidget(self.ErrorText)

        self.ErrorButtons = QDialogButtonBox(self.verticalLayoutWidget)
        self.ErrorButtons.setObjectName(u"ErrorButtons")
        sizePolicy2 = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        sizePolicy2.setHorizontalStretch(0)
        sizePolicy2.setVerticalStretch(0)
        sizePolicy2.setHeightForWidth(self.ErrorButtons.sizePolicy().hasHeightForWidth())
        self.ErrorButtons.setSizePolicy(sizePolicy2)
        self.ErrorButtons.setSizeIncrement(QSize(0, 0))
        self.ErrorButtons.setOrientation(Qt.Orientation.Horizontal)
        self.ErrorButtons.setStandardButtons(QDialogButtonBox.StandardButton.Cancel|QDialogButtonBox.StandardButton.Ok)
        self.ErrorButtons.setCenterButtons(False)

        self.verticalLayout.addWidget(self.ErrorButtons)

        self.verticalLayout.setStretch(1, 2000)

        self.retranslateUi(errorWindow)
        self.ErrorButtons.accepted.connect(errorWindow.accept)
        self.ErrorButtons.rejected.connect(errorWindow.reject)

        QMetaObject.connectSlotsByName(errorWindow)
    # setupUi

    def retranslateUi(self, errorWindow):
        errorWindow.setWindowTitle(QCoreApplication.translate("errorWindow", u"An Error Occured", None))
        self.ErrorText.setText(QCoreApplication.translate("errorWindow", u"<html><head/><body><p><span style=\" font-weight:700;\">An Error Occured...</span></p><p>An error occured so badly that the error message never loaded.</p></body></html>", None))
    # retranslateUi

