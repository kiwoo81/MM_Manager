import sys
import os

# 프로젝트 루트를 sys.path에 추가 (패키지 임포트 보장)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from database.db_manager import DBManager
from ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("MM 관리 시스템")
    app.setStyle("Fusion")

    db = DBManager()
    window = MainWindow(db)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
