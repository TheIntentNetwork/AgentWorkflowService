from app.models.DelayNode import DelayNode
from app.models.Goal import Goal
from app.models.LifecycleNode import LifecycleNode
from app.models.Node import Node
from app.models.ContextInfo import ContextInfo
from app.models.NodeStatus import NodeStatus

def get_goal_seed_data():
    return [
        Goal(
            name="CreateConditionReportsForCustomers",
            type="goal",
            description="Create a report for the customer with all necessary information and analysis.",
            context_info=ContextInfo(
                input_description="You will receive task requests for managing several aspects of the report creation process. You will need to manage the following tasks:",
                action_summary="You will need to enhance the context, register outputs, resolve dependencies, and finalize the nodes for all nodes created that align with this goal. Ensure an existing Lifecycle model is already created and currently managing these requests.",
                outcome_description="Nodes properly created and managed by lifecycle nodes built for this goal and successfully processing requests for aspects of the report creation process.",
                feedback=[
                    "Ensure all required information is collected and processed.",
                ],
                output={},
            ),
        ),
        Goal(
            name="ProcessGoals",
            type="goal",
            description="Process the goals of our Universe and ensure we are prepared with the right lifecycle to step through our process.",
            context_info=ContextInfo(
                input_description="This lifecycle is built to create a lifecycle that will enhance the context of the request with past examples, broadcast to the universe of what it plans to produce, and any node that is interested in the output can register to be notified when the output is ready. Finally, we have a finalize in which we will review the progress of this node's lifecycle and make any necessary updates to the context to correct issues.",
                action_summary="Process the goals of our Universe and ensure we are prepared with the right lifecycle to step through our process.",
                outcome_description="A fully created customer report with all necessary information and analysis.",
                feedback=[
                    "Ensure all lifecycle nodes are executed in the correct order.",
                    "Verify that all required information is collected and processed.",
                    "Maintain proper error handling and logging throughout the process.",
                ],
                output={"session_id": "{session_id}", "nodes": ["{node_id}"], "lifecycle": "CreateReportLifecycle", "agents": [{"{agent_name}": "{agent}"}]},
            ),
        )
    ]
