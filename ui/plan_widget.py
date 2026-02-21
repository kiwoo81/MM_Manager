from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget,
    QTableWidgetItem, QLabel, QHeaderView,
    QAbstractItemView, QMessageBox, QPushButton
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QBrush, QFont
from database.db_manager import DBManager
from database.models import MMPlan
from logic.mm_calculator import MMCalculator
from ui.mm_delegate import MMDelegate, MMTableWidget
import datetime

MONTH_NAMES = ['1월','2월','3월','4월','5월','6월',
               '7월','8월','9월','10월','11월','12월']

COL_PERSON    = 0
COL_TASK      = 1
COL_JAN       = 2
COL_DEC       = 13
COL_TOTAL     = 14
COL_REMAINING = 15
N_COLS        = 16


class PlanWidget(QWidget):
    data_changed = Signal()

    def __init__(self, db: DBManager, year: int = None, parent=None):
        super().__init__(parent)
        self.db = db
        self.calc = MMCalculator(db)
        self.year = year or datetime.date.today().year
        self._tasks = []
        self._persons = []
        self._row_map = {}
        self._build_ui()
        self.refresh()

    def set_year(self, year: int):
        self.year = year
        self.refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        top_bar = QHBoxLayout()
        top_bar.addStretch()
        self.reset_btn = QPushButton("전체 초기화")
        self.reset_btn.setStyleSheet(
            "QPushButton { background-color: #c62828; color: white; font-weight: bold; "
            "padding: 4px 12px; border-radius: 4px; }"
            "QPushButton:hover { background-color: #b71c1c; }"
        )
        self.reset_btn.clicked.connect(self._reset_all)
        top_bar.addWidget(self.reset_btn)

        self.table = MMTableWidget()
        # 셀 선택 후 숫자 키 입력 즉시 편집
        self.table.setEditTriggers(QAbstractItemView.AnyKeyPressed)
        self.table.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.table.setItemDelegate(MMDelegate(self.table))
        self.table.itemChanged.connect(self._on_item_changed)

        layout.addLayout(top_bar)
        layout.addWidget(QLabel(
            "※ 셀 선택 후 숫자 입력 (0.0~1.0, 소수점 1자리). 0 또는 빈칸 입력 시 삭제. "
            "인력 월합계 1.0 초과 시 빨간색 표시."
        ))
        layout.addWidget(self.table)

    # ──────────────────────────────────────────────────────────────────────────

    def refresh(self):
        self._tasks = self.db.get_all_tasks(self.year)
        self._persons = self.db.get_all_persons(self.year)
        year = self.year

        plan_map = {}
        for month in range(1, 13):
            for p in self.db.get_plans_by_month(year, month):
                plan_map[(p.person_id, p.task_id, month)] = p.planned_mm

        # 과제별 근무지 할당 MM: {task_id: {location: allocated_mm}}
        task_loc_mms = {}
        for t in self._tasks:
            task_loc_mms[t.id] = {lm.location: lm.allocated_mm
                                   for lm in self.db.get_task_location_mms(t.id)}

        # 과제+근무지별 현재 계획 합계 캐시: {(task_id, location): total}
        task_loc_totals = {}
        for t in self._tasks:
            for loc in task_loc_mms[t.id]:
                task_loc_totals[(t.id, loc)] = self.db.get_task_location_plan_total(t.id, loc)

        n_tasks = len(self._tasks)
        n_persons = len(self._persons)

        self.table.blockSignals(True)
        self.table.clearSpans()
        self.table.setRowCount(0)

        total_rows = n_persons * (n_tasks + 1)
        self.table.setRowCount(total_rows)
        self.table.setColumnCount(N_COLS)

        headers = ['인력', '과제'] + MONTH_NAMES + ['연간합계', '과제잔여']
        self.table.setHorizontalHeaderLabels(headers)

        self.table.setColumnWidth(COL_PERSON, 80)
        self.table.setColumnWidth(COL_TASK, 120)
        for c in range(COL_JAN, COL_DEC + 1):
            self.table.setColumnWidth(c, 55)
        self.table.setColumnWidth(COL_TOTAL, 75)
        self.table.setColumnWidth(COL_REMAINING, 140)
        self.table.horizontalHeader().setSectionResizeMode(COL_TASK, QHeaderView.Stretch)

        # 인력별 연간 계획 합계 미리 계산 (이름 셀 색상 결정용)
        person_annual_map = {
            person.id: sum(
                plan_map.get((person.id, t.id, m), 0.0)
                for t in self._tasks
                for m in range(1, 13)
            )
            for person in self._persons
        }

        self._row_map = {}
        row = 0

        for person in self._persons:
            person_start_row = row
            person_annual = person_annual_map[person.id]

            for t_idx, task in enumerate(self._tasks):
                self._row_map[row] = ('data', person.id, task.id)

                if t_idx == 0:
                    name_text = f"{person.name}\n({person.location})" if person.location else person.name
                    pi = QTableWidgetItem(name_text)
                    pi.setFlags(Qt.ItemIsEnabled)
                    pi.setTextAlignment(Qt.AlignCenter | Qt.AlignVCenter)
                    if person_annual >= 12.0 - 1e-9:
                        pi.setBackground(QBrush(QColor("#2e7d32")))  # 12MM 완전 할당: 초록
                    else:
                        pi.setBackground(QBrush(QColor("#455a64")))  # 기본: 청회색
                    pi.setForeground(QBrush(QColor("#ffffff")))
                    bold = QFont(); bold.setBold(True)
                    pi.setFont(bold)
                    self.table.setItem(row, COL_PERSON, pi)
                    if n_tasks + 1 > 1:
                        self.table.setSpan(person_start_row, COL_PERSON, n_tasks + 1, 1)

                ti = QTableWidgetItem(task.name)
                ti.setFlags(Qt.ItemIsEnabled)
                self.table.setItem(row, COL_TASK, ti)

                loc_map = task_loc_mms.get(task.id, {})
                location_allowed = not loc_map or (bool(person.location) and person.location in loc_map)

                annual = 0.0
                for m_idx in range(12):
                    month = m_idx + 1
                    mm = plan_map.get((person.id, task.id, month), 0.0)
                    if not location_allowed:
                        cell = _location_disabled_item(loc_map)
                    elif not task.in_range(year, month):
                        cell = _out_of_range_item()
                    else:
                        cell = QTableWidgetItem(f"{mm:.1f}" if mm else "")
                        cell.setTextAlignment(Qt.AlignCenter)
                        annual += mm
                    self.table.setItem(row, COL_JAN + m_idx, cell)

                self.table.setItem(row, COL_TOTAL, self._readonly_item(f"{annual:.1f}"))

                if loc_map:
                    # 근무지별 잔여 전체 표시
                    parts = []
                    tip_lines = []
                    worst_remaining = float('inf')
                    best_remaining = float('-inf')
                    for loc in loc_map:
                        allocated = loc_map[loc]
                        used = task_loc_totals.get((task.id, loc), 0.0)
                        rem = allocated - used
                        parts.append(f"{loc}: {int(rem)}")
                        tip_lines.append(
                            f"{loc}  할당: {int(allocated)} / 사용: {int(used)} / 잔여: {int(rem)}"
                        )
                        worst_remaining = min(worst_remaining, rem)
                        best_remaining = max(best_remaining, rem)
                    rem_item = QTableWidgetItem(" / ".join(parts))
                    rem_item.setTextAlignment(Qt.AlignCenter)
                    rem_item.setFlags(Qt.ItemIsEnabled)
                    font = QFont(); font.setBold(True)
                    rem_item.setFont(font)
                    rem_item.setToolTip("\n".join(tip_lines))
                    if worst_remaining < -1e-9:
                        rem_item.setBackground(QBrush(QColor("#c62828")))
                        rem_item.setForeground(QBrush(QColor("#ffffff")))
                    elif best_remaining < 1e-9:
                        # 모든 근무지 잔여 MM이 0 이하일 때 초록색
                        rem_item.setBackground(QBrush(QColor("#2e7d32")))
                        rem_item.setForeground(QBrush(QColor("#ffffff")))
                    else:
                        rem_item.setBackground(QBrush(QColor("#546e7a")))
                        rem_item.setForeground(QBrush(QColor("#ffffff")))
                else:
                    task_total_planned = self.db.get_task_plan_total(task.id)
                    remaining = task.total_mm - task_total_planned
                    rem_item = self._remaining_item(remaining, 0.0)
                    rem_item.setToolTip(
                        f"과제 전체 할당: {task.total_mm:.1f} / 사용: {task_total_planned:.1f}"
                    )
                self.table.setItem(row, COL_REMAINING, rem_item)
                row += 1

            # 인력 월합계 행
            self._row_map[row] = ('total', person.id)

            label = QTableWidgetItem("월합계")
            label.setFlags(Qt.ItemIsEnabled)
            label.setBackground(QBrush(QColor("#546e7a")))
            label.setForeground(QBrush(QColor("#ffffff")))
            bold = QFont(); bold.setBold(True)
            label.setFont(bold)
            self.table.setItem(row, COL_TASK, label)

            person_annual = 0.0
            for m_idx in range(12):
                monthly = sum(
                    plan_map.get((person.id, t.id, m_idx + 1), 0.0)
                    for t in self._tasks
                )
                person_annual += monthly
                mitem = self._readonly_item(f"{monthly:.1f}" if monthly else "")
                if monthly > 1.0 + 1e-9:
                    mitem.setBackground(QBrush(QColor("#c62828")))
                elif abs(monthly - 1.0) < 1e-9:
                    mitem.setBackground(QBrush(QColor("#2e7d32")))
                self.table.setItem(row, COL_JAN + m_idx, mitem)

            annual_item = self._readonly_item(f"{person_annual:.1f}" if person_annual else "")
            if person_annual > 12.0 + 1e-9:
                annual_item.setBackground(QBrush(QColor("#c62828")))
            elif abs(person_annual - 12.0) < 1e-9:
                annual_item.setBackground(QBrush(QColor("#2e7d32")))
            self.table.setItem(row, COL_TOTAL, annual_item)
            self.table.setItem(row, COL_REMAINING, self._readonly_item(""))
            row += 1

        self.table.blockSignals(False)

    # ──────────────────────────────────────────────────────────────────────────

    def _on_item_changed(self, item: QTableWidgetItem):
        r, c = item.row(), item.column()
        if c < COL_JAN or c > COL_DEC:
            return
        row_info = self._row_map.get(r)
        if row_info is None or row_info[0] != 'data':
            return

        _, person_id, task_id = row_info
        month = c - COL_JAN + 1
        year = self.year

        # 근무지 불일치 안전 체크
        _person = self.db.get_person(person_id)
        _loc_mms = {lm.location for lm in self.db.get_task_location_mms(task_id)}
        if _loc_mms and (not _person or not _person.location or _person.location not in _loc_mms):
            self.table.blockSignals(True)
            item.setText("")
            self.table.blockSignals(False)
            return

        task = self.db.get_task(task_id)
        if task and not task.in_range(year, month):
            self.table.blockSignals(True)
            item.setText("")
            self.table.blockSignals(False)
            return

        text = item.text().strip()
        try:
            mm_val = float(text) if text else 0.0
        except ValueError:
            self._restore_cell(r, c, task_id, person_id, year, month, silent=True)
            return

        if mm_val == 0.0:
            self.db.delete_plan(task_id, person_id, year, month)
        else:
            ok, msg = self.calc.validate_plan(person_id, task_id, year, month, mm_val)
            if not ok:
                QMessageBox.warning(self.window(), "계획 MM 초과", msg)
                self._restore_cell(r, c, task_id, person_id, year, month)
                return
            self.db.upsert_plan(MMPlan(None, task_id, person_id, year, month, mm_val))

        self.refresh()
        self.data_changed.emit()

    def _reset_all(self):
        year = self.year
        reply = QMessageBox.question(
            self.window(), "전체 초기화",
            f"{year}년 MM 계획 데이터를 모두 삭제하시겠습니까?\n이 작업은 되돌릴 수 없습니다.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.db.delete_all_plans_for_year(year)
            self.refresh()
            self.data_changed.emit()

    def _restore_cell(self, row, col, task_id, person_id, year, month, silent=False):
        existing = self.db.get_plan(task_id, person_id, year, month)
        self.table.blockSignals(True)
        self.table.item(row, col).setText(
            f"{existing.planned_mm:.1f}" if existing else ""
        )
        self.table.blockSignals(False)

    def _remaining_item(self, remaining: float, total_mm: float) -> QTableWidgetItem:
        """과제 잔여 MM 셀: 남은 MM 표시, 색상으로 상태 구분."""
        text = f"{remaining:.1f}"
        item = QTableWidgetItem(text)
        item.setTextAlignment(Qt.AlignCenter)
        item.setFlags(Qt.ItemIsEnabled)
        font = QFont(); font.setBold(True)
        item.setFont(font)
        if remaining < -1e-9:
            # 초과: 빨간색
            item.setBackground(QBrush(QColor("#c62828")))
            item.setForeground(QBrush(QColor("#ffffff")))
        elif remaining < 1e-9:
            # 소진 완료: 초록색
            item.setBackground(QBrush(QColor("#2e7d32")))
            item.setForeground(QBrush(QColor("#ffffff")))
        else:
            # 잔여 있음: 청회색
            item.setBackground(QBrush(QColor("#546e7a")))
            item.setForeground(QBrush(QColor("#ffffff")))
        return item

    def _readonly_item(self, text: str) -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        item.setTextAlignment(Qt.AlignCenter)
        item.setFlags(Qt.ItemIsEnabled)
        font = QFont(); font.setBold(True)
        item.setFont(font)
        item.setBackground(QBrush(QColor("#546e7a")))
        item.setForeground(QBrush(QColor("#ffffff")))
        return item

    def reload(self):
        self.refresh()


def _location_disabled_item(loc_map: dict = None) -> QTableWidgetItem:
    item = QTableWidgetItem("×")
    item.setTextAlignment(Qt.AlignCenter)
    item.setFlags(Qt.ItemIsEnabled)
    item.setBackground(QBrush(QColor("#eceff1")))
    item.setForeground(QBrush(QColor("#b0bec5")))
    if loc_map:
        locs = ", ".join(sorted(loc_map.keys()))
        item.setToolTip(f"배정 근무지 아님 (배정: {locs})")
    else:
        item.setToolTip("배정 근무지 아님")
    return item


def _out_of_range_item() -> QTableWidgetItem:
    item = QTableWidgetItem("—")
    item.setTextAlignment(Qt.AlignCenter)
    item.setFlags(Qt.ItemIsEnabled)
    item.setBackground(QBrush(QColor("#cfd8dc")))
    item.setForeground(QBrush(QColor("#78909c")))
    item.setToolTip("과제 기간 외 월입니다.")
    return item
