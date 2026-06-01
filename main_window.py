# main_window.py
import json
import os
import numpy as np
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QScrollArea, QLabel, QFrame, QCheckBox,
    QFileDialog, QMessageBox, QMenuBar, QMenu
)
from PySide6.QtCore import QThreadPool, QTimer, QMutex, QMutexLocker, Qt
import pyqtgraph as pg

from cell import FunctionCell
from constants_widget import ConstantWidget
from parser import FunctionParser
from workers import FunctionWorker

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Графический калькулятор")
        self.setGeometry(100, 100, 1500, 800)

        self.threadpool = QThreadPool()
        self.threadpool.setMaxThreadCount(8)
        self._active_workers = []
        self._workers_mutex = QMutex()

        self._update_timer = QTimer()
        self._update_timer.setSingleShot(True)
        self._update_timer.timeout.connect(self.update_all_functions)

        self._const_update_timer = QTimer()
        self._const_update_timer.setSingleShot(True)
        self._const_update_timer.timeout.connect(self._batch_update_dependents)
        self._pending_const_updates = set()

        self.cells = {}
        self.cells_order = []
        self.next_cell_id = 0
        self.cell_data = {}

        self.constants = {}
        self.constant_dependents = {}

        self.autosave_file = "autosave.json"
        self.precision_mode = False

        self._setup_menu()
        self._setup_ui()

        # Загрузка автосохранения, если есть
        autosave_loaded = False
        if os.path.exists(self.autosave_file):
            self.load_state(self.autosave_file, show_message=False)
            autosave_loaded = True
        if not autosave_loaded or len(self.cells) == 0:
            self.add_function_cell()
            first_cell = self.cells[self.cells_order[0]]
            first_cell.function_input.setPlainText("sin(x)")
            first_cell.update_function()

        self.add_function_cell()
        first_cell = self.cells[self.cells_order[0]]
        first_cell.function_input.setPlainText("sin(x)")
        first_cell.update_function()

    def _setup_menu(self):
        menubar = self.menuBar()
        file_menu = menubar.addMenu("Файл")

        new_action = file_menu.addAction("Новый")
        new_action.triggered.connect(self.new_project)

        open_action = file_menu.addAction("Открыть...")
        open_action.triggered.connect(self.open_project)

        save_action = file_menu.addAction("Сохранить как...")
        save_action.triggered.connect(self.save_project_as)

        file_menu.addSeparator()

        exit_action = file_menu.addAction("Выход")
        exit_action.triggered.connect(self.close)

    def new_project(self):
        reply = QMessageBox.question(self, "Новый проект",
                                     "Очистить все функции и константы?",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            for cell_id in list(self.cells.keys()):
                self.remove_function_cell(cell_id)
            for name in list(self.constants.keys()):
                self.constants[name]['widget'].deleteLater()
            self.constants.clear()
            self.constant_dependents.clear()
            self.add_function_cell()
            for cell in self.cells.values():
                cell.parser = FunctionParser(self.constants)
            if os.path.exists(self.autosave_file):
                os.remove(self.autosave_file)

    def _setup_ui(self):
        central = QWidget()
        main_layout = QHBoxLayout()

        self.graph_widget = pg.PlotWidget()
        self.graph_widget.showGrid(x=True, y=True, alpha=0.3)
        self.graph_widget.setLabel('left', 'Y')
        self.graph_widget.setLabel('bottom', 'X')
        self.graph_widget.setBackground('w')
        self.graph_widget.getAxis('bottom').setPen('k')
        self.graph_widget.getAxis('left').setPen('k')
        self.graph_widget.setMouseEnabled(x=True, y=True)
        self.graph_widget.sigRangeChanged.connect(self.on_range_changed)

        sidebar = QWidget()
        sidebar.setMaximumWidth(600)
        sidebar_layout = QVBoxLayout()
        sidebar_layout.setSpacing(8)
        sidebar_layout.setContentsMargins(5, 5, 5, 5)

        info_label = QLabel(
            "Неявное умножение: 2x, x sin(x), (x+1)(x-1)\n"
            "Автоматическая отрисовка при вводе (задержка 0.5 сек)\n"
            "Автоматическое обновление при масштабировании\n"
            "Неявные функции вида x = f(y) (например, x = y(1+cos(y)))\n"
            "Пользовательские константы: a = 3, b = -2.5\n\n"
            "  y = sin(x)\n"
            "  x = y(1+cos(y))\n"
            "  2x sin(x)\n"
            "  a = 5\n"
            "  y = a * sin(x)"
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: gray; font-size: 9px; padding: 5px; background-color: #F5F5F5; border-radius: 3px;")
        sidebar_layout.addWidget(info_label)

        add_btn = QPushButton("+ Добавить функцию")
        add_btn.setMinimumHeight(32)
        add_btn.clicked.connect(self.add_function_cell)
        sidebar_layout.addWidget(add_btn)

        #update_all_btn = QPushButton("⟳ Обновить все графики")
        #update_all_btn.setMinimumHeight(32)
        #update_all_btn.clicked.connect(self.update_all_functions)
        #sidebar_layout.addWidget(update_all_btn)

        reset_view_btn = QPushButton("⌂ Сбросить масштаб")
        reset_view_btn.setMinimumHeight(32)
        reset_view_btn.clicked.connect(self.reset_view)
        sidebar_layout.addWidget(reset_view_btn)

        self.precision_checkbox = QCheckBox("Высокая точность (для больших масштабов)")
        self.precision_checkbox.setChecked(False)
        self.precision_checkbox.toggled.connect(self.on_precision_toggled)
        sidebar_layout.addWidget(self.precision_checkbox)

        const_label = QLabel("Пользовательские константы:")
        const_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        sidebar_layout.addWidget(const_label)

        self.constants_container = QWidget()
        self.constants_layout = QVBoxLayout()
        self.constants_layout.setAlignment(Qt.AlignTop)
        self.constants_layout.setSpacing(5)
        self.constants_container.setLayout(self.constants_layout)

        const_scroll = QScrollArea()
        const_scroll.setWidgetResizable(True)
        const_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        const_scroll.setMaximumHeight(200)
        const_scroll.setWidget(self.constants_container)
        sidebar_layout.addWidget(const_scroll)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        sidebar_layout.addWidget(line)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setFrameShape(QFrame.NoFrame)

        self.cells_container = QWidget()
        self.cells_layout = QVBoxLayout()
        self.cells_layout.setAlignment(Qt.AlignTop)
        self.cells_layout.setSpacing(5)
        self.cells_layout.setContentsMargins(0, 0, 0, 0)
        self.cells_container.setLayout(self.cells_layout)
        scroll_area.setWidget(self.cells_container)
        sidebar_layout.addWidget(scroll_area)

        sidebar.setLayout(sidebar_layout)

        main_layout.addWidget(self.graph_widget, stretch=3)
        main_layout.addWidget(sidebar, stretch=1)
        central.setLayout(main_layout)
        self.setCentralWidget(central)

        self.draw_axes()
        self.graph_widget.setXRange(-10, 10)
        self.graph_widget.setYRange(-10, 10)

    def draw_axes(self):
        self.graph_widget.addLine(x=0, pen=pg.mkPen(color='k', width=2))
        self.graph_widget.addLine(y=0, pen=pg.mkPen(color='k', width=2))

    def reset_view(self):
        self.graph_widget.setXRange(-10, 10)
        self.graph_widget.setYRange(-10, 10)

    def on_range_changed(self):
        if not self._update_timer.isActive():
            self._update_timer.start(100)

    def on_precision_toggled(self, checked):
        self.precision_mode = checked
        FunctionWorker.clear_cache()
        self.update_all_functions()

    # ---------- Сохранение/загрузка ----------
    def save_state(self, filepath, show_message=True):
        try:
            data = {
                "version": 1,
                "constants": {},
                "cells": []
            }
            for name, const in self.constants.items():
                data["constants"][name] = {
                    "value": const["value"],
                    "min": const.get("min", -10),
                    "max": const.get("max", 10)
                }
            for cell_id in self.cells_order:
                cell = self.cells[cell_id]
                data["cells"].append({
                    "text": cell.get_func_str(),
                    "color": cell.color,
                    "visible": cell.is_visible
                })
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            if show_message:
                print(f"Состояние сохранено в {filepath}")
        except Exception as e:
            if show_message:
                QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить: {e}")
            else:
                print(f"Ошибка сохранения: {e}")

    def load_state(self, filepath, show_message=True):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Очищаем всё
            for cell_id in list(self.cells.keys()):
                self.remove_function_cell(cell_id)
            for name in list(self.constants.keys()):
                self.constants[name]['widget'].deleteLater()
            self.constants.clear()
            self.constant_dependents.clear()

            # Восстанавливаем константы
            for name, const_data in data.get("constants", {}).items():
                self.add_constant(name, const_data["value"],
                                 const_data.get("min", -1000),
                                 const_data.get("max", 1000))

            # Восстанавливаем ячейки
            for cell_data in data.get("cells", []):
                cell_id = self.add_function_cell()
                cell = self.cells[cell_id]
                cell.function_input.setPlainText(cell_data["text"])
                cell.color = cell_data["color"]
                cell.update_color_button()
                if not cell_data["visible"]:
                    cell.visible_checkbox.setChecked(False)
                cell.update_function()
            if self.cells:
                self.next_cell_id = max(self.cells.keys()) + 1

            if show_message:
                QMessageBox.information(self, "Загрузка", f"Загружено из {filepath}")
            print(f"Состояние загружено из {filepath}")
        except Exception as e:
            if show_message:
                QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить: {e}")
            else:
                print(f"Ошибка загрузки: {e}")

    def save_autosave(self):
        self.save_state(self.autosave_file, show_message=False)

    def save_project_as(self):
        filepath, _ = QFileDialog.getSaveFileName(self, "Сохранить проект",
                                                  "", "JSON files (*.json)")
        if filepath:
            self.save_state(filepath)

    def open_project(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Открыть проект",
                                                  "", "JSON files (*.json)")
        if filepath:
            self.load_state(filepath)

    # ---------- Управление константами ----------
    def add_constant(self, name, value, min_val=-10, max_val=10):
        if name in self.constants:
            self.constants[name]['value'] = value
            widget = self.constants[name]['widget']
            widget.blockSignals(True)
            widget.spinbox.setValue(int(value * 100))
            widget.slider.setValue(widget._value_to_slider(value))
            widget.blockSignals(False)
            self._pending_const_updates.add(name)
            self._const_update_timer.start(10)
        else:
            widget = ConstantWidget(name, value, min_val, max_val)
            widget.valueChanged.connect(self.on_constant_changed)
            self.constants_layout.addWidget(widget)
            self.constants[name] = {'value': value, 'widget': widget}
            self.constant_dependents[name] = set()

            for cell in self.cells.values():
                cell.parser = FunctionParser(self.constants)

            for cell_id, cell in self.cells.items():
                if name in cell.used_constants:
                    self.constant_dependents[name].add(cell_id)
                    cell.update_function()

    def on_constant_changed(self, name, new_value):
        print(f"[DEBUG] Constant changed: {name} = {new_value}")
        if new_value is None:
            if name in self.constants:
                if name in self.constant_dependents:
                    cell_ids = self.constant_dependents[name].copy()
                    del self.constant_dependents[name]
                    for cid in cell_ids:
                        if cid in self.cells:
                            self.cells[cid].parser = FunctionParser(self.constants)
                            self.update_single_function(cid)
                del self.constants[name]
                FunctionWorker.clear_cache()
        else:
            if name in self.constants:
                self.constants[name]['value'] = new_value
                self._pending_const_updates.add(name)
                self._const_update_timer.start(10)
                FunctionWorker.clear_cache()

    def _batch_update_dependents(self):
        print(f"[DEBUG] Batch update for: {self._pending_const_updates}")
        const_names = list(self._pending_const_updates)
        self._pending_const_updates.clear()
        for cname in const_names:
            self._update_dependent_functions(cname)

    def _update_dependent_functions(self, const_name):
        print(f"[DEBUG] Update dependents of {const_name}: {self.constant_dependents.get(const_name, set())}")
        if const_name not in self.constant_dependents:
            return
        for cid in self.constant_dependents[const_name].copy():
            print(f"[DEBUG] Will update cell {cid}")
            if cid in self.cells and self.cells[cid].is_visible:
                self.cells[cid].update_function()

    def update_cell_dependencies(self, cell_id, const_names):
        for cname in list(self.constant_dependents.keys()):
            self.constant_dependents[cname].discard(cell_id)
        for cname in const_names:
            if cname not in self.constant_dependents:
                self.constant_dependents[cname] = set()
            self.constant_dependents[cname].add(cell_id)

    # ---------- Управление ячейками ----------
    def add_function_cell(self, insert_after_id=None):
        cell_id = self.next_cell_id
        self.next_cell_id += 1

        parser = FunctionParser(self.constants)

        cell = FunctionCell(
            cell_id,
            parser,
            on_remove=self.remove_function_cell,
            on_toggle=self.toggle_function_visibility,
            on_color_change=self.change_function_color,
            on_update_request=self.update_single_function,
            on_enter_pressed=self.insert_function_cell_after,
            on_add_constant=self.add_constant,
            on_dependencies_updated=self.update_cell_dependencies
        )

        self.cells[cell_id] = cell
        self.cell_data[cell_id] = {'x': None, 'y': None}

        if insert_after_id is None:
            self.cells_order.append(cell_id)
            self.cells_layout.addWidget(cell)
        else:
            try:
                idx = self.cells_order.index(insert_after_id)
                self.cells_order.insert(idx + 1, cell_id)
                self.cells_layout.insertWidget(idx + 1, cell)
            except ValueError:
                self.cells_order.append(cell_id)
                self.cells_layout.addWidget(cell)

        cell.function_input.setFocus()
        return cell_id

    def insert_function_cell_after(self, after_cell_id):
        self.add_function_cell(insert_after_id=after_cell_id)

    def remove_function_cell(self, cell_id):
        if cell_id not in self.cells:
            return
        cell = self.cells[cell_id]
        cell._is_deleted = True
        cell.typing_timer.stop()

        for cname in list(self.constant_dependents.keys()):
            self.constant_dependents[cname].discard(cell_id)

        for curve in cell.get_curves():
            self.graph_widget.removeItem(curve)
        cell.clear_curves()

        self.cells_layout.removeWidget(cell)
        cell.deleteLater()
        del self.cells[cell_id]
        del self.cell_data[cell_id]
        if cell_id in self.cells_order:
            self.cells_order.remove(cell_id)

    def toggle_function_visibility(self, cell_id, visible):
        if cell_id in self.cells:
            for curve in self.cells[cell_id].get_curves():
                curve.setVisible(visible)

    def change_function_color(self, cell_id, color):
        if cell_id in self.cells:
            pen = pg.mkPen(color=color, width=2)
            for curve in self.cells[cell_id].get_curves():
                curve.setPen(pen)

    # ---------- Вычисления ----------
    def update_single_function(self, cell_id):
        print(f"[DEBUG] Updating cell {cell_id}")
        if cell_id not in self.cells:
            return
        cell = self.cells[cell_id]
        if not cell.is_visible:   # добавить проверку
            return
        func = cell.get_function()
        if func is None:
            return

        view = self.graph_widget.viewRange()
        if cell.is_implicit_func():
            y_min, y_max = view[1]
            param_range = (y_min, y_max)
        else:
            x_min, x_max = view[0]
            param_range = (x_min, x_max)

        if not np.isfinite(param_range[0]) or not np.isfinite(param_range[1]):
            param_range = (-10, 10)
        if abs(param_range[1] - param_range[0]) > 10000:
            center = (param_range[0] + param_range[1]) / 2
            param_range = (center - 5000, center + 5000)

        with QMutexLocker(self._workers_mutex):
            for w in list(self._active_workers):
                if hasattr(w, 'cell_id') and w.cell_id == cell_id:
                    w.cancel()
                    self._active_workers.remove(w)

        worker = FunctionWorker(func, cell.get_func_str(), param_range,
                                cell.is_implicit_func(), cell_id, self.precision_mode)
        worker.signals.finished.connect(self.on_function_calculated)
        with QMutexLocker(self._workers_mutex):
            self._active_workers.append(worker)
        self.threadpool.start(worker)

    def on_function_calculated(self, seg_x_list, seg_y_list, func_str, cell_id):
        if cell_id not in self.cells:
            return
        cell = self.cells[cell_id]

        for curve in cell.get_curves():
            self.graph_widget.removeItem(curve)

        new_curves = []
        for sx, sy in zip(seg_x_list, seg_y_list):
            if len(sx) >= 3:
                pen = pg.mkPen(color=cell.color, width=2)
                curve = self.graph_widget.plot(sx, sy, pen=pen, name=func_str)
                new_curves.append(curve)
        cell.set_curves(new_curves)
        for curve in new_curves:
            curve.setVisible(cell.is_visible)

        print(f"✓ График обновлён: {func_str} (сегментов: {len(seg_x_list)}, отрисовано: {len(new_curves)})")

        with QMutexLocker(self._workers_mutex):
            sender = self.sender()
            if sender in self._active_workers:
                self._active_workers.remove(sender)

    def update_all_functions(self):
        with QMutexLocker(self._workers_mutex):
            for w in self._active_workers:
                w.cancel()
            self._active_workers.clear()

        for cid in self.cells_order:
            cell = self.cells[cid]
            if cell.is_visible and cell.get_func_str():
                self.update_single_function(cid)

        print("✓ Все функции обновлены для текущего масштаба")

    def closeEvent(self, event):
        self.save_autosave()
        with QMutexLocker(self._workers_mutex):
            for w in self._active_workers:
                w.cancel()
            self._active_workers.clear()
        self.threadpool.waitForDone(1000)
        event.accept()