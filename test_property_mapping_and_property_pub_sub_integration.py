"""
Issue: Pydantic warnings and proper closing of Redis and Kafka connections.

Analysis:
1. Pydantic warnings indicate incorrect usage of SkipValidation and renaming of orm_mode to from_attributes.
2. Redis and Kafka connections are not being closed properly, possibly due to the event loop being closed prematurely.

Solutions:
1. Correct the usage of SkipValidation in the Pydantic model.
2. Rename orm_mode to from_attributes in the Pydantic configuration.
3. Ensure that the event loop is not closed before Redis and Kafka connections are properly closed by adding a delay before closing the event loop.

Tried Solutions:
1. Added a delay before closing the event loop.
"""

import asyncio
import logging
import signal
import sys
import os

from app.services.session.session import SessionManager
from app.models.ContextInfo import ContextInfo

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.models.Node import Node, NodeStatus
from app.services.events.event_manager import EventManager
from app.services.discovery.service_registry import ServiceRegistry
from app.services.cache.redis import RedisService
from app.services.queue.kafka import KafkaService
from app.services.orchestrators.lifecycle.Execution import ExecutionService
from dotenv import load_dotenv


# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Use environment variables
BOOTSTRAP_SERVERS = os.getenv('BOOTSTRAP_SERVERS', 'localhost:29092')
TOPICS = os.getenv('TOPICS', 'AGENCY_WORKFLOWS').split(',')
CONSUMER_GROUP = os.getenv('CONSUMER_GROUP', 'AGENCY_WORKFLOWS_CONSUMER')
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379')

async def setup_services():
    service_registry = ServiceRegistry.instance()
    
    service_registry.register("context_manager", ContextManager)
    bootstrap_servers = os.getenv("BOOTSTRAP_SERVERS").split(",")
    topics = os.getenv("TOPICS").split(",")
    consumer_group = os.getenv("CONSUMER_GROUP")
    redis_url = os.getenv("REDIS_URL")
    
    service_registry.register("kafka", KafkaService, **{"bootstrap_servers": bootstrap_servers, "topics": topics, "consumer_group": consumer_group})
    service_registry.register("redis", RedisService, **{"redis_url": redis_url})
    service_registry.register("event_manager", EventManager)
    service_registry.register("session_manager", SessionManager)
    
    
    from app.services.orchestrators.lifecycle.Execution import ExecutionService
    service_registry.register("execution_service", ExecutionService)

    # Start event manager
    event_manager: EventManager = service_registry.get("event_manager")
    await event_manager.start()

    return service_registry

# Remove the execution_service from Node creation
async def create_node(node_id, description, tools, assignees, status=NodeStatus.created):
    try:
        node = await Node.create(
            id=node_id,
            description=description,
            tools=tools,
            assignees=assignees,
            context_info={},  # Add an empty context_info
            name=f"Node {node_id}",  # Add a name
            type="step",  # Use a valid type from the allowed options
            status=status if status else "created"  # Add status if provided, default to "pending"
        )
        print(f"Created node: {node}")
        
        # Simulate sending a message to Kafka
        kafka_service = ServiceRegistry.instance().get("kafka")
        await kafka_service.send_message('node_update', node.json())
        
        return node
    except Exception as e:
        print(f"Error creating node: {e}")
        return None

async def cleanup_services(service_registry):
    services_to_close = ["event_manager", "kafka", "redis", "execution_service"]
    for service_name in services_to_close:
        service = service_registry.get(service_name)
        if service:
            try:
                if hasattr(service, 'close') and callable(service.close):
                    await asyncio.wait_for(service.close(), timeout=10)
                elif hasattr(service, 'stop') and callable(service.stop):
                    await asyncio.wait_for(service.stop(), timeout=10)
                else:
                    logging.warning(f"{service_name} does not have a close or stop method")
            except asyncio.TimeoutError:
                logging.error(f"Timeout while closing {service_name}")
            except asyncio.CancelledError:
                logging.warning(f"Closing of {service_name} was cancelled")
            except Exception as e:
                logging.error(f"Error closing {service_name}: {str(e)}")
        await asyncio.sleep(0.5)  # Add a small delay between closing services

    # Ensure Redis connection is closed
    redis_service = service_registry.get("redis")
    if redis_service:
        try:
            await redis_service.close()
        except Exception as e:
            logging.error(f"Error closing Redis connection: {e}")

    # Ensure Kafka connection is closed
    kafka_service = service_registry.get("kafka")
    if kafka_service:
        try:
            await kafka_service.close()
        except Exception as e:
            logging.error(f"Error closing Kafka connection: {e}")
        finally:
            kafka_service = None  # Ensure the reference is removed
            await asyncio.sleep(2)  # Increase the delay to ensure proper closure

