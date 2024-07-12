from pydantic import BaseModel


class StepOutput(BaseModel):
    step_id: str
    output_key: str
    output_value: str

    def key(self) -> str:
        return f"{self.step_id}_{self.output_key}"

    def to_dict(self) -> dict:
        return self.dict()