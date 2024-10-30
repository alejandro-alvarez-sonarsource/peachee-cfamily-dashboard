from datetime import datetime
from typing import Dict, List


class Dashboard:
    def __init__(self, projects: List[str], dates: List[datetime], table: List[Dict]):
        self.projects = projects
        self.dates = dates
        self.table = table

    def __len__(self) -> int:
        return len(self.table)
