import asyncio
import json
import traceback
from typing import Dict, Any, List, Optional, Set, Tuple

from tenacity import retry, stop_after_attempt, wait_fixed

from app.agents.ProcessNotesAgent import ProcessNotesAgent
from app.agents.ProcessIntakeAgent import ProcessIntakeAgent
from app.agents.ProcessSupplementalAgent import ProcessSupplementalAgent
from app.agents.BrowsingAgent import BrowsingAgent
from app.agents.NexusLetterWriter import NexusLetterWriter
from app.agents.PersonalStatementWriter import PersonalStatementWriter
from app.agents.CFRTipsWriter import CFRTipsWriter
from app.agents.ReportSectionWriter import ReportSectionWriter
from app.agents.CustomerReportWriter import CustomerReportWriter
from app.models.ContextInfo import ContextInfo
from app.models.agency import Agency
from app.logging_config import configure_logger
from app.services.supabase.supabase import Supabase
from app.tools import (
    SaveToNexusLetters,
    AggregateIntakes,
    SaveNotesInformation,
    Write38CFRPoints,
    WriteExecutiveSummary,
    WriteResearchSection,
    SaveToPersonalStatements,
    WriteFutureConsiderations,
    WriteKeyPoints,
    SaveIntakeInformation,
    SaveResearch
)

from app.services.metadata.metadata_manager import MetadataManager
from postgrest.exceptions import APIError

logger = configure_logger('CleanupTask')

class TaskInfo:
    """
    Represents information about a task to be executed.
    """
    def __init__(self, name, agent_class, shared_instructions, message_template, result_key, tools, dependencies=None, files_folder=None):
        self.name = name
        self.agent_class = agent_class
        self.shared_instructions = shared_instructions
        self.message_template = message_template
        self.result_key = result_key
        self.tools = tools
        self.dependencies = dependencies or []
        self.files_folder = files_folder

    def __repr__(self):
        return f"TaskInfo(name={self.name}, result_key={self.result_key}, dependencies={self.dependencies})"

