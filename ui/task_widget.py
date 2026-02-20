from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget,
    QTableWidgetItem, QDialog, QFormLayout, QLineEdit,
    QComboBox, QDialogButtonBox, QMessageBox, QHeaderView, QLabel,
    QTextEdit, QSpinBox, QGroupBox, QStyledItemDelegate, QAbstractItemDelegate
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QIntValidator
import datetime
from database.db_manager import DBManager
from database.models import Task

_SUMMARY_STYLE_OK   = ("background-color: #e8f5e9; color: #1b5e20; font-weight: bold; "
                        "font-size: 13px; padding: 4px 10px; border-radius: 5px; "
                        "border: 1px solid #a5d6a7;")
_SUMMARY_STYLE_WARN = ("background-color: #fff3e0; color: #e65100; font-weight: bold; "
                        "font-size: 13px; padding: 4px 10px; border-radius: 5px; "
                        "border: 1px solid #ffcc80;")


class _LocTableDelegate(QStyledItemDelegate):
    """근무지 테이블 전용 delegate.
    - col 0 (근무지): 기존 근무지 선택 또는 직접 입력 가능한 QComboBox
    - col 1 (MM): 0 이상 정수만 허용하는 QLineEdit
    - Enter/Tab으로 다음 셀 이동
    """

    def __init__(self, parent=None, locations=None):
        super().__init__(parent)
        self._locations = locations or []

    def createEditor(self, parent, option, index):
        if index.column() == 0:
            editor = QComboBox(parent)
            editor.setEditable(True)
            editor.setInsertPolicy(QComboBox.NoInsert)
            editor.lineEdit().setPlaceholderText("근무지 입력 또는 선택")
            for loc in self._locations:
                editor.addItem(loc)
            return editor
        editor = super().createEditor(parent, option, index)
        if index.column() == 1 and isinstance(editor, QLineEdit):
            editor.setValidator(QIntValidator(0, 999999, editor))
            editor.setAlignment(Qt.AlignCenter)
        return editor

    def setEditorData(self, editor, index):
        if index.column() == 0 and isinstance(editor, QComboBox):
            text = index.data() or ""
            editor.setCurrentText(text)
            return
        super().setEditorData(editor, index)

    def setModelData(self, editor, model, index):
        if index.column() == 0 and isinstance(editor, QComboBox):
            model.setData(index, editor.currentText().strip(), Qt.EditRole)
            return
        super().setModelData(editor, model, index)

    def commitAndMove(self, editor, table, row, col, dr, dc):
        self.commitData.emit(editor)
        self.closeEditor.emit(editor, QAbstractItemDelegate.NoHint)
        nr = max(0, min(row + dr, table.rowCount() - 1))
        nc = max(0, min(col + dc, table.columnCount() - 1))
        table.setCurrentCell(nr, nc)
        table.edit(table.model().index(nr, nc))

    def eventFilter(self, editor, event):
        from PySide6.QtCore import QEvent
        if event.type() == QEvent.KeyPress:
            table = self.parent()
            idx = table.currentIndex()
            row, col = idx.row(), idx.column()
            key = event.key()
            # QComboBox 팝업이 열린 경우 Enter/Tab을 가로채지 않음
            if isinstance(editor, QComboBox) and editor.view().isVisible():
                return super().eventFilter(editor, event)
            if key in (Qt.Key_Return, Qt.Key_Enter):
                self.commitAndMove(editor, table, row, col, 1, 0)
                return True
            if key == Qt.Key_Tab:
                self.commitAndMove(editor, table, row, col, 0, 1)
                return True
            if key == Qt.Key_Backtab:
                self.commitAndMove(editor, table, row, col, 0, -1)
                return True
        return super().eventFilter(editor, event)


