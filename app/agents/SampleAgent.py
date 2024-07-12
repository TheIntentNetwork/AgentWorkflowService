"""Module for SampleAgent."""
import argparse
import asyncio
import logging
import sys
from app.models.agents import Agent
from app.services.completion.providers.oai.openai import OpenAIInterface
from app.tools.GenerateQuestionnaire import GenerateQuestionnaire
from app.tools.UserHistory import RetrieveUserHistory
from app.tools.RetrieveSimilarQuestions import RetrieveSimilarQuestions


class SampleAgent(Agent):
    """Sample agent class for demonstration purposes."""

    def __init__(self, **kwargs):
        if not kwargs:
            sys.exit(f"{self.__class__.__name__} requires at least 1 keyword argument.")
        # iterate through kwargs and print them
        for key, value in kwargs.items():
            logging.debug("kwargs: %s %s", key, value)
        # Initialize tools in kwargs if not present
        if 'tools' not in kwargs:
            kwargs['tools'] = []
        # Add required tools
        kwargs['tools'].extend([GenerateQuestionnaire, RetrieveUserHistory, RetrieveSimilarQuestions])
        self.llm_interface = None
        self.conversation_history = []
        instructions = kwargs.get('instructions', "")
        # Set instructions
        kwargs['instructions'] = (
            "You are an advanced AI agent equipped with specialized tools to assist users in creating questionnaires effectively. "
            "Your primary objective is to fulfill the user's requests by efficiently utilizing these tools. "
            "When creating a questionnaire, you will use the 'GenerateQuestionnaire' tool to create a questionnaire based on the user's requirements."
        ) + instructions

        # Initialize the parent class
        super().__init__(**kwargs)

    def generate_prompt(self, user_input: str) -> str:
        return f"User: {user_input}\nAgent: "

    def execute_tool(self, tool_name: str, tool_input: str) -> str:
        for tool in self.tools:
            if tool.__name__ == tool_name:
                return tool().run()
        raise ValueError(f"Tool {tool_name} not found.")
        for tool in self.tools:
            if tool.__name__ == tool_name:
                return tool().run(tool_input)
        raise ValueError(f"Tool {tool_name} not found.")

if __name__ == "__main__":
    # Parse the args
    parser = argparse.ArgumentParser(description="Sample Agent")
    parser.add_argument("--api-key", type=str, default="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", help="OpenAI API key")
    parser.add_argument("--stream", action="store_true", help="Stream the responses")
    args = parser.parse_args()

    agent = SampleAgent(**{"description": "Sample Agent"})
    llm_interface = OpenAIInterface(
        api_key=args.api_key,
        **{"stream": args.stream}
    )
    agent.set_llm_interface(llm=llm_interface)
    asyncio.run(agent.chat())

