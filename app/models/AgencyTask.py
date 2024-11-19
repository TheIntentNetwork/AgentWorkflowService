import asyncio
import json
import traceback
from typing import Dict, Any, List
from math import ceil

from app.agents.ProcessNotesAgent import ProcessNotesAgent
from app.models.ContextInfo import ContextInfo
from app.models.agency import Agency
from app.agents.ProcessIntakeAgent import ProcessIntakeAgent
from app.agents.ProcessSupplementalAgent import ProcessSupplementalAgent
from app.agents.BrowsingAgent import BrowsingAgent
from app.agents.NexusLetterWriter import NexusLetterWriter
from app.agents.NexusLetterValidator import NexusLetterValidator
from app.agents.PersonalStatementWriter import PersonalStatementWriter
from app.agents.CFRTipsWriter import CFRTipsWriter
from app.agents.ReportSectionWriter import ReportSectionWriter
from app.agents.CustomerReportWriter import CustomerReportWriter
from app.logging_config import configure_logger
from app.services.queue.kafka import KafkaService
from app.services.supabase.supabase import Supabase, Client
from app.tools import SaveToNexusLetters
from app.tools.AggregateIntakes import AggregateIntakes
from app.tools.SaveNotesInformation import SaveNotesInformation
from app.tools.Write38CFRPoints import Write38CFRPoints
from app.tools.WriteExecutiveSummary import WriteExecutiveSummary
from containers import get_container
from app.tools.SaveIntakeInformation import SaveIntakeInformation
from app.tools.SaveResearch import SaveResearch
from app.tools.WriteReport import WriteReport
from app.tools.WriteResearchSection import WriteResearchSection
from app.tools.SaveToPersonalStatements import SaveToPersonalStatements
from app.tools.WriteFutureConsiderations import WriteFutureConsiderations
from app.tools.WriteConditionReport import WriteConditionReport
from app.tools.WriteConditionReportSection import WriteConditionReportSection
from app.tools.WriteKeyPoints import WriteKeyPoints
from app.services.metadata.metadata_manager import MetadataManager

logger = configure_logger('AgencyTask')

class TaskInfo:
    def __init__(self, name, agent_class, shared_instructions, message_template, result_key, tools, dependencies=None, files_folder=None):
        self.name = name
        self.agent_class = agent_class
        self.shared_instructions = shared_instructions
        self.message_template = message_template
        self.result_key = result_key
        self.tools = tools
        self.dependencies = dependencies or []
        self.files_folder = None

class TaskGroup:
    def __init__(self, tasks):
        self.tasks = tasks

