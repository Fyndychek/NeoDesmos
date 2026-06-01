# utils.py
import re
import numpy as np
from PySide6.QtGui import QColor, QFont

# Цвета для графиков по умолчанию
DEFAULT_COLORS = [
    '#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4',
    '#FFEAA7', '#DDA0DD', '#98D8C8', '#F7B05E'
]

# Моноширинный шрифт для полей ввода
MONO_FONT = QFont("Courier New", 10)

# Цвета подсветки синтаксиса
HIGHLIGHT_FUNCTION = QColor(0, 150, 200)   # голубой
HIGHLIGHT_NUMBER   = QColor(150, 100, 200) # фиолетовый
HIGHLIGHT_VARIABLE = QColor(200, 100, 50)  # оранжевый

# Базовый словарь математических функций и констант для парсера
BASE_NAMESPACE = {
    # Тригонометрические
    'sin': np.sin, 'cos': np.cos, 'tan': np.tan, 'tg': np.tan,
    'cot': lambda x: 1 / np.tan(x) if np.tan(x) != 0 else np.nan,
    'ctg': lambda x: 1 / np.tan(x) if np.tan(x) != 0 else np.nan,
    'sec': lambda x: 1 / np.cos(x),
    'csc': lambda x: 1 / np.sin(x),
    # Обратные
    'asin': np.arcsin, 'acos': np.arccos, 'atan': np.arctan,
    'arctan': np.arctan, 'arctg': np.arctan,
    # Гиперболические
    'sinh': np.sinh, 'cosh': np.cosh, 'tanh': np.tanh,
    'coth': np.cosh,
    # Прочие
    'sqrt': np.sqrt, 'exp': np.exp, 'log': np.log,
    'ln': np.log, 'log10': np.log10, 'lg': np.log10,
    'abs': np.abs, 'floor': np.floor, 'ceil': np.ceil,
    'round': np.round,
    # Константы
    'pi': np.pi,
    'e': np.e,
}

# Список имён функций для регулярных выражений
FUNCTION_NAMES = list(BASE_NAMESPACE.keys())
FUNCTION_PATTERN = '|'.join(re.escape(f) for f in FUNCTION_NAMES)