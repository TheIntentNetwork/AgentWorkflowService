import asyncio
import logging
from app.models.Workflow import Workflow, Event, Step, Feedback, Goal, Intent

class WorkflowOrchestrator:
    def __init__(self):
        from app.services.discovery.service_registry import ServiceRegistry
        from app.services.workflow.discovery import Discovery
        from app.services.workflow.analysis import Analysis
        self.workflow = None
        self.redis_service = ServiceRegistry.instance().get("redis")
        self.discovery_service = Discovery(self.redis_service)
        self.context_analysis_service = Analysis(self.redis_service)
        #self.optimization_service = WorkflowOptimizationService(redis_service)
        self.logger = self.setup_logger()

    def setup_logger(self):
        logger = logging.getLogger(__name__)
        logger.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)
        file_handler = logging.FileHandler(f"{__name__}.log")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        return logger

    async def create_workflow_from_event(self, event: Event):

        workflow = Workflow.create_from_context(event)
        # Start the workflow processing and orchestration
        event_similarities = await self.discovery_service.execute_vector_queries(self.workflow, ["event"])

        # Analyze contexts for creating new workflows
        eventbased_workflow = await self.create_workflow_from_context(event_similarities)
        
        similarities = await self.discovery_service.execute_vector_queries(eventbased_workflow, ["event"], ["event", "intent", "goals", "steps", "feedback", "models"])

        # Combine all the records
        sir_contexts = []
        for field, records in similarities.items():
            sir_contexts.extend(records)
            print(f"{field.capitalize()} Similarities: {records}")

        # Similarity search across results and gather context examples
        target_records = await self.context_analysis_service.perform_similarity_search(self.workflow, sir_contexts)

        for record in target_records:
            self.logger.info(f"Similar Record: {record}")
        
        # Analyze contexts for creating new workflows
        new_workflow = await self.create_workflow_from_context(target_records)
        
        # Check if analysis and feedback are adequate
        #feedback_analysis = await self.context_analysis_service.analyze_feedback([self.workflow])
        #feedback_threshold_exceeded = feedback_analysis['feedback_threshold_exceeded']

        #is_unique = await self.context_analysis_service.evaluate_uniqueness(new_workflow, sir_contexts)
        
        # Branch and manage child workflows if necessary
        #if feedback_analysis['impact'] == 'negative' and feedback_threshold_exceeded:
        #    await self.initiate_problem_solving_workflow(self.workflow.feedback)
        #else:
        #    # Proceed with new workflow execution
        #    await self.execute_new_workflow(new_workflow)

        # Manage index optimization and record enhancements only if the workflow is unique
        #if is_unique:
        #    await self.optimization_service.manage_index_optimization(new_workflow)
        #    await self.optimization_service.record_workflow_enhancements(new_workflow)
        #    await self.optimization_service.record_workflow_usage(new_workflow)
        return new_workflow

    async def initiate_problem_solving_workflow(self, feedback):
        # Create a problem-solving workflow based on intent analysis of the feedback
        feedback_analysis = await self.intent_agent.analyze_feedback(feedback)
        problem_solving_workflow = Workflow()
        problem_solving_workflow.initialize_from_feedback_analysis(feedback_analysis)
        await problem_solving_workflow.execute()
        return problem_solving_workflow

    async def create_workflow_from_context(self, similar_contexts):
        # Generate a new workflow based on prompts created by the intent agent
        prompts = [await self.intent_agent.generate_workflow_prompt(context) for context in similar_contexts]
        new_workflow = self.intent_agent.create_workflow(prompts)
        return new_workflow