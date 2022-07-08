#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
ProjDataVisualisationUI.py
"""

import stir
from PyQt5.QtCore import QDateTime, Qt, QTimer
from PyQt5.QtWidgets import (QApplication, QCheckBox, QComboBox, QDateTimeEdit,
                             QDial, QDialog, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
                             QRadioButton, QPushButton, QScrollBar, QSizePolicy,
                             QSlider, QSpinBox, QStyleFactory, QTableWidget, QTabWidget, QTextEdit,
                             QVBoxLayout, QWidget)

from ProjDataVisualisationBackend import ProjDataVisualisationBackend


class WidgetGallery(QDialog):
    def __init__(self, parent=None):
        super(WidgetGallery, self).__init__(parent)

        self.originalPalette = QApplication.palette()

        ### Backend ###
        self.stir_interface = ProjDataVisualisationBackend(sys.argv)

        styleComboBox = QComboBox()
        styleComboBox.addItems(QStyleFactory.keys())

        styleLabel = QLabel("&Style:")
        styleLabel.setBuddy(styleComboBox)

        self.useStylePaletteCheckBox = QCheckBox("&Use style's standard palette")
        self.useStylePaletteCheckBox.setChecked(True)

        # disableWidgetsCheckBox = QCheckBox("&Disable widgets")

        self.createTopLeftGroupBox()
        self.createTopRightGroupBox()
        self.createBottomLeftGroupBox()

        styleComboBox.textActivated.connect(self.changeStyle)
        self.useStylePaletteCheckBox.toggled.connect(self.changePalette)

        topLayout = QHBoxLayout()
        topLayout.addStretch(1)

        mainLayout = QGridLayout()
        mainLayout.addLayout(topLayout, 0, 0, 1, 5)
        mainLayout.addWidget(self.topLeftGroupBox, 1, 0)
        mainLayout.addWidget(self.topRightGroupBox, 1, 1)
        # mainLayout.addWidget(self.bottomLeftTabWidget, 2, 0)
        mainLayout.addWidget(self.bottomLeftGroupBox, 2, 0)
        mainLayout.setRowStretch(1, 1)
        mainLayout.setRowStretch(2, 1)
        mainLayout.setColumnStretch(0, 1)
        mainLayout.setColumnStretch(1, 1)
        self.setLayout(mainLayout)

        self.changeStyle('Fusion')

    def changeStyle(self, styleName):
        QApplication.setStyle(QStyleFactory.create(styleName))
        self.changePalette()

    def changePalette(self):
        if (self.useStylePaletteCheckBox.isChecked()):
            QApplication.setPalette(QApplication.style().standardPalette())
        else:
            QApplication.setPalette(self.originalPalette)

    def createTopLeftGroupBox(self):
        self.topLeftGroupBox = QGroupBox("FileName")

        # Creation group box entries
        filenameLabel = QLabel(f"Filename:\n{self.stir_interface.proj_data_filename}")

        gramTypeLabel = QLabel(f"Type of 2D data:")
        radioButtonSinogram = QRadioButton("Sinogram")
        radioButtonViewgram = QRadioButton("Viewgram")
        # radioButton3 = QRadioButton("Radio button 3")
        radioButtonSinogram.setChecked(True)

        # Configure Layout
        layout = QVBoxLayout()
        layout.addWidget(filenameLabel)

        layout.addWidget(gramTypeLabel)
        layout.addWidget(radioButtonSinogram)
        layout.addWidget(radioButtonViewgram)
        # layout.addWidget(radioButton3)

        layout.addStretch(1)
        self.topLeftGroupBox.setLayout(layout)

    def createTopRightGroupBox(self):
        self.topRightGroupBox = QGroupBox("Group 2")

        defaultPushButton = QPushButton("Default Push Button")
        defaultPushButton.setDefault(True)

        togglePushButton = QPushButton("Toggle Push Button")
        togglePushButton.setCheckable(True)
        togglePushButton.setChecked(True)

        flatPushButton = QPushButton("Flat Push Button")
        flatPushButton.setFlat(True)

        layout = QVBoxLayout()
        layout.addWidget(defaultPushButton)
        layout.addWidget(togglePushButton)
        layout.addWidget(flatPushButton)
        layout.addStretch(1)
        self.topRightGroupBox.setLayout(layout)

    def createBottomLeftGroupBox(self):
        self.bottomLeftGroupBox = QGroupBox("Sinogram Positions")

        # lineEdit = QLineEdit('s3cRe7')
        # lineEdit.setEchoMode(QLineEdit.EchoMode.Password)

        #### AXIAL POSITION ####
        max_axial_pos = self.stir_interface.proj_data.get_num_axial_poss(0) - 1
        axialPossSpinBoxLabel = QLabel(f"Axial position: {0, max_axial_pos}")
        self.spinBoxAxialPoss = QSpinBox(self.bottomLeftGroupBox)
        self.spinBoxAxialPoss.setRange(0, max_axial_pos)
        self.spinBoxAxialPoss.setValue(max_axial_pos // 2)
        self.spinBoxAxialPoss.valueChanged.connect(self.axialPossSpinBoxChanged)

        self.axial_poss_slider = QSlider(Qt.Orientation.Horizontal, self.bottomLeftGroupBox)
        self.axial_poss_slider.setRange(0, max_axial_pos)
        self.axial_poss_slider.setValue(self.spinBoxAxialPoss.value())
        self.axial_poss_slider.setTickPosition(QSlider.TicksBelow)
        self.axial_poss_slider.valueChanged.connect(self.axialPossSliderChanged)

        #### TANGENTIAL POSITION ####
        max_tangential_pos = self.stir_interface.proj_data.get_num_tangential_poss() - 1
        self.tangentialPossSpinBoxLabel = QLabel(f"Tangential position: {0, max_tangential_pos}")
        self.spinBoxTangentialPoss = QSpinBox(self.bottomLeftGroupBox)
        self.spinBoxTangentialPoss.setRange(0, max_tangential_pos)
        self.spinBoxTangentialPoss.setValue(max_tangential_pos // 2)
        self.spinBoxTangentialPoss.valueChanged.connect(self.tangentialPossSpinBoxChanged)

        self.tangential_poss_slider = QSlider(Qt.Orientation.Horizontal, self.bottomLeftGroupBox)
        self.tangential_poss_slider.setRange(0, max_tangential_pos)
        self.tangential_poss_slider.setValue(self.spinBoxTangentialPoss.value())
        self.tangential_poss_slider.setTickPosition(QSlider.TicksBelow)
        self.tangential_poss_slider.valueChanged.connect(self.tangentialPossSliderChanged)

        # dateTimeEdit = QDateTimeEdit(self.bottomLeftGroupBox)
        # dateTimeEdit.setDateTime(QDateTime.currentDateTime())

        defaultPushButton = QPushButton("Show Sinogram")
        defaultPushButton.setDefault(True)

        ##### LAYOUT ####
        layout = QGridLayout()
        # layout.addWidget(lineEdit, 0, 0, 1, 2)

        layout.addWidget(axialPossSpinBoxLabel, 0, 0, 1, 1)
        layout.addWidget(self.axial_poss_slider, 1, 0, 1, 1)
        layout.addWidget(self.spinBoxAxialPoss, 1, 1, 1, 1)

        #
        layout.addWidget(self.tangentialPossSpinBoxLabel, 2, 0, 1, 1)
        layout.addWidget(self.tangential_poss_slider, 3, 0, 1, 1)
        layout.addWidget(self.spinBoxTangentialPoss, 3, 1, 1, 1)

        layout.addWidget(defaultPushButton)

        layout.setRowStretch(5, 1)
        self.bottomLeftGroupBox.setLayout(layout)

    def axialPossSliderChanged(self):
        self.spinBoxAxialPoss.setValue(self.axial_poss_slider.value())

    def axialPossSpinBoxChanged(self):
        self.axial_poss_slider.setValue(self.spinBoxAxialPoss.value())

    def tangentialPossSliderChanged(self):
        self.spinBoxTangentialPoss.setValue(self.tangential_poss_slider.value())

    def tangentialPossSpinBoxChanged(self):
        self.tangential_poss_slider.setValue(self.spinBoxTangentialPoss.value())


if __name__ == '__main__':
    import sys

    app = QApplication(sys.argv)
    gallery = WidgetGallery()
    gallery.show()
    sys.exit(app.exec())
