
from PySide6.QtGui import QIcon
import ast
import math
import operator
import sys

from datetime import datetime

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QFont, QKeyEvent
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLineEdit,
    QLabel,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QFrame,
    QMessageBox,
)


# ============================================================
# CALCULATOR ENGINE
# ============================================================

class ExpressionError(Exception):
    """Raised when an expression is invalid or unsafe."""


ALLOWED_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def safe_calculate(expression: str):
    """Safely evaluate a mathematical expression using AST."""

    expression = expression.replace("×", "*").replace("÷", "/")

    if not expression or len(expression) > 256:
        raise ExpressionError("Invalid expression")

    try:
        tree = ast.parse(expression, mode="eval")
    except (SyntaxError, ValueError, RecursionError):
        raise ExpressionError("Invalid expression")

    nodes = list(ast.walk(tree))

    if len(nodes) > 100:
        raise ExpressionError("Expression is too complex")

    def visit(node):

        if isinstance(node, ast.Expression):
            return visit(node.body)

        if isinstance(node, ast.Constant):
            if type(node.value) not in (int, float):
                raise ExpressionError("Invalid number")

            value = node.value

            if not math.isfinite(value) or abs(value) > 1e100:
                raise ExpressionError("Number is too large")

            return value

        if isinstance(node, ast.UnaryOp):
            operator_type = type(node.op)

            if operator_type not in ALLOWED_OPERATORS:
                raise ExpressionError("Unsupported operator")

            return ALLOWED_OPERATORS[operator_type](
                visit(node.operand)
            )

        if isinstance(node, ast.BinOp):
            operator_type = type(node.op)

            if operator_type not in ALLOWED_OPERATORS:
                raise ExpressionError("Unsupported operator")

            left = visit(node.left)
            right = visit(node.right)

            if isinstance(node.op, ast.Pow):
                if abs(right) > 100:
                    raise ExpressionError("Exponent is too large")

            try:
                result = ALLOWED_OPERATORS[operator_type](
                    left,
                    right
                )
            except (ZeroDivisionError, OverflowError, ValueError):
                raise ExpressionError("Math error")

            if isinstance(result, complex):
                raise ExpressionError("Invalid result")

            if not math.isfinite(result) or abs(result) > 1e100:
                raise ExpressionError("Result is out of range")

            return result

        raise ExpressionError("Unsupported expression")

    try:
        result = visit(tree)
    except ExpressionError:
        raise
    except (ZeroDivisionError, OverflowError, TypeError, ValueError):
        raise ExpressionError("Math error")

    if isinstance(result, complex):
        raise ExpressionError("Invalid result")

    return result


def format_result(value) -> str:
    """Format calculation results."""

    if isinstance(value, int):
        return str(value)

    if value.is_integer():
        return str(int(value))

    return f"{value:.12g}"


# ============================================================
# THEME
# ============================================================

DARK_THEME = """
QMainWindow {
    background-color: #15161C;
}

QWidget {
    color: #F2F3F8;
    font-family: "Segoe UI";
}

QFrame#calculatorPanel {
    background-color: #1D1F28;
    border: 1px solid #292C38;
    border-radius: 20px;
}

QFrame#historyPanel {
    background-color: #1D1F28;
    border: 1px solid #292C38;
    border-radius: 20px;
}

QLabel#appTitle {
    color: #F4F4FA;
    font-size: 23px;
    font-weight: 700;
}

QLabel#subtitle {
    color: #9295A5;
    font-size: 12px;
}

QLabel#sectionTitle {
    color: #F4F4FA;
    font-size: 16px;
    font-weight: 700;
}

QLabel#expressionLabel {
    color: #9295A5;
    font-size: 16px;
}

QLineEdit#display {
    background-color: #252833;
    border: 1px solid #343847;
    border-radius: 14px;
    padding: 14px;
    color: #FFFFFF;
    font-size: 32px;
    font-weight: 600;
    selection-background-color: #6558D3;
}

QPushButton {
    background-color: #292D38;
    border: none;
    border-radius: 13px;
    color: #F3F4F8;
    font-size: 19px;
    font-weight: 600;
    min-height: 58px;
}

QPushButton:hover {
    background-color: #3A4050;
}

QPushButton:pressed {
    background-color: #464C5D;
}

QPushButton[buttonType="operator"] {
    background-color: #343849;
    color: #AFA6FF;
}

QPushButton[buttonType="operator"]:hover {
    background-color: #444A60;
}

QPushButton[buttonType="special"] {
    background-color: #303441;
    color: #C1C5D3;
}

QPushButton[buttonType="special"]:hover {
    background-color: #414757;
}

QPushButton[buttonType="equals"] {
    background-color: #6558D3;
    color: white;
}

QPushButton[buttonType="equals"]:hover {
    background-color: #796CE8;
}

QListWidget {
    background-color: transparent;
    border: none;
    outline: none;
    padding: 4px;
}

QListWidget::item {
    background-color: #272A35;
    border-radius: 10px;
    padding: 12px;
    margin-bottom: 7px;
}

QListWidget::item:hover {
    background-color: #343849;
}

QListWidget::item:selected {
    background-color: #403B68;
}

QPushButton#clearHistoryButton {
    background-color: transparent;
    color: #9295A5;
    font-size: 12px;
    min-height: 30px;
}

QPushButton#clearHistoryButton:hover {
    color: #FFFFFF;
    background-color: #303441;
}
"""


