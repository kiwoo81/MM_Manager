from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget,
    QTableWidgetItem, QLabel, QHeaderView,
    QAbstractItemView, QMessageBox, QPushButton
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QBrush, QFont
from database.db_manager import DBManager
from database.models import MMExecution
from logic.mm_calculator import MMCalculator
from ui.mm_delegate import MMExecutionDelegate, MMTableWidget
import datetime

MONTH_NAMES = ['1월','2월','3월','4월','5월','6월',
               '7월','8월','9월','10월','11월','12월']

COL_PERSON    = 0
COL_TASK      = 1
COL_JAN       = 2
COL_DEC       = 13
COL_TOTAL     = 14
COL_LOC_TOTAL = 15
N_COLS        = 16

LOCK_ROW = 0  # 잠금 버튼 행 (항상 첫 번째 행)


class ExecutionWidget(QWidget):
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

        self.table = MMTableWidget()
        self.table.setEditTriggers(QAbstractItemView.AnyKeyPressed)
        self.table.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.table.setItemDelegate(MMExecutionDelegate(self.table))
        self.table.itemChanged.connect(self._on_item_changed)

        layout.addLayout(top_bar)
        layout.addWidget(QLabel(
            "※ 셀 선택 후 숫자 입력 (음수 포함, 소수점 1자리). "
            "착수/완료 과제에만 입력 가능. 미착수 과제 셀은 회색 비활성화. "
            "황색=계획 없는 집행 / 계획합계: 파랑 / 집행합계: 초록=달성, 주황=부분, 빨강=초과"
        ))
        layout.addWidget(self.table)

    # ──────────────────────────────────────────────────────────────────────────

    def refresh(self):
        self._tasks = self.db.get_all_tasks(self.year)
        self._persons = self.db.get_all_persons(self.year)
        year = self.year
        self._locked_months = self.db.get_locked_months(year)

        exec_map = {}  # (person_id, task_id, month) -> actual_mm
        for month in range(1, 13):
            for e in self.db.get_executions_by_month(year, month):
                exec_map[(e.person_id, e.task_id, month)] = e.actual_mm

        # 계획 데이터 로드
        plan_map = {}  # (person_id, task_id, month) -> planned_mm
        for month in range(1, 13):
            for p in self.db.get_plans_by_month(year, month):
                plan_map[(p.person_id, p.task_id, month)] = p.planned_mm

        active_task_ids = {t.id for t in self._tasks if t.status == '착수'}

        # 과제별 근무지 할당 MM: {task_id: {loc: allocated_mm}}
        task_loc_mms: dict[int, dict[str, float]] = {}
        for task in self._tasks:
            locs = self.db.get_task_location_mms(task.id)
            if locs:
                task_loc_mms[task.id] = {lm.location: lm.allocated_mm for lm in locs}
        self._task_location_sets = {tid: set(locs.keys()) for tid, locs in task_loc_mms.items()}

        # 인력별 근무지
        person_location = {p.id: p.location for p in self._persons}

        # 근무지별 월별/연간 계획/집행 합계 (선택 연도 기준)
        loc_plan_annual: dict[str, float] = {}
        loc_plan_monthly: dict[str, dict[int, float]] = {}
        for (pid, tid, m), val in plan_map.items():
            loc = person_location.get(pid, "")
            if loc:
                loc_plan_annual[loc] = loc_plan_annual.get(loc, 0.0) + val
                month_dict = loc_plan_monthly.setdefault(loc, {})
                month_dict[m] = month_dict.get(m, 0.0) + val

        loc_exec_annual: dict[str, float] = {}
        loc_exec_monthly: dict[str, dict[int, float]] = {}
        for (pid, tid, m), val in exec_map.items():
            loc = person_location.get(pid, "")
            if loc:
                loc_exec_annual[loc] = loc_exec_annual.get(loc, 0.0) + val
                month_dict = loc_exec_monthly.setdefault(loc, {})
                month_dict[m] = month_dict.get(m, 0.0) + val

        # 과제+근무지별 연간 집행 합계: {(task_id, loc): total_exec}
        task_loc_exec: dict[tuple, float] = {}
        for (pid, tid, m), val in exec_map.items():
            loc = person_location.get(pid, "")
            if loc:
                task_loc_exec[(tid, loc)] = task_loc_exec.get((tid, loc), 0.0) + val

        # 전체 근무지 목록 (요약 행 표시용, 인력 입력 순서 유지)
        all_locs = list(dict.fromkeys(p.location for p in self._persons if p.location))

        n_tasks = len(self._tasks)
        n_persons = len(self._persons)
        n_summary_rows = (1 + len(all_locs) * 2) if all_locs else 0

        self.table.blockSignals(True)
        self.table.clearSpans()
        self.table.setRowCount(0)

        # 행 수: 잠금 행(1) + 각 인력당 (과제 수 + 계획합계 행 + 집행합계 행) + 하단 근무지 요약
        total_rows = 1 + n_persons * (n_tasks + 2) + n_summary_rows
        self.table.setRowCount(total_rows)
        self.table.setColumnCount(N_COLS)

        self.table.setHorizontalHeaderLabels(
            ['인력', '과제'] + MONTH_NAMES + ['연간합계', '근무지합계']
        )
        self.table.setColumnWidth(COL_PERSON, 80)
        self.table.setColumnWidth(COL_TASK, 120)
        for c in range(COL_JAN, COL_DEC + 1):
            self.table.setColumnWidth(c, 55)
        self.table.setColumnWidth(COL_TOTAL, 75)
        self.table.setColumnWidth(COL_LOC_TOTAL, 150)
        self.table.horizontalHeader().setSectionResizeMode(COL_TASK, QHeaderView.Stretch)

        # ── 잠금 행 (row 0) ────────────────────────────────────────────────
        self.table.setRowHeight(LOCK_ROW, 30)
        for col in [COL_PERSON, COL_TOTAL, COL_LOC_TOTAL]:
            placeholder = QTableWidgetItem("")
            placeholder.setFlags(Qt.ItemIsEnabled)
            placeholder.setBackground(QBrush(QColor("#263238")))
            self.table.setItem(LOCK_ROW, col, placeholder)
        lock_label = QTableWidgetItem("월 잠금")
        lock_label.setFlags(Qt.ItemIsEnabled)
        lock_label.setTextAlignment(Qt.AlignCenter)
        lock_label.setBackground(QBrush(QColor("#263238")))
        lock_label.setForeground(QBrush(QColor("#90a4ae")))
        font = QFont(); font.setBold(True)
        lock_label.setFont(font)
        self.table.setItem(LOCK_ROW, COL_TASK, lock_label)
        max_locked = max(self._locked_months) if self._locked_months else 0
        for m_idx in range(12):
            month = m_idx + 1
            is_locked = month in self._locked_months
            # 잠금: 이전 월이 모두 잠겨야 잠금 가능 (순서대로)
            # 해제: 마지막 잠긴 월만 해제 가능 (역순)
            can_interact = (is_locked and month == max_locked) or \
                           (not is_locked and month == max_locked + 1)
            btn = QPushButton("🔒" if is_locked else "🔓")
            if is_locked:
                if can_interact:
                    btn.setToolTip(f"{month}월 잠금 해제")
                    btn.setStyleSheet(
                        "QPushButton { background-color: #b71c1c; color: white; "
                        "font-size: 14px; border: none; }"
                        "QPushButton:hover { background-color: #d32f2f; }"
                    )
                else:
                    btn.setToolTip(f"{month}월 잠금됨 (마지막 잠긴 월부터 순서대로 해제)")
                    btn.setStyleSheet(
                        "QPushButton { background-color: #7f0000; color: #ef9a9a; "
                        "font-size: 14px; border: none; }"
                    )
                    btn.setEnabled(False)
            else:
                if can_interact:
                    btn.setToolTip(f"{month}월 잠금 설정")
                    btn.setStyleSheet(
                        "QPushButton { background-color: #37474f; color: #78909c; "
                        "font-size: 14px; border: none; }"
                        "QPushButton:hover { background-color: #455a64; color: #cfd8dc; }"
                    )
                else:
                    btn.setToolTip(f"{month}월 잠금 불가 (이전 월을 먼저 잠가야 함)")
                    btn.setStyleSheet(
                        "QPushButton { background-color: #263238; color: #546e7a; "
                        "font-size: 14px; border: none; }"
                    )
                    btn.setEnabled(False)
            btn.clicked.connect(lambda checked, m=month: self._toggle_month_lock(m))
            self.table.setCellWidget(LOCK_ROW, COL_JAN + m_idx, btn)

        self._row_map = {}
        row = 1  # LOCK_ROW(0) 다음부터 시작

        for person in self._persons:
            person_start_row = row

            for t_idx, task in enumerate(self._tasks):
                self._row_map[row] = ('data', person.id, task.id)
                is_active = task.id in active_task_ids

                # 근무지 일치 여부: 과제에 근무지 제한이 있고 인력 근무지가 불일치하면 False
                if task.id in self._task_location_sets:
                    p_loc = person_location.get(person.id, "")
                    is_loc_match = bool(p_loc) and p_loc in self._task_location_sets[task.id]
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
                        cell = _inactive_item(task.name)
                    elif not is_loc_match:
                        task_locs = " / ".join(sorted(self._task_location_sets.get(task.id, set())))
                        cell = _loc_mismatch_item(task_locs)
                    elif month in self._locked_months:
                        planned = plan_map.get((person.id, task.id, month), 0.0)
                        if mm and abs(planned) < 1e-9:
                            cell = _locked_unplanned_item(f"{mm:.1f}")
                        else:
                            cell = _locked_item(f"{mm:.1f}" if mm else "")
                    else:
                        planned = plan_map.get((person.id, task.id, month), 0.0)
                        if mm and abs(planned) < 1e-9:
                            cell = _unplanned_exec_item(f"{mm:.1f}")
                        else:
                            cell = QTableWidgetItem(f"{mm:.1f}" if mm else "")
                            cell.setTextAlignment(Qt.AlignCenter)

                    self.table.setItem(row, COL_JAN + m_idx, cell)
                    annual += mm

                self.table.setItem(
                    row, COL_TOTAL,
                    _readonly_item(f"{annual:.1f}" if annual else "")
                )
                loc_map = task_loc_mms.get(task.id, {})
                if loc_map:
                    parts, tip_lines, is_over = [], [], False
                    for loc in loc_map.keys():
                        allocated = loc_map[loc]
                        executed = task_loc_exec.get((task.id, loc), 0.0)
                        parts.append(f"{loc}: {executed:.1f}")
                        diff = executed - allocated
                        tip_lines.append(
                            f"{loc}  할당: {int(allocated)} / 집행: {executed:.1f}"
                            + (f" (초과 +{diff:.1f})" if diff > 1e-9 else f" (잔여 {-diff:.1f})")
                        )
                        if diff > 1e-9:
                            is_over = True
                    loc_cell = QTableWidgetItem(" / ".join(parts))
                    loc_cell.setTextAlignment(Qt.AlignCenter)
                    loc_cell.setFlags(Qt.ItemIsEnabled)
                    font = QFont(); font.setBold(True)
                    loc_cell.setFont(font)
                    loc_cell.setToolTip("\n".join(tip_lines))
                    loc_cell.setBackground(QBrush(QColor("#c62828") if is_over else QColor("#546e7a")))
                    loc_cell.setForeground(QBrush(QColor("#ffffff")))
                    self.table.setItem(row, COL_LOC_TOTAL, loc_cell)
                else:
                    self.table.setItem(row, COL_LOC_TOTAL, _disabled_summary_item())
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
                month_p = m_idx + 1
                monthly_plan = sum(
                    plan_map.get((person.id, t.id, month_p), 0.0)
                    for t in self._tasks
                )
                person_plan_monthly.append(monthly_plan)
                plan_annual += monthly_plan
                pitem = _plan_item(f"{monthly_plan:.1f}" if monthly_plan else "")
                # 툴팁: 과제별 계획 내역
                task_details = [
                    f"  {t.name}: {plan_map.get((person.id, t.id, month_p), 0.0):.1f}MM"
                    for t in self._tasks
                    if plan_map.get((person.id, t.id, month_p), 0.0) > 1e-9
                ]
                if task_details:
                    pitem.setToolTip(f"[{month_p}월 계획 내역]\n" + "\n".join(task_details))
                if month_p in self._locked_months:
                    pitem.setBackground(QBrush(QColor("#78909c")))
                self.table.setItem(row, COL_JAN + m_idx, pitem)

            self.table.setItem(row, COL_TOTAL, _plan_item(f"{plan_annual:.1f}" if plan_annual else ""))
            self.table.setItem(row, COL_LOC_TOTAL, _disabled_summary_item())
            row += 1

            # ── 집행합계 행 ─────────────────────────────────────────────
            self._row_map[row] = ('total', person.id)

            exec_label = QTableWidgetItem("집행합계")
            exec_label.setFlags(Qt.ItemIsEnabled)
            _apply_total_style(exec_label)
            self.table.setItem(row, COL_TASK, exec_label)

            exec_annual = 0.0
            for m_idx in range(12):
                month_e = m_idx + 1
                monthly_exec = sum(
                    exec_map.get((person.id, t.id, month_e), 0.0)
                    for t in self._tasks
                )
                monthly_plan = person_plan_monthly[m_idx]
                exec_annual += monthly_exec
                mitem = _exec_compare_item(monthly_exec, monthly_plan)
                if month_e in self._locked_months:
                    mitem.setBackground(QBrush(QColor("#78909c")))
                self.table.setItem(row, COL_JAN + m_idx, mitem)

            self.table.setItem(row, COL_TOTAL, _readonly_item(f"{exec_annual:.1f}" if exec_annual else ""))
            if all_locs:
                le_parts, le_tips, le_over = [], [], False
                for loc in all_locs:
                    plan_v = loc_plan_annual.get(loc, 0.0)
                    exec_v = loc_exec_annual.get(loc, 0.0)
                    le_parts.append(f"{loc}: {exec_v:.1f}")
                    diff = exec_v - plan_v
                    le_tips.append(
                        f"{loc}  계획: {plan_v:.1f} / 집행: {exec_v:.1f}"
                        + (f" (초과 +{diff:.1f})" if diff > 1e-9 else "")
                    )
                    if exec_v > plan_v + 1e-9:
                        le_over = True
                le_cell = QTableWidgetItem(" / ".join(le_parts))
                le_cell.setTextAlignment(Qt.AlignCenter)
                le_cell.setFlags(Qt.ItemIsEnabled)
                font = QFont(); font.setBold(True)
                le_cell.setFont(font)
                le_cell.setToolTip("\n".join(le_tips))
                le_cell.setBackground(QBrush(QColor("#c62828") if le_over else QColor("#546e7a")))
                le_cell.setForeground(QBrush(QColor("#ffffff")))
                self.table.setItem(row, COL_LOC_TOTAL, le_cell)
            else:
                self.table.setItem(row, COL_LOC_TOTAL, _disabled_summary_item())
            row += 1

        # ── 근무지별 계획/집행 합계 (하단 요약) ────────────────────────────
        if all_locs:
            # 구분선 행
            sep_label = QTableWidgetItem("근무지별 계획 / 집행 합계")
            sep_label.setFlags(Qt.ItemIsEnabled)
            sep_label.setTextAlignment(Qt.AlignCenter)
            sep_label.setBackground(QBrush(QColor("#263238")))
            sep_label.setForeground(QBrush(QColor("#90a4ae")))
            font = QFont(); font.setBold(True)
            sep_label.setFont(font)
            self.table.setSpan(row, 0, 1, N_COLS)
            self.table.setItem(row, 0, sep_label)
            self.table.setRowHeight(row, 24)
            row += 1

            for loc in all_locs:
                pm = loc_plan_monthly.get(loc, {})
                em = loc_exec_monthly.get(loc, {})

                # 근무지 이름 셀 (계획/집행 2행 span)
                loc_name_item = QTableWidgetItem(loc)
                loc_name_item.setFlags(Qt.ItemIsEnabled)
                loc_name_item.setTextAlignment(Qt.AlignCenter | Qt.AlignVCenter)
                _apply_header_style(loc_name_item)
                self.table.setItem(row, COL_PERSON, loc_name_item)
                self.table.setSpan(row, COL_PERSON, 2, 1)

                # 계획 행
                plan_label = QTableWidgetItem("계획")
                plan_label.setFlags(Qt.ItemIsEnabled)
                _apply_plan_style(plan_label)
                self.table.setItem(row, COL_TASK, plan_label)
                plan_annual = 0.0
                for m_idx in range(12):
                    val = pm.get(m_idx + 1, 0.0)
                    plan_annual += val
                    self.table.setItem(row, COL_JAN + m_idx, _plan_item(f"{val:.1f}" if val else ""))
                self.table.setItem(row, COL_TOTAL, _plan_item(f"{plan_annual:.1f}" if plan_annual else ""))
                self.table.setItem(row, COL_LOC_TOTAL, _disabled_summary_item())
                row += 1

                # 집행 행
                exec_label = QTableWidgetItem("집행")
                exec_label.setFlags(Qt.ItemIsEnabled)
                _apply_total_style(exec_label)
                self.table.setItem(row, COL_TASK, exec_label)
                exec_annual = 0.0
                for m_idx in range(12):
                    exec_val = em.get(m_idx + 1, 0.0)
                    plan_val = pm.get(m_idx + 1, 0.0)
                    exec_annual += exec_val
                    self.table.setItem(row, COL_JAN + m_idx, _exec_compare_item(exec_val, plan_val))
                self.table.setItem(row, COL_TOTAL, _readonly_item(f"{exec_annual:.1f}" if exec_annual else ""))
                self.table.setItem(row, COL_LOC_TOTAL, _disabled_summary_item())
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

        # 잠긴 월 보호
        if month in self._locked_months:
            self._restore_cell(r, c, task_id, person_id, year, month)
            QMessageBox.warning(
                self.window(), "월 잠금",
                f"{month}월은 잠겨 있어 수정할 수 없습니다.\n"
                "잠금을 해제하려면 상단의 🔒 버튼을 클릭하세요."
            )
            return

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

    def _toggle_month_lock(self, month: int):
        year = self.year
        is_locked = month in self._locked_months
        self.db.set_month_lock(year, month, not is_locked)
        self.refresh()

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