async def main():
    service_registry = None
    try:
        # Step 1: Setup services
        service_registry = await setup_services()
        logging.info("Step 1: Services set up successfully")

        # Step 2: Create initial nodes with status field
        node1 = await create_node(
            "node1",
            "Assigning an agent",
            ["AssignAgents"],
            ["UniverseAgent"],
            status="pending",
            context_info=ContextInfo(
                input_description="Assigning an agent to handle the task",
                action_summary="Agent is assigned based on availability and skill set",
                outcome_description="Agent assigned successfully",
                feedback=["Ensure the agent is assigned correctly based on the task requirements"],
                output={"assigned_agent": "{agent_id}"}
            )
        )
        node2 = await create_node(
            "node2",
            "Executing assigned task",
            ["ExecuteTask"],
            ["UniverseAgent"],
            status="pending",
            context_info=ContextInfo(
                input_description="Executing the task assigned to the agent",
                action_summary="Task execution involves processing the assigned work and reporting status",
                outcome_description="Task executed successfully",
                feedback=["Ensure the task is executed correctly and status is reported"],
                output={"execution_status": "completed"}
            )
        )

        # Create a validation node that validates the output of the node
        validation_node = await create_node(
            "validation_node",
            "Validating node output",
            ["ValidateOutput"],
            ["UniverseAgent"],
            status="pending",
            context_info=ContextInfo(
                input_description="Validating the output of the node",
                action_summary="Ensure the output meets the required criteria and standards",
                outcome_description="Output validated successfully",
                feedback=["Ensure the output is correct and meets the required criteria"],
                output={"validation_status": "success"}
            )
        )

        # Define a lambda function to filter nodes with status "completed"
        filter_func = lambda node: node.status == "completed"

        # Apply the filter function to the list of nodes
        if validation_node:
            filtered_nodes = list(filter(filter_func, [node1, node2, validation_node]))
        else:
            logging.error("Failed to create validation node")
            return

        if filtered_nodes:
            logging.info("Step 2: Initial nodes created and filtered")
        else:
            logging.error("Step 2: Failed to create and filter initial nodes")
            return

        # Step 3: Create dependent nodes using tasks
        tasks = [
            create_node(
                "node3",
                "Browsing user metadata",
                ["GetUserContext"],
                ["BrowsingAgent"],
                context_info=ContextInfo(
                    input_description="Retrieve and display user metadata for further processing",
                    action_summary="Browsing user metadata",
                    outcome_description="User metadata retrieved and displayed",
                    feedback=["Ensure the metadata is retrieved correctly"],
                    output={"user_metadata": "{metadata}"}
                )
            ),
            create_node(
                "node4",
                "Pulling user metadata",
                ["GetUserContext"],
                ["BrowsingAgent"],
                context_info=ContextInfo(
                    input_description="Extract user metadata from the database for analysis",
                    action_summary="Pulling user metadata",
                    outcome_description="User metadata extracted successfully",
                    feedback=["Ensure the metadata is extracted correctly"],
                    output={"user_metadata": "{metadata}"}
                )
            ),
            create_node(
                "node5",
                "Processing user data",
                ["ProcessData"],
                ["ProcessAgent"],
                context_info=ContextInfo(
                    input_description="Process the extracted user data to generate insights",
                    action_summary="Processing user data",
                    outcome_description="User data processed successfully",
                    feedback=["Ensure the data is processed correctly"],
                    output={"processed_data": "{data}"}
                )
            )
        ]
        node3, node4, node5 = await asyncio.gather(*tasks)
        if node3 and node4 and node5:
            logging.info("Step 3: Dependent nodes created")
        else:
            logging.error("Step 3: Failed to create dependent nodes")
            return

        # Step 4: Run tests
        logging.info("Step 4: Running tests")
        # Add your test logic here
        # For example:
        # await run_tests()

        # Wait for a short time to allow for any asynchronous operations to complete
        logging.info("Waiting for 5 seconds to allow for test completion...")
        await asyncio.sleep(5)

        logging.info("Tests completed. Exiting...")

    except asyncio.CancelledError:
        logging.info("Received cancellation signal. Shutting down...")
    except KeyboardInterrupt:
        logging.info("Keyboard interrupt received. Shutting down...")
    except Exception as e:
        logging.exception(f"An unexpected error occurred: {e}")
    finally:
        if service_registry:
            logging.info("Starting cleanup process")
            await cleanup_services(service_registry)
        
        # Ensure the event loop is still running for the final cleanup
        loop = asyncio.get_event_loop()
        if not loop.is_closed():
            # Cancel all remaining tasks
            tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            # Add a delay before closing the event loop
            await asyncio.sleep(5)
        else:
            logging.warning("Event loop is already closed")

def handle_sigint():
    for task in asyncio.all_tasks():
        task.cancel()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    loop = asyncio.get_event_loop()
    
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        print("Keyboard interrupt received. Shutting down...")
    finally:
        try:
            # Run cleanup in the event loop
            loop.run_until_complete(cleanup_services(ServiceRegistry.instance()))
        except Exception as e:
            logging.error(f"Error during cleanup: {e}")
        
        # Cancel all remaining tasks
        tasks = asyncio.all_tasks(loop=loop)
        for task in tasks:
            task.cancel()
        
        # Wait for all tasks to be cancelled
        loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=True))
        
        # Close the event loop
        loop.close()