class CleanupTask:
    """
    The CleanupTask class manages the execution of tasks needed to generate a complete report.
    It checks for missing sections and dynamically loads and executes the required tasks,
    handling dependencies and ensuring all necessary inputs are available.
    """

    def __init__(self, session_id: str, context_info: ContextInfo, **kwargs):
        """
        Initialize the CleanupTask.
        
        Args:
            session_id (str): The session ID.
            context_info (Dict[str, Any]): The context information.
            **kwargs: Additional keyword arguments.
        """
        from containers import get_container
        
        self.session_id = session_id
        self.context_info = context_info
        self.supabase = Supabase.supabase
        self.metadata_manager = MetadataManager(self.supabase)
        self.id = kwargs.get('id')
        self.description = kwargs.get('description')
        
        self.kafka = get_container().kafka()
        self.batch_size = kwargs.get('batch_size', 5)
        self.user_id = kwargs.get('context_info', {}).get('context', {}).get('user_context', {}).get('user_id', 'default_user_id')
        self.task_definitions = self.define_tasks()
        self.intake_information = {}
        self.supplemental_information = {}
        self.notes_information = {}
        self.report = {}
        self.max_retries = kwargs.get('max_retries', 3)  # Configurable maximum number of retries
        self.conditions = []  # Initialize conditions list

    def define_tasks(self) -> Dict[str, TaskInfo]:
        """
        Define all possible tasks and map them to the sections they generate.

        Returns:
            Dict[str, TaskInfo]: A dictionary of task definitions.
        """
        return {
            # Data Processing Tasks
            'process_intake': TaskInfo(
                name='Process Intake',
                agent_class=ProcessIntakeAgent,
                shared_instructions="Retrieve and process the customer intake information for all conditions.",
                message_template="""
                Process the intake information for the customer with user ID {user_id}.
                The intake forms are provided below:
                {intake_forms}
                """,
                result_key='intake_info',
                tools=[SaveIntakeInformation]
            ),
            'process_supplemental': TaskInfo(
                name='Process Supplemental',
                agent_class=ProcessSupplementalAgent,
                shared_instructions="Retrieve and process supplemental information for all conditions.",
                message_template="""
                Review and process any supplemental information provided for the conditions of the customer with user ID {user_id}.
                The supplemental forms are provided below:
                {supplemental_forms}
                """,
                result_key='aggregated_info',
                tools=[AggregateIntakes]
            ),
            'process_notes': TaskInfo(
                name='Process Notes',
                agent_class=ProcessNotesAgent,
                shared_instructions="Process the notes information for all conditions listed.",
                message_template="""
                Process the notes information for all conditions for the customer with user ID {user_id}.
                The notes are provided below:
                {notes}
                """,
                result_key='notes_info',
                tools=[SaveNotesInformation]
            ),
            # Condition-specific tasks
            'research_section': TaskInfo(
                name='Research Section',
                agent_class=BrowsingAgent,
                shared_instructions="Generate research information for all conditions",
                message_template="Generate research information for the following conditions: {conditions}",
                result_key='research_section',
                tools=[WriteResearchSection],
                dependencies=[]
            ),
            'key_points': TaskInfo(
                name='Key Points',
                agent_class=ReportSectionWriter,
                shared_instructions="Write key points for the condition",
                message_template="Provide key points for {condition_name} based on: {research_section}",
                result_key='key_points',
                tools=[WriteKeyPoints],
                dependencies=['research_section']
            ),
            'future_considerations': TaskInfo(
                name='Future Considerations',
                agent_class=ReportSectionWriter,
                shared_instructions="Write future considerations for the condition",
                message_template="Provide future considerations for {condition_name} based on: {research_section}",
                result_key='future_considerations',
                tools=[WriteFutureConsiderations],
                dependencies=['research_section']
            ),
            'points_for_38_cfr': TaskInfo(
                name='38 CFR Tips',
                agent_class=CFRTipsWriter,
                shared_instructions="Write C&P exam tips based on the 38 CFR rating criteria for the condition.",
                message_template="""
                Provide C&P exam tips for {condition_name}, including key points from the 38 CFR rating criteria.
                - Base your tips on the following information:
                    - Intake Information: {intake_information}
                    - Supplemental Information: {supplemental_information}
                    - Notes Information: {notes_information}
                    - Research Section: {research_section}
                """,
                result_key='points_for_38_cfr',
                tools=[Write38CFRPoints],
                dependencies=['research_section']
            ),
            'executive_summary': TaskInfo(
                name='Executive Summary',
                agent_class=ReportSectionWriter,
                shared_instructions="Write an executive summary for the condition",
                message_template="Write an executive summary for {condition_name} based on: {research_section} {key_points} {points_for_38_cfr} {future_considerations}",
                result_key='executive_summary',
                tools=[WriteExecutiveSummary],
                dependencies=['research_section', 'key_points', 'points_for_38_cfr', 'future_considerations']
            ),
            'personal_statement': TaskInfo(
                name='Personal Statement',
                agent_class=PersonalStatementWriter,
                shared_instructions="Write a personal statement reflecting the veteran's experiences and symptoms.",
                message_template="""
                Write a personal statement for {condition_name} based on the provided information.

                Include:
                - The veteran's personal experiences and symptoms.
                - A compassionate and understanding tone.

                Base your statement on the following information:
                    - Intake Information: {intake_information}
                    - Supplemental Information: {supplemental_information}
                    - Notes Information: {notes_information}
                    - Research Section: {research_section}
                """,
                result_key='personal_statement',
                tools=[SaveToPersonalStatements],
                dependencies=['research_section']
            ),
            'nexus_letter': TaskInfo(
                name='Nexus Letter',
                agent_class=NexusLetterWriter,
                shared_instructions="Write a nexus letter establishing a connection between the condition and military service.",
                message_template="""
                Write a nexus letter for {condition_name}.

                Instructions:
                - Establish a connection between the veteran's condition and their military service.
                - Use appropriate medical terminology.
                - Ensure the letter is suitable for submission to the VA.

                Base your letter on the following information:
                    - Intake Information: {intake_information}
                    - Supplemental Information: {supplemental_information}
                    - Notes Information: {notes_information}
                    - Research Section: {research_section}
                """,
                result_key='nexus_letter',
                tools=[SaveToNexusLetters],
                dependencies=['research_section', 'key_points', 'future_considerations', 'executive_summary']
            ),
            # Overall report tasks
            'overall_executive_summary': TaskInfo(
                name='Overall Executive Summary',
                agent_class=CustomerReportWriter,
                shared_instructions="Compile an executive summary for the entire report.",
                message_template="""
                Create an executive summary for the entire report covering all conditions.

                Include:
                - Summaries of key findings from all conditions.
                - Overarching recommendations or observations.

                Base your summary on the following condition sections:
                {condition_sections}
                """,
                result_key='overall_executive_summary',
                tools=[WriteExecutiveSummary],
                dependencies=['conditions']
            )
        }

    def save_progress(self, metadata: Dict[str, Any]):
        """
        Save the current progress of the task.

        Args:
            metadata (Dict[str, Any]): The metadata to save.
        """
        success = self.metadata_manager.save_metadata(self.user_id, metadata)
        if not success:
            logger.error(f"Failed to save progress for user {self.user_id}")
    
    async def process_user_comments(self, user_comments: List[Dict[str, str]]) -> List[Tuple[str, TaskInfo, str]]:
        """
        Process user comments to determine which sections need updates and which tasks to run.

        Args:
            user_comments (List[Dict[str, str]]): A list of dictionaries with 'json_path' and 'comment'.

        Returns:
            List[Tuple[str, TaskInfo, str]]: A list of tasks to execute, each as a tuple of condition name, TaskInfo, and user comment.
        """
        tasks_to_run = []
        for comment_entry in user_comments:
            json_path = comment_entry.get('json_path')
            comment = comment_entry.get('comment')
            if not json_path or not comment:
                logger.warning("Invalid comment entry. 'json_path' or 'comment' is missing.")
                continue

            # Determine which task corresponds to the JSON path
            task_info = self.get_task_by_json_path(json_path)
            if task_info:
                # Extract condition name if applicable
                condition_name = self.extract_condition_name_from_path(json_path)
                tasks_to_run.append((condition_name, task_info, comment))
            else:
                logger.warning(f"No task associated with JSON path '{json_path}'.")
        return tasks_to_run

    def get_task_by_json_path(self, json_path: str) -> Optional[TaskInfo]:
        """
        Determine which task corresponds to the given JSON path.

        Args:
            json_path (str): The JSON path to a section in the report.

        Returns:
            Optional[TaskInfo]: The task that can update the specified section, or None if not found.
        """
        # Mapping between JSON paths and task result keys
        mapping = {
            'executive_summary': 'executive_summary',
            'key_points': 'key_points',
            'personal_statement': 'personal_statement',
            'nexus_letter': 'nexus_letter',
            'research_section': 'research_section',
            'points_for_38_cfr': 'points_for_38_cfr',
            'future_considerations': 'future_considerations'
        }

        for key, value in mapping.items():
            if key in json_path:
                task_info = self.task_definitions.get(value)
                return task_info

        return None
    
    def extract_condition_name_from_path(self, json_path: str) -> Optional[str]:
        """
        Extract the condition name from the JSON path if applicable.

        Args:
            json_path (str): The JSON path to parse.

        Returns:
            Optional[str]: The condition name if found, else None.
        """
        import re

        # Regex to match condition name in the JSON path
        match = re.search(r"conditions\[(\d+)\]", json_path)
        if match:
            index = int(match.group(1))
            conditions = self.report.get('conditions', [])
            if 0 <= index < len(conditions):
                condition_name = conditions[index].get('condition_name')
                return condition_name
        return None

    # Adding the combine_tasks method
    def combine_tasks(self, existing_tasks: List[Tuple[str, TaskInfo]], user_tasks: List[Tuple[str, TaskInfo, Optional[str]]]) -> List[Dict[str, Any]]:
        all_tasks = {
            'research_section': self.task_definitions['research_section'],
            'points_for_38_cfr': self.task_definitions['points_for_38_cfr'],
            'key_points': self.task_definitions['key_points'],
            'future_considerations': self.task_definitions['future_considerations'],
            'executive_summary': self.task_definitions['executive_summary'],
            'personal_statement': self.task_definitions['personal_statement'],
            'nexus_letter': self.task_definitions['nexus_letter'],
        }

        combined_tasks = []
        for task_name, task_info in all_tasks.items():
            combined_tasks.append({"condition": None, "task": task_info, "comment": None})

        # Add user-specified tasks, potentially overriding defaults
        for condition, task, comment in user_tasks:
            task_index = next((i for i, t in enumerate(combined_tasks) if t['task'].name == task.name), None)
            if task_index is not None:
                combined_tasks[task_index] = {"condition": condition, "task": task, "comment": comment}
            else:
                combined_tasks.append({"condition": condition, "task": task, "comment": comment})

        return combined_tasks
    
    @classmethod
    async def handle(cls, key: str, action: str, object_data: Dict[str, Any], context: Dict[str, Any]):
        """
        Handle method to process events and execute the CleanupTask.

        Args:
            key (str): The event key.
            action (str): The action to perform.
            object_data (Dict[str, Any]): Additional data required to initialize the task.
            context (Dict[str, Any]): Context information for the task execution.
        """
        try:
            logger.info(f"CleanupTask.handle called with key: {key}, action: {action}, object_data: {object_data}, context: {context}")
            # Initialize the CleanupTask instance
            session_id = object_data.get('session_id', 'default_session_id')
            context_info = context.get('context_info')
            if not context_info:
                logger.error("Context info is missing in context data.")
                logger.debug(f"Context data: {context}")
                logger.debug(f"Object data: {object_data}")
                return

            # Instantiate CleanupTask
            cleanup_task = cls(session_id=session_id, context_info=context_info, **object_data)
            
            # Extract additional parameters for execution
            user_comments = context.get('user_comments', None)

            # Execute the task
            await cleanup_task.execute(user_comments=user_comments)
            logger.info(f"CleanupTask executed successfully for key: {key}")
        except Exception as e:
            logger.error(f"Error in CleanupTask.handle: {str(e)}")
            logger.error(traceback.format_exc())
            # Optionally, handle the error (e.g., save to a database or send a notification)
    
    @retry(stop=stop_after_attempt(3), wait=wait_fixed(1))
    async def execute(self, user_comments: List[Dict[str, str]] = None) -> Dict[str, Any]:
        try:
            # Hardcoded test inputs for user_comments
            if user_comments is None:
                user_comments = [
                    {
                        "json_path": "$.executive_summary",
                        "comment": "The executive summary is missing. Please provide an overview of the report."
                    },
                    {
                        "json_path": "$.conditions[?(@.condition_name=='Knee Pain')].key_points",
                        "comment": "Add more information about the key points related to the condition."
                    }
                ]
            
            if isinstance(self.context_info, dict):
                self.context_info = ContextInfo(**self.context_info)
                
            self.user_id = self.context_info.context['user_context']['user_id'] or '42f99089-6812-4fc8-b424-b133de8f940b'

            # Load existing metadata
            metadata = self.metadata_manager.get_metadata(self.user_id) or {}

            # Load existing report
            report_data = self.supabase.table('decrypted_reports').select('decrypted_report').eq('user_id', self.user_id).execute()
            report_entry = report_data.data[0]['decrypted_report'] if report_data.data else None

            if report_entry:
                self.report = json.loads(report_entry)
            else:
                self.report = {'conditions': []}

            # Process user comments to determine tasks to run and update report sections
            user_tasks = await self.process_user_comments(user_comments)

            # Determine tasks to run based on missing sections
            missing_sections = await self.is_report_complete(self.report)
            tasks_to_run = self.determine_tasks_to_run(missing_sections)

            # Combine user_tasks with tasks_to_run, avoiding duplicates
            combined_tasks = self.combine_tasks(tasks_to_run, user_tasks)
            sorted_task_names = self.topological_sort(combined_tasks)

            # Execute the sorted tasks
            for task_name in sorted_task_names:
                task_info = next((t for t in combined_tasks if t['task'].name == task_name), None)
                if task_info is None:
                    logger.warning(f"Task '{task_name}' not found in combined_tasks. Skipping.")
                    continue

                condition = task_info["condition"]
                task = task_info["task"]
                comment = task_info["comment"]

                logger.info(f"Executing task '{task.name}' for condition '{condition or 'N/A'}'")
                
                context = self.prepare_task_context(task, condition, comment)
                logger.debug(f"Task context: {context}")
                
                result = await self.execute_task(task, context)
                if result:
                    self.update_report_with_result(task, condition, result)
                    logger.info(f"Task '{task.name}' completed successfully")
                else:
                    logger.warning(f"Task '{task.name}' failed to produce a result")

            # After executing tasks, check again for missing sections
            missing_sections = await self.is_report_complete(self.report)
            if missing_sections:
                logger.warning(f"Report is still incomplete. Missing sections: {missing_sections}")
            else:
                logger.info("Report is now complete.")

            # Save the updated report
            await self.save_report(self.report)

            # Send the final report
            await self.send_report(self.report)

            return self.report

        except Exception as e:
            logger.error(f"Error executing CleanupTask: {str(e)}", exc_info=True)
            raise

    async def execute_task(self, task: TaskInfo, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        try:
            # Prepare the context for the message template
            serialized_context = {k: json.dumps(v) if isinstance(v, (dict, list)) else str(v) for k, v in context.items()}
            
            # Add placeholder values for potentially missing sections
            placeholder_sections = ['research_section', 'points_for_38_cfr', 'key_points', 'future_considerations']
            for section in placeholder_sections:
                if section not in serialized_context:
                    serialized_context[section] = "Not available"

            message = task.message_template.format(**serialized_context)
            
            # If a user comment exists in the context, include it in the message
            user_comment = context.get('user_comment')
            if user_comment:
                message += f"\n\nUser Comment:\n{user_comment}"

            task_config = {
                'name': task.name,
                'agent_class': task.agent_class,
                'shared_instructions': task.shared_instructions,
                'message': message,
                'result_key': task.result_key,
                'tools': task.tools,
                'files_folder': task.files_folder
            }

            result = await self.create_agent_and_get_completion(task_config)
            logger.info(f"Completed task '{task.name}'")
            return {task.result_key: result}
        except Exception as e:
            logger.error(f"Error executing task '{task.name}': {str(e)}", exc_info=True)
            return None

    def prepare_task_context(self, task: TaskInfo, condition: Optional[str], comment: Optional[str]) -> Dict[str, Any]:
        context = {
            'conditions': self.conditions,
            'research_section': self.context_info.context.get('research_section', ''),
            'user_id': self.user_id,
            'intake_information': self.intake_information,
            'supplemental_information': self.supplemental_information,
            'notes_information': self.notes_information,
            'condition_name': condition,
            'user_comment': comment,
        }
        
        # Add any previously generated sections to the context
        for section in ['research_section', 'points_for_38_cfr', 'key_points', 'future_considerations']:
            if section in self.context_info.context:
                context[section] = self.context_info.context[section]

        return context

    def update_report_with_result(self, task: TaskInfo, condition: Optional[str], result: Dict[str, Any]):
        if task.result_key in ['personal_statement', 'nexus_letter']:
            if task.result_key + 's' not in self.report:
                self.report[task.result_key + 's'] = {}
            self.report[task.result_key + 's'][condition] = result[task.result_key]
        elif condition:
            condition_obj = self.get_condition_by_name(condition)
            if condition_obj:
                condition_obj.update(result)
        else:
            self.report.update(result)
        
        # Store the result in the context for future tasks
        self.context_info.context[task.result_key] = result[task.result_key]

    async def is_report_complete(self, report: Dict[str, Any]) -> List[str]:
        # Implement logic to check if all required sections are present
        missing_sections = []
        required_sections = [
            'executive_summary',
            'personalStatementLetters',
            'nexusLetters',
            'conditions'
        ]
        for section in required_sections:
            if section not in report or not report[section]:
                missing_sections.append(section)
        
        # Check for condition-specific sections
        for condition in self.conditions:
            condition_name = condition['name']
            for subsection in ['points_for_38_cfr', 'personal_statement', 'nexus_letter']:
                if subsection not in condition or not condition[subsection]:
                    missing_sections.append(f"conditions[condition_name='{condition_name}'].{subsection}")
        
        return missing_sections

    def determine_tasks_to_run(self, missing_sections: List[str]) -> List[Tuple[str, TaskInfo]]:
        tasks_to_run = []
        for section in missing_sections:
            task = self.get_task_for_section(section)
            if task:
                tasks_to_run.append((section, task))
        
        # Add all tasks that are not condition-specific
        for task_name, task in self.task_definitions.items():
            if task not in [t[1] for t in tasks_to_run]:
                tasks_to_run.append((task_name, task))
        
        return tasks_to_run

    def get_task_for_section(self, section: str) -> Optional[TaskInfo]:
        # Map sections to tasks
        section_to_task = {
            'overall_executive_summary': self.task_definitions['overall_executive_summary'],
            'personalStatements': self.task_definitions['personal_statement'],
            'nexusLetters': self.task_definitions['nexus_letter'],
            'points_for_38_cfr': self.task_definitions['points_for_38_cfr'],
            'research_section': self.task_definitions['research_section'],
        }
        return section_to_task.get(section)

    def topological_sort(self, tasks: List[Dict[str, Any]]) -> List[str]:
        graph = {}
        for task in tasks:
            task_name = task['task'].name
            graph[task_name] = set(getattr(task['task'], 'dependencies', []))

        # Create a separate set of all dependencies
        all_dependencies = set()
        for dependencies in graph.values():
            all_dependencies.update(dependencies)

        # Ensure all dependencies are in the graph
        for dep in all_dependencies:
            if dep not in graph:
                graph[dep] = set()

        sorted_tasks = []
        visited = set()
        temp_visited = set()

        def dfs(node):
            if node in temp_visited:
                raise ValueError(f"Circular dependency detected involving {node}")
            if node not in visited:
                temp_visited.add(node)
                for neighbor in graph[node]:
                    dfs(neighbor)
                temp_visited.remove(node)
                visited.add(node)
                sorted_tasks.append(node)

        for node in list(graph.keys()):  # Create a list to avoid modifying during iteration
            if node not in visited:
                dfs(node)

        return list(reversed(sorted_tasks))
    
    async def save_report(self, report: Dict[str, Any]):
        try:
            serialized_report = self.serialize_report(report)
            result = self.supabase.table("reports").insert({
                "report": serialized_report,
                "user_id": self.user_id,
                "status": "created"  # Make sure this is a valid enum value for your database
            }).execute()
            logger.info(f"Report saved successfully: {result}")
        except APIError as e:
            logger.error(f"Error saving report: {str(e)}")
            raise

    def serialize_report(self, report: Dict[str, Any]) -> Dict[str, Any]:
        # Implement custom serialization logic here if needed
        return report

    async def send_report(self, final_report: Dict[str, Any]) -> None:
        """
        Send the final report.

        Args:
            final_report (Dict[str, Any]): The final report data.
        """
        serialized_report = json.dumps(final_report, indent=4)
        
        # Send a message indicating that the task is completed
        await self.kafka.send_message('task_completed', {
            "sessionId": self.session_id,
            "task_id": self.id,
            "response": serialized_report
        })
    
    async def process_user_comments(self, user_comments: List[Dict[str, str]]) -> List[Tuple[str, TaskInfo, str]]:
        """
        Process user comments to determine which sections need updates and which tasks to run.

        Args:
            user_comments (List[Dict[str, str]]): A list of dictionaries with 'json_path' and 'comment'.

        Returns:
            List[Tuple[str, TaskInfo, str]]: A list of tasks to execute, each as a tuple of condition name, TaskInfo, and user comment.
        """
        tasks_to_run = []
        for comment_entry in user_comments:
            json_path = comment_entry.get('json_path')
            comment = comment_entry.get('comment')
            if not json_path or not comment:
                logger.warning("Invalid comment entry. 'json_path' or 'comment' is missing.")
                continue

            # Determine which task corresponds to the JSON path
            task_info = self.get_task_by_json_path(json_path)
            if task_info:
                # Extract condition name if applicable
                condition_name = self.extract_condition_name_from_path(json_path)
                tasks_to_run.append((condition_name, task_info, comment))
            else:
                logger.warning(f"No task associated with JSON path '{json_path}'.")
        return tasks_to_run

    def update_report_section(self, json_path: str, comment: str) -> bool:
        """
        Update the report section specified by the JSON path with the user's comment.

        Args:
            json_path (str): The JSON path to the report section.
            comment (str): The user's comment to update the section with.

        Returns:
            bool: True if the update was successful, False otherwise.
        """
        try:
            # Use jsonpath_ng.ext.parse to support filter expressions
            from jsonpath_ng.ext import parse

            jsonpath_expr = parse(json_path)
            matches = jsonpath_expr.find(self.report)
            if not matches:
                logger.warning(f"No matches found for JSON path '{json_path}'.")
                return False

            for match in matches:
                # Update the value at the matched path with the comment
                path = match.path
                path.update(self.report, comment)

            # Validate that the update was made
            updated_value = jsonpath_expr.find(self.report)[0].value
            if updated_value == comment:
                return True
            else:
                logger.warning(f"Update failed for JSON path '{json_path}'.")
                return False
        except Exception as e:
            logger.error(f"Error updating report section at '{json_path}': {str(e)}", exc_info=True)
            return False

    def get_task_by_json_path(self, json_path: str) -> Optional[TaskInfo]:
        """
        Determine which task corresponds to the given JSON path.

        Args:
            json_path (str): The JSON path to a section in the report.

        Returns:
            Optional[TaskInfo]: The task that can update the specified section, or None if not found.
        """
        # Mapping between JSON paths and task result keys
        mapping = {
            'executive_summary': 'executive_summary',
            'key_points': 'key_points',
            'personal_statement': 'personal_statement',
            'nexus_letter': 'nexus_letter',
            'research_section': 'research_section',
            'points_for_38_cfr': 'points_for_38_cfr',
            'future_considerations': 'future_considerations'
        }

        for key, value in mapping.items():
            if key in json_path:
                task_info = self.task_definitions.get(value)
                return task_info

        return None

    def extract_condition_name_from_path(self, json_path: str) -> Optional[str]:
        """
        Extract the condition name from the JSON path if applicable.

        Args:
            json_path (str): The JSON path to parse.

        Returns:
            Optional[str]: The condition name if found, else None.
        """
        import re

        # Regex to match condition index in the JSON path
        match = re.search(r"conditions\[(\d+)\]", json_path)
        if match:
            index = int(match.group(1))
            conditions = self.report.get('conditions', [])
            if 0 <= index < len(conditions):
                condition_name = conditions[index].get('condition_name')
                return condition_name
        return None

    # You should also ensure that all methods like get_all_dependencies, execute_tasks, etc., are included and properly implemented.

    # Example of get_all_dependencies method
    def get_all_dependencies(self, task: TaskInfo) -> Set[str]:
        """
        Recursively collect all dependencies for a given task.

        Args:
            task (TaskInfo): The task for which dependencies are collected.

        Returns:
            Set[str]: A set of all dependency names.
        """
        dependencies = set(task.dependencies)
        for dep_name in task.dependencies:
            if dep_name in self.task_definitions:
                dep_task = self.task_definitions[dep_name]
                dependencies.update(self.get_all_dependencies(dep_task))
            else:
                # For top-level data dependencies (e.g., 'intake_information')
                dependencies.add(dep_name)
        return dependencies

    async def process_intake(self) -> Dict[str, Any]:
        """
        Process the intake information.

        Returns:
            Dict[str, Any]: The processed intake information.
        """
        intake_results = self.supabase.table("decrypted_forms").select("decrypted_form").eq("user_id", self.user_id).eq("type", "intake").execute()
        intake_forms = [record['decrypted_form'] for record in intake_results.data]

        intake_task = self.task_definitions['process_intake']

        context = {
            'user_id': self.user_id,
            'intake_forms': intake_forms
        }

        intake_information = await self.execute_task(intake_task, context)

        if isinstance(intake_information, str):
            try:
                intake_information = json.loads(intake_information)
            except json.JSONDecodeError:
                logger.error(f"Failed to parse intake information as JSON: {intake_information}")
                intake_information = {"error": "Failed to parse intake information", "raw_data": intake_information}

        if not isinstance(intake_information, dict):
            logger.error(f"Unexpected intake information type: {type(intake_information)}")
            intake_information = {"error": "Unexpected intake information type", "raw_data": str(intake_information)}

        if 'conditions' not in intake_information:
            logger.error("No 'conditions' key in intake information")
            intake_information['conditions'] = []

        self.metadata_manager.save_form_data(self.user_id, 'intake', intake_information)
        return intake_information

    async def process_supplemental(self) -> Dict[str, Any]:
        """
        Process the supplemental information.

        Returns:
            Dict[str, Any]: The processed supplemental information.
        """
        supplemental_results = self.supabase.table("decrypted_forms").select("decrypted_form").eq("user_id", self.user_id).eq("type", "supplemental").execute()
        supplemental_forms = [record['decrypted_form'] for record in supplemental_results.data]

        supplemental_task = self.task_definitions['process_supplemental']

        context = {
            'user_id': self.user_id,
            'supplemental_forms': supplemental_forms
        }

        supplemental_information = await self.execute_task(supplemental_task, context)

        self.metadata_manager.save_form_data(self.user_id, 'supplemental', supplemental_information)
        return supplemental_information

    async def process_notes(self) -> Dict[str, Any]:
        """
        Process the notes information.

        Returns:
            Dict[str, Any]: The processed notes information.
        """
        notes_results = self.supabase.table("decrypted_notes").select("decrypted_note").eq("user_id", self.user_id).execute()
        notes = [record['decrypted_note'] for record in notes_results.data]

        notes_task = self.task_definitions['process_notes']

        context = {
            'user_id': self.user_id,
            'notes': notes
        }

        notes_information = await self.execute_task(notes_task, context)

        self.metadata_manager.save_form_data(self.user_id, 'notes', notes_information)
        return notes_information

    async def execute_tasks(self, tasks_to_run: List[Tuple[str, TaskInfo, Optional[str]]]):
        """
        Execute the necessary tasks to complete the report.

        Args:
            tasks_to_run (List[Tuple[str, TaskInfo, Optional[str]]]): List of tasks to execute.
        """
        executed_tasks: Set[str] = set()
        pending_tasks = tasks_to_run.copy()

        while pending_tasks:
            condition_name, task, user_comment = pending_tasks.pop(0)
            dependencies_met = all(dep in executed_tasks for dep in task.dependencies)

            if dependencies_met:
                logger.info(f"Executing task '{task.name}' for condition '{condition_name}'")
                if condition_name:
                    # Condition-specific task
                    condition = self.get_condition_by_name(condition_name)
                    if not condition:
                        logger.error(f"Condition '{condition_name}' not found in report.")
                        continue
                    context = {
                        **condition,
                        'condition_name': condition_name,
                        'intake_information': self.intake_information,
                        'supplemental_information': self.supplemental_information,
                        'notes_information': self.notes_information,
                        'research_section': condition.get('research_section', {}),
                        'points_for_38_cfr': condition.get('points_for_38_cfr', {}),
                        'key_points': condition.get('key_points', {}),
                        'future_considerations': condition.get('future_considerations', {}),
                        'executive_summary': condition.get('executive_summary', '')
                    }
                    # Include the user comment in the context
                    if user_comment:
                        context['user_comment'] = user_comment
                else:
                    # Top-level task
                    context = {
                        'user_id': self.user_id,
                        'intake_information': self.intake_information,
                        'supplemental_information': self.supplemental_information,
                        'notes_information': self.notes_information,
                        'condition_sections': self.report.get('conditions', [])
                    }
                    if user_comment:
                        context['user_comment'] = user_comment

                # Execute the task
                result = await self.execute_task(task, context)
                if result:
                    if condition_name:
                        condition.update(result)
                    else:
                        self.report.update(result)
                else:
                    logger.warning(f"No result for task '{task.name}' for condition '{condition_name or 'N/A'}'")

                executed_tasks.add(task.result_key)
            else:
                logger.info(f"Deferring task '{task.name}' for condition '{condition_name}' due to unmet dependencies.")
                pending_tasks.append((condition_name, task, user_comment))

    def get_condition_by_name(self, condition_name: str) -> Dict[str, Any]:
        """
        Retrieve a condition from the report by its name.

        Args:
            condition_name (str): The name of the condition.

        Returns:
            Dict[str, Any]: The condition dictionary.
        """
        for condition in self.report.get('conditions', []):
            if condition.get('condition_name') == condition_name:
                return condition
        return None

    async def create_overall_summary(self, condition_sections: List[Dict[str, Any]]) -> Dict[str, Any]:
        overall_executive_summary_task = TaskInfo(
            name='Overall Executive Summary',
            agent_class=CustomerReportWriter,
            shared_instructions="Compile an executive summary for the entire report based on all condition sections.",
            message_template="Create an executive summary for the entire report covering all conditions. Use the following condition sections: {condition_sections}",
            result_key='overall_executive_summary',
            tools=[WriteExecutiveSummary]
        )

        return await self.execute_task(overall_executive_summary_task, {'condition_sections': condition_sections})

    async def create_agent_and_get_completion(self, task_config: Dict[str, Any]) -> Any:
        agent_class = task_config['agent_class']
        agent = agent_class(
            name=task_config['name'],
            tools=task_config['tools'],
            context_info=self.context_info,
            files_folder=task_config.get('files_folder', None)
        )
        
        agency = Agency(agency_chart=[agent], shared_instructions=task_config['shared_instructions'])
        
        completion = await agency.get_completion(task_config['message'])
        
        result = self.context_info.context.get(task_config['result_key'], None)
        logger.debug(f"Context after completion: {json.dumps(self.context_info.context, indent=2)}")
        
        if result:
            return result
        else:
            logger.warning(f"Result not found in context for {task_config['name']}")
            logger.info(f"Available keys in context: {list(self.context_info.context.keys())}")
            logger.info(f"Completion is not a dict, returning it directly for {task_config['name']}")
            return completion