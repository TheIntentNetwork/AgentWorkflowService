# app/services/session.py
from enum import Enum, auto
import asyncio
import json
import logging
from typing import Any, Dict, List, Union
import uuid
from app.models.Context import SessionContext
from app.interfaces import IService
from app.models.Session import Session
from app.services.context.user_context_manager import UserContextManager
from app.utilities import get_logger

logger = get_logger('SessionManager')

class SessionManager(IService):

    def __init__(self, name: str, service_registry: any, **kwargs):
        self.name = name
        self.service_registry = service_registry
        from app.services.queue.kafka import KafkaService
        from app.services.cache.redis import RedisService
        from app.services import ServiceRegistry
        logger.debug("Initializing SessionManager")
        self.redis: RedisService = ServiceRegistry.instance().get("redis")
        self.kafka: KafkaService = ServiceRegistry.instance().get("kafka")
        self.sessions: Dict[str, SessionContext] = {}
    
    async def initialize_sessions(self):
        try:
            session_ids = await self.redis.client.hgetall("sessions")
            for session_id in session_ids:
                session_context = SessionContext.from_dict(self.redis.client.hget(session_id))
                self.sessions[session_id] = session_context
        except Exception as e:
            logger.error(f"Failed to initialize sessions: {e}")
            raise

    async def start_session_with_context(self, session: Session, context: Any):
        await session.start(context)

        # Publish a message to Kafka topic to signal the session start
        await self.kafka.send_message('session_start', session.id)
        session_context = SessionContext(session_id=session.id, state=session.state, contexts=[str(context)])
        self.sessions[session.id] = session_context

        # Create the intent agent to handle the session activities
        # After the intent agent returns the workflows, the steps within the workflows should already have
        # registered the steps and the steps should have subscribed to the appropriate redis channels for
        # dependencies that are needed to run the steps. Any steps without dependencies should be run immediately
        # and the results should be returned to the caller.
        
        # Save session state to Redis
        await self.redis.client.hset('sessions', session.id, json.dumps(session_context.to_dict()))
        return session
    
    async def start_session(self, session: Session):
        session_context = SessionContext(session_id=session.id, state=session.state)
        self.sessions[session.id] = session_context

        # Save session state to Redis
        await self.redis.hset('sessions', session.id, session_context.to_dict())
        await session.start()

        # Publish a message to Kafka topic to signal the session start
        await self.kafka.send_message('session_start', session.id)

        return session

    async def add_context(self, session_id: str, user_id: str):
        if session_id not in self.sessions:
            raise KeyError("Session not found.")

        user_context_manager = UserContextManager()
        await user_context_manager.load_user_context(user_id, session_id)

        session_context = self.sessions.get(session_id, None)
        if session_context:
            session_context.contexts.append(f"user_context:{session_id}")
            await self.redis.hset('sessions', session_id, session_context.to_dict())
        else:
            raise KeyError("Session context not found.")
    
    def get_session(self, session_id: str):
        # return self.sessions.get(session_id)  # Removed direct task management within sessions
        # Implement retrieval from a centralized store or through messaging
        pass

    async def end_session(self, session_id):
        """End a session by its ID and publish a message to Kafka."""
        if session_id not in self.sessions:  # Removed direct task management within sessions
             raise KeyError("Session not found.")
            
        # Publish a message to Kafka topic to signal the session end
        await self.kafka.produce_message('session_end', session_id)

        # Update the session state in Redis
        await self.redis.save(session_id, "ENDED")

    async def add_context(self, session_id: str, context: Any):
        if session_id not in self.sessions:
            raise KeyError("Session not found.")

        if not self.sessions[session_id]:
            #retrieve the session from Redis
            session_context = await self.redis.hget('sessions', session_id)
            self.sessions[session_id] = SessionContext.from_dict(session_context)

        session_context = self.sessions[session_id]
        session_context.contexts.append(context)
        await self.redis.hset('sessions', session_id, session_context.to_dict())

if __name__ == "__main__":
    from app.services.orchestrators.startup import StartupOrchestrator
    from app.services import ServiceRegistry
    startup = StartupOrchestrator()
    asyncio.run(startup.run())
    session_manager = ServiceRegistry.instance().get("session_manager")
    asyncio.run(session_manager.initialize_sessions())
    print(session_manager.sessions)

