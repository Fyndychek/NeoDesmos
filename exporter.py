# exporter.py
"""
Модуль экспорта и импорта формул для NeoDesmos.

Поддерживаемые форматы:
  Экспорт: JSON (.json), CSV (.csv), TXT (.txt), LaTeX (.tex), Clipboard
  Импорт:  JSON (.json), CSV (.csv), TXT (.txt)
"""

import json
import csv
import re
import io
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple


# ---------------------------------------------------------------------------
# Структуры данных
# ---------------------------------------------------------------------------

@dataclass
class FormulaEntry:
    """Одна строка с формулой."""
    text: str
    color: str = "#4ECDC4"
    visible: bool = True


@dataclass
class ProjectData:
    """Полное состояние проекта (формулы + константы)."""
    cells: List[FormulaEntry] = field(default_factory=list)
    constants: Dict[str, dict] = field(default_factory=dict)
    version: int = 1


# ---------------------------------------------------------------------------
# Вспомогательный конвертер формул → LaTeX
# ---------------------------------------------------------------------------

# Таблица замен: (regex_pattern, replacement)
_LATEX_REPLACEMENTS: List[Tuple[str, str]] = [
    # Тригонометрические
    (r'\bsin\b',   r'\\sin'),
    (r'\bcos\b',   r'\\cos'),
    (r'\btan\b',   r'\\tan'),
    (r'\btg\b',    r'\\tan'),
    (r'\bcot\b',   r'\\cot'),
    (r'\bctg\b',   r'\\cot'),
    (r'\bsec\b',   r'\\sec'),
    (r'\bcsc\b',   r'\\csc'),
    # Обратные
    (r'\basin\b',  r'\\arcsin'),
    (r'\bacos\b',  r'\\arccos'),
    (r'\batan\b',  r'\\arctan'),
    (r'\barctan\b',r'\\arctan'),
    (r'\barctg\b', r'\\arctan'),
    # Гиперболические
    (r'\bsinh\b',  r'\\sinh'),
    (r'\bcosh\b',  r'\\cosh'),
    (r'\btanh\b',  r'\\tanh'),
    # Прочие
    (r'\bsqrt\(([^)]+)\)', r'\\sqrt{\1}'),
    (r'\bexp\(([^)]+)\)',  r'e^{\1}'),
    (r'\bln\b',    r'\\ln'),
    (r'\blog\b',   r'\\log'),
    (r'\blog10\b', r'\\log_{10}'),
    (r'\blg\b',    r'\\lg'),
    (r'\babs\(([^)]+)\)',  r'\\left|\1\\right|'),
    (r'\bfloor\(([^)]+)\)',r'\\lfloor \1 \\rfloor'),
    (r'\bceil\(([^)]+)\)', r'\\lceil \1 \\rceil'),
    # Константы
    (r'\bpi\b',    r'\\pi'),
    # Оператор возведения в степень
    (r'\*\*',      r'^'),
    # Неявное умножение: 2x → 2 \cdot x  (только цифра перед буквой)
    (r'(\d)([a-zA-Z])', r'\1 \\cdot \2'),
    # Дробь y=.../... не обрабатываем (слишком сложно без AST)
]


def _formula_to_latex(expr: str) -> str:
    """
    Эвристическое преобразование формулы в LaTeX-строку.
    Не претендует на полноту — покрывает типичные случаи NeoDesmos.
    """
    expr = expr.strip()

    # Нормализуем левую часть  y= / x=
    lhs = ""
    rhs = expr
    m = re.match(r'^([xy])\s*=\s*(.+)$', expr, re.IGNORECASE)
    if m:
        lhs = m.group(1) + " = "
        rhs = m.group(2)

    for pattern, repl in _LATEX_REPLACEMENTS:
        rhs = re.sub(pattern, repl, rhs)

    return lhs + rhs


