import asyncio
from typing import Literal, Optional, List
from collections import deque
from contextlib import contextmanager

from openai.types.beta import AssistantToolChoice
from app.models.agents.Agent import Agent
from app.models.thread import Thread
from app.models.User import User

class ThreadAsync(Thread):
    def __init__(self, agent: Literal[Agent, User], recipient_agent: Agent):
        super().__init__(agent, recipient_agent)
        self.message_queue = deque()
        self.queue_lock = asyncio.Lock()
        self.processing = False

    @contextmanager
    def message_operation(self):
        self.send_message_in_progress = True
        try:
            yield
        finally:
            self.send_message_in_progress = False

    async def process_queue(self):
        if self.processing:
            return
        
        self.processing = True
        while self.message_queue:
            message_data = self.message_queue.popleft()
            await self._process_message(message_data)
        self.processing = False

    async def _process_message(self, message_data):
        with self.message_operation():
            try:
                output = await super().get_completion(**message_data)
                return f"{self.recipient_agent.name}'s Response: '{output}'"
            except Exception as e:
                return f"Error processing message: {str(e)}"

    async def get_completion_async(self,
                                   message: str,
                                   message_files: List[str] = None,
                                   attachments: Optional[List[dict]] = None,
                                   recipient_agent=None,
                                   additional_instructions: str = None,
                                   tool_choice: AssistantToolChoice = None):
        message_data = {
            "message": message,
            "message_files": message_files,
            "attachments": attachments,
            "recipient_agent": recipient_agent,
            "additional_instructions": additional_instructions,
            "tool_choice": tool_choice
        }

        async with self.queue_lock:
            self.message_queue.append(message_data)
        
        asyncio.create_task(self.process_queue())
        
        return "System Notification: 'Task has been queued. You can check the status later using the 'GetResponse' tool.'"

    async def check_status(self):
        if self.processing:
            return "System Notification: 'Task is still in progress. Please check again later.'"
        
        if self.message_queue:
            return f"System Notification: 'There are {len(self.message_queue)} tasks waiting in the queue.'"
        
        run = await self.get_last_run()
        if not run:
            return "System Notification: 'No tasks are currently in progress or queued.'"

        if run.status in ['queued', 'in_progress', 'requires_action']:
            return "System Notification: 'Task is not completed yet. Please check again later.'"

        if run.status == "failed":
            return f"System Notification: 'Agent run failed with error: {run.last_error.message}. You may send another message.'"

        messages = await self.client.beta.threads.messages.list(
            thread_id=self.id,
            order="desc",
        )

        return f"{self.recipient_agent.name}'s Response: '{messages.data[0].content[0].text.value}'"

    async def get_last_run(self):
        if not self.thread:
            await self.init_thread()

        runs = await self.client.beta.threads.runs.list(
            thread_id=self.thread.id,
            order="desc",
        )

        if len(runs.data) == 0:
            return None

        return runs.data[0]