# ============================================================
# MAIN WINDOW
# ============================================================

class EasyCalculator(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Easy Calculator")
        self.setMinimumSize(720, 570)
        self.resize(850, 650)

        self.expression = ""
        self.just_calculated = False
        self.history = []

        self.setStyleSheet(DARK_THEME)

        self.setup_ui()
        self.setup_shortcuts()

    # --------------------------------------------------------
    # UI
    # --------------------------------------------------------

    def setup_ui(self):

        central = QWidget()
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(22, 20, 22, 22)
        root.setSpacing(18)

        # Header

        header = QHBoxLayout()

        title_layout = QVBoxLayout()
        title_layout.setSpacing(3)

        title = QLabel("Easy Calculator")
        title.setObjectName("appTitle")

        subtitle = QLabel("Simple. Fast. Accurate.")
        subtitle.setObjectName("subtitle")

        title_layout.addWidget(title)
        title_layout.addWidget(subtitle)

        version = QLabel("VERSION 1.0")
        version.setStyleSheet("""
            background-color: #302B50;
            color: #B7AEFF;
            padding: 7px 12px;
            border-radius: 9px;
            font-size: 10px;
            font-weight: 700;
        """)

        header.addLayout(title_layout)
        header.addStretch()
        header.addWidget(version)

        root.addLayout(header)

        # Main content

        content = QHBoxLayout()
        content.setSpacing(16)

        # Calculator panel

        calculator_panel = QFrame()
        calculator_panel.setObjectName("calculatorPanel")

        calculator_layout = QVBoxLayout(calculator_panel)
        calculator_layout.setContentsMargins(18, 18, 18, 18)
        calculator_layout.setSpacing(14)

        mode_label = QLabel("STANDARD")
        mode_label.setStyleSheet("""
            color: #AFA6FF;
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 2px;
        """)

        calculator_layout.addWidget(mode_label)

        self.expression_label = QLabel("")
        self.expression_label.setObjectName("expressionLabel")
        self.expression_label.setAlignment(
            Qt.AlignmentFlag.AlignRight |
            Qt.AlignmentFlag.AlignVCenter
        )

        calculator_layout.addWidget(self.expression_label)

        self.display = QLineEdit()
        self.display.setObjectName("display")
        self.display.setAlignment(
            Qt.AlignmentFlag.AlignRight
        )
        self.display.setPlaceholderText("0")
        self.display.setClearButtonEnabled(False)

        calculator_layout.addWidget(self.display)

        # Buttons

        grid = QGridLayout()
        grid.setSpacing(9)

        buttons = [
            ("C", "clear", 0, 0, "special"),
            ("⌫", "back", 0, 1, "special"),
            ("(", "(", 0, 2, "operator"),
            (")", ")", 0, 3, "operator"),
            ("÷", "÷", 0, 4, "operator"),

            ("7", "7", 1, 0, "number"),
            ("8", "8", 1, 1, "number"),
            ("9", "9", 1, 2, "number"),
            ("%", "percent", 1, 3, "special"),
            ("×", "×", 1, 4, "operator"),

            ("4", "4", 2, 0, "number"),
            ("5", "5", 2, 1, "number"),
            ("6", "6", 2, 2, "number"),
            ("±", "sign", 2, 3, "special"),
            ("−", "-", 2, 4, "operator"),

            ("1", "1", 3, 0, "number"),
            ("2", "2", 3, 1, "number"),
            ("3", "3", 3, 2, "number"),
            ("0", "0", 3, 3, "number"),
            ("+", "+", 3, 4, "operator"),

            (".", ".", 4, 0, "number"),
        ]

        for label, action, row, column, button_type in buttons:

            button = QPushButton(label)
            button.setProperty("buttonType", button_type)
            button.setCursor(Qt.CursorShape.PointingHandCursor)

            button.clicked.connect(
                lambda checked=False, a=action: self.handle_button(a)
            )

            grid.addWidget(button, row, column)

        equals_button = QPushButton("=")
        equals_button.setProperty("buttonType", "equals")
        equals_button.setCursor(Qt.CursorShape.PointingHandCursor)
        equals_button.clicked.connect(self.calculate)

        grid.addWidget(equals_button, 4, 1, 1, 4)

        calculator_layout.addLayout(grid)

        content.addWidget(calculator_panel, 3)

        # History panel

        history_panel = QFrame()
        history_panel.setObjectName("historyPanel")
        history_panel.setMinimumWidth(185)
        history_panel.setMaximumWidth(240)

        history_layout = QVBoxLayout(history_panel)
        history_layout.setContentsMargins(15, 17, 15, 15)
        history_layout.setSpacing(12)

        history_header = QHBoxLayout()

        history_title = QLabel("History")
        history_title.setObjectName("sectionTitle")

        clear_history = QPushButton("Clear")
        clear_history.setObjectName("clearHistoryButton")
        clear_history.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_history.clicked.connect(self.clear_history)

        history_header.addWidget(history_title)
        history_header.addStretch()
        history_header.addWidget(clear_history)

        history_layout.addLayout(history_header)

        self.history_list = QListWidget()
        self.history_list.itemClicked.connect(self.restore_history)

        history_layout.addWidget(self.history_list)

        history_hint = QLabel("Click a result to reuse it")
        history_hint.setObjectName("subtitle")
        history_hint.setWordWrap(True)

        history_layout.addWidget(history_hint)

        content.addWidget(history_panel, 1)

        root.addLayout(content)

        self.statusBar().showMessage(
            "Ready  •  Enter: Calculate  •  Esc: Clear"
        )

    # --------------------------------------------------------
    # KEYBOARD
    # --------------------------------------------------------

    def setup_shortcuts(self):

        self.display.returnPressed.connect(self.calculate)

        self.display.textChanged.connect(
            self.update_expression_preview
        )

        self.display.setFocus()

    def keyPressEvent(self, event: QKeyEvent):

        if event.key() == Qt.Key.Key_Escape:
            self.clear()
            return

        if event.key() == Qt.Key.Key_Return:
            self.calculate()
            return

        super().keyPressEvent(event)

    # --------------------------------------------------------
    # BUTTON HANDLER
    # --------------------------------------------------------

    def handle_button(self, action: str):

        current = self.display.text()

        if action == "clear":
            self.clear()
            return

        if action == "back":
            self.display.backspace()
            self.just_calculated = False
            return

        if action == "equals":
            self.calculate()
            return

        if action == "percent":
            self.apply_percent()
            return

        if action == "sign":
            self.change_sign()
            return

        if self.just_calculated:

            if action in {"+", "-", "×", "÷"}:
                pass
            else:
                self.display.clear()

            self.just_calculated = False

        self.display.insert(action)
        self.display.setFocus()

    # --------------------------------------------------------
    # CALCULATIONS
    # --------------------------------------------------------

    def calculate(self):

        current = self.display.text().strip()

        if not current:
            return

        try:

            result = safe_calculate(current)
            formatted = format_result(result)

            self.add_history(current, formatted)

            self.expression_label.setText(current)
            self.display.setText(formatted)

            self.just_calculated = True

            self.statusBar().showMessage("Calculation completed")

        except ExpressionError:

            self.expression_label.setText(current)
            self.display.setText("Error")

            self.just_calculated = True

            self.statusBar().showMessage(
                "Invalid expression or mathematical error"
            )

        self.display.setFocus()

    def apply_percent(self):

        current = self.display.text().strip()

        if not current:
            return

        try:

            result = safe_calculate(current) / 100

            self.expression_label.setText(current + " %")
            self.display.setText(format_result(result))

            self.just_calculated = True

        except ExpressionError:

            self.display.setText("Error")
            self.just_calculated = True

        self.display.setFocus()

    def change_sign(self):

        current = self.display.text().strip()

        if not current:
            return

        try:

            result = -safe_calculate(current)

            self.expression_label.setText("-(" + current + ")")
            self.display.setText(format_result(result))

            self.just_calculated = True

        except ExpressionError:

            self.display.setText("Error")
            self.just_calculated = True

        self.display.setFocus()

    # --------------------------------------------------------
    # HISTORY
    # --------------------------------------------------------

    def add_history(self, expression: str, result: str):

        timestamp = datetime.now().strftime("%H:%M")

        item_text = (
            f"{expression}\n"
            f"= {result}     •     {timestamp}"
        )

        item = QListWidgetItem(item_text)

        item.setData(
            Qt.ItemDataRole.UserRole,
            (expression, result)
        )

        self.history_list.insertItem(0, item)

        self.history.insert(0, (expression, result))

    def restore_history(self, item):

        data = item.data(Qt.ItemDataRole.UserRole)

        if data:
            expression, result = data

            self.expression_label.setText(expression)
            self.display.setText(result)

            self.just_calculated = True

        self.display.setFocus()

    def clear_history(self):

        self.history.clear()
        self.history_list.clear()

        self.statusBar().showMessage("History cleared")

    # --------------------------------------------------------
    # DISPLAY
    # --------------------------------------------------------

    def update_expression_preview(self, text):

        if not self.just_calculated:
            self.expression_label.setText("")

    def clear(self):

        self.display.clear()
        self.expression_label.clear()

        self.just_calculated = False

        self.display.setFocus()


# ============================================================
# APPLICATION ENTRY POINT
# ============================================================

def main():

    app = QApplication(sys.argv)

    app.setWindowIcon(QIcon("icon.ico"))
    app.setApplicationName("Easy Calculator")
    app.setOrganizationName("Easy Calculator")

    app.setFont(QFont("Segoe UI", 10))

    window = EasyCalculator()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
