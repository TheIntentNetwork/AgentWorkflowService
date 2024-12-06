"""Module for QuestionnaireWriter agent."""
from sys import exit
from app.tools.GenerateQuestionnaire import GenerateQuestionnaire
from app.models.agents import Agent
from app.logging_config import configure_logger

class QuestionnaireWriter(Agent):
    """Agent for writing questionnaires."""

    def __init__(self, **kwargs):
        logger = configure_logger(self.__class__.__name__)
        logger.debug("Initializing QuestionnaireWriter with kwargs: %s", kwargs)
        if not kwargs:
            exit("QuestionnaireWriter requires at least 1 keyword argument.")
        # iterate through kwargs and print them
        for key, value in kwargs.items():
            logger.debug("kwargs: %s %s", key, value)
        # Initialize tools in kwargs if not present
        if 'tools' not in kwargs:
            kwargs['tools'] = []

        # Add required tools
        kwargs['tools'].append(GenerateQuestionnaire)
        question_building_thoughts = """
        =======================================================================

        When building a questionnaire, you should consider the following:
        - What is the purpose of the questionnaire?
        - Who is the target audience?
        - What information do you need to collect?
        - How will the information be used?

        When thinking about the questions to ask, consider the following:
        - What should I ask first?
        - What information is critical to collect first?
        - Are there questions that I shouldn't ask to certain types of users?
        - How can I create question groups to organize the questions logically?
        - Should I use multiple questions with different components to collect aspects of the same information?

        When thinking about the components to use, consider the following:
        - What type of input is required?
        - Should the user select from a list of options?
        - Should the user provide a date or number?
        - Are there questions or information that will require multiple components?

        Consider the following example:
        - If the question is about the user's condition, you may want to use a dropdown, but if the user needs to provide more details, you may want to use a text input.
        - But what if the user has multiple conditions and we need to collect multiple pieces of information for each condition? You may want to use a checkbox or radio button for the condition and a text input for the details or a dropdown for the condition and a text input for the details.
        - Maybe you want to collect the user's condition, the rating percentage, and the intention to file a claim. You could use a dropdown for the condition, a dropdown for the rating percentage, and a radio button for the intention to file a claim.

        Remember, the goal is to collect the information you need in a way that is easy for the user to understand and complete.

        General tips:
        Ask the most important or basic questions first as a partial questionnaire setting partial to true in the questionnaire object.
        Use question groups to organize related questions.
        Ask only a few questions at a time to avoid overwhelming the user.
        Keep the questions clear and concise.
        Ask the questions in voice that is appropriate for the target audience as if you were speaking to them directly.
        Examples:
        Don't say: "Please provide the date of your service start."
        Do say: "When did you start your service?"
        Don't say "What conditions are they rated for?"
        Do say "What conditions are you currently rated for?"
        """

        instructions_history = """
        =======================================================================

        A list of past GenerateQuestionnaire function calls:
        
        INITIAL QUESTIONNAIRE:
            {
                "title":"Intake Sheet",
                "type":"initial",
                "question_groups":[
                    {
                        "questions":[
                            {
                                "label":"What is your current military status?",
                                "component":"radio",
                                "options":[
                                    "Active Duty",
                                    "Veteran"
                                    ],
                                "placeholder":""
                            },
                            {
                                "label":"What branch of service were you in?",
                                "component":"dropdown",
                                "options": [
                                    "Army",
                                    "Navy",
                                    "Marine Corps",
                                    "Air Force",
                                    "Coast Guard",
                                    "Space Force"
                                    ],
                                    "placeholder":"Select your branch of service"
                            },
                            {
                                "label":"What were your dates of service?",
                                "component":"date-range",
                                "options":[],
                                "placeholder":"Select your start and end date"
                            }
                        ]
                    }
                ]
            }

            REMAINING QUESTIONNAIRE:
            {
                "title":"Final Intake Sheet",
                "type": "final",
                "question_groups": [
                {
                    "questions": [
                        {
                            "label": "What conditions are you diagnosed with that you have not filed a claim for?",
                            "component": "multi-select",
                            "options": [
                                "PTSD",
                                "TBI",
                                "Back Injury",
                                "Knee Injury",
                                "Hearing Loss",
                                "Vision Loss",
                                "Other"
                            ],
                            "placeholder": ""
                        },
                        {
                            "label": "For the conditions you are intending to file a claim for, rate the severity of your condition on a scale from 1 to 10.",
                            "component": "textarea",
                            "options": [],
                            "placeholder": ""
                        },
                        {
                            "label": "How do these conditions impact your daily life on a scale from 1 to 10?",
                            "component": "textarea",
                            "options": [],
                            "placeholder": ""
                        },
                        {
                            "label": "Which of the following symptoms apply to your condition(s)? Select all that apply.",
                            "component": "multi-select",
                            "options": [
                                "Chronic pain",
                                "Headaches",
                                "Memory loss",
                                "Sleep disturbances",
                                "Mood swings",
                                "Hearing difficulty",
                                "Vision problems",
                                "Other"
                            ],
                            "placeholder": ""
                        },
                        {
                            "label": "For how long have you been experiencing these conditions?",       
                            "component": "textarea",
                            "options": [],
                            "placeholder": ""
                        },
                        {
                            "label": "How frequently do you experience symptoms of your condition(s)?", 
                            "component": "textarea",
                            "options": [],
                            "placeholder": ""
                        },
                        {
                            "label": "Do you have social and occupational impairment due to these conditions? Rate from 1 to 10.",
                            "component": "textarea",
                            "options": [],
                            "placeholder": ""
                        },
                            "component": "radio",
                            "options": [
                                "Yes",
                                "No"
                            ],
                            "placeholder": ""
                        },
                        {
                            "label": "Do you have a current diagnosis or a doctor who would sign a nexus letter for your condition?",
                            "component": "radio",
                            "options": [
                                "Yes",
                                "No"
                            ],
                            "placeholder": ""
                        }
                    ]
                }
            ]
        }
        """
        
        inputs_format ="""
        Current Answers:
        {{answers}}

        Your Objective:
        {{objective}}
        """

        instructions = instructions_history + question_building_thoughts + inputs_format + kwargs.get('instructions', "")
        self.task = kwargs.get('context', {})
        for key, value in self.task.context.items():
            try:
                if isinstance(value, list):
                    value = ', '.join(value)
                elif isinstance(value, dict):
                    value = ', '.join([f"{k}: {v}" for k, v in value.items()])
                elif isinstance(value, bool):
                    value = str(value).lower()
                elif isinstance(value, str):
                    value = value
                else:
                    continue
                logger.debug("Replacing %s with %s", f"{{{key}}}", value)
                instructions = instructions.replace(f"{{{key}}}", value)
            except Exception as e:
                logger.error(f"Failed to replace {key} with {str(value)}: {str(e)}")

        # Set instructions
        kwargs['instructions'] = ("""You are an advanced questionnaire writer equipped with specialized tools to create questionnaires effectively. 
                                    Your primary objective is to fulfill the user's requests by efficiently utilizing these tools. 
                                    When creating a questionnaire, you will use the 'GenerateQuestionnaire' tool to create a questionnaire based on 
                                    the user's requirements. Generate only 1 questionnaire and send it back to the user. All questions require a component, label, and question.
                                    """.replace("n", "")) + "nn" + instructions
        
        

        # Initialize the parent class
        super().__init__(**kwargs)
