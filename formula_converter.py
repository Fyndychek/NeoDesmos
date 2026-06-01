# formula_converter.py
import re
from typing import List, Optional


_FUNCTIONS = {
    'sin','cos','tan','tg','cot','ctg','sec','csc',
    'asin','acos','atan','arcsin','arccos','arctan','arctg',
    'sinh','cosh','tanh','coth',
    'sqrt','exp','log','ln','log10','lg',
    'abs','floor','ceil','round',
}

_FUNC_LATEX = {
    'sin': r'\sin', 'cos': r'\cos', 'tan': r'\tan', 'tg':  r'\tan',
    'cot': r'\cot', 'ctg': r'\cot', 'sec': r'\sec', 'csc': r'\csc',
    'asin': r'\arcsin', 'acos': r'\arccos', 'atan': r'\arctan',
    'arcsin': r'\arcsin', 'arccos': r'\arccos',
    'arctan': r'\arctan', 'arctg': r'\arctan',
    'sinh': r'\sinh', 'cosh': r'\cosh', 'tanh': r'\tanh', 'coth': r'\coth',
    'ln': r'\ln', 'log': r'\log', 'log10': r'\log_{10}', 'lg': r'\lg',
    # Обрабатываются отдельно:
    'exp': None, 'sqrt': None, 'abs': None,
    'floor': None, 'ceil': None, 'round': None,
}

_TOKEN_RE = re.compile(
    r'(?P<NUMBER>\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)'
    r'|(?P<FUNC>' + '|'.join(sorted(_FUNCTIONS, key=len, reverse=True)) + r')'
    r'|(?P<IDENT>[a-zA-Z_]\w*)'
    r'|(?P<OP>[+\-*/^(),])'
    r'|(?P<SPACE>\s+)',
    re.IGNORECASE,
)

_GREEK = {
    'alpha': r'\alpha', 'beta': r'\beta',  'gamma': r'\gamma',
    'delta': r'\delta', 'epsilon': r'\epsilon', 'theta': r'\theta',
    'lambda': r'\lambda', 'mu': r'\mu',   'nu': r'\nu',
    'xi': r'\xi',       'pi': r'\pi',     'rho': r'\rho',
    'sigma': r'\sigma', 'tau': r'\tau',   'phi': r'\phi',
    'chi': r'\chi',     'psi': r'\psi',   'omega': r'\omega',
    'e': 'e',
}


def _tokenize(s: str):
    tokens = []
    for m in _TOKEN_RE.finditer(s):
        kind = m.lastgroup
        val  = m.group()
        if kind == 'SPACE':
            continue
        tokens.append((kind, val.lower() if kind == 'FUNC' else val))
    # ** → ^ (два токена '*' '*' → один '^')
    result = []
    i = 0
    while i < len(tokens):
        if tokens[i] == ('OP', '*') and i+1 < len(tokens) and tokens[i+1] == ('OP', '*'):
            result.append(('OP', '^'))
            i += 2
        else:
            result.append(tokens[i])
            i += 1
    return result


def _ident_to_latex(name: str) -> str:
    low = name.lower()
    if low in _GREEK:
        return _GREEK[low]
    if len(name) > 1:
        return r'\mathrm{' + name + '}'
    return name


# ═══════════════════════════════════════════════════════════════════════════════
#  Рекурсивный Pratt-парсер
# ═══════════════════════════════════════════════════════════════════════════════

