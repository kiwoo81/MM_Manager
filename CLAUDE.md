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

## 빌드 방법 (macOS .app)
```bash
source .venv/bin/activate
python -m PyInstaller MM_Manager.spec --noconfirm
# 결과물: dist/MM_Manager.app
```
- Windows 실행 파일은 Windows 환경에서 별도 빌드 필요 (크로스 컴파일 불가)
- DB 파일(mm_manager.db)은 실행 파일 옆에 생성됨

## 프로젝트 구조
```
MM_Manager/
├── main.py                  # 진입점
├── MM_Manager.spec          # PyInstaller 빌드 설정
├── requirements.txt
├── database/
│   ├── db_manager.py        # SQLite CRUD
│   └── models.py            # Task, Person, MMPlan, MMExecution 데이터클래스
├── ui/
│   ├── main_window.py       # 메인 윈도우 (전역 연도 선택 + 탭 구조)
│   ├── task_widget.py       # 과제 관리
│   ├── person_widget.py     # 인력 관리
│   ├── plan_widget.py       # MM 계획 (매트릭스 테이블)
│   ├── execution_widget.py  # MM 집행
│   ├── dashboard_widget.py  # 현황 대시보드
│   └── mm_delegate.py       # MMTableWidget, MMDelegate, MMExecutionDelegate
└── logic/
    └── mm_calculator.py     # MM 검증/계산 로직
```

## 핵심 비즈니스 규칙
1. 동일인의 동일 월 전체 계획 MM 합 ≤ 1.0
2. 과제가 '착수' 상태일 때만 집행 MM 입력 가능
3. 집행 MM은 음수 허용 (조정 입력용)
4. 과제의 `total_mm`은 지역별 MM 합계로 자동 계산 (직접 입력 없음)
5. 과제·인력은 연도별로 독립 관리 (2025년 데이터와 2026년 데이터는 완전히 분리)
6. 인력별 `available_mm`: 기본값 12.0, 0.5 단위 입력 (Person 모델 필드)
7. MM 계획 잠금: plan_widget 전체 잠금 토글 (plan_locks 테이블, year PK)
8. MM 집행 월 잠금: 1월부터 순서대로만 잠금 가능, 역순으로만 해제 가능 (locked_months 테이블)

## 연도별 독립 아키텍처
- `tasks`, `persons` 테이블에 `year` 컬럼 존재
- `get_all_tasks(year)`, `get_all_persons(year)` 로 연도 필터링
- 전역 연도 선택기(main_window.py)가 모든 탭에 `set_year(year)` 전파
- 삭제(DELETE)는 해당 연도 데이터만 CASCADE 삭제 (타 연도 영향 없음)

## 알려진 이슈 / 주의사항

### PySide6 6.10.2 QDoubleSpinBox 크래시
`QTableWidget`의 cellWidget으로 `QDoubleSpinBox`를 사용하면 macOS ARM64에서
shiboken6 내부 재귀로 인해 세그폴트 발생.

**해결책**: cellWidget 대신 `QTableWidgetItem` 텍스트 입력 + `QStyledItemDelegate`로
`QIntValidator` 적용. (task_widget.py의 `_LocTableDelegate` 참고)

### MM 입력값
- loc_table의 MM 컬럼: 0 이상 정수만 허용 (`QIntValidator(0, 999999)`)
- plan 위젯: `MMDelegate` — 0.0~1.0, 소수점 1자리
- execution 위젯: `MMExecutionDelegate` — 음수 포함 실수, 소수점 1자리
- person dialog의 `available_mm`: `QDoubleSpinBox` 사용 (dialog 내 사용은 세그폴트 없음, cellWidget만 위험)

### 집행 셀 색상 규칙
- 일반(계획 있음): 흰 배경
- 계획 없는 집행 (편집 가능): `#f57f17` 황색
- 잠긴 월 + 계획 없는 집행: `#e65100` 진한 주황
- 잠긴 월 + 계획 있는 집행: `#b0bec5` 회색

### 집행 제안 버튼 (`_propose_execution`)
- 대상 월: 마지막 잠긴 월 + 1 (잠긴 월 없으면 1월)
- 조건: 착수 과제 + 과제 기간(`task.in_range`) 내 + 근무지 일치 + 미입력 + 잔여 MM > 0
- 계획 있는 과제 → 계획값 그대로 제안
- 계획 없거나 잔여 MM ≤ 0 → 잔여 MM가 가장 많은 과제에 1.0 배정
- 미리보기 다이얼로그 후 Yes 시 일괄 저장

### 잠금 해제 월 초기화 버튼 (`_clear_unlocked_months`)
- 잠기지 않은 모든 월의 집행 데이터를 DB에서 일괄 삭제
- `db.delete_executions_for_months(year, unlocked_months)` 호출
- 확인 다이얼로그 후 Yes 시 삭제

### 요약 라벨 색상 규칙 (task_widget, person_widget 공통)
- 근무지별 MM AND 총합 모두 일치 → `#e8f5e9` 초록
- 하나라도 불일치 → `#fff3e0` 주황
- 근무지 목록: 오름차순 정렬

### MMTableWidget 키보드 동작
- `Backspace` / `Delete`: 편집 가능 셀 값 즉시 삭제 후 해당 셀 선택 유지
- 방향키: 편집 확정 후 인접 셀로 이동 (`MMLineEdit.arrow_pressed` 시그널)
- 편집 불가 셀에서 문자 키 입력: 차단 (Qt 기본 검색 이동 방지)

## 코딩 컨벤션
- 언어: 주석 및 UI 텍스트는 한국어
- 함수명/변수명: snake_case
- 클래스명: PascalCase
- 새 파일 생성보다 기존 파일 수정 우선
- 불필요한 docstring/주석 추가 금지

## 답변 언어
한국어로 답해줄 것.
