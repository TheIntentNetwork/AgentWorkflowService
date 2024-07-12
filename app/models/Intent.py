from pydantic import BaseModel

class Intent(BaseModel):
    name: str
    description: str

    def to_dict(self) -> dict:
        return self.dict()