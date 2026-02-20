from PySide6.QtWidgets import (
    QMainWindow, QTabWidget, QWidget, QVBoxLayout,
    QHBoxLayout, QTabBar, QSplitter, QGroupBox
)
from PySide6.QtCore import Qt
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
        self._build_ui()

    def _build_ui(self):
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        # ── 탭 1: 기준 정보 ────────────────────────────────────
        base_widget = QWidget()
        base_layout = QHBoxLayout(base_widget)

        task_group = QGroupBox("과제 관리")
        tg_layout = QVBoxLayout(task_group)
        self.task_widget = TaskWidget(self.db)
        tg_layout.addWidget(self.task_widget)

        person_group = QGroupBox("인력 관리")
        pg_layout = QVBoxLayout(person_group)
        self.person_widget = PersonWidget(self.db)
        pg_layout.addWidget(self.person_widget)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(task_group)
        splitter.addWidget(person_group)
        splitter.setSizes([600, 400])
        base_layout.addWidget(splitter)

        self.tabs.addTab(base_widget, "기준 정보")

        # ── 탭 2: MM 계획 ──────────────────────────────────────
        self.plan_widget = PlanWidget(self.db)
        self.tabs.addTab(self.plan_widget, "MM 계획")

        # ── 탭 3: MM 집행 ──────────────────────────────────────
        self.exec_widget = ExecutionWidget(self.db)
        self.tabs.addTab(self.exec_widget, "MM 집행")

        # ── 탭 4: 현황 대시보드 ────────────────────────────────
        self.dashboard_widget = DashboardWidget(self.db)
        self.tabs.addTab(self.dashboard_widget, "현황 대시보드")

        # 데이터 변경 시 연계 갱신
        self.task_widget.tasks_changed.connect(self._on_data_changed)
        self.person_widget.persons_changed.connect(self._on_data_changed)
        self.plan_widget.data_changed.connect(self._on_data_changed)
        self.exec_widget.data_changed.connect(self._on_data_changed)

        self.tabs.currentChanged.connect(self._on_tab_changed)

    def _on_data_changed(self):
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
