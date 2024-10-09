import asyncio
from typing import List, Dict, Any
from pydantic import Field
from app.models.Node import Node
from app.models.ContextInfo import ContextInfo
from app.models.agency import Agency
from app.factories.agent_factory import AgentFactory
from app.logging_config import configure_logger
from app.services.cache.redis import RedisService
from containers import get_container
from app.models.NodeStatus import NodeStatus
from app.seed_node_data import get_node_seed_data
import json
import uuid

class CustomReport(Node):
    type: str = Field(default="custom_report")
    collection: List[Dict[str, Any]] = Field(default_factory=list)
    
    def __init__(self, **data):
        super().__init__(**data)
        self.logger = configure_logger(self.__class__.__name__)

    async def execute(self) -> None:
        self.logger.info(f"Executing CustomReport: {self.name}")
        await self._context_manager.save_context(f'node:{self.id}', NodeStatus.executing, "status")

        await self.initialize()
        await self.process_collection()
        await self.finalize()

        await self._context_manager.save_context(f'node:{self.id}', NodeStatus.completed, "status")
        self.logger.info(f"CustomReport execution completed: {self.name}")

    async def initialize(self) -> None:
        self.logger.info(f"Initializing CustomReport: {self.name}")
        await self._context_manager.save_context(f'node:{self.id}', NodeStatus.initialized, "status")

    async def process_collection(self) -> None:
        self.logger.info(f"Processing collection for CustomReport: {self.name}")
        for node_data in self.collection:
            await self._execute_node(node_data)

    async def finalize(self) -> None:
        self.logger.info(f"Finalizing CustomReport: {self.name}")

    async def _execute_node(self, node_data: Dict[str, Any]):
        node_data['id'] = str(uuid.uuid4())
        node_data['parent_id'] = self.id
        node_data['session_id'] = self.session_id

        self.logger.info(f"Processing node: {node_data['name']}")
        
        agent = await self._create_agent(node_data)
        response = await self._perform_completion(agent, node_data)
        await self._process_response(response, node_data)

    async def _create_agent(self, node_data: Dict[str, Any]):
        context_info = self._get_context_info(node_data['name'])
        agent_name = self._get_agent_name(node_data)
        
        agent = await AgentFactory.from_name(
            name=agent_name,
            session_id=self.session_id,
            context_info=context_info,
            instructions=node_data['description'],
            tools=self._get_agent_tools(agent_name),
            self_assign=False
        )
        return agent

    def _get_context_info(self, node_name: str) -> ContextInfo:
        seed_data = get_node_seed_data()
        for node in seed_data:
            if node.name == node_name:
                return node.context_info
        return ContextInfo()  # Return a default ContextInfo if not found

    def _get_agent_name(self, node_data: Dict[str, Any]) -> str:
        agent_mapping = {
            "GatherIntakeConditions": "IntakeProcessor",
            "CollectConditionsFromUserMeta": "UniverseAgent",
            "RetrieveDiscoveryCallNotesForCondition": "DiscoveryCallNotesAgent",
            "ReviewDetailBuilderForCondition": "SupplementalIntakeReviewAgent",
            "ResearchCondition": "BrowsingAgent",
            "SaveUserMetaFromIntake": "ProcessIntakeAgent",
            "WriteNexusLetter": "NexusLetterWriter",
            "CreateConditionReport": "ConditionReportWriter",
            "PersonalStatement": "PersonalStatementWriter",
            "ResearchExamples": "ResearchExampleFinder",
            "ExecutiveSummary": "ExecutiveSummaryWriter",
            "TipsForCustomer": "CustomerAdviceAgent",
            "AggregateCustomerReport": "ReportAggregator",
            "RetrieveIntakeForm": "IntakeFormRetriever"
        }
        return agent_mapping.get(node_data['name'], "UniverseAgent")

    def _get_agent_tools(self, agent_name: str) -> List[str]:
        tool_mapping = {
            "IntakeProcessor": ["SaveUserMeta"],
            "UniverseAgent": ["RetrieveContext", "SetContext", "GetUserContext", "CreateNodes"],
            "DiscoveryCallNotesAgent": ["RetrieveContext"],
            "SupplementalIntakeReviewAgent": ["RetrieveContext"],
            "BrowsingAgent": ["GetReport", "WriteConditionReportSection"],
            "ProcessIntakeAgent": ["SaveUserMeta"],
            "NexusLetterWriter": ["WriteReportSection"],
            "ConditionReportWriter": ["WriteReportSection"],
            "PersonalStatementWriter": ["WriteReportSection"],
            "ResearchExampleFinder": ["GetReport"],
            "ExecutiveSummaryWriter": ["WriteReportSection"],
            "CustomerAdviceAgent": ["WriteReportSection"],
            "ReportAggregator": ["SaveOutput"],
            "IntakeFormRetriever": ["RetrieveContext"]
        }
        return tool_mapping.get(agent_name, ["RetrieveContext", "SaveOutput"])

    async def _perform_completion(self, agent, node_data: Dict[str, Any]):
        agency_chart = [agent]
        agency = Agency(agency_chart=agency_chart, shared_instructions="", session_id=self.session_id)
        response = await agency.get_completion(node_data['description'])
        return response

    async def _process_response(self, response: Dict[str, Any], node_data: Dict[str, Any]):
        context_key = f"node:{node_data['id']}"
        await self._context_manager.save_context(context_key, response, "output")

        if node_data.get('process_item_level', False):
            items = response.get('items', [])
            for item in items:
                await self._process_item(item, node_data)

        next_node = self._get_next_node(node_data)
        if next_node:
            next_node['context_info']['input'] = response
            self.logger.info(f"Passing output to next node: {next_node['name']}")

    async def _process_item(self, item: Dict[str, Any], node_data: Dict[str, Any]):
        # Process individual items if needed
        pass

    def _get_next_node(self, current_node: Dict[str, Any]) -> Dict[str, Any]:
        current_order = current_node.get('order_sequence')
        if current_order is None:
            return None

        next_nodes = [node for node in self.collection if node.get('order_sequence', 0) > current_order]
        return min(next_nodes, key=lambda x: x.get('order_sequence', float('inf'))) if next_nodes else None

    async def clear_dependencies(self):
        self.logger.info(f"Clearing dependencies for CustomReport: {self.name}")
        await super().clear_dependencies()

    def to_json(self):
        return {
            **super().to_json(),
            "collection": [node for node in self.collection]
        }

