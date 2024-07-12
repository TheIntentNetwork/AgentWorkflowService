# tests/test_session_manager.py

import pytest
from unittest.mock import patch, AsyncMock
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
logger.debug("Starting test_session_management.py")

@pytest.fixture
def kafka_service_mock():
    logger.info("Setting up kafka_service_mock")
    with patch('app.services.queue.kafka.KafkaService', new_callable=AsyncMock) as mock:
        yield mock


@pytest.fixture
def redis_service_mock():
    with patch('app.services.cache.redis.RedisService', new_callable=AsyncMock) as mock:
        yield mock

@pytest.fixture
def session_manager(kafka_service_mock, redis_service_mock):
    # Assuming a default constructor without Redis and Kafka dependencies
    from app.services.session.session import SessionManager
    return SessionManager.instance(name="session_manager", service_registry=None)

@pytest.mark.asyncio
async def test_start_session(session_manager, kafka_service_mock, redis_service_mock):
    session_id = "test-session-id"
    logger.debug(f"test_start_session: session_id = {session_id}")
    logger.info(f"Starting session with ID: {session_id}")

    # Act
    session = await session_manager.start_session(session_id)

    print("Session:", session)

    # Assert
    assert session.id == session_id

#@pytest.mark.asyncio
#async def test_end_session(session_manager, kafka_service_mock, redis_service_mock):
#    session_id = "test-session-id"#

#    # Set up the manager with an active session
#    session = await session_manager.start_session(session_id)
#    
#    kafka_service_mock.send_message = AsyncMock()
#    redis_service_mock.hset = AsyncMock()#

#    # End the session
#    await session_manager.end_session(session_id)#

#    # Verify
#    kafka_service_mock.send_message.assert_called_once_with('session_end', session_id)
#    redis_service_mock.hset.assert_called_once_with(f"session_{session_id}_state", session.state)
#    
#    with pytest.raises(KeyError):
#        session_manager.get_session(session_id)  # Verify that it has been ended and removed#

## Integration test:
#@pytest.mark.asyncio
#async def test_session_integration(session_manager, kafka_service_mock, redis_service_mock):
#    # Start a new session
#    new_session = await session_manager.start_session()
#    
#    # Mock returning the same session from Redis
#    redis_service_mock.get = AsyncMock(return_value=new_session.state)#

#    # Act on the session like a consumer would based on Kafka messages
#    # Simulate a pause
#    await new_session.handle_message(SessionMessage(MessageType.PAUSE_SESSION, new_session.id))
#    # Simulate a resume
#    await new_session.handle_message(SessionMessage(MessageType.RESUME_SESSION, new_session.id))
#    # Simulate an end
#    await new_session.handle_message(SessionMessage(MessageType.END_SESSION, new_session.id))#

#    # Check that the Kafka service received the published state changes
#    assert kafka_service_mock.produce_message.call_count == 3#

#    # End the session and verify it gets updated state from Redis
#    ended_state = await session_manager.end_session(new_session.id)
#    redis_service_mock.save.assert_called()
