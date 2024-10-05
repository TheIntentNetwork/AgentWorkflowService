# app/services/session.py
from datetime import timedelta
from enum import Enum, auto
import asyncio
import json
import logging
from typing import Any, Dict, List, Union
import uuid
from app.config.settings import SessionSettings
from app.models.Context import SessionContext
from app.interfaces import IService
from app.models.Session import Session
from app.services.context.user_context_manager import UserContextManager



class SessionManager(IService):

    def __init__(self, name: str, config: SessionSettings, **kwargs):
        super().__init__(name=name, config=config, **kwargs)
        from containers import get_container
        
        from app.services.queue.kafka import KafkaService
        from app.services.cache.redis import RedisService
        
        self.logger.debug("Initializing SessionManager")
        self.redis: RedisService = get_container().redis()
        self.kafka: KafkaService = get_container().kafka()
        self.sessions: Dict[str, SessionContext] = {}
        self.context_manager: UserContextManager = get_container().user_context_manager
        self.session_expiration = timedelta(hours=1)  # Default expiration time

    async def start(self):
        self.logger.info("Starting SessionManager")
        await self.redis.connect()
        await self.kafka.start()
        self.sessions = {}  # Initialize in-memory session storage
        await self.initialize_sessions()  # Load existing sessions from Redis
        self.logger.info("SessionManager started")

    async def shutdown(self):
        self.logger.info("Shutting down SessionManager")
        self.sessions.clear()  # Clear in-memory session storage
        await self.redis.disconnect()
        await self.kafka.shutdown()
        self.logger.info("SessionManager shut down")
    
    async def initialize_sessions(self):
        try:
            session_ids = await self.redis.client.hgetall("sessions")
            for session_id in session_ids:
                session_context = SessionContext.from_dict(self.redis.client.hget(session_id))
                self.sessions[session_id] = session_context
        except Exception as e:
            self.logger.error(f"Failed to initialize sessions: {e}")
            raise

    async def start_session_with_context(self, session: Any, context: Any):
        await session.start(context)

        # Publish a message to Kafka topic to signal the session start
        await self.kafka.send_message('session_start', session.id)
        
        session_context = SessionContext(session_id=session.id, state=session.state, contexts=[str(context)])
        self.sessions[session.id] = session_context

        # Save session state to Redis and in-memory store
        await self.context_manager.add_record(
            user_id=session.user_id,
            session_id=session.id,
            record_id='session_context',
            record_data=session_context.to_dict(),
            expiration=self.session_expiration
        )

        return session
    
    async def start_session(self, session: Session):
        session_context = SessionContext(session_id=session.id, state=session.state)
        self.sessions[session.id] = session_context

        # Save session state to Redis
        await self.redis.client.hset('sessions', session.id, json.dumps(session_context.to_dict()))
        await session.start()

        # Publish a message to Kafka topic to signal the session start
        await self.kafka.send_message('session_start', session.id)

        return session
    
    async def get_session(self, user_id: str, session_id: str):
        # Try to get session from in-memory store first
        session = await self.context_manager.get_record(user_id, session_id, 'session_context')
        if session is None:
            # If not in memory, try to get from Redis
            # Implement Redis fetching logic here
            pass
        
        if session:
            return SessionContext.from_dict(session)
        return None

    async def end_session(self, user_id: str, session_id: str):
        session = await self.get_session(user_id, session_id)
        if not session:
            raise KeyError("Session not found.")
            
        # Publish a message to Kafka topic to signal the session end
        await self.kafka.produce_message('session_end', session_id)

        # Remove session from in-memory store and Redis
        await self.context_manager.clear_session_records(user_id, session_id)
        # Implement Redis deletion logic here

    async def add_context(self, user_id: str, session_id: str, context: Any):
        session = await self.get_session(user_id, session_id)
        if not session:
            raise KeyError("Session not found.")

        session.contexts.append(context)
        
        # Update session in both in-memory store and Redis
        await self.context_manager.add_record(
            user_id=user_id,
            session_id=session_id,
            record_id='session_context',
            record_data=session.to_dict(),
            expiration=self.session_expiration
        )
        # Implement Redis update logic here

    async def cleanup_expired_sessions(self):
        await self.context_manager.remove_expired_records()