class _Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    def peek(self):
        return self.tokens[self.pos] if self.pos < len(self.tokens) else ('EOF', '')

    def consume(self, expected_val=None):
        tok = self.tokens[self.pos]
        if expected_val and tok[1] != expected_val:
            raise SyntaxError(f"Ожидалось '{expected_val}', получено '{tok[1]}'")
        self.pos += 1
        return tok

    @staticmethod
    def _infix_prec(op):
        return {'+': 1, '-': 1, '*': 2, '/': 2, '^': 4}.get(op, -1)

    @staticmethod
    def _wrap_base(s):
        if re.fullmatch(r'[a-zA-Z0-9\\{}_ ]+', s):
            return s
        return '{' + s + '}'

    @staticmethod
    def _wrap_exp(s):
        return '{' + s + '}'

    @staticmethod
    def _mul(left, right):
        if right.startswith((r'\left', r'\frac', r'\sqrt')):
            return left + r' \cdot ' + right
        return left + ' ' + right

    def parse_expr(self, min_prec: int = 0) -> str:
        left = self.parse_unary()
        while True:
            tok = self.peek()
            if tok[0] == 'EOF':
                break
            op = tok[1]
            if op in (')', ','):
                break
            prec = self._infix_prec(op)
            if prec < 0 or prec <= min_prec:
                break
            self.consume()
            if op == '/':
                right = self.parse_expr(0)
                left = rf'\frac{{{left}}}{{{right}}}'
                continue
            if op == '^':
                right = self.parse_expr(prec - 1)
                left = self._wrap_base(left) + '^' + self._wrap_exp(right)
                continue
            right = self.parse_expr(prec)
            if op == '*':
                left = self._mul(left, right)
            elif op == '+':
                left = left + ' + ' + right
            elif op == '-':
                left = left + ' - ' + right
        return left

    def parse_unary(self) -> str:
        tok = self.peek()
        if tok == ('OP', '-'):
            self.consume()
            return '-' + self.parse_expr(3)
        if tok == ('OP', '+'):
            self.consume()
            return self.parse_expr(3)
        return self.parse_primary()

    def parse_primary(self) -> str:
        tok = self.peek()
        if tok == ('OP', '('):
            self.consume('(')
            inner = self.parse_expr(0)
            self.consume(')')
            return r'\left(' + inner + r'\right)'
        if tok[0] == 'NUMBER':
            self.consume()
            return tok[1]
        if tok[0] == 'FUNC':
            return self.parse_function(tok[1])
        if tok[0] == 'IDENT':
            self.consume()
            return _ident_to_latex(tok[1])
        self.consume()
        return tok[1]

    def parse_function(self, fname: str) -> str:
        self.consume()
        self.consume('(')
        args = self._parse_args()
        self.consume(')')
        if fname == 'sqrt':
            return r'\sqrt{' + args[0] + '}'
        if fname == 'exp':
            return r'e^{' + args[0] + '}'
        if fname == 'abs':
            return r'\left|' + args[0] + r'\right|'
        if fname == 'floor':
            return r'\lfloor ' + args[0] + r' \rfloor'
        if fname == 'ceil':
            return r'\lceil ' + args[0] + r' \rceil'
        if fname == 'round':
            return r'\mathrm{round}\!\left(' + args[0] + r'\right)'
        latex_name = _FUNC_LATEX.get(fname, r'\mathrm{' + fname + '}')
        return latex_name + r'\!\left(' + ', '.join(args) + r'\right)'

    def _parse_args(self):
        args = []
        if self.peek() != ('OP', ')'):
            args.append(self.parse_expr(0))
            while self.peek() == ('OP', ','):
                self.consume(',')
                args.append(self.parse_expr(0))
        return args


# ═══════════════════════════════════════════════════════════════════════════════
#  Публичный API
# ═══════════════════════════════════════════════════════════════════════════════

def formula_to_latex(formula: str, display_mode: bool = True) -> str:
    """
    Конвертирует формулу NeoDesmos в LaTeX.

    display_mode=True  → \\[ ... \\]   (блочная формула)
    display_mode=False → $ ... $       (инлайн)
    """
    formula = formula.strip()
    if not formula:
        return ''
    lhs_latex = ''
    rhs = formula
    m = re.match(r'^([xy])\s*=\s*(.+)$', formula, re.IGNORECASE)
    if m:
        lhs_latex = m.group(1) + ' = '
        rhs = m.group(2)
    rhs = rhs.replace(' ', '')
    try:
        tokens = _tokenize(rhs)
        parser = _Parser(tokens)
        latex_rhs = parser.parse_expr(0)
    except Exception as e:
        return f'% Ошибка парсинга: {e}\n{formula}'
    full = lhs_latex + latex_rhs
    if display_mode:
        return r'\[' + '\n  ' + full + '\n' + r'\]'
    else:
        return '$' + full + '$'


def formula_to_python(formula: str) -> str:
    """Нормализует формулу к Python/NumPy синтаксису."""
    s = formula.strip()
    m = re.match(r'^[xy]\s*=\s*(.+)$', s, re.IGNORECASE)
    if m:
        s = m.group(1)
    s = re.sub(r'\btg\b',  'tan',   s, flags=re.IGNORECASE)
    s = re.sub(r'\bctg\b', '1/tan', s, flags=re.IGNORECASE)
    s = re.sub(r'\blg\b',  'log10', s, flags=re.IGNORECASE)
    s = re.sub(r'\bln\b',  'log',   s, flags=re.IGNORECASE)
    s = re.sub(r'(\d)([a-zA-Z(])', r'\1*\2', s)
    return s


