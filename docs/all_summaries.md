# Agent Workflow Service - All Summaries

## Main Application (main.py)
- Entry point for the agent workflow service
- Sets up FastAPI application with CORS middleware
- Initializes services (context managers, Kafka, Redis, Worker, Session manager, Event manager, Dependency service)
- Provides profiling and debugging routes (/profile, /memory_profile, /memory_snapshot, /gc_stats, /debug_links, /object_type_info)
- Configures middleware for process time tracking
- Handles graceful shutdown of services

## Seed Context Index (seed_context_index.py)
- Creates test data for intent and workflow indexes
- Stores data in Redis and creates indexes in Redisearch
- Generates embeddings for test data using Hugging Face text vectorizer
- Provides utility functions for text preprocessing and embedding generation
- Includes asynchronous functions for creating indexes and querying the vector database

## Docker Configuration (Dockerfile)
- Creates a Docker image for the agent workflow service
- Uses selenium/standalone-chrome:latest as the base image
- Installs Python 3.10 and necessary dependencies
- Sets up TCP keepalive settings and exposes ports 5000 and 7900
- Configures the container to run the application using Uvicorn

## Agent Model (agent.md)
- Represents the core entity in the agent workflow system
- Attributes: id, name, description, capabilities, state
- Methods: perform_task, update_state, get_capabilities
- Managed by the Agency class and interacts with Task objects
- Extensible for creating specialized agent types

## Agency Model (agency.md)
- Central management and coordination entity for the agent workflow system
- Attributes: id, name, description, agents, tasks
- Methods: register_agent, assign_task, monitor_tasks, get_agent_status
- Manages Agent instances and coordinates task assignments
- Interacts with Agent and Task objects to manage the workflow

## Task Model (task.md)
- Represents a unit of work within the agent workflow system
- Attributes: id, name, description, nodes, dependencies, status, events
- Methods: add_node, add_dependency, update_status, add_event, get_status, get_dependencies
- Created and managed by the Agency class
- Contains Node objects and interacts with Agent objects during execution

## Node Model (node.md)
- Represents an individual step or action within a task
- Attributes: id, name, description, status, events, dependencies
- Methods: update_status, add_event, add_dependency, get_status, get_dependencies
- Building blocks of tasks within the agent workflow system
- Allows for fine-grained control and monitoring of task execution

## Overall Architecture
- Microservices architecture using FastAPI, Redis, and Kafka
- Containerized deployment using Docker
- Includes various services for specific functionalities (Worker, EventManager, etc.)
- Provides debugging and profiling tools for development and optimization

This document provides an overview of the key components and functionality of the Agent Workflow Service. It will be updated as more components are documented.

## Dependency Model (dependency.md)
- Represents relationships and dependencies between nodes in the workflow
- Base class: BaseDependency with attributes context_key and property_name
- Subclasses: OneToOneDependency, OneRunDependency, and Dependency
- Methods for updating subscriptions, handling dependency satisfaction, and converting to dictionary
- Used to manage data flow and execution order in the workflow

## NodeStatus Enum (node_status.md)
- Represents various states of a node during its lifecycle
- Includes states from creation to completion or failure
- Used to track and manage node progress throughout the workflow
- Utilized by Node model, workflow engine, and monitoring tools
- Provides standardized status values for consistent state management
