from datetime import datetime
import json
import traceback
from pydantic import Field
from typing import Dict, Any, List
from app.tools.base_tool import BaseTool
from app.logging_config import configure_logger
from app.services.supabase.supabase import Supabase, Client
from app.models.Report import (
    ChecklistSection, LetterClosing, MentalCAndPSection, Report, Checklist, MentalCAndPTips, OnlineFilingGuide,
    FullLetter, FAQ, GlossaryItem
)

class SaveToStaticSections(BaseTool):
    """
    Tool for writing and saving static sections to the user's report.
    Updates all static sections while preserving condition-specific data.
    """
    standardOperatingProcedure: List[str] = Field(
        default=[
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
        description="Standard operating procedures for VA claims"
    )
    
    checklist: Checklist = Field(
        default=Checklist(
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
                ),
                ChecklistSection(
                    title="Preparing for the C&P Exam",
                    items=[
                        "Review your medical records and know your conditions.",
                        "Bring a copy of all documents (records, Nexus Letters, personal statements) to the exam.",
                        "Be prepared to describe your worst days truthfully during the exam."
                    ],
                    tips=[
                        "Do not exaggerate or minimize your symptoms. Be specific and honest."
                    ]
                ),
                ChecklistSection(
                    title="Filing Your Claim",
                    items=[
                        "Visit VA.gov and start your claim. Consider opening a Notice of Intent to File to lock in your effective date.",
                        "Choose to submit a Fully Developed Claim (FDC) for faster processing.",
                        "Upload all supporting evidence when filing (diagnosis, Nexus Letters, personal statements, buddy letters)."
                    ],
                    tips=[
                        "A VSO (Veteran Service Officer) can file your claim for you for free if you prefer not to file it yourself."
                    ]
                ),
                ChecklistSection(
                    title="After Filing",
                    items=[
                        "Monitor your claim status on VA.gov or by calling the VA.",
                        "Respond quickly to any VA requests for additional information.",
                        "If denied, explore options like a Higher Level Review or Supplemental Claim."
                    ],
                    tips=[]
                ),
                ChecklistSection(
                    title="Key Reminders",
                    items=[
                        "Keep a copy of everything you submit.",
                        "Provide updated medical evidence if applying for an increase.",
                        "Stay proactive and follow up regularly until your claim is resolved."
                    ],
                    tips=[]
                )
            ]
        ),
        description="Checklist for VA claim process"
    )
    
    mentalCAndPTips: MentalCAndPTips = Field(
        default=MentalCAndPTips(
            sections=[
                MentalCAndPSection(
                    title="Worst Moment with Friends or Family:",
                    tips=["(Think of a time your mental health made it hard to get along with others. This could be arguments, feeling left out, or not wanting to be around people.)"]
                ),
                MentalCAndPSection(
                    title="Biggest Trouble at Work:",
                    tips=["(Remember a time when your mental health made it hard to do your job. This could be having trouble finishing tasks, missing work, or problems with coworkers. If retired, list how it WOULD affect your work if you decided to work again.)"]
                ),
                MentalCAndPSection(
                    title="Worst Mental Health Moment:",
                    tips=["(Think of the most difficult mental health symptom youve had. This could be feeling very sad, very worried, or having panic attacks.)"]
                )
            ]
        ),
        description="Mental health C&P exam tips"
    )
    
    letter: FullLetter = Field(
        default=FullLetter(
            salutation="Dear Veteran,",
            paragraphs=[
                "I hope this letter finds you well. As the founder of VA Claims Academy and a fellow veteran, I understand the challenges you may be facing in navigating the VA claims process. I want to personally encourage you to persist in your efforts to secure the benefits you've rightfully earned through your service.",
                "Your dedication and sacrifice to our nation are immeasurable, and it's crucial that you receive the support and recognition you deserve. The claims process can be complex, but please know that you're not alone in this journey. Our team at VA Claims Academy is here to support and guide you every step of the way.",
                "Remember, pursuing your VA claim is not just about the benefits; it's about acknowledging your service and ensuring you have access to the resources you need for a fulfilling life post-service. Your perseverance in this process is a continuation of the strength you've already demonstrated in your military career.",
                "Don't hesitate to reach out if you need assistance or have any questions. We're committed to empowering veterans like you with the knowledge and tools necessary to navigate the VA system successfully."
            ],
            closing=LetterClosing(
                message="Wishing you all the best in your claims process and beyond.",
                signature="Jordan Anderson",
                title="VA Claims Academy"
            )
        ),
        description="Standard letter format"
    )
    
    onlineFilingGuide: OnlineFilingGuide = Field(
        default=OnlineFilingGuide(
            title="Guide to Filing a VA Disability Claim Online",
            introduction="This guide provides step-by-step instructions to help you file a VA disability claim online.",
            steps=[
                {
                    "title": "Step 1: Prepare Your Documents",
                    "description": "Gather all necessary documents such as medical records, service records, and any other evidence that supports your claim.",
                    "resources": [
                        {
                            "name": "Evidence Needed for Your Disability Claim",
                            "url": "https://www.va.gov/disability/how-to-file-claim/evidence-needed/"
                        }
                    ]
                },
                {
                    "title": "Step 2: Visit the VA Website",
                    "description": "Go to the official VA website to begin the claim process.",
                    "resources": [
                        {
                            "name": "VA Disability Compensation",
                            "url": "https://www.va.gov/disability/"
                        }
                    ]
                },
                {
                    "title": "Step 3: Sign In or Create an Account",
                    "description": "Sign in using your existing VA.gov account or create a new one if you don't have it.",
                    "resources": [
                        {
                            "name": "VA.gov Sign-In",
                            "url": "https://www.va.gov/sign-in/"
                        }
                    ]
                },
                {
                    "title": "Step 4: Start Your Application",
                    "description": "Navigate to the disability compensation section and click on 'File a Claim' to start your application.",
                    "resources": [
                        {
                            "name": "How to File a Disability Claim",
                            "url": "https://www.va.gov/disability/how-to-file-claim/"
                        }
                    ]
                },
                {
                    "title": "Step 5: Complete the Application Form",
                    "description": "Fill out all required fields accurately, including personal information, service details, and medical conditions.",
                    "resources": []
                }
            ],
            additionalResources=[
                {
                    "name": "VA Disability Compensation",
                    "url": "https://www.va.gov/disability/"
                },
                {
                    "name": "How to File a Disability Claim",
                    "url": "https://www.va.gov/disability/how-to-file-claim/"
                }
            ],
        ),
        description="Guide for filing claims online"
    )

    faqs: List[FAQ] = Field(
        default=[
            FAQ(
                question="How does the VA determine my disability rating?",
                answer="The VA determines disability ratings based on the severity of your condition and how it impacts your daily life and ability to work. Ratings are assigned in 10% increments, with higher percentages indicating more severe impairment."
            ),
            FAQ(
                question="Can conditions be considered service-connected even if they started after I left the military?", 
                answer="Yes, conditions can be considered service-connected even if they started after leaving the military, as long as there's evidence linking them to your service. A nexus letter from a medical professional can help establish this connection."
            ),
            FAQ(
                question="What should I include in my personal statement for my VA claim?",
                answer="Your personal statement should include details about how your condition developed during or as a result of your service, how it affects your daily life, and any specific incidents or experiences that may have contributed to your condition."
            ),
            FAQ(
                question="How can I increase my chances of a successful VA claim?",
                answer="To increase your chances of a successful claim, gather comprehensive medical records, obtain buddy statements, secure nexus letters from healthcare providers, and provide detailed personal statements about how your conditions impact your daily life and work."
            ),
            FAQ(
                question="What is a C&P exam, and how should I prepare for it?",
                answer="A C&P (Compensation and Pension) exam is used by the VA to evaluate the severity of your disability. Prepare by reviewing your medical history, being honest about your symptoms and their impact, and bringing any relevant medical records or documentation."
            ),
            FAQ(
                question="How long does the VA claims process typically take?",
                answer="The VA claims process can vary in length, but it typically takes several months. Complex cases or those requiring additional evidence may take longer. You can check the status of your claim online through the VA's eBenefits portal."
            ),
            FAQ(
                question="What should I do if my VA claim is denied?",
                answer="If your claim is denied, you have the right to appeal. Options include filing a Supplemental Claim with new evidence, requesting a Higher-Level Review, or appealing to the Board of Veterans' Appeals. Consider seeking assistance from a Veterans Service Organization (VSO) for guidance."
            ),
            FAQ(
                question="Can I receive compensation for conditions secondary to my service-connected disabilities?",
                answer="Yes, you can receive compensation for secondary conditions. For example, if a service-connected condition leads to another health issue, you may be eligible for additional compensation for the secondary condition."
            ),
            FAQ(
                question="Are there any additional benefits I should be aware of besides disability compensation?",
                answer="Yes, there are several additional benefits you may be eligible for, including VA Health Care, Vocational Rehabilitation and Employment (VR&E), VA Home Loan Guarantee, and various state-specific veterans benefits."
            ),
            FAQ(
                question="How can I get help with my VA claim?",
                answer="You can get help with your VA claim by contacting a Veterans Service Organization (VSO) or working with a VA-accredited claims agent. Many of these services are available free of charge."
            )
        ],
        description="Frequently asked questions about VA claims"
    )

    howToContestClaim: str = Field(
        default="""If your claim is denied or you disagree with the rating assigned, you have the right to appeal. The appeals process includes several options:
        1. Supplemental Claim: Submit new and relevant evidence.
        2. Higher-Level Review: Request a review by a senior VA employee.
        3. Board Appeal: Appeal directly to the Board of Veterans' Appeals.

        To contest a claim:
        1. Review your decision letter carefully to understand the reason for the denial or rating.
        2. Gather any new and relevant evidence that addresses the reason for denial.
        3. Consider obtaining additional medical opinions or nexus letters.
        4. File the appropriate appeal form within the specified timeframe (usually one year from the date of the decision letter).
        5. Consider seeking assistance from a VSO or attorney specializing in VA law.
        6. Be prepared to provide additional statements or attend further examinations if required.
        7. Stay informed about the status of your appeal and respond promptly to any requests for information from the VA.""",
        description="Information on how to contest a claim"
    )

    otherPossibleBenefits: List[str] = Field(
        default=[
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
        description="List of other possible VA benefits"
    )

    glossary: List[GlossaryItem] = Field(
        default=[
            GlossaryItem(
                term="VA",
                definition="The Department of Veterans Affairs, a government agency responsible for providing vital services to America's veterans."
            ),
            GlossaryItem(
                term="C&P Exam",
                definition="Compensation and Pension Exam, a medical examination used by the VA to evaluate the severity of a veteran's disability."
            ),
            GlossaryItem(
                term="Nexus Letter",
                definition="A letter from a medical professional that links a veteran's current medical condition to their military service."
            ),
            GlossaryItem(
                term="Service Connection",
                definition="The establishment of a direct link between a veteran's current disability and their military service."
            ),
            GlossaryItem(
                term="Disability Rating",
                definition="A percentage assigned by the VA that represents the severity of a veteran's disability and determines the amount of compensation."
            ),
            GlossaryItem(
                term="VSO",
                definition="Veterans Service Organization, a group that provides free assistance to veterans in filing and appealing VA claims."
            ),
            GlossaryItem(
                term="Appeal",
                definition="The process by which a veteran can challenge a VA decision on their claim."
            ),
            GlossaryItem(
                term="Supplemental Claim",
                definition="A type of appeal where a veteran submits new and relevant evidence to support their claim."
            ),
            GlossaryItem(
                term="Higher-Level Review",
                definition="A type of appeal where a more senior VA employee reviews the veteran's claim without considering new evidence."
            ),
            GlossaryItem(
                term="Board Appeal",
                definition="An appeal directly to the Board of Veterans' Appeals, which can include a hearing before a Veterans Law Judge."
            ),
            GlossaryItem(
                term="VA Form 21-526EZ",
                definition="The form used by veterans to apply for disability compensation and related benefits."
            ),
            GlossaryItem(
                term="Buddy Statement",
                definition="A statement from a fellow service member or family member that supports a veteran's claim by providing additional evidence or context."
            ),
            GlossaryItem(
                term="VA Health Care",
                definition="Medical services provided by the VA to eligible veterans."
            ),
            GlossaryItem(
                term="Vocational Rehabilitation and Employment (VR&E)",
                definition="A VA program that helps veterans with service-connected disabilities prepare for, find, and maintain suitable employment."
            ),
            GlossaryItem(
                term="Aid and Attendance",
                definition="An additional benefit paid to veterans, their spouses, or surviving spouses who require the aid and attendance of another person."
            ),
            GlossaryItem(
                term="VA Home Loan Guarantee",
                definition="A VA benefit that helps veterans, service members, and eligible surviving spouses become homeowners by providing a home loan guarantee."
            ),
            GlossaryItem(
                term="Veterans' Group Life Insurance (VGLI)",
                definition="A program that allows veterans to convert their Servicemembers' Group Life Insurance (SGLI) to renewable term insurance."
            ),
            GlossaryItem(
                term="Dependents' Educational Assistance",
                definition="A VA program that provides education and training opportunities to eligible dependents of veterans."
            ),
            GlossaryItem(
                term="Automobile Allowance and Adaptive Equipment",
                definition="A benefit that provides a one-time payment to help veterans with certain disabilities purchase a specially equipped vehicle."
            ),
            GlossaryItem(
                term="Veterans' Preference in Federal Employment",
                definition="A policy that gives eligible veterans preference in hiring for federal jobs."
            ),
            GlossaryItem(
                term="State Veterans Benefits",
                definition="Benefits provided by individual states to veterans, which can include education, employment, and health care services."
            ),
            GlossaryItem(
                term="Vet Center Services",
                definition="Community-based counseling centers that provide a wide range of social and psychological services to eligible veterans and their families."
            ),
            GlossaryItem(
                term="Caregiver Support",
                definition="VA programs that offer support to family caregivers of veterans, including education, resources, and in some cases, financial assistance."
            )
        ],
        description="Glossary of VA terms and definitions"
    )
    
    legendExplanation: str = Field(
        default="""Legend Explanation:
        * Required: These items are essential for your claim
        + Recommended: These items will strengthen your claim
        - Optional: These items may help in specific cases
        ! Important: Pay special attention to these items
        ? Tips: Helpful advice for the claims process""",
        description="Explanation of report legends and symbols"
    )

    vaBenefitRatingsCriteria: str = Field(
        default="""VA disability ratings are assigned in 10% increments from 0% to 100%. The rating is based on:
            1. Severity of symptoms
            2. Impact on daily activities
            3. Effect on work capacity
            4. Frequency of episodes or flare-ups
            5. Need for continuous medication or treatment

            Common Rating Levels:
            0% - Condition exists but doesn't impact function
            10% - Mild symptoms with minimal impact
            30% - Moderate symptoms affecting work/daily life
            50% - Serious symptoms with significant limitations
            70% - Severe symptoms with major functional impact
            100% - Total disability/unable to work

            Note: Multiple disabilities are combined using VA's combined ratings table, not simply added together.""",
        description="VA benefit ratings criteria explanation"
    )
    
    async def run(self) -> Dict[str, Any]:
        logger = configure_logger('SaveToStaticSections')
        logger.info("Running SaveToStaticSections tool")
        
        user_id = self._caller_agent.context_info.context['user_id']
        report_id = None
        
        client: Client = Supabase.supabase
        try:
            # Fetch existing report
            result = client.from_("decrypted_reports").select("id, decrypted_report").eq("user_id", user_id).single().execute()
            report = Report(**json.loads(result.data['decrypted_report']))
            report_id = result.data['id']
            
            # Check if static sections already exist and are populated
            if (report.standardOperatingProcedure and len(report.standardOperatingProcedure) > 0 and
                report.checklist and report.checklist.sections and
                report.mentalCAndPTips and report.mentalCAndPTips.sections and
                report.glossary and len(report.glossary) > 0):
                
                logger.info("Static sections already exist")
                return json.dumps({
                    "static_sections": {
                        "standardOperatingProcedure": report.standardOperatingProcedure,
                        "checklist": report.checklist.dict() if report.checklist else None,
                        "mentalCAndPTips": report.mentalCAndPTips.dict() if report.mentalCAndPTips else None,
                        "onlineFilingGuide": report.onlineFilingGuide.dict() if report.onlineFilingGuide else None,
                        "letter": report.letter.dict() if report.letter else None,
                        "faqs": [faq.dict() for faq in report.faqs] if report.faqs else [],
                        "howToContestClaim": report.howToContestClaim,
                        "otherPossibleBenefits": report.otherPossibleBenefits,
                        "glossary": [item.dict() for item in report.glossary] if report.glossary else [],
                        "vaBenefitRatingsCriteria": report.vaBenefitRatingsCriteria
                    },
                    "status": "existing"
                }, skipkeys=True, default=lambda x: x.__dict__)
            
            # Update only static sections while preserving condition-specific data
            report.standardOperatingProcedure = self.standardOperatingProcedure
            report.checklist = self.checklist
            report.mentalCAndPTips = self.mentalCAndPTips
            report.onlineFilingGuide = self.onlineFilingGuide
            report.letter = self.letter
            report.faqs = self.faqs
            report.howToContestClaim = self.howToContestClaim
            report.otherPossibleBenefits = self.otherPossibleBenefits
            report.glossary = self.glossary
            report.vaBenefitRatingsCriteria = self.vaBenefitRatingsCriteria
            
            record = {
                "user_id": user_id,
                "report": json.dumps(report.dict()),
                "updated_at": datetime.now().isoformat()
            }
            
            if report_id:
                record["id"] = report_id
                
            updated_result = client.from_("reports").update(record).eq("user_id", user_id).execute()
            
        except Exception as e:
            logger.error(f"Error fetching report: {e}")
            logger.error(traceback.format_exc())
            # Create new report with static sections
            report = Report(
                user_id=user_id,
                conditions=[],
                executive_summary=[],
                personalStatementLetters=[],
                nexusLetters=[],
                standardOperatingProcedure=self.standardOperatingProcedure,
                checklist=self.checklist,
                mentalCAndPTips=self.mentalCAndPTips,
                onlineFilingGuide=self.onlineFilingGuide,
                letter=self.letter,
                faqs=self.faqs,
                howToContestClaim=self.howToContestClaim,
                otherPossibleBenefits=self.otherPossibleBenefits,
                glossary=self.glossary,
                #vaBenefitRatingsCriteria=self.vaBenefitRatingsCriteria
            )
            
            record = {
                "user_id": user_id,
                "report": json.dumps(report.dict()),
                "updated_at": datetime.now().isoformat()
            }
            
            if report_id:
                record["id"] = report_id
                
            updated_result = client.from_("reports").insert(record).execute()
            
        # Store static sections in agent context
        static_sections = {
            "standardOperatingProcedure": report.standardOperatingProcedure,
            "checklist": report.checklist.dict() if report.checklist else None,
            "mentalCAndPTips": report.mentalCAndPTips.dict() if report.mentalCAndPTips else None,
            "onlineFilingGuide": report.onlineFilingGuide.dict() if report.onlineFilingGuide else None,
            "letter": report.letter.dict() if report.letter else None,
            "faqs": [faq.dict() for faq in report.faqs] if report.faqs else [],
            "howToContestClaim": report.howToContestClaim,
            "otherPossibleBenefits": report.otherPossibleBenefits,
            "glossary": [item.dict() for item in report.glossary] if report.glossary else [],
            #"vaBenefitRatingsCriteria": report.vaBenefitRatingsCriteria
        }
        
        self._caller_agent.context_info.context["static_sections"] = json.dumps(
            static_sections,
            skipkeys=True,
            default=lambda x: x.__dict__
        )
        
        return json.dumps(static_sections, skipkeys=True, default=lambda x: x.__dict__)