def formula_to_wolfram(formula: str) -> str:
    """Конвертирует в синтаксис Wolfram Alpha."""
    s = formula.strip()
    lhs = ''
    m = re.match(r'^([xy])\s*=\s*(.+)$', s, re.IGNORECASE)
    if m:
        lhs = m.group(1) + ' = '
        s = m.group(2)
    for pat, rep in [
        (r'\btg\b',    'Tan'),  (r'\bctg\b',  'Cot'),
        (r'\bsin\b',   'Sin'),  (r'\bcos\b',  'Cos'),
        (r'\btan\b',   'Tan'),  (r'\bcot\b',  'Cot'),
        (r'\bsqrt\b',  'Sqrt'), (r'\bexp\b',  'Exp'),
        (r'\bln\b',    'Log'),  (r'\babs\b',  'Abs'),
        (r'\bfloor\b', 'Floor'),(r'\bceil\b', 'Ceiling'),
        (r'\bsinh\b',  'Sinh'), (r'\bcosh\b', 'Cosh'),
        (r'\btanh\b',  'Tanh'), (r'\bpi\b',   'Pi'),
    ]:
        s = re.sub(pat, rep, s, flags=re.IGNORECASE)
    s = re.sub(r'\*\*', '^', s)
    return lhs + s


# ═══════════════════════════════════════════════════════════════════════════════
#  Диалог PySide6
# ═══════════════════════════════════════════════════════════════════════════════

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit,
    QPushButton, QComboBox, QFrame, QApplication, QWidget,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont

_MONO = QFont("Courier New", 10)

_FORMATS = [
    ('LaTeX — блочный  \\[ \\]',  'latex_display'),
    ('LaTeX — инлайн  $ $',        'latex_inline'),
    ('Python / NumPy',              'python'),
    ('Wolfram Alpha',               'wolfram'),
]


