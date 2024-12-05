from app.tools.base_tool import BaseTool
from pydantic import Field

class ExampleTool(BaseTool):
    example_field: str = Field(..., description="An example field for the tool.")

    async def run(self) -> str:
        self._logger.info(f"Running ExampleTool with example_field: {self.example_field}")
        # Tool logic here
        return "ExampleTool completed successfully." 