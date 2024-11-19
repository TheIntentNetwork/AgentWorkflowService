from typing import List, Optional
from pydantic import BaseModel, Field
from app.services.supabase.supabase import Supabase, Client
from app.tools.base_tool import BaseTool
from app.logging_config import configure_logger
from app.models.Report import LetterFormat, Report, Checklist, MentalCAndPTips, OnlineFilingGuide, FAQ, GlossaryItem

class WriteStaticReportSections(BaseTool):
    """Tool for writing static sections of the report that don't vary by condition."""
    
    user_id: str = Field(..., description="The user id for the report")
    
    async def run(self) -> dict:
        logger = configure_logger(self.__class__.__name__)
        logger.info(f"Writing static report sections for user {self.user_id}")
        
        # Create new report or fetch existing
        try:
            report = await self.fetch_report(self.user_id)
        except:
            # If fetch fails, create new Report instance
            report = Report(user_id=self.user_id)
        
        # Update static sections
        report.standardOperatingProcedure = [
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

        report.checklist = Checklist(
            title="VA Disability Claim Checklist",
            sections=[
                {
                    "title": "Diagnosis & Medical Evidence",
                    "items": [
                        "Obtain a current diagnosis from a doctor (VA, military, or private).",
                        "Collect all relevant medical records (Service Treatment Records, VA records, private records).",
                        "Consider getting a Nexus Letter from a private provider if not diagnosed during service."
                    ]
                },
                {
                    "title": "Proof of Service Connection (Nexus)",
                    "items": [
                        "Ensure your condition is service-connected (caused or worsened by service).",
                        "Collect buddy letters from people who can confirm your condition and in-service events, if possible."
                    ]
                },
                {
                    "title": "Severity & Impact",
                    "items": [
                        "Write a personal statement detailing how your condition affects your daily life, work, and social interactions.",
                        "Complete VA Form 21-4138 (Statement in Support of Claim)."
                    ]
                },
                {
                    "title": "Preparing for the C&P Exam",
                    "items": [
                        "Review your medical records and know your conditions.",
                        "Bring a copy of all documents (records, Nexus Letters, personal statements) to the exam.",
                        "Be prepared to describe your worst days truthfully during the exam."
                    ],
                    "tips": [
                        "Do not exaggerate or minimize your symptoms. Be specific and honest."
                    ]
                },
                {
                    "title": "Filing Your Claim",
                    "items": [
                        "Visit VA.gov and start your claim. Consider opening a Notice of Intent to File to lock in your effective date.",
                        "Choose to submit a Fully Developed Claim (FDC) for faster processing.",
                        "Upload all supporting evidence when filing (diagnosis, Nexus Letters, personal statements, buddy letters)."
                    ],
                    "tips": [
                        "A VSO (Veteran Service Officer) can file your claim for you for free if you prefer not to file it yourself."
                    ]
                },
                {
                    "title": "After Filing",
                    "items": [
                        "Monitor your claim status on VA.gov or by calling the VA.",
                        "Respond quickly to any VA requests for additional information.",
                        "If denied, explore options like a Higher Level Review or Supplemental Claim."
                    ]
                },
                {
                    "title": "Key Reminders",
                    "items": [
                        "Keep a copy of everything you submit.",
                        "Provide updated medical evidence if applying for an increase.",
                        "Stay proactive and follow up regularly until your claim is resolved."
                    ]
                }
            ]
        )

        report.mentalCAndPTips = MentalCAndPTips(
            sections=[
                {
                    "title": "Worst Moment with Friends or Family:",
                    "tips": [
                        "(Think of a time your mental health made it hard to get along with others. This could be arguments, feeling left out, or not wanting to be around people.)"
                    ]
                },
                {
                    "title": "Biggest Trouble at Work:",
                    "tips": [
                        "(Remember a time when your mental health made it hard to do your job. This could be having trouble finishing tasks, missing work, or problems with coworkers. If retired, list how it WOULD affect your work if you decided to work again.)"
                    ]
                },
                {
                    "title": "Worst Mental Health Moment:",
                    "tips": [
                        "(Think of the most difficult mental health symptom youve had. This could be feeling very sad, very worried, or having panic attacks.)"
                    ]
                }
            ]
        )

        report.onlineFilingGuide = OnlineFilingGuide(
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
                },
                {
                    "title": "Step 6: Upload Supporting Documents",
                    "description": "Attach any supporting evidence like medical records or statements from healthcare providers.",
                    "resources": [
                        {
                            "name": "Uploading Evidence for Your Claim",
                            "url": "https://www.va.gov/disability/how-to-file-claim/"
                        }
                    ]
                },
                {
                    "title": "Step 7: Review and Submit Your Claim",
                    "description": "Review your application for any errors or omissions before submitting.",
                    "resources": []
                },
                {
                    "title": "Step 8: Track Your Claim Status",
                    "description": "After submission, you can track the status of your claim through your VA.gov account.",
                    "resources": [
                        {
                            "name": "Check Your Claim Status",
                            "url": "https://www.va.gov/claim-or-appeal-status/"
                        }
                    ]
                }
            ],
            additionalResources=[
                {
                    "name": "VA Benefits Eligibility",
                    "url": "https://www.va.gov/disability/eligibility/"
                },
                {
                    "name": "Get Help Filing Your Claim",
                    "url": "https://www.va.gov/disability/get-help-filing-claim/"
                },
                {
                    "name": "VA Disability Compensation Rates",
                    "url": "https://www.va.gov/disability/compensation-rates/veteran-rates/"
                }
            ]
        )

        report.letter = LetterFormat(
            salutation="Dear Veteran,",
            paragraphs=[
                "I hope this letter finds you well. As the founder of VA Claims Academy and a fellow veteran, I understand the challenges you may be facing in navigating the VA claims process. I want to personally encourage you to persist in your efforts to secure the benefits you've rightfully earned through your service.",
                "Your dedication and sacrifice to our nation are immeasurable, and it's crucial that you receive the support and recognition you deserve. The claims process can be complex, but please know that you're not alone in this journey. Our team at VA Claims Academy is here to support and guide you every step of the way.",
                "Remember, pursuing your VA claim is not just about the benefits; it's about acknowledging your service and ensuring you have access to the resources you need for a fulfilling life post-service. Your perseverance in this process is a continuation of the strength you've already demonstrated in your military career.",
                "Don't hesitate to reach out if you need assistance or have any questions. We're committed to empowering veterans like you with the knowledge and tools necessary to navigate the VA system successfully."
            ],
            closing={
                "message": "Wishing you all the best in your claims process and beyond.",
                "signature": "Jordan Anderson",
                "title": "VA Claims Academy"
            }
        )

        report.faqs = [
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
        ]

        report.howToContestClaim = """If your claim is denied or you disagree with the rating assigned, you have the right to appeal. The appeals process includes several options:
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
7. Stay informed about the status of your appeal and respond promptly to any requests for information from the VA."""

        report.otherPossibleBenefits = [
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
        ]

        report.glossary = [
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
        ]

        # Save updated report
        await self.save_report(report)
        
        return report.dict()

    async def fetch_report(self, user_id: str) -> Report:
        """Fetch the report from the decrypted_reports table"""
        client: Client = Supabase.supabase
        try:
            result = client.from_("decrypted_reports").select("*").eq("user_id", user_id).single().execute()
            if result.data:
                return Report(**result.data)
            return Report(user_id=user_id)
        except Exception as e:
            logger = configure_logger(self.__class__.__name__)
            logger.error(f"Error fetching report: {str(e)}")
            return Report(user_id=user_id)

    async def save_report(self, report: Report) -> None:
        """Save the report to the reports table"""
        client: Client = Supabase.supabase
        try:
            # Convert report to dict but preserve the original user_id
            report_dict = report.dict()
            result = client.from_("reports").upsert(report_dict).execute()
            return result
        except Exception as e:
            logger = configure_logger(self.__class__.__name__)
            logger.error(f"Error saving report: {str(e)}")
            # Log the report data for debugging
            logger.error(f"Report data: {report.dict()}")
            raise
