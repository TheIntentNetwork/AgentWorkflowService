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
        self.config = config  # Add this line
        from containers import get_container
        
        from app.services.queue.kafka import KafkaService
        from app.services.cache.redis import RedisService
        
        self.logger.debug("Initializing SessionManager")
        self.redis: RedisService = get_container().redis()
        self.kafka: KafkaService = get_container().kafka()
        self.sessions: Dict[str, SessionContext] = {}
        self.context_manager: UserContextManager = get_container().context_manager()
        self.session_expiration = timedelta(seconds=config['session_timeout'])

    async def start(self):
        self.logger.info("Starting SessionManager")
        try:
            self.sessions = {}  # Initialize in-memory session storage
            await self.initialize_sessions()  # Load existing sessions from Redis
            # Start the cleanup task
            asyncio.create_task(self.periodic_cleanup())
            self.logger.info("SessionManager started successfully")
        except Exception as e:
            self.logger.error(f"Failed to start SessionManager: {str(e)}")
            raise

    async def shutdown(self):
        self.logger.info("Shutting down SessionManager")
        try:
            # Save all sessions to Redis before shutting down
            for session_id, session_context in self.sessions.items():
                await self.redis.client.hset('sessions', session_id, json.dumps(session_context.to_dict()))
            self.sessions.clear()  # Clear in-memory session storage
            self.logger.info("SessionManager shut down successfully")
        except Exception as e:
            self.logger.error(f"Error during SessionManager shutdown: {str(e)}")
            raise

    async def initialize_sessions(self):
        try:
            session_data = await self.redis.client.hgetall("sessions")
            for session_id, session_json in session_data.items():
                session_context = SessionContext.from_dict(json.loads(session_json))
                self.sessions[session_id] = session_context
            self.logger.info(f"Initialized {len(self.sessions)} sessions from Redis")
        except Exception as e:
            self.logger.error(f"Failed to initialize sessions: {str(e)}")
            raise

    async def periodic_cleanup(self):
        while True:
            await asyncio.sleep(self.config['session_cleanup_interval'])
            await self.cleanup_expired_sessions()

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
        current_time = asyncio.get_event_loop().time()
        expired_sessions = [
            session_id for session_id, session in self.sessions.items()
            if (current_time - session.last_accessed) > self.session_expiration.total_seconds()
        ]
        for session_id in expired_sessions:
            await self.end_session(session_id.split(':')[0], session_id)
        self.logger.info(f"Cleaned up {len(expired_sessions)} expired sessions")

