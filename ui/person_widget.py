import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget,
    QTableWidgetItem, QDialog, QFormLayout, QLineEdit, QComboBox,
    QDialogButtonBox, QMessageBox, QHeaderView, QLabel
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QFont
from database.db_manager import DBManager
from database.models import Person

_SUMMARY_STYLE_OK   = ("background-color: #e8f5e9; color: #1b5e20; font-weight: bold; "
                        "font-size: 13px; padding: 4px 10px; border-radius: 5px; "
                        "border: 1px solid #a5d6a7;")
_SUMMARY_STYLE_WARN = ("background-color: #fff3e0; color: #e65100; font-weight: bold; "
                        "font-size: 13px; padding: 4px 10px; border-radius: 5px; "
                        "border: 1px solid #ffcc80;")


class PersonDialog(QDialog):
    def __init__(self, parent=None, person: Person = None, db: DBManager = None):
        super().__init__(parent)
        self.setWindowTitle("인력 등록" if person is None else "인력 수정")
        self.setMinimumWidth(300)

        layout = QFormLayout(self)

        self.name_edit = QLineEdit()
        self.dept_edit = QLineEdit()

        # 근무지: 기존 근무지 선택 또는 직접 입력
        self.loc_edit = QComboBox()
        self.loc_edit.setEditable(True)
        self.loc_edit.setInsertPolicy(QComboBox.NoInsert)
        self.loc_edit.lineEdit().setPlaceholderText("예: 안양, 부산")
        if db:
            for loc in db.get_all_locations():
                self.loc_edit.addItem(loc)
        # 빈 항목(선택 안 함)을 맨 앞에 추가
        self.loc_edit.insertItem(0, "")
        self.loc_edit.setCurrentIndex(0)

        layout.addRow("이름 *", self.name_edit)
        layout.addRow("부서", self.dept_edit)
        layout.addRow("근무지", self.loc_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

        if person:
            self.name_edit.setText(person.name)
            self.dept_edit.setText(person.department)
            self.loc_edit.setCurrentText(person.location)

    def focus_field(self, col: int):
        """테이블 열 번호에 해당하는 입력 필드에 포커스 및 전체 선택."""
        if col == 1:
            self.name_edit.setFocus()
            self.name_edit.selectAll()
        elif col == 2:
            self.dept_edit.setFocus()
            self.dept_edit.selectAll()
        elif col == 3:
            self.loc_edit.setFocus()
            self.loc_edit.lineEdit().selectAll()

    def _accept(self):
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "입력 오류", "이름을 입력하세요.")
            return
        self.accept()

    def get_person(self, person_id=None, year=None) -> Person:
        return Person(
            id=person_id,
            year=year or datetime.date.today().year,
            name=self.name_edit.text().strip(),
            department=self.dept_edit.text().strip(),
            location=self.loc_edit.currentText().strip(),
        )


