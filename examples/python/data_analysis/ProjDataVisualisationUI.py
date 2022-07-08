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

        self.configure_backend()

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

    def configure_backend(self):
        ### Backend ###
        self.stir_interface = ProjDataVisualisationBackend(sys.argv)
        self.stir_interface.refresh_segment_data(0)

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

        #### AXIAL POSITION ####
        max_axial_pos = self.stir_interface.proj_data_stream.get_num_axial_poss(0) - 1
        self.axialPossLabel = QLabel(f"Axial position: {0, max_axial_pos}")
        self.axialPossSpinBox = QSpinBox(self.bottomLeftGroupBox)
        self.axialPossSpinBox.setRange(0, max_axial_pos)
        self.axialPossSpinBox.setValue(max_axial_pos // 2)
        self.axialPossSpinBox.valueChanged.connect(self.axialPossSpinBoxChanged)

        self.axialPossSlider = QSlider(Qt.Orientation.Horizontal, self.bottomLeftGroupBox)
        self.axialPossSlider.setRange(0, max_axial_pos)
        self.axialPossSlider.setValue(self.axialPossSpinBox.value())
        self.axialPossSlider.setTickPosition(QSlider.TicksBelow)
        self.axialPossSlider.valueChanged.connect(self.axialPossSliderChanged)

        if max_axial_pos == 0:
            self.axialPossSpinBox.setEnabled(False)
            self.axialPossLabel.setEnabled(False)
            self.axialPossSlider.setEnabled(False)

        # #### TANGENTIAL POSITION ####
        # max_tangential_pos = self.stir_interface.proj_data.get_num_tangential_poss() - 1
        # self.tangentialPossSpinBoxLabel = QLabel(f"Tangential position: {0, max_tangential_pos}")
        # self.tangentialPossSpinBox = QSpinBox(self.bottomLeftGroupBox)
        # self.tangentialPossSpinBox.setRange(0, max_tangential_pos)
        # self.tangentialPossSpinBox.setValue(max_tangential_pos // 2)
        # self.tangentialPossSpinBox.valueChanged.connect(self.tangentialPossSpinBoxChanged)
        #
        # self.tangentialPossSlider = QSlider(Qt.Orientation.Horizontal, self.bottomLeftGroupBox)
        # self.tangentialPossSlider.setRange(0, max_tangential_pos)
        # self.tangentialPossSlider.setValue(self.tangentialPossSpinBox.value())
        # self.tangentialPossSlider.setTickPosition(QSlider.TicksBelow)
        # self.tangentialPossSlider.valueChanged.connect(self.tangentialPossSliderChanged)

        #### SEGMENT NUMBER ####
        max_segment_number = self.stir_interface.proj_data_stream.get_max_segment_num()  # TODO needs rework because this is actually variable
        min_segment_number = self.stir_interface.proj_data_stream.get_min_segment_num()
        self.segmentNumberLabel = QLabel(f"Segment Number: {min_segment_number, max_segment_number}")
        self.segmentNumberSpinBox = QSpinBox(self.bottomLeftGroupBox)
        self.segmentNumberSpinBox.setRange(min_segment_number, max_segment_number)
        self.segmentNumberSpinBox.setValue(0)
        self.segmentNumberSpinBox.valueChanged.connect(self.segmentNumberSpinBoxChanged)

        self.segmentNumberSlider = QSlider(Qt.Orientation.Horizontal, self.bottomLeftGroupBox)
        self.segmentNumberSlider.setRange(min_segment_number, max_segment_number)
        self.segmentNumberSlider.setValue(self.segmentNumberSpinBox.value())
        self.segmentNumberSlider.setTickPosition(QSlider.TicksBelow)
        self.segmentNumberSlider.valueChanged.connect(self.segmentNumberSliderChanged)

        if max_segment_number == 0 and min_segment_number == 0:
            self.segmentNumberSpinBox.setEnabled(False)
            self.segmentNumberSlider.setEnabled(False)
            self.segmentNumberLabel.setEnabled(False)

        self.showSinogramPushButton = QPushButton("Show Sinogram")
        self.showSinogramPushButton.setDefault(True)

        ##### LAYOUT ####
        layout = QGridLayout()
        # layout.addWidget(lineEdit, 0, 0, 1, 2)

        layout.addWidget(self.segmentNumberLabel, 0, 0, 1, 1)
        layout.addWidget(self.segmentNumberSlider, 1, 0, 1, 1)
        layout.addWidget(self.segmentNumberSpinBox, 1, 1, 1, 1)

        layout.addWidget(self.axialPossLabel, 2, 0, 1, 1)
        layout.addWidget(self.axialPossSlider, 3, 0, 1, 1)
        layout.addWidget(self.axialPossSpinBox, 3, 1, 1, 1)

        #
        # layout.addWidget(self.tangentialPossSpinBoxLabel, 2, 0, 1, 1)
        # layout.addWidget(self.tangentialPossSlider, 3, 0, 1, 1)
        # layout.addWidget(self.tangentialPossSpinBox, 3, 1, 1, 1)

        layout.addWidget(self.showSinogramPushButton, 4, 0, 1, 2)

        layout.setRowStretch(5, 1)
        self.bottomLeftGroupBox.setLayout(layout)


    def segmentNumberSliderChanged(self):
        self.segmentNumberSpinBox.setValue(self.segmentNumberSlider.value())
        self.stir_interface.refresh_segment_data(self.segmentNumberSlider.value())
        self.correctAxialPossUI()

    def segmentNumberSpinBoxChanged(self):
        self.segmentNumberSlider.setValue(self.segmentNumberSpinBox.value())
        self.stir_interface.refresh_segment_data(self.segmentNumberSpinBox.value())
        self.correctAxialPossUI()

    def axialPossSliderChanged(self):
        self.axialPossSpinBox.setValue(self.axialPossSlider.value())

    def axialPossSpinBoxChanged(self):
        self.axialPossSlider.setValue(self.axialPossSpinBox.value())

    def tangentialPossSliderChanged(self):
        self.tangentialPossSpinBox.setValue(self.tangentialPossSlider.value())

    def tangentialPossSpinBoxChanged(self):
        self.tangentialPossSlider.setValue(self.tangentialPossSpinBox.value())


    def correctAxialPossUI(self):

        min_axial_pos = self.stir_interface.segment_data.get_min_axial_pos_num()
        max_axial_pos = self.stir_interface.segment_data.get_max_axial_pos_num()
        new_axial_value = min(max_axial_pos, max(self.axialPossSlider.value(), min_axial_pos))

        self.axialPossSlider.setRange(min_axial_pos, max_axial_pos)
        self.axialPossSpinBox.setRange(min_axial_pos, max_axial_pos)
        self.axialPossSlider.setValue(new_axial_value)
        self.axialPossSpinBox.setValue(new_axial_value)


if __name__ == '__main__':
    import sys

    app = QApplication(sys.argv)
    gallery = WidgetGallery()
    gallery.show()
    sys.exit(app.exec())
