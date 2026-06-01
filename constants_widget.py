# constants_widget.py
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QSlider, QSpinBox, QPushButton
from PySide6.QtCore import Signal, Qt

class ConstantWidget(QWidget):
    valueChanged = Signal(str, float)

    def __init__(self, name, initial_value, min_val=-10, max_val=10, parent=None):
        super().__init__(parent)
        self.name = name
        self.min_val = min_val
        self.max_val = max_val
        self._setup_ui(initial_value)
    
    def _setup_ui(self, initial_value):
        layout = QHBoxLayout()
        layout.setContentsMargins(2, 2, 2, 2)

        self.name_label = QLabel(f"{self.name} =")
        layout.addWidget(self.name_label)

        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, 1000)
        self.slider.setValue(self._value_to_slider(initial_value))
        self.slider.valueChanged.connect(self.on_slider_changed)
        layout.addWidget(self.slider)

        self.spinbox = QSpinBox()
        self.spinbox.setRange(int(self.min_val * 100), int(self.max_val * 100))
        self.spinbox.setValue(int(initial_value * 100))
        self.spinbox.setSingleStep(10)
        self.spinbox.valueChanged.connect(self.on_spinbox_changed)
        layout.addWidget(self.spinbox)

        self.remove_btn = QPushButton("✖")
        self.remove_btn.setFixedSize(20, 20)
        self.remove_btn.clicked.connect(self.remove)
        layout.addWidget(self.remove_btn)

        self.setLayout(layout)

    def _value_to_slider(self, value):
        return int((value - self.min_val) / (self.max_val - self.min_val) * 1000)

    def _slider_to_value(self, slider_val):
        return self.min_val + (slider_val / 1000) * (self.max_val - self.min_val)

    def on_slider_changed(self, val):
        value = self._slider_to_value(val)
        self.spinbox.blockSignals(True)
        self.spinbox.setValue(int(value * 100))
        self.spinbox.blockSignals(False)
        self.valueChanged.emit(self.name, value)

    def on_spinbox_changed(self, val):
        value = val / 100.0
        self.slider.blockSignals(True)
        self.slider.setValue(self._value_to_slider(value))
        self.slider.blockSignals(False)
        self.valueChanged.emit(self.name, value)

    def remove(self):
        self.valueChanged.emit(self.name, None)
        self.deleteLater()