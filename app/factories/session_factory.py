# app/factories/session_factory.py
from app.models import Task
from app.models.Event import Event
from app.models.Session import Session
from app.services.cache.redis import RedisService

class SessionFactory:
    @staticmethod
    async def create_session(session_id: str = None) -> Session:
        session = Session(session_id)
        return session

