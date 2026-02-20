from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget,
    QTableWidgetItem, QLabel, QComboBox, QHeaderView,
    QAbstractItemView, QMessageBox
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QBrush, QFont
from database.db_manager import DBManager
from database.models import MMExecution
from logic.mm_calculator import MMCalculator
from ui.mm_delegate import MMDelegate, MMTableWidget
import datetime

MONTH_NAMES = ['1월','2월','3월','4월','5월','6월',
               '7월','8월','9월','10월','11월','12월']

COL_PERSON = 0
COL_TASK   = 1
COL_JAN    = 2
COL_DEC    = 13
COL_TOTAL  = 14
N_COLS     = 15


class ExecutionWidget(QWidget):
    data_changed = Signal()

    def __init__(self, db: DBManager, parent=None):
        super().__init__(parent)
        self.db = db
        self.calc = MMCalculator(db)
        self._tasks = []
        self._persons = []
        self._row_map = {}
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        top_bar = QHBoxLayout()
        top_bar.addWidget(QLabel("연도:"))
        self.year_combo = QComboBox()
        now = datetime.date.today()
        for y in range(now.year - 2, now.year + 3):
            self.year_combo.addItem(str(y), y)
        self.year_combo.setCurrentIndex(2)
        top_bar.addWidget(self.year_combo)
        top_bar.addStretch()
        self.year_combo.currentIndexChanged.connect(self.refresh)

        self.table = MMTableWidget()
        self.table.setEditTriggers(QAbstractItemView.AnyKeyPressed)
        self.table.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.table.setItemDelegate(MMDelegate(self.table))
        self.table.itemChanged.connect(self._on_item_changed)

        layout.addLayout(top_bar)
        layout.addWidget(QLabel(
            "※ 셀 선택 후 숫자 입력 (0.0~1.0, 소수점 1자리). "
            "착수/완료 과제에만 입력 가능. 미착수 과제 셀은 회색 비활성화. "
            "계획합계: 파랑 / 집행합계: 초록=달성, 주황=부분, 빨강=초과"
        ))
        layout.addWidget(self.table)

    # ──────────────────────────────────────────────────────────────────────────

    def refresh(self):
        self._tasks = self.db.get_all_tasks()
        self._persons = self.db.get_all_persons()
        year = self.year_combo.currentData()

        exec_map = {}  # (person_id, task_id, month) -> actual_mm
        for month in range(1, 13):
            for e in self.db.get_executions_by_month(year, month):
                exec_map[(e.person_id, e.task_id, month)] = e.actual_mm

        # 계획 데이터 로드
        plan_map = {}  # (person_id, task_id, month) -> planned_mm
        for month in range(1, 13):
            for p in self.db.get_plans_by_month(year, month):
                plan_map[(p.person_id, p.task_id, month)] = p.planned_mm

        active_task_ids = {t.id for t in self._tasks if t.status in ('착수', '완료')}

        # 과제별 허용 근무지 집합 (항목 없으면 제한 없음)
        task_location_sets = {}
        for task in self._tasks:
            locs = self.db.get_task_location_mms(task.id)
            if locs:
                task_location_sets[task.id] = {lm.location for lm in locs}
        self._task_location_sets = task_location_sets

        # 인력별 근무지
        person_location = {p.id: p.location for p in self._persons}

        n_tasks = len(self._tasks)
        n_persons = len(self._persons)

        self.table.blockSignals(True)
        self.table.clearSpans()
        self.table.setRowCount(0)

        # 행 수: 각 인력당 (과제 수 + 계획합계 행 + 집행합계 행)
        total_rows = n_persons * (n_tasks + 2)
        self.table.setRowCount(total_rows)
        self.table.setColumnCount(N_COLS)

        self.table.setHorizontalHeaderLabels(
            ['인력', '과제'] + MONTH_NAMES + ['연간합계']
        )
        self.table.setColumnWidth(COL_PERSON, 80)
        self.table.setColumnWidth(COL_TASK, 120)
        for c in range(COL_JAN, COL_DEC + 1):
            self.table.setColumnWidth(c, 55)
        self.table.setColumnWidth(COL_TOTAL, 75)
        self.table.horizontalHeader().setSectionResizeMode(COL_TASK, QHeaderView.Stretch)

        self._row_map = {}
        row = 0

        for person in self._persons:
            person_start_row = row

            for t_idx, task in enumerate(self._tasks):
                self._row_map[row] = ('data', person.id, task.id)
                is_active = task.id in active_task_ids

                # 근무지 일치 여부: 과제에 근무지 제한이 있고 인력 근무지가 불일치하면 False
                if task.id in task_location_sets:
                    p_loc = person_location.get(person.id, "")
                    is_loc_match = bool(p_loc) and p_loc in task_location_sets[task.id]
                else:
                    is_loc_match = True

                # 인력명 (첫 행에만, span: 과제 수 + 2행 모두 포함)
                if t_idx == 0:
                    name_text = f"{person.name}\n({person.location})" if person.location else person.name
                    pi = QTableWidgetItem(name_text)
                    pi.setFlags(Qt.ItemIsEnabled)
                    pi.setTextAlignment(Qt.AlignCenter | Qt.AlignVCenter)
                    _apply_header_style(pi)
                    self.table.setItem(row, COL_PERSON, pi)
                    self.table.setSpan(person_start_row, COL_PERSON, n_tasks + 2, 1)

                # 과제명
                ti = QTableWidgetItem(task.name)
                ti.setFlags(Qt.ItemIsEnabled)
                if not is_active:
                    ti.setForeground(QBrush(QColor("#888888")))
                self.table.setItem(row, COL_TASK, ti)

                # 월별 집행 MM
                annual = 0.0
                for m_idx in range(12):
                    month = m_idx + 1
                    mm = exec_map.get((person.id, task.id, month), 0.0)

                    if not task.in_range(year, month):
                        cell = _out_of_range_item()
                    elif not is_active:
                        cell = QTableWidgetItem(f"{mm:.1f}" if mm else "")
                        cell.setTextAlignment(Qt.AlignCenter)
                        cell.setFlags(Qt.ItemIsEnabled)
                        cell.setBackground(QBrush(QColor("#e0e0e0")))
                        cell.setForeground(QBrush(QColor("#9e9e9e")))
                        cell.setToolTip(f"'{task.name}'은(는) 아직 착수되지 않았습니다.")
                    elif not is_loc_match:
                        task_locs = " / ".join(sorted(task_location_sets.get(task.id, set())))
                        cell = QTableWidgetItem("")
                        cell.setTextAlignment(Qt.AlignCenter)
                        cell.setFlags(Qt.ItemIsEnabled)
                        cell.setBackground(QBrush(QColor("#ede7f6")))
                        cell.setForeground(QBrush(QColor("#9e9e9e")))
                        cell.setToolTip(f"이 과제는 '{task_locs}' 근무지 인력만 집행할 수 있습니다.")
                    else:
                        cell = QTableWidgetItem(f"{mm:.1f}" if mm else "")
                        cell.setTextAlignment(Qt.AlignCenter)

                    self.table.setItem(row, COL_JAN + m_idx, cell)
                    annual += mm

                self.table.setItem(
                    row, COL_TOTAL,
                    _readonly_item(f"{annual:.1f}" if annual else "")
                )
                row += 1

            # ── 계획합계 행 ─────────────────────────────────────────────
            self._row_map[row] = ('plan_total', person.id)

            plan_label = QTableWidgetItem("계획합계")
            plan_label.setFlags(Qt.ItemIsEnabled)
            _apply_plan_style(plan_label)
            self.table.setItem(row, COL_TASK, plan_label)

            person_plan_monthly = []
            plan_annual = 0.0
            for m_idx in range(12):
                monthly_plan = sum(
                    plan_map.get((person.id, t.id, m_idx + 1), 0.0)
                    for t in self._tasks
                )
                person_plan_monthly.append(monthly_plan)
                plan_annual += monthly_plan
                pitem = _plan_item(f"{monthly_plan:.1f}" if monthly_plan else "")
                self.table.setItem(row, COL_JAN + m_idx, pitem)

            self.table.setItem(row, COL_TOTAL, _plan_item(f"{plan_annual:.1f}" if plan_annual else ""))
            row += 1

            # ── 집행합계 행 ─────────────────────────────────────────────
            self._row_map[row] = ('total', person.id)

            exec_label = QTableWidgetItem("집행합계")
            exec_label.setFlags(Qt.ItemIsEnabled)
            _apply_total_style(exec_label)
            self.table.setItem(row, COL_TASK, exec_label)

            exec_annual = 0.0
            for m_idx in range(12):
                monthly_exec = sum(
                    exec_map.get((person.id, t.id, m_idx + 1), 0.0)
                    for t in self._tasks
                )
                monthly_plan = person_plan_monthly[m_idx]
                exec_annual += monthly_exec
                mitem = _exec_compare_item(monthly_exec, monthly_plan)
                self.table.setItem(row, COL_JAN + m_idx, mitem)

            self.table.setItem(row, COL_TOTAL, _readonly_item(f"{exec_annual:.1f}" if exec_annual else ""))
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
        year = self.year_combo.currentData()

        task = self.db.get_task(task_id)
        if task and not task.in_range(year, month):
            self.table.blockSignals(True)
            item.setText("—")
            self.table.blockSignals(False)
            return

        # 근무지 불일치 시 차단
        if task_id in self._task_location_sets:
            person = self.db.get_person(person_id)
            p_loc = person.location if person else ""
            if not p_loc or p_loc not in self._task_location_sets[task_id]:
                self._restore_cell(r, c, task_id, person_id, year, month)
                return

        text = item.text().strip()
        try:
            mm_val = float(text) if text else 0.0
        except ValueError:
            self._restore_cell(r, c, task_id, person_id, year, month)
            return

        ok, msg = self.calc.validate_execution(task_id, person_id, year, month, mm_val)
        if not ok:
            QMessageBox.warning(self.window(), "집행 입력 불가", msg)
            self._restore_cell(r, c, task_id, person_id, year, month)
            return

        warning = self.calc.get_execution_warning(task_id, mm_val, year, month, person_id)
        if warning:
            reply = QMessageBox.question(
                self.window(), "집행 MM 경고",
                f"{warning}\n\n계속 입력하시겠습니까?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.No:
                self._restore_cell(r, c, task_id, person_id, year, month)
                return

        if mm_val == 0.0:
            self.db.delete_execution(task_id, person_id, year, month)
        else:
            self.db.upsert_execution(
                MMExecution(None, task_id, person_id, year, month, mm_val, "")
            )

        self.refresh()
        self.data_changed.emit()

    def _restore_cell(self, row, col, task_id, person_id, year, month):
        existing = self.db.get_execution(task_id, person_id, year, month)
        self.table.blockSignals(True)
        self.table.item(row, col).setText(
            f"{existing.actual_mm:.1f}" if existing else ""
        )
        self.table.blockSignals(False)

    def reload(self):
        self.refresh()


# ── 스타일 헬퍼 ─────────────────────────────────────────────────────────────

def _out_of_range_item() -> QTableWidgetItem:
    """과제 기간 외 월 셀."""
    item = QTableWidgetItem("—")
    item.setTextAlignment(Qt.AlignCenter)
    item.setFlags(Qt.ItemIsEnabled)
    item.setBackground(QBrush(QColor("#cfd8dc")))
    item.setForeground(QBrush(QColor("#78909c")))
    item.setToolTip("과제 기간 외 월입니다.")
    return item


def _apply_header_style(item: QTableWidgetItem):
    """인력명 셀 스타일 (짙은 청회색 배경, 흰 텍스트)"""
    item.setBackground(QBrush(QColor("#455a64")))
    item.setForeground(QBrush(QColor("#ffffff")))
    font = QFont(); font.setBold(True)
    item.setFont(font)


def _apply_plan_style(item: QTableWidgetItem):
    """계획합계 레이블 셀 스타일 (파란색 계열)"""
    item.setBackground(QBrush(QColor("#1565c0")))
    item.setForeground(QBrush(QColor("#ffffff")))
    font = QFont(); font.setBold(True)
    item.setFont(font)


def _apply_total_style(item: QTableWidgetItem):
    """집행합계 레이블 셀 스타일"""
    item.setBackground(QBrush(QColor("#546e7a")))
    item.setForeground(QBrush(QColor("#ffffff")))
    font = QFont(); font.setBold(True)
    item.setFont(font)


def _plan_item(text: str) -> QTableWidgetItem:
    """계획합계 값 셀 (파란색, 읽기전용)"""
    item = QTableWidgetItem(text)
    item.setTextAlignment(Qt.AlignCenter)
    item.setFlags(Qt.ItemIsEnabled)
    item.setBackground(QBrush(QColor("#1976d2")))
    item.setForeground(QBrush(QColor("#ffffff")))
    font = QFont(); font.setBold(True)
    item.setFont(font)
    return item


def _readonly_item(text: str) -> QTableWidgetItem:
    """읽기 전용 합계 값 셀"""
    item = QTableWidgetItem(text)
    item.setTextAlignment(Qt.AlignCenter)
    item.setFlags(Qt.ItemIsEnabled)
    item.setBackground(QBrush(QColor("#546e7a")))
    item.setForeground(QBrush(QColor("#ffffff")))
    font = QFont(); font.setBold(True)
    item.setFont(font)
    return item


def _exec_compare_item(exec_mm: float, plan_mm: float) -> QTableWidgetItem:
    """집행합계 셀: 계획 대비 색상 표시."""
    text = f"{exec_mm:.1f}" if exec_mm else ""
    item = QTableWidgetItem(text)
    item.setTextAlignment(Qt.AlignCenter)
    item.setFlags(Qt.ItemIsEnabled)
    font = QFont(); font.setBold(True)
    item.setFont(font)

    if plan_mm < 1e-9:
        # 계획 없음
        item.setBackground(QBrush(QColor("#546e7a")))
    elif exec_mm > plan_mm + 1e-9:
        # 계획 초과 (빨강)
        item.setBackground(QBrush(QColor("#c62828")))
        item.setToolTip(f"계획 초과: 집행 {exec_mm:.1f} / 계획 {plan_mm:.1f}")
    elif abs(exec_mm - plan_mm) < 1e-9:
        # 계획 달성 (초록)
        item.setBackground(QBrush(QColor("#2e7d32")))
        item.setToolTip(f"계획 달성: {exec_mm:.1f}MM")
    elif exec_mm > 1e-9:
        # 부분 집행 (주황)
        item.setBackground(QBrush(QColor("#e65100")))
        item.setToolTip(f"부분 집행: 집행 {exec_mm:.1f} / 계획 {plan_mm:.1f}")
    else:
        # 미집행
        item.setBackground(QBrush(QColor("#546e7a")))
        item.setToolTip(f"미집행 (계획: {plan_mm:.1f})")

    item.setForeground(QBrush(QColor("#ffffff")))
    return item
