# Dynamic Prompting with Semantic Lookup

## Overview

This document provides a detailed explanation of the code snippet from `AgentWorkflowService/app/models/Task.py`. The code demonstrates how to dynamically prompt and assign agents to tasks using semantic lookup.

## Step-by-Step Instructions

1. **Import Required Modules**
    - The code begins by importing necessary modules and configuring the logger.
    ```python
    from app.services.discovery.service_registry import ServiceRegistry
    from app.services.cache.redis import RedisService
    from app.factories.agent_factory import AgentFactory
    from redisvl.query.filter import Tag
    from app.logging_config import configure_logger

    logger = configure_logger('Task')
    ```

2. **Log Task Assignment**
    - Log the start of the agent assignment process.
    ```python
    logger.info(f"Assigning agents to the task: {self.description}")
    ```

3. **Retrieve Potential Agents**
    - Retrieve potential agents, tools, and nodes from the context using Redis.
    ```python
    redis: RedisService = ServiceRegistry.instance().get('redis')
    
    filter = Tag("type") == "agent"
    results = await redis.async_search_index(self.description, "action_summary_vector", "context", 6, ["item"], filter)
    sorted_agents = sorted(results, key=lambda x: x['vector_distance'], reverse=True)
    sorted_agents = [json.loads(agent['item']) for agent in sorted_agents]
    ```

4. **Create Detailed Prompt**
    - Create a detailed prompt for the Universe Agent to assess the task and determine the appropriate assignment.
    ```python
    prompt = f"""
    Assess the task first to determine if a node should be created or if the scope can be completed by a single agent:
    1.) Review the example nodes to determine if the scope is feasible for a single agent or if multiple agents are required.
    2.) If there are example nodes that provide an example of this scope of work being broken into steps, this indicates that a node is required and you should use your tools to assign the UniverseAgent with the ability to CreateNode.
    3.) Be sure to review the feedback and incorporate any learnings from previous nodes to ensure that the task is completed successfully.
    4.) If there is evidence that multiple agents are required, you must assign the UniverseAgent (CreateNodes) with the ability to create several nodes for the scope of the work.
    5.) If the scope is feasible for a single agent, you must assign a single agent but not the UniverseAgent.
    6.) If there are multiple tools necessary that are not typically used together to accomplish all tasks, you must assign the UniverseAgent with the ability to CreateNodes and AssignAgents.
    
    Rules: 
    - You must call the AssignAgents tool to assign the most appropriate agents for the task to complete the task successfully.
    - Only assign 1 agent.
    
    Task Description: {self.description}
    Input Description: {self.context_info.input_description}
    Action Summary: {self.context_info.action_summary}
    Outcome Description: {self.context_info.outcome_description}
    Output: {self.context_info.output}
    
    Example Agents: {json.dumps(sorted_agents, indent=4)}
    """
    
    instructions = f"""
    {prompt}
    """
    ```

5. **Instantiate Universe Agent**
    - Instantiate the Universe Agent with the enhanced prompt and necessary tools.
    ```python
    universe_agent = await AgentFactory.from_name(
        name='UniverseAgent',
        session_id=self.session_id,
        context_info=ContextInfo(key=self.key, input_description=self.context_info.input_description, action_summary=self.context_info.action_summary, outcome_description=self.context_info.outcome_description, output=self.context_info.output, context=self.context_info.context),
        instructions=instructions,
        tools=['AssignAgents']
    )
    
    logger.debug(f"Universe agent: {universe_agent}")
    ```

6. **Manage Assignment**
    - Manage the assignment by creating an agency chart and getting the completion message.
    ```python
    agency_chart = [universe_agent]
    agency = Agency(agency_chart=agency_chart, shared_instructions="", session_id=self.session_id)
    await agency.get_completion(message="AssignAgents most appropriate for the task.", session_id=self.session_id)
    self.assignees = universe_agent.context_info.context['assignees']

    logger.debug(f"Assigned agents: {self.assignees}")
    ```

## FAQ

### What is the purpose of this code?
The code dynamically prompts and assigns agents to tasks using semantic lookup. It retrieves potential agents, creates a detailed prompt, and assigns the most appropriate agent to the task.

