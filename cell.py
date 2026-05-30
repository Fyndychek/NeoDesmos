# cell.py
import re
from PySide6.QtWidgets import QFrame, QHBoxLayout, QCheckBox, QTextEdit, QPushButton, QColorDialog
from PySide6.QtCore import QTimer, Qt, QEvent
from PySide6.QtGui import QFont
from highlighter import FunctionHighlighter
from utils import MONO_FONT, DEFAULT_COLORS

class FunctionCell(QFrame):
    def __init__(self, cell_id, parser, on_remove, on_toggle, on_color_change,
                 on_update_request, on_enter_pressed, on_add_constant,
                 on_dependencies_updated, parent=None):
        super().__init__(parent)
        self.cell_id = cell_id
        self.parser = parser
        self.on_remove = on_remove
        self.on_toggle = on_toggle
        self.on_color_change = on_color_change
        self.on_update_request = on_update_request
        self.on_enter_pressed = on_enter_pressed
        self.on_add_constant = on_add_constant
        self.on_dependencies_updated = on_dependencies_updated
        self.is_visible = True
        self.color = None
        self.func = None
        self.func_str = ""
        self.is_implicit = False
        self.curve_items = []
        self.curve_item = None
        self.used_constants = set()
        self._is_deleted = False

        self.typing_timer = QTimer()
        self.typing_timer.setSingleShot(True)
        self.typing_timer.timeout.connect(self.deferred_update)

        self._setup_ui()
        self.set_default_color()

    def _setup_ui(self):
        self.setFrameStyle(QFrame.Box | QFrame.Raised)
        self.setLineWidth(1)
        self.setFixedHeight(55)
        self.setMinimumWidth(400)

        layout = QHBoxLayout()
        layout.setSpacing(5)
        layout.setContentsMargins(3, 2, 3, 2)

        self.visible_checkbox = QCheckBox()
        self.visible_checkbox.setChecked(True)
        self.visible_checkbox.setToolTip("Показать/скрыть график")
        self.visible_checkbox.setFixedSize(20, 20)
        self.visible_checkbox.toggled.connect(self.toggle_visibility)
        layout.addWidget(self.visible_checkbox)

        self.function_input = QTextEdit()
        self.function_input.setPlaceholderText("y = ...  или  x = ...  или  a = 3")
        self.function_input.setMinimumWidth(350)
        self.function_input.setMaximumHeight(40)
        self.function_input.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.function_input.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.function_input.setFont(MONO_FONT)
        self.function_input.document().setDocumentMargin(2)
        self.function_input.setStyleSheet("""
            QTextEdit {
                padding: 2px;
                margin: 0px;
                border: 1px solid #ccc;
                border-radius: 3px;
            }
        """)
        self.function_input.textChanged.connect(self.on_text_changed)
        self.function_input.installEventFilter(self)
        layout.addWidget(self.function_input)

        self.highlighter = FunctionHighlighter(self.function_input.document())

        self.update_btn = QPushButton("⟳")
        self.update_btn.setFixedSize(30, 30)
        self.update_btn.setToolTip("Обновить график")
        self.update_btn.clicked.connect(self.update_function)
        layout.addWidget(self.update_btn)

        self.color_btn = QPushButton("🎨")
        self.color_btn.setFixedSize(30, 30)
        self.color_btn.setToolTip("Выбрать цвет графика")
        self.color_btn.clicked.connect(self.choose_color)
        layout.addWidget(self.color_btn)

        self.remove_btn = QPushButton("✖")
        self.remove_btn.setFixedSize(30, 30)
        self.remove_btn.setToolTip("Удалить функцию")
        self.remove_btn.clicked.connect(lambda: self.on_remove(self.cell_id))
        layout.addWidget(self.remove_btn)

        self.setLayout(layout)

    def set_default_color(self):
        self.color = DEFAULT_COLORS[self.cell_id % len(DEFAULT_COLORS)]
        self.update_color_button()

    def update_color_button(self):
        self.color_btn.setStyleSheet(f"background-color: {self.color};")

    def choose_color(self):
        color = QColorDialog.getColor()
        if color.isValid():
            self.color = color.name()
            self.update_color_button()
            if self.on_color_change:
                self.on_color_change(self.cell_id, self.color)

    def toggle_visibility(self, checked):
        self.is_visible = checked
        if self.on_toggle:
            self.on_toggle(self.cell_id, checked)

    def on_text_changed(self):
        if self._is_deleted:
            return
        self.typing_timer.start(500)

    def deferred_update(self):
        if self._is_deleted:
            return
        self.update_function()

    def eventFilter(self, obj, event):
        if self._is_deleted:
            return super().eventFilter(obj, event)
        if obj == self.function_input and event.type() == QEvent.KeyPress:
            key = event.key()
            if key in (Qt.Key_Return, Qt.Key_Enter) and not (event.modifiers() & Qt.ShiftModifier):
                self.typing_timer.stop()
                if self.on_enter_pressed:
                    self.on_enter_pressed(self.cell_id)
                return True
        return super().eventFilter(obj, event)

    def update_function(self):
        if self._is_deleted:
            return

        func_str = self.function_input.toPlainText().strip()
        if not func_str:
            return

        const_match = re.match(r'^\s*([a-zA-Z])\s*=\s*([+-]?\d*\.?\d+)\s*$', func_str)
        if const_match:
            name = const_match.group(1).lower()
            if name not in ('x', 'y'):
                value = float(const_match.group(2))
                if self.on_add_constant:
                    self.on_add_constant(name, value)
                if self.on_remove:
                    self.on_remove(self.cell_id)
                return

        self.func_str = func_str
        self.func, processed_str, self.is_implicit, used_constants, error = self.parser.parse(func_str)
        self.used_constants = used_constants

        if self.on_dependencies_updated:
            self.on_dependencies_updated(self.cell_id, used_constants)

        if self.func is not None:
            self.function_input.setStyleSheet("""
                QTextEdit {
                    padding: 2px;
                    margin: 0px;
                    border: 1px solid #ccc;
                    border-radius: 3px;
                }
            """)
            self.function_input.setToolTip("")
            if self.on_update_request:
                self.on_update_request(self.cell_id)
        else:
            self.function_input.setStyleSheet("""
                QTextEdit {
                    background-color: #FFE0E0;
                    border: 1px solid red;
                    padding: 2px;
                    margin: 0px;
                    border-radius: 3px;
                }
            """)
            tooltip = error if error else "Ошибка синтаксиса функции"
            self.function_input.setToolTip(tooltip)

    def get_function(self):
        return self.func

    def get_func_str(self):
        return self.func_str

    def is_implicit_func(self):
        return self.is_implicit

    def set_curves(self, curves):
        self.curve_items = curves
        self.curve_item = curves[0] if curves else None

    def get_curves(self):
        return self.curve_items

    def clear_curves(self):
        self.curve_items = []
        self.curve_item = None

    def get_curve(self):
        return self.curve_item