from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget,
    QTableWidgetItem, QLabel, QHeaderView, QSplitter, QGroupBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QBrush, QFont
from database.db_manager import DBManager


class DashboardWidget(QWidget):
    def __init__(self, db: DBManager, parent=None):
        super().__init__(parent)
        self.db = db
        self._build_ui()
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
        self.task_table.setColumnWidth(1, 80)
        self.task_table.setColumnWidth(2, 90)
        self.task_table.setColumnWidth(3, 90)
        self.task_table.setColumnWidth(4, 90)
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
        tasks = self.db.get_all_tasks()
        self.task_table.setRowCount(len(tasks))

        for row, task in enumerate(tasks):
            plan_total = self.db.get_task_plan_total(task.id)
            exec_total = self.db.get_task_execution_total(task.id)
            remaining = task.total_mm - exec_total

            items = [
                QTableWidgetItem(task.name),
                self._centered(task.status),
                self._centered(f"{task.total_mm:.2f}"),
                self._centered(f"{exec_total:.2f}"),
                self._centered(f"{remaining:.2f}"),
            ]

            # 상태 색상
            status_color = {
                '대기': QColor("#e0e0e0"),
                '착수': QColor("#cce5ff"),
                '완료': QColor("#d4edda"),
            }.get(task.status, None)
            if status_color:
                items[1].setBackground(QBrush(status_color))

            # 잔여 MM 색상
            if remaining < -1e-9:
                items[4].setBackground(QBrush(QColor("#ffcccc")))  # 초과
            elif abs(remaining) < 1e-9:
                items[4].setBackground(QBrush(QColor("#ccffcc")))  # 정확히 소진

            for col, item in enumerate(items):
                self.task_table.setItem(row, col, item)

    def _refresh_person_table(self):
        persons = self.db.get_all_persons()
        if not persons:
            self.person_table.setRowCount(0)
            self.person_table.setColumnCount(0)
            return

        import datetime
        now = datetime.date.today()
        # 최근 6개월 ~ 향후 2개월 표시
        months = []
        for delta in range(-5, 3):
            y = now.year + (now.month + delta - 1) // 12
            m = (now.month + delta - 1) % 12 + 1
            months.append((y, m))

        n_months = len(months)
        n_persons = len(persons)

        self.person_table.setRowCount(n_persons)
        self.person_table.setColumnCount(n_months * 2)

        # 헤더: 각 월에 계획/집행 두 열
        headers = []
        for y, m in months:
            headers.append(f"{y}-{m:02d}\n계획")
            headers.append(f"{y}-{m:02d}\n집행")
        self.person_table.setHorizontalHeaderLabels(headers)
        self.person_table.setVerticalHeaderLabels([p.name for p in persons])
        self.person_table.horizontalHeader().setSectionResizeMode(QHeaderView.Fixed)
        for c in range(n_months * 2):
            self.person_table.setColumnWidth(c, 65)

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
                    plan_item.setBackground(QBrush(QColor("#ffcccc")))

                self.person_table.setItem(row, col_idx * 2, plan_item)
                self.person_table.setItem(row, col_idx * 2 + 1, exec_item)

    def _centered(self, text: str) -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        item.setTextAlignment(Qt.AlignCenter)
        return item

    def reload(self):
        self.refresh()
