from pydantic import BaseModel, Field
from typing import Dict, List
from app.tools.base_tool import BaseTool
from app.utilities.logger import get_logger

class Agent(BaseModel):
    """
    This class represents the agents involved in the workflow.
    """
    name: str = Field(..., description="The name of the agent.")
    description: str = Field(..., description="The description of the agent.")
    instructions: str = Field(..., description="The instructions for the agent including step by step instructions.")
    tools: List[str] = Field(..., description="The tools that the agent uses.")
    leader: bool = Field(..., description="Whether the agent is the leader of the group.")

class AssignAgents(BaseTool):
    """
    This class represents the AssignAgents tool which is used to create an AgentGroup to assign agents to a node. One agent in the group is the leader.
    The agents assigned to a node should provide the necessary information to complete the node including the actions and outputs.
    """

    node_id: str = Field(..., description="The ID of the node.")
    agents: List[Agent] = Field(..., description="The agents to assign to the node.")

    async def run(self) -> str:
        get_logger(self.__class__.__name__).info(f"Assigning agents {self.agents} to step {self.node_id}")
            
        
        if not self.caller_agent.context_info.context.get("assignees"):
            self.caller_agent.context_info.context["assignees"] = []
        if not self.caller_agent.context_info.context.get("assignees"):
            self.caller_agent.context_info.context["assignees"] = []

        self.caller_agent.context_info.context["assignees"] = self.agents
        
        return self.agents


        
        