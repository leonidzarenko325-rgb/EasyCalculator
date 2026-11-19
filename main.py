import ast
import math
import operator
import sys
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QIcon, QKeyEvent
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


# ============================================================
# CALCULATOR ENGINE
# ============================================================

class ExpressionError(Exception):
    """Raised when an expression is invalid or unsafe."""


BINARY_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
}

UNARY_OPERATORS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def _factorial(value):
    if not isinstance(value, (int, float)) or not float(value).is_integer():
        raise ExpressionError("Factorial requires a whole number")
    value = int(value)
    if value < 0 or value > 170:
        raise ExpressionError("Factorial is out of range")
    return math.factorial(value)


def safe_calculate(expression: str, degrees: bool = True):
    """Evaluate a restricted mathematical expression without eval()."""

    expression = (
        expression.strip()
        .replace("×", "*")
        .replace("÷", "/")
        .replace("−", "-")
        .replace("^", "**")
        .replace("π", "pi")
    )

    if not expression or len(expression) > 256:
        raise ExpressionError("Invalid expression")

    def angle_in(value):
        return math.radians(value) if degrees else value

    def angle_out(value):
        return math.degrees(value) if degrees else value

    functions = {
        "sqrt": math.sqrt,
        "sin": lambda x: math.sin(angle_in(x)),
        "cos": lambda x: math.cos(angle_in(x)),
        "tan": lambda x: math.tan(angle_in(x)),
        "asin": lambda x: angle_out(math.asin(x)),
        "acos": lambda x: angle_out(math.acos(x)),
        "atan": lambda x: angle_out(math.atan(x)),
        "ln": math.log,
        "log": math.log10,
        "exp": math.exp,
        "abs": abs,
        "floor": math.floor,
        "ceil": math.ceil,
        "factorial": _factorial,
    }

    constants = {"pi": math.pi, "e": math.e}

    try:
        tree = ast.parse(expression, mode="eval")
    except (SyntaxError, ValueError, RecursionError):
        raise ExpressionError("Invalid expression")

    if len(list(ast.walk(tree))) > 120:
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

        if isinstance(node, ast.Name):
            if node.id in constants:
                return constants[node.id]
            raise ExpressionError("Unknown constant")

        if isinstance(node, ast.UnaryOp):
            op_type = type(node.op)
            if op_type not in UNARY_OPERATORS:
                raise ExpressionError("Unsupported operator")
            return UNARY_OPERATORS[op_type](visit(node.operand))

        if isinstance(node, ast.BinOp):
            op_type = type(node.op)
            if op_type not in BINARY_OPERATORS:
                raise ExpressionError("Unsupported operator")

            left = visit(node.left)
            right = visit(node.right)

            if isinstance(node.op, ast.Pow) and abs(right) > 100:
                raise ExpressionError("Exponent is too large")

            try:
                result = BINARY_OPERATORS[op_type](left, right)
            except (ZeroDivisionError, OverflowError, ValueError):
                raise ExpressionError("Math error")

            if isinstance(result, complex):
                raise ExpressionError("Invalid result")
            if not math.isfinite(result) or abs(result) > 1e100:
                raise ExpressionError("Result is out of range")
            return result

        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in functions:
                raise ExpressionError("Unsupported function")
            if node.keywords or len(node.args) != 1:
                raise ExpressionError("Invalid function arguments")
            argument = visit(node.args[0])
            try:
                result = functions[node.func.id](argument)
            except (ValueError, OverflowError, ZeroDivisionError):
                raise ExpressionError("Math error")
            if isinstance(result, complex) or not math.isfinite(result):
                raise ExpressionError("Invalid result")
            if abs(result) > 1e100:
                raise ExpressionError("Result is out of range")
            return result

        raise ExpressionError("Unsupported expression")

    try:
        result = visit(tree)
    except ExpressionError:
        raise
    except (ArithmeticError, TypeError, ValueError):
        raise ExpressionError("Math error")

    if isinstance(result, complex) or not math.isfinite(result):
        raise ExpressionError("Invalid result")
    return result