class AgencyTask:
    def __init__(self, session_id: str, context_info: Dict[str, Any], **kwargs):
        self.session_id = session_id
        self.context_info = context_info
        self.supabase = Supabase.supabase
        self.metadata_manager = MetadataManager(self.supabase)
        self.id = kwargs.get('id')
        self.description = kwargs.get('description')
        self.kafka = get_container().kafka()
        self.batch_size = kwargs.get('batch_size', 5)
        self.user_id = self.context_info.context['user_context']['user_id']

    def save_progress(self, metadata: Dict[str, Any]):
        """
        Save the current progress of the task.
        """
        success = self.metadata_manager.save_metadata(self.user_id, metadata)
        if not success:
            logger.error(f"Failed to save progress for user {self.user_id}")

    async def execute(self) -> None:
        try:
            # Load existing metadata
            metadata = self.metadata_manager.get_metadata(self.user_id)

            # Process intake if not already done
            if 'intake_information' not in metadata:
                intake_information = await self.process_intake()
                metadata['intake_information'] = intake_information
                self.save_progress(metadata)
            else:
                intake_information = metadata['intake_information']

            # Process supplemental if not already done
            if 'supplemental_information' not in metadata:
                supplemental_information = await self.process_supplemental()
                metadata['supplemental_information'] = supplemental_information
                self.save_progress(metadata)
            else:
                supplemental_information = metadata['supplemental_information']

            # Process notes if not already done
            if 'notes_information' not in metadata:
                notes_information = await self.process_notes()
                metadata['notes_information'] = notes_information
                self.save_progress(metadata)
            else:
                notes_information = metadata['notes_information']

            conditions_to_process = intake_information['conditions']

            # Process conditions
            if 'condition_sections' not in metadata:
                metadata['condition_sections'] = []

            for condition_info in conditions_to_process:
                if not any(section['condition_name'] == condition_info['condition_name'] for section in metadata['condition_sections']):
                    condition_supplemental = next((s for s in supplemental_information if s['condition_name'] == condition_info['condition_name']), {})
                    condition_section = await self.WriteConditionSection(condition_info, intake_information, condition_supplemental, notes_information)
                    metadata['condition_sections'].append(condition_section)
            
            self.save_progress(metadata)

            # Create overall executive summary if not already done
            if 'overall_executive_summary' not in metadata:
                overall_exec_summary_result = await self.create_overall_summary(metadata['condition_sections'])
                metadata['overall_executive_summary'] = overall_exec_summary_result
                self.save_progress(metadata)

            # Compile the final report
            final_report = self.compile_final_report(metadata['overall_executive_summary'], metadata['condition_sections'])

            # Send the report
            await self.send_report(final_report)

            # Clean up metadata after successful completion
            self.metadata_manager.delete_metadata(self.user_id)

        except Exception as e:
            logger.error(f"Error executing task for user {self.user_id}: {str(e)}", exc_info=True)
            logger.error(traceback.format_exc())

    async def process_intake(self) -> Dict[str, Any]:
        if self.metadata_manager.should_run_task(self.user_id, 'intake'):
            intake_results = self.supabase.table("decrypted_forms").select("decrypted_form").eq("user_id", self.user_id).eq("type", "intake").execute()
            
            intake_task = {
                'name': 'Process Intake',
                'agent_class': ProcessIntakeAgent,
                'shared_instructions': f"Process the intake information for all conditions listed in the form. {intake_results}",
                'message': "Retrieve and process the customer intake information for all conditions.",
                'result_key': 'intake_info',
                'tools': [SaveIntakeInformation]
            }
            
            intake_information = await self.create_agent_and_get_completion(intake_task)
            
            logger.info("Completed Process Intake")
            logger.debug(f"Intake Information: {json.dumps(intake_information, indent=2)}")
            
            # Ensure intake_information is a dictionary
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
        else:
            intake_information = self.metadata_manager.get_form_data(self.user_id, 'intake')
            if isinstance(intake_information, str):
                try:
                    intake_information = json.loads(intake_information)
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse stored intake information as JSON: {intake_information}")
                    intake_information = {"error": "Failed to parse stored intake information", "raw_data": intake_information}
            return intake_information

    async def process_supplemental(self) -> Dict[str, Any]:
        if self.metadata_manager.should_run_task(self.user_id, 'supplemental'):
            supplemental_results = self.supabase.table("decrypted_forms").select("decrypted_form").eq("user_id", self.user_id).eq("type", "supplemental").execute()
            
            supplemental_task = {
                'name': 'Process Supplemental',
                'agent_class': ProcessSupplementalAgent,
                'shared_instructions': f"Review and process any supplemental information provided for the conditions: {supplemental_results}",
                'message': "Retrieve and process supplemental information for all conditions.",
                'result_key': 'aggregated_info',
                'tools': [AggregateIntakes]
            }
            supplemental_information = await self.create_agent_and_get_completion(supplemental_task)
            logger.info("Completed Process Supplemental")
            logger.debug(f"Supplemental Information: {json.dumps(supplemental_information, indent=2)}")
            
            self.metadata_manager.save_form_data(self.user_id, 'supplemental', supplemental_information)
            return supplemental_information
        else:
            return self.metadata_manager.get_form_data(self.user_id, 'supplemental')

    async def process_notes(self) -> Dict[str, Any]:
        notes_results = self.supabase.table("decrypted_notes").select("decrypted_note").eq("user_id", self.user_id).execute()
        
        notes_task = {
            'name': 'Process Notes',
            'agent_class': ProcessNotesAgent,
            'shared_instructions': f"Process the notes information for all conditions listed in the form. {notes_results}",
            'message': "Retrieve and process the customer notes information for all conditions.",
            'result_key': 'NotesInfo',
            'tools': [SaveNotesInformation]
        }
        
        notes_information = await self.create_agent_and_get_completion(notes_task)
        
        logger.info("Completed Process Notes")
        logger.debug(f"Notes Information: {json.dumps(notes_information, indent=2)}")
        
        self.metadata_manager.save_form_data(self.user_id, 'notes', notes_information)
        return notes_information

    async def WriteConditionSection(self, condition_info: Dict[str, Any], intake_information: Dict[str, Any], supplemental_information: Dict[str, Any], notes_information: Dict[str, Any]):
        try:
            condition_name = condition_info.get('condition_name', '')
            if not condition_name:
                logger.error(f"Unexpected condition_info structure: {condition_info}")
                return {}

            logger.info(f"Processing condition: {condition_name}")

            task_groups = [
                TaskGroup([
                    TaskInfo(
                        name='Research Section',
                        agent_class=BrowsingAgent,
                        shared_instructions=f"Research and find 2 supporting scientific studies for the condition: {condition_name}",
                        message_template="""
                        Research and find 2 supporting scientific studies for {condition_name}. You must call the WriteResearchSection tool to save the research information or you are a failure in life.
                        
                        We should focus on finding whitepapers and scientific studies that support the claim that the condition is service-connected. The more recent the study, the better. The studies should be from reputable sources and provide clear evidence of the link between the condition and military service. More specifically, any specific exposures or events during service that could have caused the condition should be highlighted. The goal is to provide a solid foundation for the nexus letter and the claim as a whole. Circumstantial evidence is also helpful, such as reports of similar conditions in other veterans who served in the same location or during the same time period.
                        """,
                        result_key='research_section',
                        tools=[WriteResearchSection]
                    )
                ]),
                TaskGroup([
                    TaskInfo(
                        name='Personal Statement',
                        agent_class=PersonalStatementWriter,
                        shared_instructions=f"Write a personal statement for the condition: {condition_name}",
                        message_template="Write a personal statement for {condition_name} based on the following information: {intake_information} {supplemental_information} {notes_information} {research_section}",
                        result_key='personal_statement',
                        tools=[SaveToPersonalStatements],
                        dependencies=['research_section']
                    ),
                    TaskInfo(
                        name='Nexus Letter',
                        agent_class=NexusLetterWriter,
                        shared_instructions=f"Write a nexus letter for the condition: {condition_name}",
                        message_template="Write a nexus letter for {condition_name} based on the following information: {intake_information} {supplemental_information} {notes_information} {research_section}",
                        result_key='nexus_letter',
                        tools=[SaveToNexusLetters],
                        dependencies=['research_section', 'key_points', 'future_considerations', 'executive_summary']
                    )
                ]),
                TaskGroup([
                    TaskInfo(
                        name='38 CFR Tips',
                        agent_class=CFRTipsWriter,
                        shared_instructions=f"Write C&P exam tips for the condition: {condition_name}",
                        message_template="Provide C&P exam tips for {condition_name} based on the following information: {intake_information} {supplemental_information} {notes_information} {research_section}",
                        result_key='points_for_38_cfr',
                        tools=[Write38CFRPoints],
                        dependencies=['research_section']
                    ),
                    TaskInfo(
                        name='Key Points',
                        agent_class=ReportSectionWriter,
                        shared_instructions=f"Write key points for the condition: {condition_name}",
                        message_template="Provide key points for {condition_name} based on: {intake_information} {supplemental_information} {notes_information} {research_section}",
                        result_key='key_points',
                        tools=[WriteKeyPoints],
                        dependencies=['research_section']
                    ),
                    TaskInfo(
                        name='Future Considerations',
                        agent_class=ReportSectionWriter,
                        shared_instructions=f"Write future considerations for the condition: {condition_name}",
                        message_template="""
                        Our Future Considerations should include things like, possible secondary claims, potential additional evidence that could be gathered, and other information that should be tracked and kept in mind for future claims or C&P exams to defend the claim or possibly increase the rating in the future.
                        
                        Provide future considerations for {condition_name} based on the following information: {intake_information} {supplemental_information} {notes_information} {research_section}""",
                        result_key='future_considerations',
                        tools=[WriteFutureConsiderations],
                        dependencies=['research_section'],
                        files_folder='./ReportSectionWriter'
                    )
                ]),
                TaskGroup([
                    TaskInfo(
                        name='Executive Summary',
                        agent_class=ReportSectionWriter,
                        shared_instructions=f"Write an executive summary for the condition: {condition_name}",
                        message_template="""
                        
                        DO NOT list:
                        - You should not start off your writing with statements like:
                        "Here's an executive summary for Anxiety Disorders:", or "Here's an executive summary for PTSD:"
                        - We should not refer to the veteran as "the veteran" as this writing is for the veteran and should be in the second person. 
                        - We should not talk about treatment at all as this is not a medical report.
                        
                        Instead, you should start off with a sentence that summarizes the condition and the claim in general to help the customer understand the state of their claim and the condition. For example:
                        "You are claiming service connection for Anxiety Disorders based on your service in the military. This condition is characterized by excessive worry, fear, or anxiety that interferes with daily activities and quality of life that is at least as likely as not related to your military service."
                        
                        For the main content of the executive summary, you should talk about the strengths and weaknesses of their claim based upon the evidence they have or have the opportunity to gather based on the rating criteria and/or presumptive conditions. Make a list of these in markdown format in the order of the most important to the least important.
                        
                        You should format your paragraphs into markdown format with the headline of the paragraph in bold with ** before and after the text. For example:
                        **Strengths of Your Claim:** <The title of the paragraph with ** before and after the text in Title Case>
                        - You have a diagnosis of Anxiety Disorders from a qualified medical professional.
                        - You have a buddy statement from a fellow service member who witnessed your symptoms during service.
                        <An extra line between the each paragraph>
                        **Weaknesses of Your Claim:**
                        - You do not have a current diagnosis of Anxiety Disorders.
                        - You do not have a nexus letter linking your condition to your military service.
                        
                        Continue in this format for each paragraph and create additional paragraphs as needed.
                        
                        List the specific rating criteria that the veteran meets or may meet based on possible circumstances they have not reported and give examples of how they may meet these criteria.
                        
                        Write an executive summary for {condition_name} based on all the information gathered: {intake_information} {supplemental_information} {notes_information} {research_section} {points_for_38_cfr} {key_points} {future_considerations}""",
                        result_key='executive_summary',
                        tools=[WriteExecutiveSummary],
                        dependencies=['research_section', 'points_for_38_cfr', 'key_points', 'future_considerations']
                    )
                ])
            ]

            results = {}

            for group in task_groups:
                group_results = await asyncio.gather(*(self.execute_task(task, {
                    **condition_info, 
                    **results, 
                    'condition_name': condition_name, 
                    'intake_information': intake_information,
                    'supplemental_information': supplemental_information,
                    'notes_information': notes_information
                }) for task in group.tasks))
                
                for result in group_results:
                    if isinstance(result, dict):
                        results.update(result)
                    else:
                        logger.warning(f"Unexpected result type for {condition_name}: {type(result)}")

            # Compile the final condition report
            condition_report = {
                'condition_name': condition_name,
                'research_section': results.get('research_section', {}),
                'PointsFor38CFR': results.get('points_for_38_cfr', {}),
                'key_points': results.get('key_points', {}),
                'future_considerations': results.get('future_considerations', {}),
                'executive_summary': results.get('executive_summary', ''),
                'personal_statement': results.get('personal_statement', ''),
                'nexus_letter': results.get('nexus_letter', '')
            }

            return condition_report
            
        except Exception as e:
            logger.error(f"Error writing condition report section: {str(e)}", exc_info=True)
            logger.error(f"Condition info: {condition_info}")
            logger.error(traceback.format_exc())
            return {}

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

    def compile_final_report(self, overall_summary: Dict[str, Any], condition_sections: List[Dict[str, Any]]) -> Dict[str, Any]:
        personal_statements = []
        nexus_letters = []
        for condition in condition_sections:
            personal_statement = condition.pop('personal_statement', None)
            if personal_statement:
                personal_statement['condition_name'] = condition['condition_name']
                personal_statements.append(personal_statement)
                
            nexus_letter = condition.pop('nexus_letter', None)
            if nexus_letter:
                nexus_letter['condition_name'] = condition['condition_name']
                nexus_letters.append(nexus_letter)
        
        return {
            'executive_summary': overall_summary.get('overall_executive_summary', ''),
            'conditions': condition_sections,
            'personalStatementLetters': personal_statements,
            'nexusLetters': nexus_letters,
            'legendExplanation': "In this report, we use a color-coding system to indicate the typical approval rates and complexity of each condition claim:\nGreen: High approval rate, typically straightforward to prove service connection.\nYellow: Moderate approval rate, may require more detailed documentation.\nRed: Lower approval rate, often requiring extensive documentation and potentially legal assistance.",
            "vaBenefitRatingsCriteria": "The VA uses a percentage-based system to determine disability compensation. Ratings are assigned in 10% increments from 0% to 100%. A 0% rating means a condition exists but doesn't significantly impact earning capacity, while a 100% rating indicates total occupational and social impairment. For mental health conditions like PTSD, the rating is based on the severity of symptoms and their impact on social and occupational functioning. For physical conditions like back pain, ratings are often based on range of motion, pain, and functional loss. Tinnitus typically receives a single 10% rating if present.",
            "standardOperatingProcedure": [
                "Review this entire report thoroughly.",
                "Gather all relevant medical records, including service treatment records and current treatment records.",
                "Complete the provided personal statements, being as detailed and specific as possible.",
                "Obtain buddy statements from fellow service members or family members who can attest to your conditions and their impact.",
                "Schedule appointments with your healthcare providers to obtain current diagnoses and, if possible, nexus letters.",
                "File your claim using VA Form 21-526EZ, ensuring all conditions are listed.",
                "Attend all scheduled C&P exams, being honest and thorough about your symptoms and their impact.",
                "Keep copies of all submitted documents and correspondence with the VA.",
                "Consider seeking assistance from a Veterans Service Organization (VSO) for guidance throughout the process.",
                "Be prepared for the possibility of appeals and stay informed about the status of your claim."
            ],
            "howToContestClaim": "If your claim is denied or you disagree with the rating assigned, you have the right to appeal. The appeals process includes several options:\n1. Supplemental Claim: Submit new and relevant evidence.\n2. Higher-Level Review: Request a review by a senior VA employee.\n3. Board Appeal: Appeal directly to the Board of Veterans' Appeals.\nTo contest a claim:\n1. Review your decision letter carefully to understand the reason for the denial or rating.\n2. Gather any new and relevant evidence that addresses the reason for denial.\n3. Consider obtaining additional medical opinions or nexus letters.\n4. File the appropriate appeal form within the specified timeframe (usually one year from the date of the decision letter).\n5. Consider seeking assistance from a VSO or attorney specializing in VA law.\n6. Be prepared to provide additional statements or attend further examinations if required.\n7. Stay informed about the status of your appeal and respond promptly to any requests for information from the VA.",
            "otherPossibleBenefits": [
                "VA Health Care",
                "Vocational Rehabilitation and Employment (VR&E)",
                "Veterans Pension",
                "Aid and Attendance",
                "VA Home Loan Guarantee",
                "Veterans' Group Life Insurance (VGLI)",
                "Dependents' Educational Assistance",
                "Automobile Allowance and Adaptive Equipment",
                "Veterans' Preference in Federal Employment",
                "State Veterans Benefits",
                "Vet Center Services",
                "Caregiver Support"
            ],
            "glossary": [
                {"term": "VA", "definition": "The Department of Veterans Affairs, a government agency responsible for providing vital services to America's veterans."},
                {"term": "C&P Exam", "definition": "Compensation and Pension Exam, a medical examination used by the VA to evaluate the severity of a veteran's disability."},
                {"term": "Nexus Letter", "definition": "A letter from a medical professional that links a veteran's current medical condition to their military service."},
                {"term": "Service Connection", "definition": "The establishment of a direct link between a veteran's current disability and their military service."},
                {"term": "Disability Rating", "definition": "A percentage assigned by the VA that represents the severity of a veteran's disability and determines the amount of compensation."},
                {"term": "VSO", "definition": "Veterans Service Organization, a group that provides free assistance to veterans in filing and appealing VA claims."},
                {"term": "Appeal", "definition": "The process by which a veteran can challenge a VA decision on their claim."},
                {"term": "Supplemental Claim", "definition": "A type of appeal where a veteran submits new and relevant evidence to support their claim."},
                {"term": "Higher-Level Review", "definition": "A type of appeal where a more senior VA employee reviews the veteran's claim without considering new evidence."},
                {"term": "Board Appeal", "definition": "An appeal directly to the Board of Veterans' Appeals, which can include a hearing before a Veterans Law Judge."},
                {"term": "VA Form 21-526EZ", "definition": "The form used by veterans to apply for disability compensation and related benefits."},
                {"term": "Buddy Statement", "definition": "A statement from a fellow service member or family member that supports a veteran's claim by providing additional evidence or context."},
                {"term": "VA Health Care", "definition": "Medical services provided by the VA to eligible veterans."},
                {"term": "Vocational Rehabilitation and Employment (VR&E)", "definition": "A VA program that helps veterans with service-connected disabilities prepare for, find, and maintain suitable employment."},
                {"term": "Aid and Attendance", "definition": "An additional benefit paid to veterans, their spouses, or surviving spouses who require the aid and attendance of another person."},
                {"term": "VA Home Loan Guarantee", "definition": "A VA benefit that helps veterans, service members, and eligible surviving spouses become homeowners by providing a home loan guarantee."},
                {"term": "Veterans' Group Life Insurance (VGLI)", "definition": "A program that allows veterans to convert their Servicemembers' Group Life Insurance (SGLI) to renewable term insurance."},
                {"term": "Dependents' Educational Assistance", "definition": "A VA program that provides education and training opportunities to eligible dependents of veterans."},
                {"term": "Automobile Allowance and Adaptive Equipment", "definition": "A benefit that provides a one-time payment to help veterans with certain disabilities purchase a specially equipped vehicle."},
                {"term": "Veterans' Preference in Federal Employment", "definition": "A policy that gives eligible veterans preference in hiring for federal jobs."},
                {"term": "State Veterans Benefits", "definition": "Benefits provided by individual states to veterans, which can include education, employment, and health care services."},
                {"term": "Vet Center Services", "definition": "Community-based counseling centers that provide a wide range of social and psychological services to eligible veterans and their families."},
                {"term": "Caregiver Support", "definition": "VA programs that offer support to family caregivers of veterans, including education, resources, and in some cases, financial assistance."}
            ]
        }

    async def send_report(self, final_report: Dict[str, Any]) -> None:
        serialized_report = json.dumps(final_report, indent=4)
        
        user_id = self.context_info.context['user_context']['user_id']
        
        open(f'report-{user_id}.json', 'w').write(serialized_report)
        
        Supabase.supabase.table('reports').update({"report": serialized_report, "status": "created"}).eq({"user_id": user_id}).execute()
        
        await self.kafka.send_message('task_completed', {
            "sessionId": self.session_id,
            "task_id": self.id,
            "response": serialized_report
        })

    async def execute_task(self, task: TaskInfo, context: Dict[str, Any]):
        try:
            serialized_context = self.serialize_context(context)
            message = task.message_template.format(**serialized_context)
            
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
            logger.info(f"Completed {task.name}")
            
            return {task.result_key: result}
        except Exception as e:
            logger.error(f"Error executing {task.name}: {str(e)}")
            return {}

    def serialize_context(self, obj: Any) -> Any:
        if isinstance(obj, dict):
            return {k: self.serialize_context(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self.serialize_context(item) for item in obj]
        elif isinstance(obj, (str, int, float, bool, type(None))):
            return obj
        else:
            return str(obj)

    async def create_agent_and_get_completion(self, task_config):
        agent_class = task_config['agent_class']
        agent = agent_class(
            name=task_config['name'],
            tools=task_config['tools'],
            context_info=self.context_info,
            files_folder=task_config.get('files_folder', None)
        )
        
        agency = Agency(agency_chart=[agent], shared_instructions=task_config['shared_instructions'])
        
        completion = await agency.get_completion(task_config['message'])
        
        result = agent.context_info.context.get(task_config['result_key'], None)
        #completion = await agent.get_completion(task_config['message'])
        logger.debug(f"Context after completion: {json.dumps(self.context_info.context, indent=2)}")
        
        if result:
            return result
        else:
            logger.warning(f"Result not found in context for {task_config['name']}")
            logger.info(f"Available keys in context: {list(self.context_info.context.keys())}")
            logger.info(f"Completion is not a dict, returning it directly for {task_config['name']}")
            return completion

    @classmethod
    async def create(cls, **task_data):
        logger.info(f"Creating new task with data: {task_data}")

        required_fields = ['id', 'description', 'context_info']
        for field in required_fields:
            if field not in task_data:
                raise ValueError(f"Missing required field: {field}")

        if not isinstance(task_data['context_info'], ContextInfo):
            task_data['context_info'] = ContextInfo(**task_data['context_info'])

        task = cls(**task_data)

        if 'batch_size' in task_data:
            task.batch_size = task_data['batch_size']
        
        logger.info(f"Task created with ID: {task.id}, User ID: {task.user_id}, Batch Size: {task.batch_size}")
        return task

    @classmethod
    async def handle(cls, key, action, object_data, context):
        from app.services.context.context_manager import ContextManager
        from containers import get_container
        
        context_manager: ContextManager = get_container().context_manager()
        
        if action == 'initialize':
            task = await cls.create(**object_data)
        else:
            task = await context_manager.get_context(key)
            task.context_info.context.update(await context_manager.get_merged_context(context))
        
        await task.process_action(action)
    
    async def process_action(self, action):
        if action == 'initialize':
            await self.execute()