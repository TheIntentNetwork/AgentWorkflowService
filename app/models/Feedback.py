from typing import Dict
from pydantic import BaseModel


class Feedback(BaseModel):
    score: float
    metadata: Dict[str, str]
    summary: str
    analysis: str

    def to_dict(self) -> dict:
        return self.dict()