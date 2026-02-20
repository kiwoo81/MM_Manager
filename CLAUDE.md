# MM 관리 시스템 - Claude Code 가이드

## 프로젝트 개요
R&D 프로젝트의 인력 투입 공수(MM, Man/Month)를 계획하고 집행 실적을 관리하는 데스크톱 앱.
단일 사용자용 로컬 애플리케이션 (Windows/macOS).

## 기술 스택
- Python 3.11+
- PySide6 6.10.2 (Qt for Python)
- SQLite (내장 sqlite3)
- PyInstaller (패키징)

## Python 실행 방법
**항상 venv를 사용할 것.**
```bash
# macOS
/Users/kiwoo/Claude\ Projects/MM_Manager/.venv/bin/python main.py

# 또는
source .venv/bin/activate && python main.py
```

## 프로젝트 구조
```
MM_Manager/
├── main.py                  # 진입점
├── database/
│   ├── db_manager.py        # SQLite CRUD
│   └── models.py            # Task, Person, MMPlan, MMExecution 데이터클래스
├── ui/
│   ├── main_window.py       # 메인 윈도우 (탭 구조)
│   ├── task_widget.py       # 과제 관리
│   ├── person_widget.py     # 인력 관리
│   ├── plan_widget.py       # MM 계획 (매트릭스 테이블)
│   ├── execution_widget.py  # MM 집행
│   └── dashboard_widget.py  # 현황 대시보드
└── logic/
    └── mm_calculator.py     # MM 검증/계산 로직
```

## 핵심 비즈니스 규칙
1. 동일인의 동일 월 전체 계획 MM 합 ≤ 1.0
2. 과제가 '착수' 상태일 때만 집행 MM 입력 가능
3. 집행 MM은 음수 허용 (조정 입력용)
4. 과제의 `total_mm`은 지역별 MM 합계로 자동 계산 (직접 입력 없음)

## 알려진 이슈 / 주의사항

### PySide6 6.10.2 QDoubleSpinBox 크래시
`QTableWidget`의 cellWidget으로 `QDoubleSpinBox`를 사용하면 macOS ARM64에서
shiboken6 내부 재귀로 인해 세그폴트 발생.

**해결책**: cellWidget 대신 `QTableWidgetItem` 텍스트 입력 + `QStyledItemDelegate`로
`QIntValidator` 적용. (task_widget.py의 `_LocTableDelegate` 참고)

### MM 입력값
- loc_table의 MM 컬럼: 0 이상 정수만 허용 (`QIntValidator(0, 999999)`)
- plan/execution 위젯: `mm_delegate.py`의 `MMDelegate` 사용

## 코딩 컨벤션
- 언어: 주석 및 UI 텍스트는 한국어
- 함수명/변수명: snake_case
- 클래스명: PascalCase
- 새 파일 생성보다 기존 파일 수정 우선
- 불필요한 docstring/주석 추가 금지

## 답변 언어
한국어로 답해줄 것.