### How does the semantic lookup work?
The semantic lookup uses Redis to search for potential agents based on the task description and action summary vector. The results are sorted by vector distance to find the most relevant agents.

### What is the role of the Universe Agent?
The Universe Agent assesses the task and determines whether a node should be created or if the task can be completed by a single agent. It uses the provided tools to assign the most appropriate agents for the task.

### How are agents assigned to tasks?
Agents are assigned to tasks based on the detailed prompt created for the Universe Agent. The prompt includes rules and examples to guide the assignment process. The Universe Agent uses the AssignAgents tool to assign the most appropriate agent.

### What are the key components of the prompt?
The prompt includes the task description, input description, action summary, outcome description, output, and example agents. It provides detailed instructions for assessing the task and assigning agents.

### How is the assignment managed?
The assignment is managed by creating an agency chart and getting the completion message from the Universe Agent. The assigned agents are then stored in the task's assignees attribute.

### What tools are used in this process?
The process uses the AssignAgents tool to assign the most appropriate agents for the task. The Universe Agent is instantiated with the necessary tools and instructions to complete the assignment.

### How is logging used in this code?
Logging is used to track the progress of the agent assignment process. It logs the start of the assignment, the retrieved agents, the created prompt, the instantiated Universe Agent, and the assigned agents.

### What is the role of the Redis service?
The Redis service is used to retrieve potential agents, tools, and nodes from the context. It performs the semantic lookup based on the task description and action summary vector.

### How is the context information used?
The context information is used to create the detailed prompt for the Universe Agent. It includes the task description, input description, action summary, outcome description, and output.

### What is the purpose of the agency chart?
The agency chart is used to manage the assignment process. It includes the Universe Agent and any other agents involved in the task. The agency chart is used to get the completion message and assign agents to the task.

### How are the results sorted?
The results are sorted by vector distance to find the most relevant agents. The sorted agents are then included in the detailed prompt for the Universe Agent.

### What is the output of this process?
The output of this process is the assigned agents for the task. The assigned agents are stored in the task's assignees attribute and logged for tracking.

### How is the Universe Agent instantiated?
The Universe Agent is instantiated using the AgentFactory.from_name method. It is provided with the session ID, context information, instructions, and tools needed to complete the assignment.

### What is the role of the AssignAgents tool?
The AssignAgents tool is used by the Universe Agent to assign the most appropriate agents for the task. It follows the rules and instructions provided in the detailed prompt.

### How is the detailed prompt created?
The detailed prompt is created by combining the task description, input description, action summary, outcome description, output, and example agents. It provides step-by-step instructions for assessing the task and assigning agents.

### How is the completion message obtained?
The completion message is obtained by calling the get_completion method on the agency. The message instructs the Universe Agent to assign the most appropriate agents for the task.

### How are the assigned agents stored?
The assigned agents are stored in the task's assignees attribute. The assigned agents are also logged for tracking purposes.

### What is the purpose of the ContextInfo class?
The ContextInfo class is used to store the context information for the task. It includes the input description, action summary, outcome description, output, and any additional context needed for the assignment.

### How is the Redis service configured?
The Redis service is configured using the ServiceRegistry.instance().get method. It retrieves the Redis service instance and performs the semantic lookup for potential agents.

### How is the logger configured?
The logger is configured using the configure_logger method. It sets up the logger for the Task class and logs the progress of the agent assignment process.

### What is the role of the ServiceRegistry class?
The ServiceRegistry class is used to retrieve service instances, such as the Redis service. It provides a centralized registry for accessing services needed for the assignment process.

### How is the semantic lookup performed?
The semantic lookup is performed using the async_search_index method of the Redis service. It searches for potential agents based on the task description and action summary vector.

### How are the results of the semantic lookup processed?
The results of the semantic lookup are processed by sorting the agents by vector distance. The sorted agents are then included in the detailed prompt for the Universe Agent.

### What is the purpose of the detailed prompt?
The detailed prompt provides step-by-step instructions for assessing the task and assigning agents. It includes rules, examples, and context information to guide the assignment process.

### How is the Universe Agent used in the assignment process?
The Universe Agent is used to assess the task and determine the appropriate assignment. It follows the detailed prompt and uses the AssignAgents tool to assign the most appropriate agents for the task.

### How is the context information updated?