def _inactive_item(task_name: str) -> QTableWidgetItem:
    """미착수 과제 셀 (— 기호, 회색)."""
    item = QTableWidgetItem("—")
    item.setTextAlignment(Qt.AlignCenter)
    item.setFlags(Qt.ItemIsEnabled)
    item.setBackground(QBrush(QColor("#e0e0e0")))
    item.setForeground(QBrush(QColor("#9e9e9e")))
    item.setToolTip(f"'{task_name}'은(는) 아직 착수되지 않았습니다.")
    return item


def _loc_mismatch_item(task_locs: str) -> QTableWidgetItem:
    """근무지 불일치 셀 (× 기호, 연보라)."""
    item = QTableWidgetItem("×")
    item.setTextAlignment(Qt.AlignCenter)
    item.setFlags(Qt.ItemIsEnabled)
    item.setBackground(QBrush(QColor("#eceff1")))
    item.setForeground(QBrush(QColor("#b0bec5")))
    item.setToolTip(f"배정 근무지 아님 (배정: {task_locs})")
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


def _locked_item(text: str) -> QTableWidgetItem:
    """잠긴 월 셀 (편집 불가, 회색)."""
    item = QTableWidgetItem(text)
    item.setTextAlignment(Qt.AlignCenter)
    item.setFlags(Qt.ItemIsEnabled)
    item.setBackground(QBrush(QColor("#b0bec5")))
    item.setForeground(QBrush(QColor("#455a64")))
    item.setToolTip("🔒 잠긴 월 — 편집 불가")
    return item


def _disabled_summary_item() -> QTableWidgetItem:
    """근무지합계 컬럼의 데이터 행 비활성 셀."""
    item = QTableWidgetItem("")
    item.setFlags(Qt.ItemIsEnabled)
    item.setBackground(QBrush(QColor("#eceff1")))
    return item


def _locked_unplanned_item(text: str) -> QTableWidgetItem:
    """잠긴 월 + 계획 없는 집행 셀 (황색 계열, 편집 불가)."""
    item = QTableWidgetItem(text)
    item.setTextAlignment(Qt.AlignCenter)
    item.setFlags(Qt.ItemIsEnabled)
    item.setBackground(QBrush(QColor("#e65100")))
    item.setForeground(QBrush(QColor("#ffffff")))
    item.setToolTip("🔒 계획 없는 집행 (잠긴 월)")
    return item


def _unplanned_exec_item(text: str) -> QTableWidgetItem:
    """계획 없이 집행값이 입력된 셀 (황색 경고)."""
    item = QTableWidgetItem(text)
    item.setTextAlignment(Qt.AlignCenter)
    item.setBackground(QBrush(QColor("#f57f17")))
    item.setForeground(QBrush(QColor("#ffffff")))
    item.setToolTip("⚠ 계획 없는 집행")
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
