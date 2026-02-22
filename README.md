# MM 관리 시스템

R&D 프로젝트의 인력 투입 공수(MM, Man/Month)를 계획하고 집행 실적을 관리하는 데스크톱 애플리케이션입니다.

## 주요 기능

### 기준 정보 관리
- **과제 관리**: 과제 등록/수정/삭제, 착수 상태 변경, 근무지별 MM 배분 설정
- **인력 관리**: 인력 등록/수정/삭제, 근무지 지정

### MM 계획
- 인력 × 과제 매트릭스 테이블로 월별 계획 MM 입력
- 동일인 월 합계 1.0 초과 시 빨간색 경고 표시
- 근무지별 과제 배분 MM 대비 계획 잔여량 표시

### MM 집행
- 착수된 과제에 한해 월별 실투입 MM 입력
- 음수 입력 허용 (조정 입력)
- 월 잠금 기능 (🔒): 확정된 월의 집행 데이터 보호
- 하단 근무지별 계획/집행 합계 비교

### 현황 대시보드
- 과제별 계획/집행/잔여 MM 현황 (근무지별 구분)
- 인력별 월별 계획/집행 비교 (1월~12월)

### 연도별 독립 관리
- 상단 연도 선택기로 전체 탭 동기 전환
- 연도별로 과제·인력·계획·집행 데이터 완전 독립

## 설치 및 실행

### 요구사항
- Python 3.11+
- PySide6

### 개발 환경 실행
```bash
# 가상환경 생성 및 패키지 설치
python -m venv .venv
source .venv/bin/activate        # macOS/Linux
.venv\Scripts\activate           # Windows

pip install -r requirements.txt

# 실행
python main.py
```

### 빌드된 실행 파일 사용
- macOS: `dist/MM_Manager.app` 더블클릭
- 최초 실행 시 macOS Gatekeeper 경고가 뜨면 **Control+클릭 → 열기** 선택

> **DB 파일**: 실행 파일 위치와 동일한 디렉토리에 `mm_manager.db`로 자동 생성됩니다.

## 빌드 (macOS .app 생성)

```bash
source .venv/bin/activate
pip install pyinstaller
python -m PyInstaller MM_Manager.spec --noconfirm
# 결과물: dist/MM_Manager.app (약 97MB)
```

> Windows `.exe`는 Windows 환경에서 동일한 방법으로 빌드합니다.

## 기술 스택

| 항목 | 내용 |
|------|------|
| 언어 | Python 3.11+ |
| GUI | PySide6 (Qt for Python) |
| DB | SQLite (내장 sqlite3) |
| 패키징 | PyInstaller |

## 사용법

### 처음 시작하기
1. **기준 정보** 탭에서 과제와 인력을 등록합니다.
   - 과제: 이름, 기간, 근무지별 MM 배분 입력
   - 인력: 이름, 부서, 근무지 입력
2. **MM 계획** 탭에서 월별 계획 MM을 입력합니다.
   - 셀 선택 후 숫자 입력 (0.0~1.0, 소수점 1자리)
   - Backspace/Delete로 삭제, 방향키로 셀 이동
3. 과제를 **착수** 상태로 변경한 후 **MM 집행** 탭에서 실투입 MM을 입력합니다.
4. **현황 대시보드** 탭에서 계획 대비 집행 현황을 확인합니다.

### 연도 변경
- 화면 상단 연도 입력란에서 연도를 선택하거나 직접 입력(2000~2100)
- 모든 탭이 동시에 해당 연도 데이터로 전환됩니다.

## 프로젝트 구조

```
MM_Manager/
├── main.py                  # 진입점
├── MM_Manager.spec          # PyInstaller 빌드 설정
├── requirements.txt
├── database/
│   ├── db_manager.py        # SQLite CRUD
│   └── models.py            # 데이터 모델 (Task, Person, MMPlan, MMExecution)
├── ui/
│   ├── main_window.py       # 메인 윈도우
│   ├── task_widget.py       # 과제 관리 화면
│   ├── person_widget.py     # 인력 관리 화면
│   ├── plan_widget.py       # MM 계획 입력 화면
│   ├── execution_widget.py  # MM 집행 입력 화면
│   ├── dashboard_widget.py  # 현황 대시보드 화면
│   └── mm_delegate.py       # 테이블 입력 위젯/델리게이트
└── logic/
    └── mm_calculator.py     # MM 검증/계산 로직
```
