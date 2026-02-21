from typing import Optional, Tuple
from database.db_manager import DBManager
from database.models import MMPlan, MMExecution

MM_LIMIT_PER_PERSON_MONTH = 1.0
TOLERANCE = 1e-9


class MMCalculator:
    def __init__(self, db: DBManager):
        self.db = db

    def validate_plan(
        self,
        person_id: int,
        task_id: int,
        year: int,
        month: int,
        new_mm: float,
    ) -> Tuple[bool, str]:
        """
        계획 MM 입력 유효성 검사.
        1) 동일인의 해당 월 전체 계획 MM 합 ≤ 1.0
        2) 과제의 전체 계획 MM 합 ≤ task.total_mm
        """
        # ① 인력 월 한도 검사
        other_person_total = self.db.get_person_month_plan_total(
            person_id, year, month, exclude_task_id=task_id
        )
        if other_person_total + new_mm > MM_LIMIT_PER_PERSON_MONTH + TOLERANCE:
            remaining = MM_LIMIT_PER_PERSON_MONTH - other_person_total
            return False, (
                f"월 투입 한도 초과: 해당 인력의 {year}년 {month}월 계획 합계가 "
                f"1.0 MM을 초과합니다.\n"
                f"현재 다른 과제 합계: {other_person_total:.1f} MM, "
                f"입력 가능 잔여: {max(0.0, remaining):.1f} MM"
            )

        # ② 과제 총 계획 MM 한도 검사
        task = self.db.get_task(task_id)
        if task and task.total_mm > 0:
            other_task_total = self.db.get_task_plan_total_excluding(
                task_id, person_id, year, month
            )
            if other_task_total + new_mm > task.total_mm + TOLERANCE:
                remaining = task.total_mm - other_task_total
                return False, (
                    f"과제 계획 MM 초과: 과제 '{task.name}'의 계획 총 MM "
                    f"{task.total_mm:.1f}을 초과합니다.\n"
                    f"현재 다른 인력/월 합계: {other_task_total:.1f} MM, "
                    f"입력 가능 잔여: {max(0.0, remaining):.1f} MM"
                )

        # ③ 근무지별 할당 MM 한도 검사
        person = self.db.get_person(person_id)
        if person and person.location:
            loc_mms = {lm.location: lm for lm in self.db.get_task_location_mms(task_id)}
            if person.location in loc_mms:
                allocated = loc_mms[person.location].allocated_mm
                other_loc_total = self.db.get_task_location_plan_total_excluding(
                    task_id, person.location, person_id, year, month
                )
                if other_loc_total + new_mm > allocated + TOLERANCE:
                    remaining = allocated - other_loc_total
                    task = task or self.db.get_task(task_id)
                    return False, (
                        f"근무지 MM 초과: '{person.location}' 근무지의 "
                        f"과제 '{task.name if task else ''}' 할당 MM {allocated:.1f}을 초과합니다.\n"
                        f"현재 합계: {other_loc_total:.1f} MM, "
                        f"입력 가능 잔여: {max(0.0, remaining):.1f} MM"
                    )

        return True, ""

    def validate_execution(
        self,
        task_id: int,
        person_id: int,
        year: int,
        month: int,
        new_mm: float,
    ) -> Tuple[bool, str]:
        """
        집행 MM 입력 유효성 검사.
        - 과제가 착수/완료 상태인지 확인
        - 음수 값은 허용 (조정 목적)
        - 과제의 전체 집행 합계가 계획 total_mm 초과 시 경고 (차단하지 않음)
        """
        from database.models import Task
        task = self.db.get_task(task_id)
        if task is None:
            return False, "존재하지 않는 과제입니다."

        if task.status == '미착수':
            return False, (
                f"과제 '{task.name}'이(가) 아직 착수되지 않았습니다.\n"
                "집행 MM은 착수 상태의 과제에만 입력할 수 있습니다."
            )

        # 근무지 불일치 검사
        person = self.db.get_person(person_id)
        loc_mms = self.db.get_task_location_mms(task_id)
        if loc_mms:
            task_locations = {lm.location for lm in loc_mms}
            person_loc = person.location if person else ""
            if not person_loc or person_loc not in task_locations:
                loc_str = " / ".join(sorted(task_locations))
                return False, (
                    f"근무지 불일치: 과제 '{task.name}'은(는) "
                    f"'{loc_str}' 근무지 인력만 집행할 수 있습니다."
                )

        return True, ""

    def get_execution_warning(self, task_id: int, new_mm: float,
                              year: int, month: int, person_id: int) -> str:
        """
        집행 후 과제 총 집행 MM이 계획 MM을 초과하면 경고 메시지 반환 (빈 문자열이면 정상).
        """
        task = self.db.get_task(task_id)
        if task is None:
            return ""

        existing_exec = self.db.get_execution(task_id, person_id, year, month)
        existing_mm = existing_exec.actual_mm if existing_exec else 0.0
        current_total = self.db.get_task_execution_total(task_id)
        new_total = current_total - existing_mm + new_mm

        if new_total > task.total_mm + TOLERANCE:
            return (
                f"주의: 과제 '{task.name}'의 전체 집행 합계 ({new_total:.2f} MM)가 "
                f"계획 MM ({task.total_mm:.2f} MM)을 초과합니다."
            )
        return ""

    def get_person_month_plan_summary(self, person_id: int, year: int, month: int) -> dict:
        """인력의 특정 월 계획 현황 반환."""
        total = self.db.get_person_month_plan_total(person_id, year, month)
        return {
            "total_planned": total,
            "remaining": MM_LIMIT_PER_PERSON_MONTH - total,
            "is_full": total >= MM_LIMIT_PER_PERSON_MONTH - TOLERANCE,
            "is_over": total > MM_LIMIT_PER_PERSON_MONTH + TOLERANCE,
        }
