from pydantic import BaseModel


class Summary(BaseModel):
    totalSolved: int = 0
    totalActiveDays: int = 0
