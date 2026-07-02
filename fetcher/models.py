from dataclasses import dataclass
from datetime import datetime

@dataclass
class Transaction:
    merchant: str
    amount: float
    timestamp: datetime

    @property
    def is_expense(self) -> bool:
        return self.amount < 0

    @property
    def abs_amount(self) -> float:
        return abs(self.amount)
