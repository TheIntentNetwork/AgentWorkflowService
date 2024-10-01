"""Module for the IntakeAgent class, responsible for handling intake processes."""

import asyncio
import sys

from app.models.agents import Agent
from app.logging_config import configure_logger
from app.services.discovery import ServiceRegistry
from app.services.cache import RedisService


class IntakeAgent(Agent):
    """
    IntakeAgent class for handling intake processes.
    Inherits from the base Agent class.
    """

    def __init__(self, **kwargs):
        self.redis_service: RedisService = ServiceRegistry.instance().get(name="redis")
        self.logger = configure_logger(self.__class__.__name__)
        self.logger.debug("Initializing IntakeAgent with kwargs: %s", kwargs)

        # Initialize the parent class
        super().__init__(**kwargs)
        self.session_id = kwargs.get('session_id', '')

        self.queue = asyncio.Queue()

    async def async_init(self):
        """Asynchronous initialization method."""
        pass

    @classmethod
    async def create(cls, **kwargs):
        """
        Class method to create and initialize an IntakeAgent instance.

        Args:
            **kwargs: Keyword arguments for agent initialization.

        Returns:
            IntakeAgent: An initialized IntakeAgent instance.
        """
        instance = cls(**kwargs)
        await instance.async_init()
        await instance.set_instructions(**kwargs)
        return instance

    async def set_tools(self):
        """
        Set the tools for the IntakeAgent.
        This method is required to override the abstract method in the parent class.
        """
        # Implement the logic to set tools for IntakeAgent
        pass

    async def set_instructions(self, **kwargs):
        """
        Set instructions for the IntakeAgent.
        This method should be implemented if it's called in the create method.
        """
        # Implement the logic to set instructions for IntakeAgent
        pass

    def exit_program(self):
        """Exit the program using sys.exit()."""
        sys.exit()