class TaskDialog(QDialog):
    def __init__(self, parent=None, task: Task = None, db: DBManager = None):
        super().__init__(parent)
        self.setWindowTitle("과제 등록" if task is None else "과제 수정")
        self.setMinimumWidth(480)
        self._db = db
        self._focus_col = None

        layout = QFormLayout(self)
        layout.setRowWrapPolicy(QFormLayout.DontWrapRows)

        self.name_edit = QLineEdit()
        self.desc_edit = QTextEdit()
        self.desc_edit.setMaximumHeight(70)
        self.status_combo = QComboBox()
        self.status_combo.addItems(Task.statuses())

        layout.addRow("과제명 *", self.name_edit)
        layout.addRow("설명", self.desc_edit)
        layout.addRow("상태", self.status_combo)

        # ── 기간 설정 ────────────────────────────────────────────────────────
        period_group = QGroupBox("과제 기간")
        period_group.setCheckable(True)
        period_group.setChecked(False)
        self.period_group = period_group

        now = datetime.date.today()
        pg_layout = QHBoxLayout(period_group)

        pg_layout.addWidget(QLabel("시작"))
        self.start_year = QSpinBox()
        self.start_year.setRange(2000, 2099)
        self.start_year.setValue(now.year)
        self.start_year.setFixedWidth(65)
        self.start_month = QComboBox()
        for m in range(1, 13):
            self.start_month.addItem(f"{m}월", m)
        self.start_month.setCurrentIndex(0)

        pg_layout.addWidget(self.start_year)
        pg_layout.addWidget(self.start_month)
        pg_layout.addSpacing(12)
        pg_layout.addWidget(QLabel("종료"))

        self.end_year = QSpinBox()
        self.end_year.setRange(2000, 2099)
        self.end_year.setValue(now.year)
        self.end_year.setFixedWidth(65)
        self.end_month = QComboBox()
        for m in range(1, 13):
            self.end_month.addItem(f"{m}월", m)
        self.end_month.setCurrentIndex(11)

        pg_layout.addWidget(self.end_year)
        pg_layout.addWidget(self.end_month)
        pg_layout.addStretch()

        layout.addRow(period_group)

        # ── 근무지별 MM 할당 ──────────────────────────────────────────────────
        loc_group = QGroupBox("근무지별 MM 할당")
        loc_v = QVBoxLayout(loc_group)

        loc_btn_bar = QHBoxLayout()
        self.loc_add_btn = QPushButton("행 추가")
        self.loc_del_btn = QPushButton("행 삭제")
        loc_btn_bar.addWidget(self.loc_add_btn)
        loc_btn_bar.addWidget(self.loc_del_btn)
        loc_btn_bar.addStretch()
        loc_v.addLayout(loc_btn_bar)

        self.loc_table = QTableWidget(0, 2)
        self.loc_table.setHorizontalHeaderLabels(["근무지", "할당 MM"])
        self.loc_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.loc_table.setColumnWidth(1, 90)
        self.loc_table.setMaximumHeight(140)
        _locations = db.get_all_locations() if db else []
        self.loc_table.setItemDelegate(_LocTableDelegate(self.loc_table, locations=_locations))
        self.loc_table.itemChanged.connect(self._on_loc_item_changed)
        loc_v.addWidget(self.loc_table)

        self.total_label = QLabel("합계: 0.0 MM")
        self.total_label.setAlignment(Qt.AlignRight)
        font = QFont(); font.setBold(True)
        self.total_label.setFont(font)
        loc_v.addWidget(self.total_label)

        self.loc_add_btn.clicked.connect(lambda: self._add_loc_row())
        self.loc_del_btn.clicked.connect(self._del_loc_row)

        layout.addRow(loc_group)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

        # 기존 데이터 채우기
        if task:
            self.name_edit.setText(task.name)
            self.desc_edit.setPlainText(task.description)
            idx = self.status_combo.findText(task.status)
            if idx >= 0:
                self.status_combo.setCurrentIndex(idx)

            has_period = task.start_year is not None
            period_group.setChecked(has_period)
            if has_period:
                self.start_year.setValue(task.start_year)
                self.start_month.setCurrentIndex((task.start_month or 1) - 1)
                self.end_year.setValue(task.end_year)
                self.end_month.setCurrentIndex((task.end_month or 12) - 1)

            # 근무지별 MM 로드
            if db and task.id is not None:
                for lm in db.get_task_location_mms(task.id):
                    self._add_loc_row(lm.location, lm.allocated_mm)
        else:
            # 등록된 근무지를 초기 행으로 자동 추가
            if db:
                for loc in db.get_all_locations():
                    self._add_loc_row(loc, 0.0)

    def _add_loc_row(self, location: str = "", allocated_mm: float = 0.0):
        self.loc_table.blockSignals(True)
        r = self.loc_table.rowCount()
        self.loc_table.setRowCount(r + 1)
        self.loc_table.setItem(r, 0, QTableWidgetItem(location))
        mm_text = str(int(allocated_mm)) if allocated_mm else ""
        mm_item = QTableWidgetItem(mm_text)
        mm_item.setTextAlignment(Qt.AlignCenter)
        self.loc_table.setItem(r, 1, mm_item)
        self.loc_table.blockSignals(False)
        self._update_total_label()

    def _del_loc_row(self):
        r = self.loc_table.currentRow()
        if r >= 0:
            self.loc_table.removeRow(r)
            self._update_total_label()

    def _on_loc_item_changed(self, item):
        if item.column() == 1:
            self._update_total_label()

    def _update_total_label(self):
        total = 0.0
        for r in range(self.loc_table.rowCount()):
            it = self.loc_table.item(r, 1)
            if it and it.text().strip():
                try:
                    total += int(it.text())
                except ValueError:
                    pass
        self.total_label.setText(f"합계: {int(total)} MM")

    def get_location_mms(self) -> list:
        """[(location, allocated_mm), ...] 반환. 빈 근무지 행은 제외."""
        result = []
        for r in range(self.loc_table.rowCount()):
            item0 = self.loc_table.item(r, 0)
            item1 = self.loc_table.item(r, 1)
            if item0 and item0.text().strip():
                try:
                    mm = int(item1.text()) if item1 and item1.text().strip() else 0
                except ValueError:
                    mm = 0
                if mm > 0:
                    result.append((item0.text().strip(), mm))
        return result

    def showEvent(self, event):
        super().showEvent(event)
        if self._focus_col is not None:
            self.focus_field(self._focus_col)
            self._focus_col = None

    def focus_field(self, col: int):
        """테이블 열 번호에 해당하는 입력 필드에 포커스 및 선택."""
        if col == 1:
            self.name_edit.setFocus()
            self.name_edit.selectAll()
        elif col == 2:
            self.desc_edit.setFocus()
            self.desc_edit.selectAll()
        elif col == 3:
            self.period_group.setChecked(True)
            self.start_year.setFocus()
            self.start_year.selectAll()
        elif col == 4:
            self.loc_table.setFocus()
        elif col == 5:
            self.status_combo.setFocus()

    def _accept(self):
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "입력 오류", "과제명을 입력하세요.")
            return
        if self.period_group.isChecked():
            sy, sm = self.start_year.value(), self.start_month.currentData()
            ey, em = self.end_year.value(), self.end_month.currentData()
            if (sy, sm) > (ey, em):
                QMessageBox.warning(self, "기간 오류", "시작 년월이 종료 년월보다 늦을 수 없습니다.")
                return
        self.accept()

    def get_task(self, task_id=None) -> Task:
        if self.period_group.isChecked():
            sy = self.start_year.value()
            sm = self.start_month.currentData()
            ey = self.end_year.value()
            em = self.end_month.currentData()
        else:
            sy = sm = ey = em = None

        total_mm = sum(mm for _, mm in self.get_location_mms())

        return Task(
            id=task_id,
            name=self.name_edit.text().strip(),
            description=self.desc_edit.toPlainText().strip(),
            total_mm=total_mm,
            status=self.status_combo.currentText(),
            start_year=sy, start_month=sm,
            end_year=ey, end_month=em,
        )


