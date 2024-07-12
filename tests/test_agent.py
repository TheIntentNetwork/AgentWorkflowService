import pytest
from unittest.mock import MagicMock
from app.tools.base_tool import BaseTool
from app.tools.GenerateQuestionnaire import GenerateQuestionnaire
from app.tools.UserHistory import RetrieveUserHistory
from app.tools.RetrieveSimilarQuestions import RetrieveSimilarQuestions
from app.models.agents import Agent
from app.agents.SampleAgent import SampleAgent
from app.interfaces.llm import LLMInterface

import logging

logger = logging.getLogger(__name__)

class MockLLMInterface(LLMInterface):
    logger.info("MockLLMInterface initialized")
    def set_system_message(self, message: str):
        pass
    def set_system_message(self, message: str):
        pass
    def __init__(self):
        pass

    def initialize(self):
        pass

    def get_completion(self, prompt: str, **kwargs) -> str:
        return f"Mock completion for prompt: {prompt}"

    async def get_completion_async(self, prompt: str, **kwargs):
        yield f"Mock async completion for prompt: {prompt}"

    def execute_tool(self, tool_call, agent):
        pass

def test_sample_agent_initialization():
    agent = SampleAgent(name="Test Agent", description="A test agent", tools=[])
    logger.info("SampleAgent initialized for test_sample_agent_initialization")
    assert agent.name == "Test Agent"
    assert agent.description == "A test agent"
    assert agent.tools == [GenerateQuestionnaire, RetrieveUserHistory, RetrieveSimilarQuestions]
    assert agent.llm_interface is None
    assert agent.conversation_history == []

def test_sample_agent_set_llm_interface():
    agent = SampleAgent(name="Test Agent", description="A test agent", tools=[])
    llm_interface = MockLLMInterface()
    agent.set_llm_interface(llm_interface)
    assert agent.llm_interface == llm_interface

def test_sample_agent_generate_prompt():
    agent = SampleAgent(name="Test Agent", description="A test agent", tools=[])
    user_input = "Hello, how are you?"
    expected_prompt = "User: Hello, how are you?\nAgent: "
    assert agent.generate_prompt(user_input) == expected_prompt

@pytest.mark.asyncio
async def test_sample_agent_get_completion():
    agent = SampleAgent(name="Test Agent", description="A test agent", tools=[])
    llm_interface_mock = MagicMock(spec=LLMInterface)
    llm_interface_mock.get_completion_async = MagicMock(return_value=MockLLMInterface().get_completion_async("Hello, how are you?"))
    llm_interface_mock.set_system_message = MagicMock()
    agent.set_llm_interface(llm_interface_mock)
    agent.llm = llm_interface_mock  # Ensure llm_interface is set
    llm_interface_mock.set_system_message = MagicMock()
    agent.set_llm_interface(llm_interface_mock)

    user_input = "Hello, how are you?"
    completion = ""
    completion_generator = await agent.get_completion(user_input)
    async for result in completion_generator:
        completion = result

    assert completion == "Mock async completion for prompt: Hello, how are you?"
    llm_interface_mock.get_completion_async.assert_called_once_with("Hello, how are you?", agent)

def test_sample_agent_execute_tool():
    class MockTool(BaseTool):
        def run(self):
            return "Mock tool output"

    agent = SampleAgent(name="Test Agent", description="A test agent", tools=[MockTool])

    tool_name = "MockTool"
    tool_input = "Some input"
    output = agent.execute_tool(tool_name, tool_input)

    assert output == "Mock tool output"
