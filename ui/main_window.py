import datetime
from PySide6.QtWidgets import (
    QMainWindow, QTabWidget, QWidget, QVBoxLayout,
    QHBoxLayout, QSplitter, QGroupBox, QLabel, QComboBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QIntValidator
from database.db_manager import DBManager
from ui.task_widget import TaskWidget
from ui.person_widget import PersonWidget
from ui.plan_widget import PlanWidget
from ui.execution_widget import ExecutionWidget
from ui.dashboard_widget import DashboardWidget


class MainWindow(QMainWindow):
    def __init__(self, db: DBManager):
        super().__init__()
        self.db = db
        self.setWindowTitle("MM 관리 시스템")
        self.setMinimumSize(1000, 700)
        self.resize(1200, 800)
        self._current_year = datetime.date.today().year
        self._build_ui()

    def _build_ui(self):
        central = QWidget()
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(6, 6, 6, 6)
        main_layout.setSpacing(4)
        self.setCentralWidget(central)

        # ── 전역 연도 선택 바 ────────────────────────────────────
        year_bar = QHBoxLayout()
        year_bar.addWidget(QLabel("연도:"))
        self.year_combo = QComboBox()
        self.year_combo.setEditable(True)
        self.year_combo.setInsertPolicy(QComboBox.NoInsert)
        now = datetime.date.today()
        for y in range(now.year - 5, now.year + 6):
            self.year_combo.addItem(str(y), y)
        self.year_combo.setCurrentText(str(now.year))
        self.year_combo.lineEdit().setValidator(QIntValidator(2000, 2100))
        self.year_combo.setFixedWidth(90)
        year_bar.addWidget(self.year_combo)
        year_bar.addStretch()
        main_layout.addLayout(year_bar)

        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        year = self._current_year

        # ── 탭 1: 기준 정보 ─────────────────────────────────────
        base_widget = QWidget()
        base_layout = QHBoxLayout(base_widget)

        task_group = QGroupBox("과제 관리")
        tg_layout = QVBoxLayout(task_group)
        self.task_widget = TaskWidget(self.db, year=year)
        tg_layout.addWidget(self.task_widget)

        person_group = QGroupBox("인력 관리")
        pg_layout = QVBoxLayout(person_group)
        self.person_widget = PersonWidget(self.db, year=year)
        pg_layout.addWidget(self.person_widget)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(task_group)
        splitter.addWidget(person_group)
        splitter.setSizes([600, 400])
        base_layout.addWidget(splitter)

        self.tabs.addTab(base_widget, "기준 정보")

        # ── 탭 2: MM 계획 ────────────────────────────────────────
        self.plan_widget = PlanWidget(self.db, year=year)
        self.tabs.addTab(self.plan_widget, "MM 계획")

        # ── 탭 3: MM 집행 ────────────────────────────────────────
        self.exec_widget = ExecutionWidget(self.db, year=year)
        self.tabs.addTab(self.exec_widget, "MM 집행")

        # ── 탭 4: 현황 대시보드 ──────────────────────────────────
        self.dashboard_widget = DashboardWidget(self.db, year=year)
        self.tabs.addTab(self.dashboard_widget, "현황 대시보드")

        # 신호 연결
        self.task_widget.tasks_changed.connect(self._on_data_changed)
        self.person_widget.persons_changed.connect(self._on_data_changed)
        self.plan_widget.data_changed.connect(self._on_data_changed)
        self.exec_widget.data_changed.connect(self._on_data_changed)
        self.year_combo.currentIndexChanged.connect(self._on_year_changed)
        self.year_combo.lineEdit().editingFinished.connect(self._on_year_edited)
        self.tabs.currentChanged.connect(self._on_tab_changed)

    def _on_year_edited(self):
        text = self.year_combo.lineEdit().text().strip()
        if text.isdigit() and 2000 <= int(text) <= 2100:
            year = int(text)
            if self.year_combo.findText(text) == -1:
                self.year_combo.addItem(text, year)
            self.year_combo.setCurrentText(text)
            self._apply_year(year)

    def _on_year_changed(self):
        year = self.year_combo.currentData()
        if year is None:
            return
        self._current_year = year
        self._apply_year(year)

    def _apply_year(self, year: int):
        self._current_year = year
        self.task_widget.set_year(year)
        self.person_widget.set_year(year)
        self.plan_widget.set_year(year)
        self.exec_widget.set_year(year)
        self.dashboard_widget.set_year(year)

    def _on_data_changed(self):
        self.task_widget.refresh()
        self.person_widget.refresh()
        self.plan_widget.reload()
        self.exec_widget.reload()
        self.dashboard_widget.reload()

    def _on_tab_changed(self, index: int):
        widget = self.tabs.widget(index)
        if hasattr(widget, 'reload'):
            widget.reload()
        elif widget is self.tabs.widget(0):
            self.task_widget.refresh()
            self.person_widget.refresh()