class TaskWidget(QWidget):
    tasks_changed = Signal()

    def __init__(self, db: DBManager, parent=None):
        super().__init__(parent)
        self.db = db
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        btn_bar = QHBoxLayout()
        self.add_btn = QPushButton("과제 추가")
        self.edit_btn = QPushButton("수정")
        self.delete_btn = QPushButton("삭제")
        self.edit_btn.setEnabled(False)
        self.delete_btn.setEnabled(False)
        btn_bar.addWidget(self.add_btn)
        btn_bar.addWidget(self.edit_btn)
        btn_bar.addWidget(self.delete_btn)
        btn_bar.addStretch()

        self.add_btn.clicked.connect(self._add_task)
        self.edit_btn.clicked.connect(lambda: self._edit_task())
        self.delete_btn.clicked.connect(self._delete_task)

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["ID", "과제명", "설명", "기간", "계획 MM", "상태"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setColumnWidth(0, 40)
        self.table.setColumnWidth(3, 140)
        self.table.setColumnWidth(4, 180)
        self.table.setColumnWidth(5, 70)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        self.table.doubleClicked.connect(lambda idx: self._edit_task(idx.column()))

        self.task_summary_label = QLabel()
        self.task_summary_label.setAlignment(Qt.AlignRight)
        bold = QFont(); bold.setBold(True)
        self.task_summary_label.setFont(bold)

        layout.addLayout(btn_bar)
        layout.addWidget(self.table)
        layout.addWidget(self.task_summary_label)

    def refresh(self):
        tasks = self.db.get_all_tasks()
        self.table.setRowCount(len(tasks))

        loc_totals = {}  # {location: total_mm} (insertion order 유지)
        grand_total = 0.0

        for row, task in enumerate(tasks):
            self.table.setItem(row, 0, QTableWidgetItem(str(task.id)))
            self.table.setItem(row, 1, QTableWidgetItem(task.name))
            self.table.setItem(row, 2, QTableWidgetItem(task.description))

            # 기간 표시
            if task.start_year is not None:
                period = (f"{task.start_year}.{task.start_month:02d} ~ "
                          f"{task.end_year}.{task.end_month:02d}")
            else:
                period = "-"
            period_item = QTableWidgetItem(period)
            period_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 3, period_item)

            # 계획 MM - 근무지별 표시
            loc_mms = self.db.get_task_location_mms(task.id)
            if loc_mms:
                parts = [f"{lm.location}: {int(lm.allocated_mm)}" for lm in loc_mms]
                mm_text = " / ".join(parts)
                tooltip = "\n".join(
                    f"{lm.location}: {int(lm.allocated_mm)}MM" for lm in loc_mms
                ) + f"\n합계: {int(task.total_mm)}MM"
                for lm in loc_mms:
                    if lm.location not in loc_totals:
                        loc_totals[lm.location] = 0.0
                    loc_totals[lm.location] += lm.allocated_mm
            else:
                mm_text = f"{int(task.total_mm)}" if task.total_mm else "0"
                tooltip = ""
            grand_total += task.total_mm

            mm_item = QTableWidgetItem(mm_text)
            mm_item.setTextAlignment(Qt.AlignCenter)
            if tooltip:
                mm_item.setToolTip(tooltip)
            self.table.setItem(row, 4, mm_item)

            status_item = QTableWidgetItem(task.status)
            status_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 5, status_item)

        # 하단 요약 레이블
        if loc_totals:
            loc_parts = [f"{loc}: {int(v)}MM" for loc, v in loc_totals.items()]
            summary = "  /  ".join(loc_parts) + f"   |   총합계: {int(grand_total)}MM"
            # 근무지별 계획 MM이 필요 MM과 모두 일치하면 초록색
            loc_planned = self.db.get_all_location_plan_totals()
            all_match = all(
                abs(loc_planned.get(loc, 0.0) - v) < 1e-9
                for loc, v in loc_totals.items()
            ) and abs(sum(loc_planned.get(loc, 0.0) for loc in loc_totals) - grand_total) < 1e-9
            self.task_summary_label.setStyleSheet(
                _SUMMARY_STYLE_OK if all_match else _SUMMARY_STYLE_WARN
            )
        else:
            summary = f"계획된 총 MM 합계: {int(grand_total)}MM"
            self.task_summary_label.setStyleSheet(_SUMMARY_STYLE_WARN)
        self.task_summary_label.setText(summary)
        self._on_selection_changed()

    def _on_selection_changed(self):
        has_sel = bool(self.table.selectedItems())
        self.edit_btn.setEnabled(has_sel)
        self.delete_btn.setEnabled(has_sel)

    def _selected_task_id(self):
        if not self.table.selectedItems():
            return None
        return int(self.table.item(self.table.currentRow(), 0).text())

    def _add_task(self):
        dlg = TaskDialog(self, db=self.db)
        if dlg.exec() == QDialog.Accepted:
            task_id = self.db.add_task(dlg.get_task())
            self.db.replace_task_location_mms(task_id, dlg.get_location_mms())
            self.refresh()
            self.tasks_changed.emit()

    def _edit_task(self, focus_col=None):
        task_id = self._selected_task_id()
        if task_id is None:
            return
        dlg = TaskDialog(self, self.db.get_task(task_id), db=self.db)
        if focus_col is not None:
            dlg._focus_col = focus_col
        if dlg.exec() == QDialog.Accepted:
            self.db.update_task(dlg.get_task(task_id))
            self.db.replace_task_location_mms(task_id, dlg.get_location_mms())
            self.db.delete_location_mismatched_plans(task_id=task_id)
            self.refresh()
            self.tasks_changed.emit()

    def _delete_task(self):
        task_id = self._selected_task_id()
        if task_id is None:
            return
        task = self.db.get_task(task_id)
        reply = QMessageBox.question(
            self, "삭제 확인",
            f"과제 '{task.name}'을(를) 삭제하시겠습니까?\n관련 계획/집행 데이터도 모두 삭제됩니다.",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.db.delete_task(task_id)
            self.refresh()
            self.tasks_changed.emit()
