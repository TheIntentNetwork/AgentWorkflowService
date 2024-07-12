from abc import abstractmethod
from pydantic import BaseModel, Field
from app.models.StepOutput import StepOutput
from typing import Any
from dataclasses import dataclass

class BaseDependency(BaseModel):
    context_key: str
    property_name: Any

    @abstractmethod
    def update_subscription(self, message: dict):
        pass

    async def on_dependency_satisfied(self, message: dict, dependent_step_id: str):
        """
        Callback method to be overridden by subclasses.
        This method is called when the dependency condition is met.
        """
        #await KafkaService().instance().send_message("DEPENDENCY_SATISFIED", {"message": message, "dependent_step_id": dependent_step_id})

    async def subscribe_to_dependency(self, step_output_key: str, dependent_step_id: str):
        """
        Subscribe to a Redis channel based on the step output key.
        """
        channel = f"dependency_{step_output_key}"
        #await RedisService.instance().subscribe(channel, lambda message: self.on_message_received(message, dependent_step_id))

    async def on_message_received(self, message: dict, dependent_step_id: str):
        """
        Handle messages received from Redis. Check if the dependency condition is met and call the callback.
        """
        await self.on_dependency_satisfied(message, dependent_step_id)
        self.process(message)

    def to_dict(self) -> dict:
        return self.dict()

class OneToOneDependency(BaseDependency):
    """
    The OneToOneDependency class represents a one-to-one dependency between two steps meaning that each output of the first step is processed by the second step.
    """

    def update_subscription(self, message: dict):
        # Do something every time a message is received
        pass

    def to_dict(self) -> dict:
        return self.dict()

class OneRunDependency(BaseDependency):
    """
    The OneRunDependency class represents a one-run dependency between two steps meaning that the second step processes the output of the first step only once.
    """

    def update_subscription(self, message: dict):
        # Do something only once then unsubscribe
        self.unsubscribe()
    
    def to_dict(self) -> dict:
        return self.dict()

@dataclass
class Dependency(BaseDependency):
    output: Any
