from app.models.agents.Agent import Agent
from app.tools.ValidationTool import ValidationTool

class ValidatorAgent(Agent):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def set_tools(self):
        self.tools.extend([ValidationTool])