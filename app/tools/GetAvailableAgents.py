import json
import logging
from app.tools.base_tool import BaseTool



class GetAvailableAgents(BaseTool):

    def run(self) -> str:
        return f"{self.caller_agent._contexts['available_agents']}"