def _latex_document(entries: List[FormulaEntry]) -> str:
    """Оборачивает формулы в минимальный LaTeX-документ."""
    lines = [
        r"\documentclass{article}",
        r"\usepackage{amsmath}",
        r"\begin{document}",
        r"\begin{align*}",
    ]
    for i, e in enumerate(entries):
        if not e.text.strip():
            continue
        latex = _formula_to_latex(e.text)
        sep = r" \\" if i < len(entries) - 1 else ""
        lines.append(f"  {latex}{sep}")
    lines += [r"\end{align*}", r"\end{document}"]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Экспорт
# ---------------------------------------------------------------------------

class Exporter:
    """Экспортирует ProjectData в разные форматы."""

    # --- JSON ---------------------------------------------------------------

    @staticmethod
    def to_json(data: ProjectData, filepath: str) -> None:
        payload = {
            "version": data.version,
            "constants": data.constants,
            "cells": [
                {"text": e.text, "color": e.color, "visible": e.visible}
                for e in data.cells
            ],
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)

    # --- CSV ----------------------------------------------------------------

    @staticmethod
    def to_csv(data: ProjectData, filepath: str) -> None:
        """
        Колонки: formula, color, visible
        Константы записываются как formula = «name=value».
        """
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["formula", "color", "visible"])
            # Сначала константы
            for name, const in data.constants.items():
                writer.writerow([f"{name}={const['value']}", "#888888", "true"])
            # Затем формулы
            for e in data.cells:
                writer.writerow([e.text, e.color, str(e.visible).lower()])

    # --- TXT ----------------------------------------------------------------

    @staticmethod
    def to_txt(data: ProjectData, filepath: str) -> None:
        """
        Простой текстовый формат:
          # comment lines ignored on import
          [constants]
          name = value
          [formulas]
          formula text
        """
        lines = ["# NeoDesmos export", ""]
        if data.constants:
            lines.append("[constants]")
            for name, const in data.constants.items():
                lines.append(f"{name} = {const['value']}")
            lines.append("")
        lines.append("[formulas]")
        for e in data.cells:
            if e.text.strip():
                vis = "" if e.visible else "  # hidden"
                lines.append(f"{e.text}{vis}")
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

    # --- LaTeX --------------------------------------------------------------

    @staticmethod
    def to_latex(data: ProjectData, filepath: str) -> None:
        content = _latex_document(data.cells)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

    # --- Clipboard (plain text) ---------------------------------------------

    @staticmethod
    def to_clipboard_text(data: ProjectData) -> str:
        """Возвращает строку для помещения в буфер обмена."""
        parts = []
        if data.constants:
            parts.append("Константы:")
            for name, const in data.constants.items():
                parts.append(f"  {name} = {const['value']}")
            parts.append("")
        parts.append("Формулы:")
        for e in data.cells:
            if e.text.strip():
                vis = "" if e.visible else " [скрыта]"
                parts.append(f"  {e.text}{vis}")
        return "\n".join(parts)


# ---------------------------------------------------------------------------
# Импорт
# ---------------------------------------------------------------------------

