from datetime import datetime
from typing import Dict, List


class Dashboard:
    def __init__(self, projects: List[str], dates: List[datetime], table: List[Dict]):
        self.projects = projects
        self.dates = dates
        self.table = table
        self.date_health = self._date_health()
        self.project_health = self._project_health()

    def __len__(self) -> int:
        return len(self.table)

    def _date_health(self) -> Dict[datetime, int]:
        health = dict.fromkeys(self.dates, None)
        for date, row in zip(self.dates, self.table):
            p = sum(task["status"] == "COMPLETED" for task in row.values()) / len(row)
            p *= 100
            health[date] = int(p)
        return health

    def _project_health(self) -> Dict[str, int]:
        health = dict.fromkeys(self.projects, None)
        for project in self.projects:
            p = sum(
                task["status"] == "COMPLETED" for row in self.table for task in row.values() if task["name"] == project
            ) / len(self.table)
            p *= 100
            health[project] = int(p)
        return health