class FormulaConverterDialog(QDialog):
    """
    Диалог конвертации одной формулы в разные форматы.
    Открывается через меню Инструменты → Конвертер формул.
    Можно передать initial_formula, например из выбранной ячейки.
    """

    def __init__(self, initial_formula: str = '', all_formulas: list = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Конвертер формул")
        self.setMinimumSize(700, 460)
        self.resize(820, 520)
        self._all_formulas = all_formulas or []
        self._build_ui(initial_formula)
        self._schedule_convert()

    def _build_ui(self, initial_formula: str):
        root = QVBoxLayout(self)
        root.setSpacing(10)

        # ── Ввод ────────────────────────────────────────────────────────────
        root.addWidget(QLabel("<b>Исходная формула:</b>"))

        if self._all_formulas:
            row_pick = QWidget()
            pl = QHBoxLayout(row_pick)
            pl.setContentsMargins(0, 0, 0, 0)
            pl.addWidget(QLabel("Выбрать из проекта:"))

            self.pick_combo = QComboBox()
            self.pick_combo.addItem("— выберите формулу —")
            for f in self._all_formulas:
                # Обрезаем длинные формулы для читаемости в списке
                label = f if len(f) <= 50 else f[:47] + '...'
                self.pick_combo.addItem(label, userData=f)
            self.pick_combo.currentIndexChanged.connect(self._on_pick_formula)
            pl.addWidget(self.pick_combo, stretch=1)
            root.addWidget(row_pick)

        row_input = QWidget()
        rl = QHBoxLayout(row_input)
        rl.setContentsMargins(0, 0, 0, 0)

        self.input_edit = QTextEdit()
        self.input_edit.setFont(_MONO)
        self.input_edit.setFixedHeight(52)
        self.input_edit.setPlaceholderText(
            "Введите формулу:  sin(x)/x   y=(x+1)/(x-1)   (-b+sqrt(b**2-4*a*c))/(2*a)"
        )
        self.input_edit.setPlainText(initial_formula)
        self.input_edit.textChanged.connect(self._schedule_convert)
        rl.addWidget(self.input_edit, stretch=1)

        paste_btn = QPushButton("📋 Вставить")
        paste_btn.setFixedWidth(95)
        paste_btn.setToolTip("Вставить из буфера обмена")
        paste_btn.clicked.connect(self._paste_formula)
        rl.addWidget(paste_btn)

        root.addWidget(row_input)

        # ── Выбор формата ───────────────────────────────────────────────────
        row_fmt = QWidget()
        fl = QHBoxLayout(row_fmt)
        fl.setContentsMargins(0, 0, 0, 0)
        fl.addWidget(QLabel("Формат:"))

        self.fmt_combo = QComboBox()
        for label, _ in _FORMATS:
            self.fmt_combo.addItem(label)
        self.fmt_combo.setFixedWidth(280)
        self.fmt_combo.currentIndexChanged.connect(self._convert_now)
        fl.addWidget(self.fmt_combo)
        fl.addStretch()
        root.addWidget(row_fmt)

        # ── Разделитель ─────────────────────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFrameShadow(QFrame.Sunken)
        root.addWidget(sep)

        # ── Результат ───────────────────────────────────────────────────────
        root.addWidget(QLabel("<b>Результат:</b>"))

        self.output_edit = QTextEdit()
        self.output_edit.setFont(_MONO)
        self.output_edit.setReadOnly(True)
        self.output_edit.setStyleSheet("""
            QTextEdit {
                background: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 6px;
            }
        """)
        root.addWidget(self.output_edit, stretch=1)

        # ── Статус ──────────────────────────────────────────────────────────
        self.status_lbl = QLabel("")
        self.status_lbl.setStyleSheet("color: gray; font-size: 10px;")
        root.addWidget(self.status_lbl)

        # ── Кнопки ──────────────────────────────────────────────────────────
        row_btn = QWidget()
        bl = QHBoxLayout(row_btn)
        bl.setContentsMargins(0, 0, 0, 0)

        copy_btn = QPushButton("📋 Копировать результат")
        copy_btn.setMinimumHeight(32)
        copy_btn.clicked.connect(self._copy_result)
        bl.addWidget(copy_btn)

        bl.addStretch()

        close_btn = QPushButton("Закрыть")
        close_btn.setMinimumHeight(32)
        close_btn.clicked.connect(self.close)
        bl.addWidget(close_btn)

        root.addWidget(row_btn)

        # Таймер отложенной конвертации
        self._timer = QTimer()
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._convert_now)

    # ── Логика ──────────────────────────────────────────────────────────────

    def _schedule_convert(self):
        self._timer.start(300)

    def _convert_now(self):
        formula = self.input_edit.toPlainText().strip()
        if not formula:
            self.output_edit.setPlainText('')
            self.status_lbl.setText('')
            return
        fmt_key = _FORMATS[self.fmt_combo.currentIndex()][1]
        try:
            if fmt_key == 'latex_display':
                result = formula_to_latex(formula, display_mode=True)
            elif fmt_key == 'latex_inline':
                result = formula_to_latex(formula, display_mode=False)
            elif fmt_key == 'python':
                result = formula_to_python(formula)
            else:
                result = formula_to_wolfram(formula)
            self.output_edit.setPlainText(result)
            self.status_lbl.setText('✓ Конвертация успешна')
            self.status_lbl.setStyleSheet('color: green; font-size: 10px;')
        except Exception as e:
            self.output_edit.setPlainText(f'Ошибка: {e}')
            self.status_lbl.setText('✗ Ошибка конвертации')
            self.status_lbl.setStyleSheet('color: red; font-size: 10px;')

    def _paste_formula(self):
        text = QApplication.clipboard().text().strip()
        if text:
            self.input_edit.setPlainText(text)
        else:
            self.status_lbl.setText('Буфер обмена пуст')
            self.status_lbl.setStyleSheet('color: orange; font-size: 10px;')

    def _copy_result(self):
        text = self.output_edit.toPlainText()
        if text:
            QApplication.clipboard().setText(text)
            self.status_lbl.setText('✓ Скопировано в буфер обмена')
            self.status_lbl.setStyleSheet('color: green; font-size: 10px;')

    def _on_pick_formula(self, index: int):
        if index <= 0:
            return
        formula = self.pick_combo.itemData(index)
        if formula:
            self.input_edit.setPlainText(formula)
            # Сбрасываем комбо обратно на заглушку,
            # чтобы можно было выбрать ту же формулу повторно
            self.pick_combo.blockSignals(True)
            self.pick_combo.setCurrentIndex(0)
            self.pick_combo.blockSignals(False)
