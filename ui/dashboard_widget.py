import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget,
    QTableWidgetItem, QHeaderView, QSplitter, QGroupBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QBrush
from database.db_manager import DBManager


class DashboardWidget(QWidget):
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

        splitter = QSplitter(Qt.Vertical)

        # ── 과제별 현황 ──────────────────────────────────────
        task_group = QGroupBox("과제별 계획 / 집행 현황")
        task_layout = QVBoxLayout(task_group)

        self.task_table = QTableWidget()
        self.task_table.setColumnCount(5)
        self.task_table.setHorizontalHeaderLabels(
            ["과제명", "상태", "계획 MM", "집행 MM", "잔여 MM"]
        )
        self.task_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.task_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.task_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        for col, width in [(1, 70), (2, 160), (3, 160), (4, 160)]:
            self.task_table.setColumnWidth(col, width)
        task_layout.addWidget(self.task_table)

        # ── 인력별 현황 ──────────────────────────────────────
        person_group = QGroupBox("인력별 월별 투입 현황 (계획 / 집행)")
        person_layout = QVBoxLayout(person_group)

        self.person_table = QTableWidget()
        self.person_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.person_table.setSelectionBehavior(QTableWidget.SelectRows)
        person_layout.addWidget(self.person_table)

        splitter.addWidget(task_group)
        splitter.addWidget(person_group)
        splitter.setSizes([300, 300])

        layout.addWidget(splitter)

    def refresh(self):
        self._refresh_task_table()
        self._refresh_person_table()

    def _refresh_task_table(self):
        tasks = self.db.get_all_tasks(self.year)
        self.task_table.setRowCount(len(tasks))

        for row, task in enumerate(tasks):
            loc_mms = self.db.get_task_location_mms(task.id)
            exec_by_loc = self.db.get_task_execution_totals_by_location(task.id)
            exec_total = self.db.get_task_execution_total(task.id)

            if loc_mms:
                plan_text = " / ".join(f"{l.location}: {l.allocated_mm:.1f}" for l in loc_mms)
                exec_text = " / ".join(
                    f"{l.location}: {exec_by_loc.get(l.location, 0.0):.1f}" for l in loc_mms
                )
                rem_parts = [(l.location, l.allocated_mm - exec_by_loc.get(l.location, 0.0))
                             for l in loc_mms]
                rem_text = " / ".join(f"{loc}: {val:.1f}" for loc, val in rem_parts)
                remaining = sum(val for _, val in rem_parts)
            else:
                plan_text = f"{task.total_mm:.2f}"
                exec_text = f"{exec_total:.2f}"
                remaining = task.total_mm - exec_total
                rem_text = f"{remaining:.2f}"

            status_item = self._centered(task.status)
            if task.status == '미착수':
                status_item.setBackground(QBrush(QColor("#78909c")))
                status_item.setForeground(QBrush(QColor("#ffffff")))
            elif task.status == '착수':
                status_item.setBackground(QBrush(QColor("#1976d2")))
                status_item.setForeground(QBrush(QColor("#ffffff")))

            plan_item = self._centered(plan_text)
            exec_item = self._centered(exec_text)
            rem_item = self._centered(rem_text)

            if remaining < -1e-9:
                rem_item.setBackground(QBrush(QColor("#ef9a9a")))
            elif abs(remaining) < 1e-9:
                rem_item.setBackground(QBrush(QColor("#a5d6a7")))

            items = [
                QTableWidgetItem(task.name),
                status_item, plan_item, exec_item, rem_item,
            ]
            for col, item in enumerate(items):
                self.task_table.setItem(row, col, item)

        self.task_table.resizeRowsToContents()

    def _refresh_person_table(self):
        persons = self.db.get_all_persons(self.year)
        if not persons:
            self.person_table.setRowCount(0)
            self.person_table.setColumnCount(0)
            return

        year = self.year
        months = [(year, m) for m in range(1, 13)]
        n_months = len(months)

        self.person_table.setRowCount(len(persons))
        self.person_table.setColumnCount(n_months * 2)

        headers = []
        for y, m in months:
            headers.append(f"{m}월\n계획")
            headers.append(f"{m}월\n집행")
        self.person_table.setHorizontalHeaderLabels(headers)
        self.person_table.setVerticalHeaderLabels([p.name for p in persons])
        self.person_table.horizontalHeader().setSectionResizeMode(QHeaderView.Fixed)
        for c in range(n_months * 2):
            self.person_table.setColumnWidth(c, 55)

        for row, person in enumerate(persons):
            for col_idx, (y, m) in enumerate(months):
                plan_total = self.db.get_person_month_plan_total(person.id, y, m)
                exec_plans = self.db.get_executions_by_month(y, m)
                exec_total = sum(
                    e.actual_mm for e in exec_plans if e.person_id == person.id
                )

                plan_item = self._centered(f"{plan_total:.2f}" if plan_total else "")
                exec_item = self._centered(f"{exec_total:.2f}" if exec_total else "")

                if plan_total > 1.0 + 1e-9:
                    plan_item.setBackground(QBrush(QColor("#ef9a9a")))

                self.person_table.setItem(row, col_idx * 2, plan_item)
                self.person_table.setItem(row, col_idx * 2 + 1, exec_item)

    def _centered(self, text: str) -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        item.setTextAlignment(Qt.AlignCenter)
        return item

    def reload(self):
        self.refresh()
