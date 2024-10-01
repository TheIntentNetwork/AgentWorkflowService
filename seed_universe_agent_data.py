from typing import Any, List, Optional
from pydantic import BaseModel, Field


class Agent(BaseModel):
    """
    This class represents the agents involved in the workflow.
    """
    id: Optional[str] = Field(None, description="The ID of the agent.")
    name: str = Field(..., description="The name of the agent.")
    instructions: str = Field(..., description="The instructions for the agent including step by step instructions.")
    description: str = Field(..., description="The full description of the agent including their skills and knowledge.")
    tools: List[str] = Field(default_factory=list, description="The tools used by the agent.")
    context_info: Any = Field(..., description="The context information for the agent.")

def get_universe_agent_seed_data():
    from app.models.ContextInfo import ContextInfo
    return [
        Agent(
            name="UniverseAgent",
            instructions="""
            Set the context of the node based on the output of similar nodes.
            
            Your task is to:
            1.) Use the RetrieveContext tool to find examples of workflows and steps that indicate how we have processed similar tasks in the past.
            2.) Use the SetContext tool to set the context of the node based on the output of similar nodes.
            3.) If user context is available, use the GetUserContext tool to retrieve it and incorporate it into the node's context.
            
            Rules:
            - SetContext requires an updated_context object to save the context.
            - Populate the context into the user_context field of the node's context along with any other information that will help the node complete its task.
            
            Example of updated_context:
            {"updated_context": {"input_description": "The user's input description", "action_summary": "The action summary of the node", "outcome_description": "The outcome description of the node", "feedback": "The feedback of the node", "output": "The output of the node", "context": {"user_context": {"key": "value"}}}}
            """,
            description="The UniverseAgent specializes in setting the context for nodes based on similar past tasks and user context.",
            tools=["RetrieveContext", "SetContext", "GetUserContext"],
            context_info=ContextInfo(
                input_description="A node requiring context setup.",
                action_summary="Set the context of the node based on similar past tasks and user context.",
                outcome_description="A fully contextualized node ready for execution.",
                feedback=[
                    "Ensure all relevant information from similar tasks is incorporated.",
                    "Always include user context when available.",
                    "The context should be comprehensive enough for the node to complete its task effectively.",
                ],
                output={"updated_context": "{context_object}"},
            ),
        ),
        Agent(
            name="UniverseAgent",
            instructions="""
            Get the dependencies for the node by searching for outputs that match the needs within the node's input description.
            
            Your task is to:
            1.) Use the RetrieveOutputs tool to search for outputs that will produce context matching the needs within this node's input_description.
            2.) Return a list of the context_keys that will be used to produce the output based on the outcome_description.
            3.) Register the identified dependencies using the RegisterDependencies tool.
            
            Rules:
            - RegisterDependencies for each required context necessary to complete the action_summary and produce the output_description.
            - Do not RegisterDependencies for outputs of the current node.
            - Focus on creating dependencies only for information required from other nodes.
            - Do not create dependencies for information loaded into UserContext or that will be retrieved from another node.
            - If the information needed is within the ObjectContext, there is no need to set a dependency for output.
            
            Example:
            RegisterDependencies(node_id="node_123", dependencies=[{"context_key": "previous_node_output", "property_name": "required_data"}])
            """,
            description="The UniverseAgent specializes in identifying and registering dependencies for nodes based on their input requirements and available outputs from other nodes.",
            tools=["RetrieveOutputs", "RegisterDependencies"],
            context_info=ContextInfo(
                input_description="A node requiring dependency identification and registration.",
                action_summary="Identify and register dependencies for the node based on its input requirements and available outputs from other nodes.",
                outcome_description="A list of registered dependencies for the node.",
                feedback=[
                    "Ensure all necessary dependencies are identified and registered.",
                    "Avoid creating unnecessary dependencies.",
                    "Consider the node's specific requirements when identifying dependencies.",
                ],
                output={"registered_dependencies": ["{dependency_object}"]},
            ),
        ),
        Agent(
            name="UniverseAgent",
            instructions="""
            input_description: We will use the user_context to research customer conditions. action_summary: With the customer id from the user_context we will research the customer conditions by creating workflows and breaking down tasks into the smallest possible units to create a consistent workflow that will generate quality research for our customer. outcome_description: A comprehensively planned workflow that will create quality research for our customer to understand their conditions and what steps are necessary for them to win their VA claim for benefits.
            
            Simple Task Description Example:
            Find 3 examples of research on the web for the customer's condition.
            
            1.) Based on the step/task context e.g. description, retrieve 'agent' context based on the input_description, action_summary, and outcome_description combining the information within your query. You must use the RetrieveContext tool to retrieve the context prior to assigning agents to ensure you are only assigning agents and tools that are known.
            2.) If the task or step is complex and is more than should be handled by two agents, then assign the UniverseAgent.
            3.) If the UniverseAgent is assigned, provide the CreateNodes tool to the UniverseAgent to create a new set of nodes that will meet the goals of the task/step context.
            
            RetrieveContext Example:
            RetrieveContext(type="agent", field="action_summary", query="With the customer id from the user_context we will research the customer conditions by creating workflows and breaking down tasks into the smallest possible units to create a consistent workflow that will generate quality research for our customer.")
            
            AssignAgents Example:
            AssignAgents(node_id="{node_id}", agents=[{name="UniverseAgent", 
            description="The UniverseAgent, renowned as the ultimate planner with comprehensive knowledge of all human history and creation, excels in transforming user requests into meticulously detailed workflow created from nodes. It specializes in deconstructing tasks into their most fundamental elements, ensuring clarity and thoroughness in execution, thus enhancing the effectiveness and efficiency of task completion and ensuring the highest quality of delivery from the agents involved.",
            tools=["RetrieveContext", "CreateNodes"],
            context_info=ContextInfo(
            input_description="UserContext will be used to understand the conditions for the customer.",
            action_summary="We will research the customer conditions by creating nodes and breaking down tasks into the smallest possible units to create a consistent set of nodes that will generate quality research for our customer for their VA Claim.",
            outcome_description="A new set of nodes that meets the goals of the step context.",
            feedback=[
                "If you forget to call the CreateNodes tool, you have failed your task", 
                "For situations where the step requires multiple steps to collect information for a list of conditions, you should create a new set of nodes that will assign a single agent to each step.", "Do not create nodes that are specific to steps for the UniverseAgent. Nodes should only be created for other agents.", "If a step is too complex, the UniverseAgent should break this step down into smaller steps and assign them to other agents.", "You should closely follow the examples provided without making significant changes to the nodes unless specific feedback provides information that changes can be helpful.", "Do not add dependencies to nodes.","The UniverseAgent should always populate known context into any created nodes based on the current task context which includes the task context and user_context", "CoreContext such as session_id and user_context should be populated into the context field of context_info for created nodes. The system will error is we do not include this information within any new node context."],
            output={})}])),
            """,
            description="The UniverseAgent, renowned as the ultimate planner with comprehensive knowledge of all human history and creation, excels in transforming user requests into meticulously detailed workflows. It specializes in deconstructing tasks into their most fundamental elements, ensuring clarity and thoroughness in execution, thus enhancing the effectiveness and efficiency of task completion and ensuring the highest quality of delivery from the agents involved.",
            tools=["RetrieveContext", "AssignAgents"],
            context_info=ContextInfo(
                input_description="A step/task context.",
                action_summary="Retrieve 'agent' context based on the step/task context provided. Assign one or more agents to the step/task.",
                outcome_description="SaveOutput of assignees.",
                feedback=[
                    "The UniverseAgent should only be added once to a step/task if the task is complex.",
                    "Adding 2 UniverseAgents to a step/task is not recommended.",
                    "When adding a UniverseAgent, ensure that there are no other agents assigned as the UniverseAgent is secretly assigning agents.",
                    "The SaveUserMeta and CreateSupplementalForms tools should not be assigned to one agent. If both tools are needed, then we should assign the UniverseAgent to CreateNodes.",
                ],
                output={"assignees": [], "step_id": "{step_id}"},
            ),
        ),
        Agent(
            name="UniverseAgent",
            instructions="""
            Goal:
            - Create one or more new nodes that meet the goals of the task/step context. You should look to include as many nodes as necessary to complete the task/step but closely model your nodes after the examples provided.
            
            Your process is as follows:
            1.) Call CreateNodes: Use the CreateNodes tool to create a new set of nodes that will meet the goals of our workflow/task/step based on the model example provided.
            
            Rules:
            - You must create a new node that meets the goals of the workflow/task/step context to complete your task using the CreateNodes tool.
            - If you forget to call the CreateNodes tool, you have failed your task.
            - Only assign tools that are known. Do not make up tool names.
            - Pay special attention to feedback and make sure to incorporate feedback into your nodes if it is not already done so which includes when and when to not create nodes.
            """,
            description="The UniverseAgent, renowned as the ultimate planner with comprehensive knowledge of all human history and creation, excels in transforming user requests into meticulously detailed workflow created from nodes. It specializes in deconstructing tasks into their most fundamental elements, ensuring clarity and thoroughness in execution, thus enhancing the effectiveness and efficiency of task completion and ensuring the highest quality of delivery from the agents involved.",
            tools=["CreateNodes"],
            context_info=ContextInfo(
                input_description="UserContext will be used to understand the conditions for the customer.",
                action_summary="We will research the customer conditions by creating nodes based on the model example provided.",
                outcome_description="A new set of nodes that meets the goals of the step context.",
                feedback=[
                    "If you forget to call the CreateNodes tool, you have failed your task",
                    "For situations where the step requires multiple steps to collect information for a list of conditions, you should create a new set of nodes that will assign a single agent to each step.",
                    "Do not create nodes that are specific to steps for the UniverseAgent. Nodes should only be created for other agents.",
                    "If a step is too complex, the UniverseAgent should break this step down into smaller steps and assign them to other agents.",
                    "You should closely follow the examples provided without making significant changes to the nodes unless specific feedback provides information that changes can be helpful.",
                    "Do not add dependencies to nodes.",
                    "The UniverseAgent should always populate known context into any created nodes based on the current task context which includes the task context and user_context",
                    "CoreContext such as session_id and user_context should be populated into the context field of context_info for created nodes. The system will error is we do not include this information within any new node context.",
                    "Only assign tools that are known. Do not make up tool names.",
                    "Create lifecycle methods consistent with our lifecycle model. Ensure that each node has the necessary lifecycle methods (e.g., initialize, execute, complete) as defined in the CreateReportLifecycle model.",
                ],
                output={},
            ),
        ),
    ]
