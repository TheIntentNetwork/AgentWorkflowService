from datetime import datetime
import json
import logging
import traceback
from pydantic import Field
from typing import Dict, Any, List, ClassVar, Literal, Union
from app.tools.base_tool import BaseTool
from app.logging_config import configure_logger
from app.services.supabase.supabase import Supabase, Client
from app.models.Report import (
    Report, Condition, Letter, Checklist, MentalCAndPTips,
    OnlineFilingGuide, FullLetter, FAQ, GlossaryItem, ResearchItem,
    Point, FutureConsideration
)
import uuid

class CompileDocument(BaseTool):
    """
    Tool for compiling and updating report documents by collecting metadata from context
    and constructing a validated Report object. Supports both full and partial updates.
    """
    result_keys: ClassVar[List[str]] = ['final_document']
    mode: Union[Literal['draft'], Literal['publish']] = Field(..., description="The mode of the document to be compiled")

    async def _collect_conditions_data(self, context: Dict[str, Any], condition_names: List[str] = None) -> List[Condition]:
        """
        Helper method to collect conditions data
        
        Args:
            context: The context dictionary containing conditions data
            condition_names: Optional list of specific condition names to filter by
        """
        self._logger.info(f"Collecting conditions data with context: {context}")
        
        try:
            # Log initial context keys
            self._logger.debug(f"Available context keys: {context.keys()}")
            
            # Handle both string and list inputs for conditions
            conditions_raw = context.get('conditions', '[]')
            self._logger.debug(f"Raw conditions data type: {type(conditions_raw)}")
            self._logger.debug(f"Raw conditions data: {conditions_raw}")
            
            all_conditions = (
                json.loads(conditions_raw) 
                if isinstance(conditions_raw, str) 
                else conditions_raw
            )
            
            if isinstance(all_conditions, bytes):
                all_conditions = json.loads(all_conditions.decode('utf-8'))
            
            self._logger.debug(f"Parsed conditions: {all_conditions}")
            
            # Filter conditions if specific ones are requested
            conditions_to_process = [c for c in all_conditions]            # Ensure all required fields are included when creating ResearchItem instances
            research_section = []
            if context.get('research_sections'):
                research_data = context['research_sections']
                self._logger.debug(f"Research data: {research_data}")
            
                if isinstance(research_data, bytes):
                    research_data = research_data.decode('utf-8')
                if isinstance(research_data, str):
                    research_data = json.loads(research_data)
                self._logger.debug(f"Parsed research data: {research_data}")
            
                if isinstance(research_data, list):
                    research_section = [
                        ResearchItem(
                            researchTitle=item.get('researchTitle', 'Default Title'),
                            authorName=item.get('authorName', 'Unknown Author'),
                            researchUrl=item.get('researchUrl', 'http://example.com'),
                            summaryOfResearch=item.get('summaryOfResearch', 'No summary available')
                        )
                        for item in research_data
                        if item.get('condition_name') == condition_name
                    ]
            
            self._logger.debug(f"Processing {len(conditions_to_process)} conditions")

            for condition in conditions_to_process:
                condition_name = condition['condition_name']
                self._logger.debug(f"Processing condition: {condition_name}")
                
                # Collect research sections
                research_section = []
                if context.get('research_sections'):
                    research_data = context['research_sections']
                    self._logger.debug(f"Research data type: {type(research_data)}")
                    
                    if isinstance(research_data, bytes):
                        research_data = research_data.decode('utf-8')
                    if isinstance(research_data, str):
                        research_data = json.loads(research_data)
                        
                    self._logger.debug(f"Research data for {condition_name}: {research_data}")
                    
                    if isinstance(research_data, list):
                        research_section = [
                            ResearchItem(
                                condition_name=condition_name,
                                researchTitle=item.get('researchTitle', 'Default Title'),
                                authorName=item.get('authorName', 'Unknown Author'),
                                researchUrl=item.get('researchUrl', 'http://example.com'),
                                summaryOfResearch=item.get('summaryOfResearch', 'No summary available')
                            )
                            for item in research_data
                            if item.get('condition_name') == condition_name
                        ]
                    self._logger.debug(f"Research items for {condition_name}: {research_section}")
    
                # Collect CFR points
                cfr_points = []
                if context.get('cfr_tips'):
                    cfr_data = context['cfr_tips']
                    self._logger.debug(f"CFR data type: {type(cfr_data)}")
                    
                    if isinstance(cfr_data, bytes):
                        cfr_data = cfr_data.decode('utf-8')
                    if isinstance(cfr_data, str):
                        cfr_data = json.loads(cfr_data)
                        
                    self._logger.debug(f"CFR data for {condition_name}: {cfr_data}")
                    
                    if isinstance(cfr_data, list):
                        cfr_points = [
                            Point(**point) 
                            for point in cfr_data
                            if point.get('condition_name') == condition_name
                        ]
                    self._logger.debug(f"Found {len(cfr_points)} CFR points for {condition_name}")
    
                # Collect key points
                key_points = []
                if context.get('key_points'):
                    key_points_data = context['key_points']
                    self._logger.debug(f"Key points data type: {type(key_points_data)}")
                    
                    if isinstance(key_points_data, bytes):
                        key_points_data = key_points_data.decode('utf-8')
                    if isinstance(key_points_data, str):
                        key_points_data = json.loads(key_points_data)
                        
                    self._logger.debug(f"Key points data for {condition_name}: {key_points_data}")
                    
                    if isinstance(key_points_data, list):
                        key_points = [
                            Point(**point) 
                            for point in key_points_data 
                            if point.get('condition_name') == condition_name
                        ]
                    self._logger.debug(f"Found {len(key_points)} key points for {condition_name}")
    
                # Collect future considerations
                future_considerations = []
                if context.get('future_considerations'):
                    future_data = context['future_considerations']
                    self._logger.debug(f"Future considerations data type: {type(future_data)}")
                    
                    if isinstance(future_data, bytes):
                        future_data = future_data.decode('utf-8')
                    if isinstance(future_data, str):
                        future_data = json.loads(future_data)
                        
                    self._logger.debug(f"Future considerations data for {condition_name}: {future_data}")
                    
                    if isinstance(future_data, list):
                        future_considerations = [
                            FutureConsideration(**item) 
                            for item in future_data 
                            if item.get('condition_name') == condition_name
                        ]
                    self._logger.debug(f"Found {len(future_considerations)} future considerations for {condition_name}")
                    
                    # Ensure all required fields are included when creating ResearchItem instances
                    research_section = []
                    if context.get('research_sections'):
                        research_data = context['research_sections']
                        self._logger.debug(f"Research data: {research_data}")
                    
                        if isinstance(research_data, bytes):
                            research_data = research_data.decode('utf-8')
                        if isinstance(research_data, str):
                            research_data = json.loads(research_data)
                        self._logger.debug(f"Parsed research data: {research_data}")
                    
                        if isinstance(research_data, list):
                            research_section = [
                                ResearchItem(
                                    condition_name=condition_name,
                                    researchTitle=item.get('researchTitle', 'Default Title'),  # Ensure researchTitle is provided
                                    research_items=item.get('research_items', [])
                                )
                                for item in research_data
                                if item.get('condition_name') == condition_name
                            ]
                        self._logger.debug(f"Research items for {condition_name}: {research_section}")
                    self._logger.debug(f"Found {len(future_considerations)} future considerations for {condition_name}")
    
                # Collect executive summary
                exec_summary = ""
                if context.get('condition_executive_summary'):
                    try:
                        summary_data = context['condition_executive_summary']
                        self._logger.debug(f"Executive summary data type: {type(summary_data)}")
                        
                        if isinstance(summary_data, bytes):
                            summary_data = summary_data.decode('utf-8')
                        if isinstance(summary_data, str):
                            summary_data = json.loads(summary_data)
                            
                        self._logger.debug(f"Executive summary data for {condition_name}: {summary_data}")
                        
                        if isinstance(summary_data, dict) and summary_data.get('condition_name') == condition_name:
                            exec_summary = summary_data.get('executive_summary', '')
                        self._logger.debug(f"Found executive summary for {condition_name}: {bool(exec_summary)}")
                    except json.JSONDecodeError:
                        self._logger.warning(f"Could not decode executive summary for condition {condition_name}")
    
                # Create condition object
                condition_obj = Condition(
                    executive_summary="Hello",
                    condition_name=condition_name,
                    research_section=[ResearchItem(researchTitle=condition_name, authorName='test', researchUrl='test', summaryOfResearch='test'), ResearchItem(researchTitle=condition_name, authorName='test', researchUrl='test', summaryOfResearch='test')],
                    PointsFor38CFR=[Point(pointTitle='test', point='test'), Point(pointTitle='test', point='test')],
                    key_points=[Point(pointTitle='test', point='test'), Point(pointTitle='test', point='test')],
                    future_considerations=[FutureConsideration(considerationTitle='test', consideration='test'), FutureConsideration(considerationTitle='test', consideration='test')],
                )
                
                self._logger.debug(f"""
                Final data collected for condition {condition_name}:
                - Research sections: {len(research_section)}
                - CFR points: {len(cfr_points)}
                - Key points: {len(key_points)}
                - Future considerations: {len(future_considerations)}
                - Has executive summary: {bool(exec_summary)}
                """)
                
                conditions_data.append(condition_obj)
    
        except Exception as e:
            self._logger.error(f"Error collecting conditions data: {e}")
            self._logger.error(traceback.format_exc())
            raise
    
        return conditions_data

    async def _collect_letters(self, context: Dict[str, Any], letter_type: str) -> List[Letter]:
        """Helper method to collect letters by type"""
        letters = []
        if context.get(letter_type):
            letters_data = json.loads(context[letter_type])
            if isinstance(letters_data, list):
                letters = [Letter(**letter) for letter in letters_data]
        return letters

    async def _get_existing_report(self, client: Client, user_id: str) -> Dict[str, Any]:
        """
        Helper method to get existing report from database.
        Returns both the report data and its ID.
        """
        result = client.from_("decrypted_reports").select("id, decrypted_report").eq("user_id", user_id).single().execute()
        if not result.data:
            return None
        
        report_data = json.loads(result.data['decrypted_report'])
        return {
            'data': report_data,
            'id': result.data['id']
        }

    async def run(self) -> Dict[str, Any]:
        """
        Run the document compilation tool.
        
        Args:
            Possible values: ['conditions', 'personal_statements', 'nexus_letters', 'static_sections', 
                            'executive_summary']
                            
        Returns:
            Dict containing:
                - status: Success status
                - report_id: ID of the saved report
                - final_document: Complete report document fetched from database after update
        """
        self._logger.info("Running CompileDocument tool")
        try:
            context = self._caller_agent.context_info.context
            user_id = context['user_id']
            
            # Validate user_id format
            try:
                uuid.UUID(user_id)
            except ValueError:
                self._logger.error(f"Invalid UUID format for user_id: {user_id}")
                raise ValueError("Invalid UUID format for user_id")
            
            client: Client = Supabase.supabase

            # Get existing report if it exists
            existing_report_wrapper = await self._get_existing_report(client, user_id)
            current_report = Report(**existing_report_wrapper['data']) if existing_report_wrapper else None
            report_id = existing_report_wrapper['id'] if existing_report_wrapper else None

            # Initialize new report with existing data or empty
            report_data = current_report.dict() if current_report else {}

            # Update conditions if needed
            if any(key in context for key in ['research_sections', 'cfr_tips', 'key_points', 'future_considerations', 'executive_summary']):
                conditions_data = await self._collect_conditions_data(context)
                report_data['conditions'] = conditions_data

            # Update letters if needed
            if 'personal_statements' in context:
                report_data['personalStatementLetters'] = await self._collect_letters(context, 'personal_statements')

            if 'nexus_letters' in context:
                report_data['nexusLetters'] = await self._collect_letters(context, 'nexus_letters')

            # Handle static sections
            if 'static_sections' in context:
                # Handle both string and list inputs for conditions
                conditions_raw = context.get('conditions', '[]')
                self._logger.debug(f"Raw conditions data type: {type(conditions_raw)}")
                self._logger.debug(f"Raw conditions data: {conditions_raw}")
                
                all_conditions = (
                    json.loads(conditions_raw) 
                    if isinstance(conditions_raw, str) 
                    else conditions_raw
                )
                
                if isinstance(all_conditions, bytes):
                    all_conditions = json.loads(all_conditions.decode('utf-8'))
                
                self._logger.debug(f"Parsed conditions: {all_conditions}")
                
                # Filter conditions if specific ones are requested
                conditions_to_process = [c for c in all_conditions]
                
                # Ensure all required fields are included when creating ResearchItem instances
                research_section = []
                if context.get('research_sections'):
                    research_data = context['research_sections']
                    self._logger.debug(f"Research data: {research_data}")
                
                    if isinstance(research_data, bytes):
                        research_data = research_data.decode('utf-8')
                    if isinstance(research_data, str):
                        research_data = json.loads(research_data)
                    self._logger.debug(f"Parsed research data: {research_data}")
                
                    if isinstance(research_data, list):
                        research_section = [
                            ResearchItem(
                                researchTitle=item.get('researchTitle', 'Default Title'),
                                authorName=item.get('authorName', 'Unknown Author'),
                                researchUrl=item.get('researchUrl', 'http://example.com'),
                                summaryOfResearch=item.get('summaryOfResearch', 'No summary available')
                            )
                            for item in research_data
                        ]
                    self._logger.debug(f"Research items: {research_section}")
                try:
                    # Handle bytes or string input
                    static_sections_raw = context.get('static_sections', '{}')
                    if isinstance(static_sections_raw, bytes):
                        static_sections_raw = static_sections_raw.decode('utf-8')
                    
                    # Parse JSON if needed
                    static_sections = (
                        json.loads(static_sections_raw)
                        if isinstance(static_sections_raw, str)
                        else static_sections_raw
                    )
                    
                    self._logger.debug(f"Parsed static sections type: {type(static_sections)}")
                    self._logger.debug(f"Static sections content: {static_sections}")
                    
                    # Update static sections selectively
                    if isinstance(static_sections, dict):
                        if 'checklist' in static_sections:
                            checklist_data = static_sections['checklist']
                            report_data['checklist'] = Checklist(**checklist_data)
                        
                        if 'mental_c_and_p_tips' in static_sections:
                            tips_data = static_sections['mental_c_and_p_tips']
                            report_data['mentalCAndPTips'] = MentalCAndPTips(**tips_data)
                        
                        if 'online_filing_guide' in static_sections:
                            guide_data = static_sections['online_filing_guide']
                            report_data['onlineFilingGuide'] = OnlineFilingGuide(**guide_data)
                        
                        if 'letter' in static_sections:
                            letter_data = static_sections['letter']
                            report_data['letter'] = FullLetter(**letter_data)
                        
                        if 'faqs' in static_sections:
                            faq_data = static_sections['faqs']
                            report_data['faqs'] = [FAQ(**item) for item in faq_data]
                        
                        if 'glossary' in static_sections:
                            glossary_data = static_sections['glossary']
                            report_data['glossary'] = [GlossaryItem(**item) for item in glossary_data]
                    else:
                        self._logger.warning(f"static_sections is not a dictionary: {type(static_sections)}")
                        
                except json.JSONDecodeError as e:
                    self._logger.error(f"Error parsing static_sections: {e}")
                    self._logger.error(f"Raw static_sections: {context.get('static_sections')}")
                except Exception as e:
                    self._logger.error(f"Error processing static_sections: {e}")
                    self._logger.error(traceback.format_exc())

            # Handle executive summary
            if 'report_summary' in context:
                try:
                    summary_raw = context.get('report_summary', '[]')
                    if isinstance(summary_raw, bytes):
                        summary_raw = summary_raw.decode('utf-8')
                    report_data['executive_summary'] = json.loads(summary_raw)
                except Exception as e:
                    self._logger.error(f"Error processing executive_summary: {e}")
                    self._logger.error(traceback.format_exc())

            # Construct updated report
            updated_report = Report(**report_data)

            # Save to database
            record = {
                "user_id": user_id,
                "report": json.dumps(updated_report.dict()),
                "updated_at": datetime.now().isoformat()
            }
            
            if self.mode == 'publish':
                if report_id:
                    result = client.from_("reports").update(record).eq("id", report_id).execute()
                else:
                    result = client.from_("reports").insert(record).execute()
                    report_id = result.data[0]['id']
                    
                    # Fetch the complete document after update
                    final_result = client.from_("decrypted_reports").select("decrypted_report").eq("id", report_id).single().execute()
                    final_document = json.loads(final_result.data['decrypted_report']) if final_result.data else None
                
            
            final_document = updated_report.dict()

            self._logger.info(f"Successfully updated report sections for user {user_id}")
            
            self._caller_agent.context_info.context["final_document"] = final_document
            
            return {
                "status": "success",
                "report_id": report_id,
                "final_document": final_document  # Complete document fetched from database
            }

        except Exception as e:
            self._logger.error(f"Error compiling document: {e}")
            self._logger.error(traceback.format_exc())
            raise
