import sqlite3
import os
import datetime
from typing import List, Optional
from .models import Task, Person, MMPlan, MMExecution, TaskLocationMM


def get_db_path() -> str:
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_dir, "mm_manager.db")


class DBManager:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or get_db_path()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_db(self):
        current_year = datetime.date.today().year
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    year INTEGER NOT NULL DEFAULT 0,
                    name TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    total_mm REAL NOT NULL DEFAULT 0.0,
                    status TEXT NOT NULL DEFAULT '미착수',
                    start_year INTEGER,
                    start_month INTEGER,
                    end_year INTEGER,
                    end_month INTEGER,
                    is_active INTEGER NOT NULL DEFAULT 1
                );

                CREATE TABLE IF NOT EXISTS persons (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    year INTEGER NOT NULL DEFAULT 0,
                    name TEXT NOT NULL,
                    department TEXT DEFAULT '',
                    location TEXT DEFAULT '',
                    is_active INTEGER NOT NULL DEFAULT 1
                );

                CREATE TABLE IF NOT EXISTS mm_plan (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
                    person_id INTEGER NOT NULL REFERENCES persons(id) ON DELETE CASCADE,
                    year INTEGER NOT NULL,
                    month INTEGER NOT NULL,
                    planned_mm REAL NOT NULL DEFAULT 0.0,
                    UNIQUE(task_id, person_id, year, month)
                );

                CREATE TABLE IF NOT EXISTS mm_execution (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
                    person_id INTEGER NOT NULL REFERENCES persons(id) ON DELETE CASCADE,
                    year INTEGER NOT NULL,
                    month INTEGER NOT NULL,
                    actual_mm REAL NOT NULL DEFAULT 0.0,
                    note TEXT DEFAULT '',
                    UNIQUE(task_id, person_id, year, month)
                );

                CREATE TABLE IF NOT EXISTS task_location_mm (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
                    location TEXT NOT NULL,
                    allocated_mm REAL NOT NULL DEFAULT 0.0,
                    UNIQUE(task_id, location)
                );

                CREATE TABLE IF NOT EXISTS execution_month_locks (
                    year INTEGER NOT NULL,
                    month INTEGER NOT NULL,
                    PRIMARY KEY (year, month)
                );

                CREATE TABLE IF NOT EXISTS plan_locks (
                    year INTEGER PRIMARY KEY
                );
            """)
            # tasks 테이블 마이그레이션
            existing_cols = {row[1] for row in conn.execute("PRAGMA table_info(tasks)").fetchall()}
            for col in ('start_year', 'start_month', 'end_year', 'end_month'):
                if col not in existing_cols:
                    conn.execute(f"ALTER TABLE tasks ADD COLUMN {col} INTEGER")
            if 'is_active' not in existing_cols:
                conn.execute("ALTER TABLE tasks ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1")
            if 'year' not in existing_cols:
                conn.execute(f"ALTER TABLE tasks ADD COLUMN year INTEGER NOT NULL DEFAULT {current_year}")
            # persons 테이블 마이그레이션
            existing_person_cols = {row[1] for row in conn.execute("PRAGMA table_info(persons)").fetchall()}
            if 'location' not in existing_person_cols:
                conn.execute("ALTER TABLE persons ADD COLUMN location TEXT DEFAULT ''")
            if 'is_active' not in existing_person_cols:
                conn.execute("ALTER TABLE persons ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1")
            if 'year' not in existing_person_cols:
                conn.execute(f"ALTER TABLE persons ADD COLUMN year INTEGER NOT NULL DEFAULT {current_year}")
            if 'available_mm' not in existing_person_cols:
                conn.execute("ALTER TABLE persons ADD COLUMN available_mm REAL NOT NULL DEFAULT 12.0")
            # status 마이그레이션: '대기' → '미착수', '완료' → '착수'
            conn.execute("UPDATE tasks SET status='미착수' WHERE status='대기'")
            conn.execute("UPDATE tasks SET status='착수' WHERE status='완료'")

    # ─── Tasks ────────────────────────────────────────────────────────────────

    def get_all_tasks(self, year: int = None) -> List[Task]:
        with self._connect() as conn:
            if year is not None:
                rows = conn.execute("SELECT * FROM tasks WHERE year=? ORDER BY id", (year,)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM tasks ORDER BY id").fetchall()
            return [Task(**dict(r)) for r in rows]

    def get_task(self, task_id: int) -> Optional[Task]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
            return Task(**dict(row)) if row else None

    def add_task(self, task: Task) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO tasks (year, name, description, total_mm, status, "
                "start_year, start_month, end_year, end_month) VALUES (?,?,?,?,?,?,?,?,?)",
                (task.year, task.name, task.description, task.total_mm, task.status,
                 task.start_year, task.start_month, task.end_year, task.end_month)
            )
            return cur.lastrowid

    def update_task(self, task: Task):
        with self._connect() as conn:
            conn.execute(
                "UPDATE tasks SET name=?, description=?, total_mm=?, status=?, "
                "start_year=?, start_month=?, end_year=?, end_month=? WHERE id=?",
                (task.name, task.description, task.total_mm, task.status,
                 task.start_year, task.start_month, task.end_year, task.end_month,
                 task.id)
            )

    def delete_task(self, task_id: int):
        with self._connect() as conn:
            conn.execute("DELETE FROM tasks WHERE id=?", (task_id,))

    # ─── Persons ──────────────────────────────────────────────────────────────

    def get_all_persons(self, year: int = None) -> List[Person]:
        with self._connect() as conn:
            if year is not None:
                rows = conn.execute("SELECT * FROM persons WHERE year=? ORDER BY id", (year,)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM persons ORDER BY id").fetchall()
            return [Person(**dict(r)) for r in rows]

    def get_person(self, person_id: int) -> Optional[Person]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM persons WHERE id=?", (person_id,)).fetchone()
            return Person(**dict(row)) if row else None

    def add_person(self, person: Person) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO persons (year, name, department, location, available_mm) VALUES (?,?,?,?,?)",
                (person.year, person.name, person.department, person.location, person.available_mm)
            )
            return cur.lastrowid

    def update_person(self, person: Person):
        with self._connect() as conn:
            conn.execute(
                "UPDATE persons SET name=?, department=?, location=?, available_mm=? WHERE id=?",
                (person.name, person.department, person.location, person.available_mm, person.id)
            )

    def delete_person(self, person_id: int):
        with self._connect() as conn:
            conn.execute("DELETE FROM persons WHERE id=?", (person_id,))

    # ─── MM Plan ──────────────────────────────────────────────────────────────

    def get_plans_by_year(self, year: int) -> List[MMPlan]:
        """연도별 전체 MM 계획 일괄 조회 (12회 개별 호출 대체)."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM mm_plan WHERE year=?", (year,)
            ).fetchall()
            return [MMPlan(**dict(r)) for r in rows]

    def get_plans_by_month(self, year: int, month: int) -> List[MMPlan]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM mm_plan WHERE year=? AND month=?",
                (year, month)
            ).fetchall()
            return [MMPlan(**dict(r)) for r in rows]

    def get_plan(self, task_id: int, person_id: int, year: int, month: int) -> Optional[MMPlan]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM mm_plan WHERE task_id=? AND person_id=? AND year=? AND month=?",
                (task_id, person_id, year, month)
            ).fetchone()
            return MMPlan(**dict(row)) if row else None

    def upsert_plan(self, plan: MMPlan):
        with self._connect() as conn:
            conn.execute("""
                INSERT INTO mm_plan (task_id, person_id, year, month, planned_mm)
                VALUES (?,?,?,?,?)
                ON CONFLICT(task_id, person_id, year, month)
                DO UPDATE SET planned_mm=excluded.planned_mm
            """, (plan.task_id, plan.person_id, plan.year, plan.month, plan.planned_mm))

    def delete_all_plans_for_year(self, year: int) -> int:
        """특정 연도의 모든 MM 계획 삭제."""
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM mm_plan WHERE year=?", (year,))
            return cur.rowcount

    def delete_plan(self, task_id: int, person_id: int, year: int, month: int):
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM mm_plan WHERE task_id=? AND person_id=? AND year=? AND month=?",
                (task_id, person_id, year, month)
            )

    def get_task_plan_total_excluding(self, task_id: int,
                                      person_id: int, year: int, month: int) -> float:
        """과제의 전체 계획 MM 합계 (특정 셀 제외)."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COALESCE(SUM(planned_mm),0) FROM mm_plan "
                "WHERE task_id=? AND NOT (person_id=? AND year=? AND month=?)",
                (task_id, person_id, year, month)
            ).fetchone()
            return row[0]

    def get_person_month_plan_total(self, person_id: int, year: int, month: int,
                                    exclude_task_id: Optional[int] = None) -> float:
        with self._connect() as conn:
            if exclude_task_id is not None:
                row = conn.execute(
                    "SELECT COALESCE(SUM(planned_mm),0) FROM mm_plan "
                    "WHERE person_id=? AND year=? AND month=? AND task_id!=?",
                    (person_id, year, month, exclude_task_id)
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT COALESCE(SUM(planned_mm),0) FROM mm_plan "
                    "WHERE person_id=? AND year=? AND month=?",
                    (person_id, year, month)
                ).fetchone()
            return row[0]

    # ─── MM Execution ─────────────────────────────────────────────────────────

    def get_executions_by_year(self, year: int) -> List[MMExecution]:
        """연도별 전체 MM 집행 일괄 조회 (12회 개별 호출 대체)."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM mm_execution WHERE year=?", (year,)
            ).fetchall()
            return [MMExecution(**dict(r)) for r in rows]

    def get_executions_by_month(self, year: int, month: int) -> List[MMExecution]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM mm_execution WHERE year=? AND month=?",
                (year, month)
            ).fetchall()
            return [MMExecution(**dict(r)) for r in rows]

    def get_execution(self, task_id: int, person_id: int, year: int, month: int) -> Optional[MMExecution]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM mm_execution WHERE task_id=? AND person_id=? AND year=? AND month=?",
                (task_id, person_id, year, month)
            ).fetchone()
            return MMExecution(**dict(row)) if row else None

    def upsert_execution(self, execution: MMExecution):
        with self._connect() as conn:
            conn.execute("""
                INSERT INTO mm_execution (task_id, person_id, year, month, actual_mm, note)
                VALUES (?,?,?,?,?,?)
                ON CONFLICT(task_id, person_id, year, month)
                DO UPDATE SET actual_mm=excluded.actual_mm, note=excluded.note
            """, (execution.task_id, execution.person_id, execution.year,
                  execution.month, execution.actual_mm, execution.note))

    def delete_execution(self, task_id: int, person_id: int, year: int, month: int):
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM mm_execution WHERE task_id=? AND person_id=? AND year=? AND month=?",
                (task_id, person_id, year, month)
            )

    def get_task_execution_total(self, task_id: int) -> float:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COALESCE(SUM(actual_mm),0) FROM mm_execution WHERE task_id=?",
                (task_id,)
            ).fetchone()
            return row[0]

    def get_task_execution_totals_by_location(self, task_id: int) -> dict:
        """과제의 근무지별 집행 MM 합계. {location: total_mm}"""
        with self._connect() as conn:
            rows = conn.execute("""
                SELECT COALESCE(per.location, '') as location,
                       COALESCE(SUM(e.actual_mm), 0) as total
                FROM mm_execution e
                JOIN persons per ON e.person_id = per.id
                WHERE e.task_id = ?
                GROUP BY per.location
            """, (task_id,)).fetchall()
            return {r[0]: r[1] for r in rows}

    def get_task_plan_total(self, task_id: int) -> float:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COALESCE(SUM(planned_mm),0) FROM mm_plan WHERE task_id=?",
                (task_id,)
            ).fetchone()
            return row[0]

    # ─── Task Location MM ─────────────────────────────────────────────────────

    def get_all_task_location_mms_bulk(self, task_ids: list) -> dict:
        """task_ids 목록에 대한 근무지별 할당 MM 일괄 조회. {task_id: {location: allocated_mm}}"""
        if not task_ids:
            return {}
        placeholders = ",".join("?" * len(task_ids))
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT task_id, location, allocated_mm FROM task_location_mm "
                f"WHERE task_id IN ({placeholders}) ORDER BY id",
                task_ids
            ).fetchall()
        result: dict = {}
        for r in rows:
            result.setdefault(r[0], {})[r[1]] = r[2]
        return result

    def get_all_task_location_plan_totals_for_tasks(self, task_ids: list) -> dict:
        """task_ids의 {(task_id, location): total_planned_mm} 일괄 조회."""
        if not task_ids:
            return {}
        placeholders = ",".join("?" * len(task_ids))
        with self._connect() as conn:
            rows = conn.execute(f"""
                SELECT p.task_id, per.location, COALESCE(SUM(p.planned_mm), 0)
                FROM mm_plan p
                JOIN persons per ON per.id = p.person_id
                WHERE p.task_id IN ({placeholders}) AND per.location != ''
                GROUP BY p.task_id, per.location
            """, task_ids).fetchall()
        return {(r[0], r[1]): r[2] for r in rows}

    def get_all_task_plan_totals_for_tasks(self, task_ids: list) -> dict:
        """{task_id: total_planned_mm} 일괄 조회."""
        if not task_ids:
            return {}
        placeholders = ",".join("?" * len(task_ids))
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT task_id, COALESCE(SUM(planned_mm), 0) FROM mm_plan "
                f"WHERE task_id IN ({placeholders}) GROUP BY task_id",
                task_ids
            ).fetchall()
        return {r[0]: r[1] for r in rows}

    def get_task_location_mms(self, task_id: int) -> List[TaskLocationMM]:
        """과제의 근무지별 할당 MM 목록."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM task_location_mm WHERE task_id=? ORDER BY id",
                (task_id,)
            ).fetchall()
            return [TaskLocationMM(**dict(r)) for r in rows]

    def upsert_task_location_mm(self, task_id: int, location: str, allocated_mm: float):
        with self._connect() as conn:
            conn.execute("""
                INSERT INTO task_location_mm (task_id, location, allocated_mm)
                VALUES (?,?,?)
                ON CONFLICT(task_id, location)
                DO UPDATE SET allocated_mm=excluded.allocated_mm
            """, (task_id, location, allocated_mm))

    def delete_task_location_mm(self, task_id: int, location: str):
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM task_location_mm WHERE task_id=? AND location=?",
                (task_id, location)
            )

    def delete_location_mismatched_plans(self, task_id: int = None, person_id: int = None) -> int:
        """근무지 불일치 계획 MM 삭제. task_id/person_id로 범위 제한 가능."""
        extra = ""
        params = []
        if task_id is not None:
            extra += " AND p.task_id = ?"
            params.append(task_id)
        if person_id is not None:
            extra += " AND p.person_id = ?"
            params.append(person_id)
        with self._connect() as conn:
            cur = conn.execute(f"""
                DELETE FROM mm_plan
                WHERE id IN (
                    SELECT p.id
                    FROM mm_plan p
                    JOIN persons per ON per.id = p.person_id
                    WHERE p.task_id IN (SELECT DISTINCT task_id FROM task_location_mm)
                      AND (
                          COALESCE(per.location, '') = ''
                          OR per.location NOT IN (
                              SELECT location FROM task_location_mm WHERE task_id = p.task_id
                          )
                      )
                      {extra}
                )
            """, params)
            return cur.rowcount

    def replace_task_location_mms(self, task_id: int, loc_list: list):
        """과제의 근무지별 할당 MM 전체 교체. loc_list: [(location, allocated_mm), ...]"""
        with self._connect() as conn:
            conn.execute("DELETE FROM task_location_mm WHERE task_id=?", (task_id,))
            for location, allocated_mm in loc_list:
                if location.strip() and allocated_mm > 0:
                    conn.execute(
                        "INSERT INTO task_location_mm (task_id, location, allocated_mm) VALUES (?,?,?)",
                        (task_id, location.strip(), allocated_mm)
                    )

    def get_task_location_plan_total_excluding(
        self, task_id: int, location: str,
        person_id: int, year: int, month: int
    ) -> float:
        """과제+근무지 기준 전체 계획 MM 합계 (특정 셀 제외)."""
        with self._connect() as conn:
            row = conn.execute("""
                SELECT COALESCE(SUM(p.planned_mm), 0)
                FROM mm_plan p
                JOIN persons per ON per.id = p.person_id
                WHERE p.task_id = ?
                  AND per.location = ?
                  AND NOT (p.person_id = ? AND p.year = ? AND p.month = ?)
            """, (task_id, location, person_id, year, month)).fetchone()
            return row[0]

    def get_task_location_plan_total(self, task_id: int, location: str) -> float:
        """과제+근무지 기준 전체 계획 MM 합계."""
        with self._connect() as conn:
            row = conn.execute("""
                SELECT COALESCE(SUM(p.planned_mm), 0)
                FROM mm_plan p
                JOIN persons per ON per.id = p.person_id
                WHERE p.task_id = ? AND per.location = ?
            """, (task_id, location)).fetchone()
            return row[0]

    def get_all_location_plan_totals(self, year: int = None) -> dict:
        """근무지별 전체 계획 MM 합계. {location: total_planned_mm}"""
        with self._connect() as conn:
            if year is not None:
                rows = conn.execute("""
                    SELECT per.location, COALESCE(SUM(p.planned_mm), 0)
                    FROM mm_plan p
                    JOIN persons per ON per.id = p.person_id
                    JOIN tasks t ON t.id = p.task_id
                    WHERE t.year = ? AND per.location != ''
                    GROUP BY per.location
                """, (year,)).fetchall()
            else:
                rows = conn.execute("""
                    SELECT per.location, COALESCE(SUM(p.planned_mm), 0)
                    FROM mm_plan p
                    JOIN persons per ON per.id = p.person_id
                    WHERE per.location != ''
                    GROUP BY per.location
                """).fetchall()
            return {r[0]: r[1] for r in rows}

    # ─── Execution Month Locks ────────────────────────────────────────────────

    def get_locked_months(self, year: int) -> set:
        """해당 연도에서 잠긴 월 집합 반환."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT month FROM execution_month_locks WHERE year=?", (year,)
            ).fetchall()
            return {r[0] for r in rows}

    def set_month_lock(self, year: int, month: int, locked: bool):
        """월 잠금 설정/해제."""
        with self._connect() as conn:
            if locked:
                conn.execute(
                    "INSERT OR IGNORE INTO execution_month_locks (year, month) VALUES (?,?)",
                    (year, month)
                )
            else:
                conn.execute(
                    "DELETE FROM execution_month_locks WHERE year=? AND month=?",
                    (year, month)
                )

    # ─── Plan Locks ───────────────────────────────────────────────────────────

    def get_plan_locked(self, year: int) -> bool:
        """해당 연도 MM 계획 잠금 여부."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM plan_locks WHERE year=?", (year,)
            ).fetchone()
            return row is not None

    def set_plan_locked(self, year: int, locked: bool):
        """MM 계획 잠금 설정/해제."""
        with self._connect() as conn:
            if locked:
                conn.execute("INSERT OR IGNORE INTO plan_locks (year) VALUES (?)", (year,))
            else:
                conn.execute("DELETE FROM plan_locks WHERE year=?", (year,))

    def get_all_locations(self) -> List[str]:
        """persons 및 task_location_mm 테이블의 고유 근무지 목록."""
        with self._connect() as conn:
            rows = conn.execute("""
                SELECT DISTINCT location FROM (
                    SELECT location FROM persons WHERE location != ''
                    UNION
                    SELECT location FROM task_location_mm WHERE location != ''
                ) ORDER BY location
            """).fetchall()
            return [r[0] for r in rows]

    def get_all_departments(self) -> List[str]:
        """persons 테이블에 등록된 고유 부서 목록."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT DISTINCT department FROM persons WHERE department != '' ORDER BY department"
            ).fetchall()
            return [r[0] for r in rows]
