from PySide6.QtWidgets import QStyledItemDelegate, QLineEdit, QAbstractItemDelegate, QTableWidget
from PySide6.QtGui import QValidator
from PySide6.QtCore import Qt, Signal, QTimer


class MMTableWidget(QTableWidget):
    """편집 불가 셀에서 문자 키 입력 시 Qt 기본 검색 이동 동작을 차단."""

    def keyPressEvent(self, event):
        idx = self.currentIndex()
        if idx.isValid():
            item = self.item(idx.row(), idx.column())
            is_editable = item is not None and bool(item.flags() & Qt.ItemIsEditable)

            if event.key() in (Qt.Key_Backspace, Qt.Key_Delete):
                if is_editable and item.text():
                    r, c = idx.row(), idx.column()
                    item.setText("")
                    QTimer.singleShot(0, lambda r=r, c=c: self._restore_selection(r, c))
                event.accept()
                return

            if event.text() and not is_editable:
                event.accept()
                return

        super().keyPressEvent(event)

    def _restore_selection(self, row: int, col: int):
        if row < self.rowCount() and col < self.columnCount():
            self.setCurrentCell(row, col)


class MMLineEdit(QLineEdit):
    """방향키 입력 시 시그널 발생."""
    arrow_pressed = Signal(int)  # Qt.Key 값

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Up, Qt.Key_Down, Qt.Key_Left, Qt.Key_Right):
            self.arrow_pressed.emit(event.key())
        else:
            super().keyPressEvent(event)


class MMValidator(QValidator):
    """0.0 ~ 1.0, 소수점 첫째 자리까지만 허용."""

    def validate(self, text: str, pos: int):
        if text == "":
            return (QValidator.Intermediate, text, pos)

        allowed = set("0123456789.")
        if any(c not in allowed for c in text):
            return (QValidator.Invalid, text, pos)

        if text.count(".") > 1:
            return (QValidator.Invalid, text, pos)

        if text.endswith("."):
            try:
                val = float(text[:-1])
            except ValueError:
                return (QValidator.Invalid, text, pos)
            return (QValidator.Intermediate, text, pos) if 0.0 <= val <= 1.0 else (QValidator.Invalid, text, pos)

        try:
            val = float(text)
        except ValueError:
            return (QValidator.Invalid, text, pos)

        if "." in text and len(text.split(".")[1]) > 1:
            return (QValidator.Invalid, text, pos)

        if 0.0 <= val <= 1.0:
            return (QValidator.Acceptable, text, pos)

        return (QValidator.Invalid, text, pos)

    def fixup(self, text: str) -> str:
        if text.endswith("."):
            return text + "0"
        return text


class MMExecutionValidator(QValidator):
    """집행 MM: 음수 포함 실수, 소수점 첫째 자리까지 허용."""

    def validate(self, text: str, pos: int):
        if text in ("", "-"):
            return (QValidator.Intermediate, text, pos)

        allowed = set("0123456789.-")
        if any(c not in allowed for c in text):
            return (QValidator.Invalid, text, pos)

        if text.count(".") > 1:
            return (QValidator.Invalid, text, pos)

        if text.count("-") > 1 or ("-" in text and not text.startswith("-")):
            return (QValidator.Invalid, text, pos)

        if text.endswith("."):
            try:
                float(text[:-1])
                return (QValidator.Intermediate, text, pos)
            except ValueError:
                return (QValidator.Invalid, text, pos)

        try:
            val = float(text)
        except ValueError:
            return (QValidator.Invalid, text, pos)

        if "." in text and len(text.split(".")[1]) > 1:
            return (QValidator.Invalid, text, pos)

        return (QValidator.Acceptable, text, pos)

    def fixup(self, text: str) -> str:
        if text.endswith("."):
            return text + "0"
        return text


class MMDelegate(QStyledItemDelegate):
    """
    셀 선택 후 숫자 키 즉시 편집.
    방향키: 입력 확정 후 해당 방향 셀로 이동.
    """

    def __init__(self, table):
        super().__init__(table)
        self._table = table

    def createEditor(self, parent, option, index):
        editor = MMLineEdit(parent)
        editor.setValidator(MMValidator(editor))
        editor.setAlignment(Qt.AlignCenter)

        row, col = index.row(), index.column()
        editor.arrow_pressed.connect(
            lambda key: self._handle_arrow(editor, row, col, key)
        )
        return editor

    def setEditorData(self, editor, index):
        text = index.data(Qt.DisplayRole) or ""
        editor.setText(text)
        editor.selectAll()

    def setModelData(self, editor, model, index):
        text = editor.text().strip()
        if text.endswith("."):
            text += "0"
        model.setData(index, text, Qt.EditRole)

    def _handle_arrow(self, editor, row: int, col: int, key: int):
        # 이동 목적지를 commit/closeEditor 전에 계산
        dr = {Qt.Key_Up: -1, Qt.Key_Down: 1}.get(key, 0)
        dc = {Qt.Key_Left: -1, Qt.Key_Right: 1}.get(key, 0)
        max_row = self._table.rowCount() - 1
        max_col = self._table.columnCount() - 1
        new_row = max(0, min(row + dr, max_row))
        new_col = max(0, min(col + dc, max_col))

        # 편집 확정 (→ itemChanged → refresh() 로 테이블 재구성됨)
        self.commitData.emit(editor)
        self.closeEditor.emit(editor, QAbstractItemDelegate.NoHint)

        # Qt 이벤트 루프가 closeEditor 후처리를 마친 뒤 셀 선택
        QTimer.singleShot(0, lambda: self._navigate_to(new_row, new_col))

    def _navigate_to(self, row: int, col: int):
        max_row = self._table.rowCount() - 1
        max_col = self._table.columnCount() - 1
        row = max(0, min(row, max_row))
        col = max(0, min(col, max_col))
        idx = self._table.model().index(row, col)
        if idx.isValid():
            self._table.setCurrentIndex(idx)
            self._table.setFocus()
            self._table.scrollTo(idx)


class MMExecutionDelegate(MMDelegate):
    """집행 MM 전용 델리게이트 (음수 허용)."""

    def createEditor(self, parent, option, index):
        editor = MMLineEdit(parent)
        editor.setValidator(MMExecutionValidator(editor))
        editor.setAlignment(Qt.AlignCenter)

        row, col = index.row(), index.column()
        editor.arrow_pressed.connect(
            lambda key: self._handle_arrow(editor, row, col, key)
        )
        return editor
