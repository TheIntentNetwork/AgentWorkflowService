from app.models.LifecycleNode import LifecycleNode
from app.models.Node import Node
from app.models.ContextInfo import ContextInfo
from app.models.NodeStatus import NodeStatus

def get_lifecycle_seed_data():
    return [
        Node(
            name="CreateReportLifecycle",
            type="model",
            description="Lifecycle model for creating a report",
            context_info=ContextInfo(
                input_description="This lifecycle is built to create a lifecycle that will enhance the context of the request with past examples, broadcast to the universe of what it plans to produce, and any node that is interested in the output can register to be notified when the output is ready. Finally, we have a finalize in which we will review the progress of this node's lifecycle and make any necessary updates to the context to correct issues.",
                action_summary="Orchestrate the process of creating a customer report by managing various lifecycle nodes to ensure the report is created as expected. Pay special attention to the tools mentioned in the descriptions and summaries.",
                outcome_description="A fully created customer report with all necessary information and analysis.",
                feedback=[
                    "Ensure all lifecycle nodes are executed in the correct order.",
                    "Verify that all required information is collected and processed.",
                    "Maintain proper error handling and logging throughout the process.",
                ],
                output={"session_id": "{session_id}", "nodes": ["{node_id}"], "lifecycle": "CreateReportLifecycle", "agents": [{"{agent_name}": "{agent}"}]},
            ),
            collection=[
                LifecycleNode(
                    name="SetContext",
                    type="lifecycle",
                    description="Set the context for the report creation process",
                    context_info=ContextInfo(
                        input_description="Initial customer data and report requirements.",
                        action_summary="Initialize the report creation context with necessary information.",
                        outcome_description="A fully set up context for the report creation process.",
                        feedback=["Ensure all required initial data is properly set in the context."],
                        output={},
                    ),
                    status_filter=NodeStatus.created,
                    status_result=NodeStatus.initializing,
                    failed_status_result=NodeStatus.failed,
                ),
                LifecycleNode(
                    name="RegisterOutputs",
                    type="lifecycle",
                    description="Register the expected outputs for the report",
                    context_info=ContextInfo(
                        input_description="Report requirements and structure.",
                        action_summary="Define and register all expected outputs for the report.",
                        outcome_description="A complete list of registered outputs for the report.",
                        feedback=["Verify that all necessary report sections are included in the registered outputs."],
                        output={},
                    ),
                    status_filter=NodeStatus.initializing,
                    status_result=NodeStatus.initialized,
                    failed_status_result=NodeStatus.failed,
                ),
                LifecycleNode(
                    name="RegisterDependencies",
                    type="lifecycle",
                    description="Register the dependencies for the report creation process",
                    context_info=ContextInfo(
                        input_description="Required resources and data sources for the report.",
                        action_summary="Identify and register all dependencies needed for creating the report.",
                        outcome_description="A comprehensive list of registered dependencies for the report creation process.",
                        feedback=["Ensure all necessary data sources and tools are included in the dependencies."],
                        output={},
                    ),
                    status_filter=NodeStatus.initialized,
                    status_result=NodeStatus.resolving_dependencies,
                    failed_status_result=NodeStatus.failed,
                    no_action_result=NodeStatus.ready,
                )
            ],
        ),
    ]