def format_result(value) -> str:
    if isinstance(value, int):
        return str(value)
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.12g}"


# ============================================================
# VISUAL STYLE
# ============================================================

APP_STYLE = """
QMainWindow {
    background: #17191e;
}
QWidget {
    color: #e8eaf0;
    font-family: "Segoe UI";
    font-size: 10pt;
}
QFrame#calculatorPanel, QFrame#historyPanel {
    background: #20232a;
    border: 1px solid #30343e;
    border-radius: 8px;
}
QLabel#appTitle {
    color: #f1f2f5;
    font-size: 22pt;
    font-weight: 650;
}
QLabel#subtitle, QLabel#muted {
    color: #969daa;
    font-size: 9pt;
}
QLabel#sectionTitle {
    color: #f1f2f5;
    font-size: 12pt;
    font-weight: 650;
}
QLabel#expressionLabel {
    color: #9ba2b0;
    font-size: 11pt;
}
QLineEdit#display {
    background: #171a20;
    border: 1px solid #3a404c;
    border-radius: 6px;
    padding: 12px;
    color: #ffffff;
    font-size: 25pt;
    font-weight: 500;
    selection-background-color: #526b91;
}
QPushButton {
    background: #303640;
    border: 1px solid #3a424f;
    border-radius: 6px;
    color: #edf0f5;
    min-height: 48px;
    font-size: 14pt;
    font-weight: 500;
}
QPushButton:hover {
    background: #3a4350;
    border-color: #596779;
}
QPushButton:pressed {
    background: #252b34;
}
QPushButton[buttonType="operator"] {
    background: #303b4b;
    color: #c6d5eb;
}
QPushButton[buttonType="special"] {
    background: #292e37;
    color: #c1c7d1;
}
QPushButton[buttonType="function"] {
    background: #293440;
    color: #c4d3e5;
    font-size: 11pt;
}
QPushButton[buttonType="equals"] {
    background: #526b91;
    border-color: #526b91;
    color: white;
    font-size: 17pt;
    font-weight: 650;
}
QPushButton[buttonType="equals"]:hover {
    background: #607da8;
}
QPushButton#modeButton, QPushButton#angleButton {
    min-height: 32px;
    padding: 0 12px;
    font-size: 9pt;
    border-radius: 5px;
}
QPushButton#modeButton {
    background: #34465d;
    border-color: #405673;
    color: #e1eaf6;
}
QPushButton#clearHistoryButton {
    min-height: 28px;
    border: none;
    background: transparent;
    color: #9ba2b0;
    font-size: 9pt;
}
QPushButton#clearHistoryButton:hover {
    background: #303640;
    color: #ffffff;
}
QListWidget {
    background: transparent;
    border: none;
    outline: none;
    padding: 2px;
}
QListWidget::item {
    background: #292e37;
    border: 1px solid #343b47;
    border-radius: 5px;
    padding: 10px;
    margin-bottom: 6px;
}
QListWidget::item:hover {
    background: #343c48;
}
QListWidget::item:selected {
    background: #3a4b62;
}
QStatusBar {
    color: #969daa;
    background: #17191e;
}
"""


# ============================================================
# MAIN WINDOW
# ============================================================

