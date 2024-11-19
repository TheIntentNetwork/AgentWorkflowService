from pydantic import Field
from app.tools.base_tool import BaseTool

class ValidationTool(BaseTool):
    content_to_validate: str = Field(..., description="The content to be validated.")
    is_valid: bool = Field(..., description="Whether the content is valid or not.")
    feedback: str = Field(..., description="Feedback on the validation result.")

    async def run(self) -> dict:
        validation_result = {
            "is_valid": self.is_valid,
            "feedback": self.feedback
        }
        
        self._caller_agent.context_info.context["validation_result"] = validation_result
        
        return validation_result