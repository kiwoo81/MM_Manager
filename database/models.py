from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Task:
    id: Optional[int]
    name: str
    description: str
    total_mm: float
    status: str  # '대기', '착수', '완료'
    start_year: Optional[int] = None
    start_month: Optional[int] = None
    end_year: Optional[int] = None
    end_month: Optional[int] = None

    @staticmethod
    def statuses():
        return ['대기', '착수', '완료']

    def in_range(self, year: int, month: int) -> bool:
        """해당 년월이 과제 기간 내에 있으면 True. 기간 미설정 시 항상 True."""
        if self.start_year is None or self.end_year is None:
            return True
        start = (self.start_year, self.start_month or 1)
        end = (self.end_year, self.end_month or 12)
        return start <= (year, month) <= end


@dataclass
class Person:
    id: Optional[int]
    name: str
    department: str
    location: str = ""


@dataclass
class TaskLocationMM:
    id: Optional[int]
    task_id: int
    location: str
    allocated_mm: float


@dataclass
class MMPlan:
    id: Optional[int]
    task_id: int
    person_id: int
    year: int
    month: int
    planned_mm: float


@dataclass
class MMExecution:
    id: Optional[int]
    task_id: int
    person_id: int
    year: int
    month: int
    actual_mm: float
    note: str = ""