class EasyCalculator(QMainWindow):
    STANDARD_BUTTONS = [
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

    SCIENTIFIC_BUTTONS = [
        ("sin", "sin(", 0, 0, "function"),
        ("cos", "cos(", 0, 1, "function"),
        ("tan", "tan(", 0, 2, "function"),
        ("√", "sqrt(", 0, 3, "function"),
        ("x²", "**2", 0, 4, "function"),
        ("asin", "asin(", 1, 0, "function"),
        ("acos", "acos(", 1, 1, "function"),
        ("atan", "atan(", 1, 2, "function"),
        ("ln", "ln(", 1, 3, "function"),
        ("log", "log(", 1, 4, "function"),
        ("π", "pi", 2, 0, "function"),
        ("e", "e", 2, 1, "function"),
        ("xʸ", "^", 2, 2, "function"),
        ("1/x", "1/(", 2, 3, "function"),
        ("n!", "factorial(", 2, 4, "function"),
    ]

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Easy Calculator")
        self.setMinimumSize(760, 590)
        self.resize(940, 680)

        self.just_calculated = False
        self.scientific_mode = False
        self.degrees_mode = True

        self.setStyleSheet(APP_STYLE)
        self.setup_ui()
        self.setup_shortcuts()

    def setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(20, 18, 20, 16)
        root.setSpacing(14)

        header = QHBoxLayout()
        title_layout = QVBoxLayout()
        title_layout.setSpacing(2)

        title = QLabel("Easy Calculator")
        title.setObjectName("appTitle")
        subtitle = QLabel("A practical calculator for everyday work")
        subtitle.setObjectName("subtitle")

        title_layout.addWidget(title)
        title_layout.addWidget(subtitle)
        header.addLayout(title_layout)
        header.addStretch()

        self.mode_button = QPushButton("Scientific mode")
        self.mode_button.setObjectName("modeButton")
        self.mode_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mode_button.clicked.connect(self.toggle_mode)
        header.addWidget(self.mode_button)

        version = QLabel("2.0")
        version.setStyleSheet(
            "color:#aeb8c7; padding:5px 8px; border:1px solid #3a424f; "
            "border-radius:4px; font-size:9pt;"
        )
        header.addWidget(version)
        root.addLayout(header)

        content = QHBoxLayout()
        content.setSpacing(14)

        self.calculator_panel = QFrame()
        self.calculator_panel.setObjectName("calculatorPanel")
        calculator_layout = QVBoxLayout(self.calculator_panel)
        calculator_layout.setContentsMargins(16, 15, 16, 16)
        calculator_layout.setSpacing(11)

        mode_row = QHBoxLayout()
        self.mode_label = QLabel("STANDARD")
        self.mode_label.setStyleSheet(
            "color:#a9bad0; font-size:9pt; font-weight:650; letter-spacing:1px;"
        )
        mode_row.addWidget(self.mode_label)
        mode_row.addStretch()

        self.angle_button = QPushButton("DEG")
        self.angle_button.setObjectName("angleButton")
        self.angle_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.angle_button.clicked.connect(self.toggle_angle_mode)
        self.angle_button.hide()
        mode_row.addWidget(self.angle_button)
        calculator_layout.addLayout(mode_row)

        self.expression_label = QLabel("")
        self.expression_label.setObjectName("expressionLabel")
        self.expression_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        calculator_layout.addWidget(self.expression_label)

        self.display = QLineEdit()
        self.display.setObjectName("display")
        self.display.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.display.setPlaceholderText("0")
        self.display.setClearButtonEnabled(False)
        calculator_layout.addWidget(self.display)

        self.button_grid = QGridLayout()
        self.button_grid.setSpacing(7)
        calculator_layout.addLayout(self.button_grid)
        self.rebuild_buttons()

        content.addWidget(self.calculator_panel, 3)

        history_panel = QFrame()
        history_panel.setObjectName("historyPanel")
        history_panel.setMinimumWidth(190)
        history_panel.setMaximumWidth(245)

        history_layout = QVBoxLayout(history_panel)
        history_layout.setContentsMargins(13, 15, 13, 13)
        history_layout.setSpacing(10)

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

        hint = QLabel("Select a result to use it again")
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        history_layout.addWidget(hint)

        content.addWidget(history_panel, 1)
        root.addLayout(content)

        self.statusBar().showMessage(
            "Ready  •  Enter: calculate  •  Esc: clear  •  ^: power"
        )

    def rebuild_buttons(self):
        while self.button_grid.count():
            item = self.button_grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        buttons = list(self.STANDARD_BUTTONS)
        if self.scientific_mode:
            buttons.extend(self.SCIENTIFIC_BUTTONS)

        for label, action, row, column, button_type in buttons:
            button = QPushButton(label)
            button.setProperty("buttonType", button_type)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(
                lambda checked=False, a=action: self.handle_button(a)
            )
            grid_row = row + (5 if self.scientific_mode and button_type == "function" else 0)
            self.button_grid.addWidget(button, grid_row, column)

        equals = QPushButton("=")
        equals.setProperty("buttonType", "equals")
        equals.setCursor(Qt.CursorShape.PointingHandCursor)
        equals.clicked.connect(self.calculate)
        self.button_grid.addWidget(equals, 4, 1, 1, 4)

    def setup_shortcuts(self):
        self.display.returnPressed.connect(self.calculate)
        self.display.textChanged.connect(self.update_expression_preview)
        self.display.setFocus()

    def toggle_mode(self):
        self.scientific_mode = not self.scientific_mode
        self.mode_button.setText(
            "Standard mode" if self.scientific_mode else "Scientific mode"
        )
        self.mode_label.setText(
            "SCIENTIFIC" if self.scientific_mode else "STANDARD"
        )
        self.angle_button.setVisible(self.scientific_mode)
        self.rebuild_buttons()
        self.statusBar().showMessage(
            "Scientific functions enabled" if self.scientific_mode
            else "Standard calculator"
        )
        self.display.setFocus()

    def toggle_angle_mode(self):
        self.degrees_mode = not self.degrees_mode
        self.angle_button.setText("DEG" if self.degrees_mode else "RAD")
        self.statusBar().showMessage(
            "Angles are in degrees" if self.degrees_mode
            else "Angles are in radians"
        )
        self.display.setFocus()

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Escape:
            self.clear()
            return
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.calculate()
            return
        super().keyPressEvent(event)

    def handle_button(self, action: str):
        if action == "clear":
            self.clear()
            return
        if action == "back":
            self.display.backspace()
            self.just_calculated = False
            self.display.setFocus()
            return
        if action == "percent":
            self.apply_percent()
            return
        if action == "sign":
            self.change_sign()
            return

        if self.just_calculated:
            if action in {"+", "-", "×", "÷", "^", "**2"}:
                pass
            else:
                self.display.clear()
            self.just_calculated = False

        self.display.insert(action)
        self.display.setFocus()

    def calculate(self):
        current = self.display.text().strip()
        if not current:
            return
        try:
            result = safe_calculate(current, self.degrees_mode)
            formatted = format_result(result)
            self.add_history(current, formatted)
            self.expression_label.setText(current + " =")
            self.display.setText(formatted)
            self.just_calculated = True
            self.statusBar().showMessage("Calculation completed")
        except ExpressionError as error:
            self.expression_label.setText(current)
            self.display.setText("Error")
            self.just_calculated = True
            self.statusBar().showMessage(str(error))
        self.display.setFocus()

    def apply_percent(self):
        current = self.display.text().strip()
        if not current:
            return
        try:
            result = safe_calculate(current, self.degrees_mode) / 100
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
            result = -safe_calculate(current, self.degrees_mode)
            self.expression_label.setText("-(" + current + ")")
            self.display.setText(format_result(result))
            self.just_calculated = True
        except ExpressionError:
            self.display.setText("Error")
            self.just_calculated = True
        self.display.setFocus()

    def add_history(self, expression: str, result: str):
        timestamp = datetime.now().strftime("%H:%M")
        item = QListWidgetItem(f"{expression}\n= {result}    •    {timestamp}")
        item.setData(Qt.ItemDataRole.UserRole, (expression, result))
        self.history_list.insertItem(0, item)

    def restore_history(self, item):
        data = item.data(Qt.ItemDataRole.UserRole)
        if data:
            expression, result = data
            self.expression_label.setText(expression + " =")
            self.display.setText(result)
            self.just_calculated = True
        self.display.setFocus()

    def clear_history(self):
        self.history_list.clear()
        self.statusBar().showMessage("History cleared")

    def update_expression_preview(self, _text):
        if not self.just_calculated:
            self.expression_label.clear()

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