class Importer:
    """Импортирует ProjectData из разных форматов."""

    # --- JSON ---------------------------------------------------------------

    @staticmethod
    def from_json(filepath: str) -> ProjectData:
        with open(filepath, "r", encoding="utf-8") as f:
            raw = json.load(f)
        return Importer._parse_json_dict(raw)

    @staticmethod
    def _parse_json_dict(raw: dict) -> ProjectData:
        cells = [
            FormulaEntry(
                text=c.get("text", ""),
                color=c.get("color", "#4ECDC4"),
                visible=c.get("visible", True),
            )
            for c in raw.get("cells", [])
        ]
        return ProjectData(
            cells=cells,
            constants=raw.get("constants", {}),
            version=raw.get("version", 1),
        )

    # --- CSV ----------------------------------------------------------------

    @staticmethod
    def from_csv(filepath: str) -> ProjectData:
        cells = []
        constants = {}
        with open(filepath, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                text = row.get("formula", "").strip()
                if not text:
                    continue
                # Проверяем, не является ли строка константой (a=3.14)
                m = re.match(r'^([a-zA-Z])\s*=\s*([+-]?\d*\.?\d+)$', text)
                if m and m.group(1).lower() not in ('x', 'y'):
                    name = m.group(1).lower()
                    constants[name] = {"value": float(m.group(2)), "min": -10, "max": 10}
                else:
                    visible_str = row.get("visible", "true").lower()
                    cells.append(FormulaEntry(
                        text=text,
                        color=row.get("color", "#4ECDC4"),
                        visible=(visible_str != "false"),
                    ))
        return ProjectData(cells=cells, constants=constants)

    # --- TXT ----------------------------------------------------------------

    @staticmethod
    def from_txt(filepath: str) -> ProjectData:
        cells = []
        constants = {}
        section = None
        with open(filepath, "r", encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.lower() == "[constants]":
                    section = "constants"
                    continue
                if line.lower() == "[formulas]":
                    section = "formulas"
                    continue

                # Убираем inline-комментарии
                line = re.sub(r'\s*#.*$', '', line).strip()
                if not line:
                    continue

                if section == "constants":
                    m = re.match(r'^([a-zA-Z])\s*=\s*([+-]?\d*\.?\d+)$', line)
                    if m:
                        name = m.group(1).lower()
                        constants[name] = {
                            "value": float(m.group(2)),
                            "min": -10,
                            "max": 10,
                        }
                elif section == "formulas":
                    cells.append(FormulaEntry(text=line))
                else:
                    # Файл без секций — просто список формул
                    cells.append(FormulaEntry(text=line))

        return ProjectData(cells=cells, constants=constants)

    # --- Универсальный по расширению ----------------------------------------

    @staticmethod
    def from_file(filepath: str) -> ProjectData:
        """Автоматически выбирает парсер по расширению файла."""
        lower = filepath.lower()
        if lower.endswith(".json"):
            return Importer.from_json(filepath)
        elif lower.endswith(".csv"):
            return Importer.from_csv(filepath)
        elif lower.endswith(".txt"):
            return Importer.from_txt(filepath)
        else:
            raise ValueError(f"Неподдерживаемый формат файла: {filepath}")


# ---------------------------------------------------------------------------
# Вспомогательные функции для main_window
# ---------------------------------------------------------------------------

def project_data_from_window(window) -> ProjectData:
    """
    Собирает ProjectData из объекта MainWindow.
    Вызывается перед любым экспортом.
    """
    cells = []
    for cell_id in window.cells_order:
        cell = window.cells[cell_id]
        cells.append(FormulaEntry(
            text=cell.get_func_str() or cell.function_input.toPlainText().strip(),
            color=cell.color,
            visible=cell.is_visible,
        ))

    constants = {
        name: {
            "value": info["value"],
            "min": info.get("min", -10),
            "max": info.get("max", 10),
        }
        for name, info in window.constants.items()
    }

    return ProjectData(cells=cells, constants=constants)


def apply_project_data_to_window(data: ProjectData, window) -> None:
    """
    Загружает ProjectData в MainWindow, полностью заменяя текущее состояние.
    Логика аналогична window.load_state(), но работает с объектом ProjectData.
    """
    from parser import FunctionParser

    # Очистка
    for cell_id in list(window.cells.keys()):
        window.remove_function_cell(cell_id)
    for name in list(window.constants.keys()):
        window.constants[name]['widget'].deleteLater()
    window.constants.clear()
    window.constant_dependents.clear()

    # Константы
    for name, const in data.constants.items():
        window.add_constant(name, const["value"],
                            const.get("min", -10),
                            const.get("max", 10))

    # Ячейки
    for entry in data.cells:
        cell_id = window.add_function_cell()
        cell = window.cells[cell_id]
        cell.function_input.setPlainText(entry.text)
        cell.color = entry.color
        cell.update_color_button()
        if not entry.visible:
            cell.visible_checkbox.setChecked(False)
        cell.update_function()

    if window.cells:
        window.next_cell_id = max(window.cells.keys()) + 1
