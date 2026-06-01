# highlighter.py
import re
from PySide6.QtGui import QSyntaxHighlighter, QTextCharFormat, QFont
from utils import HIGHLIGHT_FUNCTION, HIGHLIGHT_NUMBER, HIGHLIGHT_VARIABLE, FUNCTION_NAMES

class FunctionHighlighter(QSyntaxHighlighter):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.functions = FUNCTION_NAMES

        self.function_format = QTextCharFormat()
        self.function_format.setForeground(HIGHLIGHT_FUNCTION)
        self.function_format.setFontWeight(QFont.Bold)

        self.number_format = QTextCharFormat()
        self.number_format.setForeground(HIGHLIGHT_NUMBER)

        self.variable_format = QTextCharFormat()
        self.variable_format.setForeground(HIGHLIGHT_VARIABLE)

    def highlightBlock(self, text):
        for func in self.functions:
            pattern = r'\b' + re.escape(func) + r'\b'
            for match in re.finditer(pattern, text, re.IGNORECASE):
                start, end = match.start(), match.end()
                self.setFormat(start, end - start, self.function_format)

        number_pattern = r'\b\d+(?:\.\d+)?\b'
        for match in re.finditer(number_pattern, text):
            start, end = match.start(), match.end()
            self.setFormat(start, end - start, self.number_format)

        var_pattern = r'\bx\b|\by\b'
        for match in re.finditer(var_pattern, text, re.IGNORECASE):
            start, end = match.start(), match.end()
            self.setFormat(start, end - start, self.variable_format)