async def create_sample_custom_report(user_context, session_id) -> CustomReport:
    seed_data = get_node_seed_data()
    custom_report = CustomReport(
        name="CreateCustomerReport",
        description="Create a customer report for the customer",
        context_info=ContextInfo(
            input_description="The customer's intake form to gather all of the conditions.",
            action_summary="Create a customer report for the customer",
            outcome_description="A complete customer report",
            output={},
            context={"user_context": user_context}
        ),
        collection=[
            {
                "name": "GatherIntakeConditions",
                "type": "model",
                "description": "Gather intake conditions and write the user's metadata",
                "context_info": next((node.context_info.dict() for node in seed_data if node.name == "GatherIntakeConditions"), {}),
                "order_sequence": 1,
                "collection": [
                    {
                        "name": "RetrieveIntakeForm",
                        "type": "step",
                        "description": "Retrieve the intake form for the customer",
                        "context_info": next((node.context_info.dict() for node in seed_data if node.name == "RetrieveIntakeForm"), {}),
                        "order_sequence": 1
                    },
                    {
                        "name": "SaveUserMetaFromIntake",
                        "type": "step",
                        "description": "Save the user's information from their intake form",
                        "context_info": next((node.context_info.dict() for node in seed_data if node.name == "SaveUserMetaFromIntake"), {}),
                        "order_sequence": 2
                    }
                ]
            },
            {
                "name": "CollectConditionsAndProcess",
                "type": "model",
                "description": "Collect the supplemental intake for our customer",
                "context_info": next((node.context_info.dict() for node in seed_data if node.name == "CollectConditionsAndProcess"), {}),
                "order_sequence": 2,
                "collection": [
                    {
                        "name": "CollectConditionsFromUserMeta",
                        "type": "step",
                        "description": "Collect the conditions from the user's metadata",
                        "context_info": next((node.context_info.dict() for node in seed_data if node.name == "CollectConditionsFromUserMeta"), {}),
                        "order_sequence": 1
                    }
                ]
            },
            {
                "name": "ResearchConditionModel",
                "type": "model",
                "description": "Gather all the information for each condition",
                "context_info": next((node.context_info.dict() for node in seed_data if node.name == "ResearchConditionModel"), {}),
                "order_sequence": 3,
                "process_item_level": True,
                "collection": [
                    {
                        "name": "RetrieveDiscoveryCallNotesForCondition",
                        "type": "step",
                        "description": "Retrieve the discovery call notes for the condition",
                        "context_info": next((node.context_info.dict() for node in seed_data if node.name == "RetrieveDiscoveryCallNotesForCondition"), {}),
                        "order_sequence": 1
                    },
                    {
                        "name": "ReviewDetailBuilderForCondition",
                        "type": "step",
                        "description": "Collect the detail builder for the specific condition for our customer",
                        "context_info": next((node.context_info.dict() for node in seed_data if node.name == "ReviewDetailBuilderForCondition"), {}),
                        "order_sequence": 2
                    },
                    {
                        "name": "ResearchCondition",
                        "type": "step",
                        "description": "Research the condition information from the (processed_supplemental_intake)",
                        "context_info": next((node.context_info.dict() for node in seed_data if node.name == "ResearchCondition"), {}),
                        "order_sequence": 3,
                        "process_item_level": True
                    }
                ]
            },
            {
                "name": "CreateConditionReport",
                "type": "model",
                "description": "Create a condition report for the customer",
                "context_info": next((node.context_info.dict() for node in seed_data if node.name == "CreateConditionReport"), {}),
                "order_sequence": 4,
                "process_item_level": True,
                "collection": [
                    {
                        "name": "ResearchExamples",
                        "type": "step",
                        "description": "Provide research examples for the customer",
                        "context_info": next((node.context_info.dict() for node in seed_data if node.name == "ResearchExamples"), {}),
                        "order_sequence": 1
                    },
                    {
                        "name": "PersonalStatement",
                        "type": "step",
                        "description": "Write a personal statement for the customer",
                        "context_info": next((node.context_info.dict() for node in seed_data if node.name == "PersonalStatement"), {}),
                        "order_sequence": 2
                    },
                    {
                        "name": "WriteNexusLetter",
                        "type": "step",
                        "description": "Write a Nexus letter using context information",
                        "context_info": next((node.context_info.dict() for node in seed_data if node.name == "WriteNexusLetter"), {}),
                        "order_sequence": 3
                    },
                    {
                        "name": "TipsForCustomer",
                        "type": "step",
                        "description": "Provide tips for the customer for customizing their report",
                        "context_info": next((node.context_info.dict() for node in seed_data if node.name == "TipsForCustomer"), {}),
                        "order_sequence": 4
                    },
                    {
                        "name": "SaveResearchIntoReport",
                        "type": "step",
                        "description": "Save the research into a report for the customer",
                        "context_info": next((node.context_info.dict() for node in seed_data if node.name == "SaveResearchIntoReport"), {}),
                        "order_sequence": 5
                    }
                ]
            },
            {
                "name": "AggregateCustomerReport",
                "type": "model",
                "description": "Aggregate all the outputs from CreateConditionReport",
                "context_info": next((node.context_info.dict() for node in seed_data if node.name == "AggregateCustomerReport"), {}),
                "order_sequence": 5,
                "collection": [
                    {
                        "name": "ExecutiveSummary",
                        "type": "step",
                        "description": "Write an executive summary for the customer",
                        "context_info": next((node.context_info.dict() for node in seed_data if node.name == "ExecutiveSummary"), {}),
                        "order_sequence": 1
                    }
                ]
            }
        ]
    )
    return custom_report

async def main(user_context, session_id):
    logger = configure_logger("CustomReportMain")
    
    try:
        container = get_container()
        container.init_resources()
        
        custom_report = await create_sample_custom_report(user_context, session_id)
        await custom_report.execute()
        
        logger.info("CustomReport execution completed successfully")
    except Exception as e:
        logger.error(f"Error during CustomReport execution: {str(e)}")
    finally:
        container.shutdown_resources()

if __name__ == "__main__":
    import sys

    if len(sys.argv) != 3:
        print("Usage: python CustomReport.py <user_id> <session_id>")
        sys.exit(1)

    user_context = {"user_id": sys.argv[1]}
    session_id = sys.argv[2]
    asyncio.run(main(user_context, session_id))