class PersonWidget(QWidget):
    persons_changed = Signal()

    def __init__(self, db: DBManager, year: int = None, parent=None):
        super().__init__(parent)
        self.db = db
        self.year = year or datetime.date.today().year
        self._build_ui()
        self.refresh()

    def set_year(self, year: int):
        self.year = year
        self.refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        btn_bar = QHBoxLayout()
        self.add_btn = QPushButton("인력 추가")
        self.edit_btn = QPushButton("수정")
        self.delete_btn = QPushButton("삭제")
        self.edit_btn.setEnabled(False)
        self.delete_btn.setEnabled(False)
        btn_bar.addWidget(self.add_btn)
        btn_bar.addWidget(self.edit_btn)
        btn_bar.addWidget(self.delete_btn)
        btn_bar.addStretch()

        self.add_btn.clicked.connect(self._add_person)
        self.edit_btn.clicked.connect(self._edit_person)
        self.delete_btn.clicked.connect(self._delete_person)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["ID", "이름", "부서", "근무지"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setColumnWidth(0, 50)
        self.table.setColumnWidth(3, 100)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        self.table.doubleClicked.connect(lambda idx: self._edit_person(idx.column()))

        self.person_summary_label = QLabel()
        self.person_summary_label.setAlignment(Qt.AlignRight)
        bold = QFont(); bold.setBold(True)
        self.person_summary_label.setFont(bold)

        layout.addLayout(btn_bar)
        layout.addWidget(self.table)
        layout.addWidget(self.person_summary_label)

    def refresh(self):
        persons = self.db.get_all_persons(self.year)
        self.table.setRowCount(len(persons))
        for row, person in enumerate(persons):
            self.table.setItem(row, 0, QTableWidgetItem(str(person.id)))
            self.table.setItem(row, 1, QTableWidgetItem(person.name))
            self.table.setItem(row, 2, QTableWidgetItem(person.department))
            self.table.setItem(row, 3, QTableWidgetItem(person.location))

        # 하단 요약: 근무지별 할당 MM 합계 + 총합계
        loc_totals = {}
        grand_total = 0.0
        for task in self.db.get_all_tasks(self.year):
            loc_mms = self.db.get_task_location_mms(task.id)
            if loc_mms:
                for lm in loc_mms:
                    if lm.location not in loc_totals:
                        loc_totals[lm.location] = 0.0
                    loc_totals[lm.location] += lm.allocated_mm
            grand_total += task.total_mm

        if loc_totals:
            loc_parts = [f"{loc}: {int(v)}MM" for loc, v in loc_totals.items()]
            summary = "총 필요 MM  " + "  /  ".join(loc_parts) + f"   |   총합계: {int(grand_total)}MM"
            # 근무지별 계획 MM이 필요 MM과 모두 일치하면 초록색
            loc_planned = self.db.get_all_location_plan_totals(self.year)
            tooltip_lines = ["[근무지별 필요 MM vs 계획 MM]"]
            all_match = True
            for loc, req in loc_totals.items():
                plan = loc_planned.get(loc, 0.0)
                match = abs(plan - req) < 0.05
                if not match:
                    all_match = False
                icon = "✓" if match else "✗"
                tooltip_lines.append(
                    f"  {icon} {loc}: 필요 {int(req)}MM / 계획 {plan:.1f}MM"
                    + ("" if match else f"  (차이: {plan - req:+.1f}MM)")
                )
            total_plan = sum(loc_planned.get(loc, 0.0) for loc in loc_totals)
            if abs(total_plan - grand_total) >= 0.05:
                all_match = False
            tooltip_lines.append(
                f"  {'✓' if all_match else '✗'} 총합계: 필요 {int(grand_total)}MM / 계획 {total_plan:.1f}MM"
            )
            self.person_summary_label.setToolTip("\n".join(tooltip_lines))
            self.person_summary_label.setStyleSheet(
                _SUMMARY_STYLE_OK if all_match else _SUMMARY_STYLE_WARN
            )
        else:
            summary = f"총 필요 MM: {int(grand_total)}MM"
            self.person_summary_label.setStyleSheet(_SUMMARY_STYLE_WARN)
            self.person_summary_label.setToolTip("")
        self.person_summary_label.setText(summary)
        self._on_selection_changed()

    def _on_selection_changed(self):
        has_sel = bool(self.table.selectedItems())
        self.edit_btn.setEnabled(has_sel)
        self.delete_btn.setEnabled(has_sel)

    def _selected_person_id(self):
        rows = self.table.selectedItems()
        if not rows:
            return None
        return int(self.table.item(self.table.currentRow(), 0).text())

    def _add_person(self):
        dlg = PersonDialog(self, db=self.db)
        if dlg.exec() == QDialog.Accepted:
            person = dlg.get_person(year=self.year)
            self.db.add_person(person)
            self.refresh()
            self.persons_changed.emit()

    def _edit_person(self, focus_col=None):
        person_id = self._selected_person_id()
        if person_id is None:
            return
        existing = self.db.get_person(person_id)
        dlg = PersonDialog(self, existing, db=self.db)
        if focus_col is not None:
            dlg.focus_field(focus_col)
        if dlg.exec() == QDialog.Accepted:
            updated = dlg.get_person(person_id, year=existing.year)
            self.db.update_person(updated)
            self.db.delete_location_mismatched_plans(person_id=person_id)
            self.refresh()
            self.persons_changed.emit()

    def _delete_person(self):
        person_id = self._selected_person_id()
        if person_id is None:
            return
        person = self.db.get_person(person_id)
        reply = QMessageBox.question(
            self, "삭제 확인",
            f"인력 '{person.name}'을(를) 삭제하시겠습니까?\n관련 계획/집행 데이터도 모두 삭제됩니다.",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.db.delete_person(person_id)
            self.refresh()
            self.persons_changed.emit()
