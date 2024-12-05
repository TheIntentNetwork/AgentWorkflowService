from datetime import datetime
import json
import traceback
from pydantic import Field
from typing import ClassVar, Dict, Any, List
from app.tools.base_tool import BaseTool
from app.logging_config import configure_logger
from app.services.supabase.supabase import Supabase, Client
from app.models.Report import (
    ChecklistSection, LetterClosing, MentalCAndPSection, Report, Checklist, MentalCAndPTips, OnlineFilingGuide,
    FullLetter, FAQ, GlossaryItem, FilingStep, Resource
)

class SaveToStaticSections(BaseTool):
    """
    Tool for saving static sections to context.
    Uses predefined default values that cannot be modified.
    The data will be used by CompileDocument to construct the final report.
    """
    result_keys: ClassVar[List[str]] = ['static_sections']

    # Standard Operating Procedure
    _standardOperatingProcedure: ClassVar[List[str]] = [
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
    ]

    # Checklist
    _checklist: ClassVar[Checklist] = Checklist(
        title="VA Disability Claim Checklist",
        sections=[
            ChecklistSection(
                title="Diagnosis & Medical Evidence",
                items=[
                    "Obtain a current diagnosis from a doctor (VA, military, or private).",
                    "Collect all relevant medical records (Service Treatment Records, VA records, private records).",
                    "Consider getting a Nexus Letter from a private provider if not diagnosed during service."
                ],
                tips=[]
            ),
            ChecklistSection(
                title="Proof of Service Connection (Nexus)",
                items=[
                    "Ensure your condition is service-connected (caused or worsened by service).",
                    "Collect buddy letters from people who can confirm your condition and in-service events, if possible."
                ],
                tips=[]
            ),
            ChecklistSection(
                title="Severity & Impact",
                items=[
                    "Write a personal statement detailing how your condition affects your daily life, work, and social interactions.",
                    "Complete VA Form 21-4138 (Statement in Support of Claim)."
                ],
                tips=[]
            )
        ]
    )

    # Mental C&P Tips
    _mentalCAndPTips: ClassVar[MentalCAndPTips] = MentalCAndPTips(
        title="Mental Health C&P Exam Tips",
        sections=[
            MentalCAndPSection(
                title="Before the Exam",
                tips=[
                    "Review your symptoms and their impact on your daily life",
                    "Prepare specific examples of how your condition affects you",
                    "Bring any relevant documentation"
                ]
            ),
            MentalCAndPSection(
                title="During the Exam",
                tips=[
                    "Be honest about your worst days",
                    "Provide specific examples",
                    "Don't downplay your symptoms"
                ]
            )
        ]
    )

    # Online Filing Guide
    _onlineFilingGuide: ClassVar[OnlineFilingGuide] = OnlineFilingGuide(
        title="VA.gov Online Filing Guide",
        introduction="A step-by-step guide to filing your VA disability claim online",
        steps=[
            FilingStep(
                title="Account Access",
                description="Create or sign in to your VA.gov account",
                resources=[
                    Resource(name="VA.gov Login Guide", url="https://www.va.gov/resources/login-guide"),
                    Resource(name="Account Creation Tutorial", url="https://www.va.gov/resources/create-account")
                ]
            ),
            FilingStep(
                title="Navigate to Claims",
                description="Navigate to the disability section",
                resources=[
                    Resource(name="VA Claims Portal Guide", url="https://www.va.gov/resources/claims-portal"),
                    Resource(name="Navigation Help", url="https://www.va.gov/resources/navigation")
                ]
            ),
            FilingStep(
                title="Start New Claim",
                description="Select 'File a claim for compensation'",
                resources=[
                    Resource(name="Claim Types Guide", url="https://www.va.gov/resources/claim-types"),
                    Resource(name="Filing Instructions", url="https://www.va.gov/resources/filing")
                ]
            ),
            FilingStep(
                title="Complete Process",
                description="Follow the step-by-step process",
                resources=[
                    Resource(name="Form Completion Guide", url="https://www.va.gov/resources/form-guide"),
                    Resource(name="Documentation Checklist", url="https://www.va.gov/resources/checklist")
                ]
            ),
            FilingStep(
                title="Submit Documentation",
                description="Upload all supporting documentation",
                resources=[
                    Resource(name="Document Upload Guide", url="https://www.va.gov/resources/upload-guide"),
                    Resource(name="File Format Requirements", url="https://www.va.gov/resources/file-formats")
                ]
            )
        ],
        additionalResources=[
            Resource(
                name="VA Help Center",
                url="https://www.va.gov/help/"
            ),
            Resource(
                name="Tech Support",
                url="https://www.va.gov/contact-us/"
            )
        ]
    )

    # Letter Template
    _letter: ClassVar[FullLetter] = FullLetter(
        salutation="Dear Veterans Affairs Representative,",
        paragraphs=[
            "I am writing to formally submit my VA disability claim.",
            "Please find all supporting documentation attached to this submission."
        ],
        closing=LetterClosing(
            message="Thank you for your consideration of this claim.",
            signature="[Veteran's Name]\n[Veteran's ID Number]",
            title="Veteran"
        )
    )

    # FAQs
    _faqs: ClassVar[List[FAQ]] = [
        FAQ(
            question="How long does the claims process take?",
            answer="The VA's goal is to complete claims within 125 days, but processing times can vary."
        ),
        FAQ(
            question="What if my claim is denied?",
            answer="You have the right to appeal the decision through various channels, including supplemental claims and appeals to the Board."
        )
    ]

    # How to Contest Claim
    _howToContestClaim: ClassVar[str] = """
    If your claim is denied, you have several options:
    1. File a Supplemental Claim with new evidence
    2. Request a Higher-Level Review
    3. Appeal to the Board of Veterans' Appeals
    """

    # Other Possible Benefits
    _otherPossibleBenefits: ClassVar[List[str]] = [
        "VA Health Care",
        "VA Education Benefits",
        "VA Home Loan",
        "Life Insurance",
        "Vocational Rehabilitation"
    ]

    # Glossary
    _glossary: ClassVar[List[GlossaryItem]] = [
        GlossaryItem(
            term="C&P Exam",
            definition="Compensation and Pension examination - a medical assessment to evaluate disability claims"
        ),
        GlossaryItem(
            term="Nexus",
            definition="The connection between a current disability and military service"
        )
    ]

    # VA Benefit Ratings Criteria
    _vaBenefitRatingsCriteria: ClassVar[str] = """
    VA disability ratings are assigned in 10% increments from 0% to 100%.
    The rating is based on the severity of your condition and its impact on your ability to work and perform daily activities.
    """

    async def run(self) -> Dict[str, Any]:
        logger = configure_logger('SaveToStaticSections')
        logger.info("Running SaveToStaticSections tool")
        
        try:
            static_sections = {
                "standardOperatingProcedure": self._standardOperatingProcedure,
                "checklist": self._checklist.dict(),
                "mentalCAndPTips": self._mentalCAndPTips.dict(),
                "onlineFilingGuide": self._onlineFilingGuide.dict(),
                "letter": self._letter.dict(),
                "faqs": [faq.dict() for faq in self._faqs],
                "howToContestClaim": self._howToContestClaim,
                "otherPossibleBenefits": self._otherPossibleBenefits,
                "glossary": [item.dict() for item in self._glossary],
                "vaBenefitRatingsCriteria": self._vaBenefitRatingsCriteria,
                "last_updated": datetime.now().isoformat()
            }
            
            self._caller_agent.context_info.context["static_sections"] = json.dumps(
                static_sections,
                skipkeys=True,
                default=str
            )

            return json.dumps(static_sections)

        except Exception as e:
            logger.error(f"Error in SaveToStaticSections: {e}")
            logger.error(traceback.format_exc())
            raise
