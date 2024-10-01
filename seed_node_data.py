from app.models.Node import Node
from app.models.ContextInfo import ContextInfo

def get_node_seed_data():
    return [
        Node(
            name="CreateCustomerReport",
            type="model",
            description="Create a customer report for the customer using the customer's metadata and the customer's supplemental forms.",
            context_info=ContextInfo(
                input_description="The customer's metadata and the customer's supplemental forms will be used to create the customer report.",
                input_context={},
                action_summary="Create a customer report for the customer using the customer's metadata and the customer's supplemental forms.",
                outcome_description="At the end of this model, you will have a customer report for the customer.",
                feedback=[
                    "The UniverseAgent should be assigned to this task to create a customer report for the customer using the customer's metadata and the customer's supplemental forms."
                ],
                output={
                    "customer_report": {
                        "customer_id": "{customer_id}",
                        "report": "{report}",
                    }
                },
            ),
            collection=[
                Node(
                    name="GatherIntakeConditions",
                    type="model",
                    description="Gather intake conditions and write the user's metadata",
                    context_info=ContextInfo(
                        input_description="The user_context which contains their intake form.",
                        action_summary="Gather intake conditions and write the user's metadata.",
                        outcome_description="A list of conditions extracted from the intake form and saved user metadata.",
                        feedback=[
                            "The IntakeProcessor agent should be assigned to this task to ensure accurate extraction of conditions from the intake form.",
                            "Use the SaveUserMeta tool to store the extracted information."
                        ],
                        output={
                            "conditions": ["{condition1}", "{condition2}"],
                            "user_metadata": {
                                "user_id": "{user_id}",
                                "intake_date": "{intake_date}",
                                "conditions": ["{condition1}", "{condition2}"]
                            }
                        },
                        context={
                            "user_context": {"user_id": "{user_id}"},
                            "goals": [
                                "Extract conditions from the intake form.",
                                "Save the user's metadata including the extracted conditions.",
                                "Prepare the conditions list for further processing."
                            ]
                        }
                    ),
                    collection=[
                        Node(
                            name="RetrieveIntakeForm",
                            type="step",
                            description="Retrieve the intake form for the customer",
                            context_info=ContextInfo(
                                input_description="The user_context which contains their user ID.",
                                action_summary="Retrieve the intake form for the customer using their user ID.",
                                outcome_description="The complete intake form for the customer.",
                                feedback=[
                                    "The IntakeFormRetriever agent should be assigned to this task to ensure the correct and complete intake form is retrieved."
                                ],
                                output={
                                    "intake_form": {
                                        "user_id": "{user_id}",
                                        "form_data": "{form_data}"
                                    }
                                },
                                context={
                                    "user_context": {"user_id": "{user_id}"},
                                    "goals": [
                                        "Retrieve the complete intake form for the specified user.",
                                        "Ensure all form fields and responses are included in the output.",
                                        "Prepare the intake form data for further processing in subsequent steps."
                                    ]
                                }
                            ),
                        ),
                        Node(
                            name="SaveUserMetaFromIntake",
                            type="step",
                            description="Save the user's information from their intake form",
                            context_info=ContextInfo(
                                input_description="The user_context which contains their intake form will be used to understand the conditions for the customer.",
                                action_summary="Save the user's information from their intake form which can be found within the node context metadata into the UserMeta.",
                                outcome_description="At the end of this step, you will have saved the user's information from their intake form into the UserMeta.",
                                feedback=[
                                    "The ProcessIntakeAgent should be assigned to this task to save the user's information from their intake form into the UserMeta.",
                                    "You should not try to save the user_meta if the key already exists within the user_context."
                                ],
                                output={"processed_intake": True},
                                context={
                                    "user_context": {"user_id": "{user_id}"},
                                    "goals": [
                                        "Save the user's information from their intake form into the UserMeta.",
                                        "Save the conditions into the UserMeta and as an output."
                                    ]
                                }
                            ),
                        ),
                    ],
                ),
                Node(
                    name="ResearchConditionModel",
                    type="model",
                    description="Gather all the information for each condition",
                    context_info=ContextInfo(
                        input_description="The condition to be processed and the user_context.",
                        action_summary="Gather all the information for each condition, including research and personal experiences.",
                        outcome_description="A comprehensive set of information about the condition, including medical research and personal impact.",
                        feedback=[
                            "The ResearchAgent should be assigned to gather medical information about the condition.",
                            "The PersonalImpactAgent should be used to analyze the condition's impact on the customer's life."
                        ],
                        output={
                            "condition_research": {
                                "condition_name": "{condition_name}",
                                "medical_research": [
                                    {
                                        "title": "{research_title}",
                                        "summary": "{research_summary}",
                                        "source": "{research_source}"
                                    }
                                ],
                                "personal_impact": {
                                    "symptoms": ["{symptom1}", "{symptom2}"],
                                    "daily_life_impact": "{impact_description}"
                                }
                            }
                        },
                        context={
                            "user_context": {"user_id": "{user_id}"},
                            "goals": [
                                "Gather comprehensive medical research about the condition.",
                                "Analyze the personal impact of the condition on the customer's life.",
                                "Prepare a detailed report combining medical and personal aspects of the condition."
                            ]
                        }
                    ),
                    collection=[
                        Node(
                            name="ReviewSupplementalIntake",
                            type="step",
                            description="Collect and review the supplemental intake for the specific condition for our customer.",
                            context_info=ContextInfo(
                                input_description="Retrieve the supplemental intake by looking into the form context or use RetrieveContext and look for records in the user_context.",
                                action_summary="Collect and review the supplemental intake for the specific condition for our customer.",
                                outcome_description="A processed review of the supplemental intake for the specific condition.",
                                feedback=[
                                    "The SupplementalIntakeReviewAgent should be assigned to this task to ensure accurate review of the condition-specific supplemental intake.",
                                    "Use the RetrieveContext tool if the form context doesn't contain the necessary information."
                                ],
                                output={
                                    "processed_supplemental_intake": {
                                        "condition": "{condition}",
                                        "details": "{details}",
                                        "review_notes": "{review_notes}"
                                    }
                                },
                                context={
                                    "user_context": {"user_id": "{user_id}"},
                                    "form_context": "{form_context}",
                                    "goals": [
                                        "Retrieve the supplemental intake for the specific condition.",
                                        "Review and process the information in the supplemental intake.",
                                        "Prepare the processed information for use in subsequent steps of the workflow."
                                    ]
                                }
                            ),
                        ),
                        Node(
                            name="RetrieveDiscoveryCallNotesForCondition",
                            type="step",
                            description="Retrieve the discovery call notes for the condition",
                            context_info=ContextInfo(
                                input_description="The discovery call notes that provides the details for the {condition}.",
                                action_summary="Retrieve the discovery call notes for the customer specifically for {condition} and ignore information about other conditions.",
                                outcome_description="The discovery call notes for the customer specifically for {condition}.",
                                feedback=[
                                    "The DiscoveryCallNotesAgent can handle this task specific to retrieving the discovery call notes for the customer specifically for {condition} and ignore information about other conditions."
                                ],
                                output={"notes": "{notes}", "condition": "{condition}"},
                                context={
                                    "user_context": {},
                                    "goals": [
                                        "Retrieve the discovery call notes for the customer specifically for {condition}."
                                    ]
                                }
                            ),
                        ),
                        Node(
                            name="ResearchCondition",
                            type="step",
                            description="Research the condition information from {processed_supplemental_intake} and discovery call {notes} by browsing the internet and output a summary of findings.",
                            context_info=ContextInfo(
                                input_description="The condition information from the {processed_supplemental_intake} and discovery call {notes}.",
                                action_summary="Research the condition information from the {processed_supplemental_intake} and discovery call {notes} and output a summary of findings.",
                                outcome_description="A summary of findings in the specified format.",
                                feedback=[
                                    "The BrowsingAgent should be assigned to research the condition information from the {processed_supplemental_intake} and discovery call {notes}.",
                                    "This step is primarily used once we information from our intake and supplemental intake that has been approved and is ready to process."
                                ],
                                output={
                                    "research_summary": {
                                        "title": "{title}",
                                        "author": "{author}",
                                        "journal": "{journal}",
                                        "summary_of_the_study": "{summary_of_the_study}",
                                        "excerpts": [
                                            {"excerpt": "{excerpt1}"},
                                            {"excerpt": "{excerpt2}"},
                                            {"excerpt": "{excerpt3}"}
                                        ],
                                        "date": "{date}",
                                        "url": "{url}"
                                    }
                                },
                                context={
                                    "user_context": {"user_id": "{user_id}"},
                                    "goals": [
                                        "Research the condition information from the supplemental forms.",
                                        "Output a summary of findings in the specified format."
                                    ]
                                }
                            ),
                        ),
                    ],
                ),
                Node(
                    name="CreateConditionReport",
                    type="model",
                    description="Create a condition report for the customer",
                    context_info=ContextInfo(
                        input_description="The customer's metadata and the customer's supplemental forms will be used to create a comprehensive report for the customer.",
                        action_summary="Create a condition report for the customer using the provided context and condition information.",
                        outcome_description="A fully written condition report saved in the specified format.",
                        feedback=[
                            "The ConditionReportWriter agent should be assigned to this task to ensure the report is comprehensive and well-structured."
                        ],
                        output={
                            "condition_report": {
                                "condition_name": "{condition_name}",
                                "summary": "{summary}",
                                "details": "{details}",
                                "research": "{research}",
                                "recommendations": "{recommendations}"
                            }
                        },
                        context={
                            "user_context": {"user_id": "{user_id}"},
                            "condition_info": {
                                "intake_form": "{intake_form}",
                                "supplemental_forms": "{supplemental_forms}",
                                "research": "{research}"
                            },
                            "goals": [
                                "Create a comprehensive condition report using the provided context and condition information.",
                                "Ensure the report covers all aspects of the condition and its impact on the customer.",
                                "Save the final output."
                            ]
                        }
                    ),
                    collection=[
                        Node(
                            name="WriteNexusLetter",
                            type="step",
                            description="Write a Nexus letter using context information",
                            context_info=ContextInfo(
                                input_description="Context information about the user, condition information from the intake form, supplemental forms, and research from browsing the internet.",
                                action_summary="Write a Nexus letter using the provided context and condition information.",
                                outcome_description="A fully written Nexus letter saved in the specified format.",
                                feedback=[
                                    "The NexusLetterWriter agent should be assigned to this task to ensure the letter is written in a professional and complete manner."
                                ],
                                output={
                                    "nexus_letter": {
                                        "title": "{title}",
                                        "author": "{author}",
                                        "letter_body": "{letter_body}",
                                        "references": [
                                            {"reference": "{reference1}"},
                                            {"reference": "{reference2}"}
                                        ],
                                        "date": "{date}"
                                    }
                                },
                                context={
                                    "user_context": {"user_id": "{user_id}"},
                                    "condition_info": {
                                        "intake_form": "{intake_form}",
                                        "supplemental_forms": "{supplemental_forms}",
                                        "research": "{research}"
                                    },
                                    "goals": [
                                        "Write a Nexus letter using the provided context and condition information.",
                                        "Ensure the letter is written in a professional and complete manner.",
                                        "Save the final output."
                                    ]
                                }
                            ),
                        ),
                        Node(
                            name="PersonalStatement",
                            type="step",
                            description="Write a personal statement for the customer",
                            context_info=ContextInfo(
                                input_description="The customer's metadata and the customer's supplemental forms.",
                                action_summary="Write a personal statement for the customer based on their condition information.",
                                outcome_description="A personalized statement describing the customer's experience with their condition.",
                                feedback=[
                                    "The PersonalStatementWriter agent should be assigned to this task to ensure the statement is empathetic and accurately reflects the customer's experience."
                                ],
                                output={
                                    "personal_statement": "{personal_statement_text}"
                                },
                                context={
                                    "user_context": {"user_id": "{user_id}"},
                                    "condition_info": {
                                        "condition_name": "{condition_name}",
                                        "symptoms": "{symptoms}",
                                        "impact": "{impact}"
                                    },
                                    "goals": [
                                        "Write a personal statement that accurately reflects the customer's experience with their condition.",
                                        "Ensure the statement is empathetic and highlights the condition's impact on the customer's life.",
                                        "Save the final output."
                                    ]
                                }
                            ),
                        ),
                        Node(
                            name="ResearchExamples",
                            type="step",
                            description="Provide research examples for the customer",
                            context_info=ContextInfo(
                                input_description="The customer's metadata and the customer's supplemental forms.",
                                action_summary="Provide research examples relevant to the customer's conditions.",
                                outcome_description="A set of relevant research examples for each of the customer's conditions.",
                                feedback=[
                                    "The ResearchExampleFinder agent should be assigned to this task to ensure relevant and up-to-date research examples are provided."
                                ],
                                output={
                                    "research_examples": [
                                        {
                                            "condition_name": "{condition_name}",
                                            "examples": [
                                                {
                                                    "title": "{research_title}",
                                                    "summary": "{research_summary}",
                                                    "source": "{research_source}",
                                                    "relevance": "{relevance_explanation}"
                                                }
                                            ]
                                        }
                                    ]
                                },
                                context={
                                    "user_context": {"user_id": "{user_id}"},
                                    "conditions": ["{condition1}", "{condition2}"],
                                    "goals": [
                                        "Find relevant research examples for each of the customer's conditions.",
                                        "Ensure the research examples are recent and from reputable sources.",
                                        "Explain the relevance of each research example to the customer's specific case."
                                    ]
                                }
                            ),
                        ),
                        Node(
                            name="TipsForCustomer",
                            type="step",
                            description="Provide tips for the customer for customizing their report",
                            context_info=ContextInfo(
                                input_description="The customer's metadata and the customer's supplemental forms.",
                                action_summary="Provide tips for the customer for customizing their report and preparing for further steps in their process.",
                                outcome_description="A set of personalized tips and recommendations for the customer.",
                                feedback=[
                                    "The CustomerAdviceAgent should be assigned to this task to ensure the tips are personalized and relevant to the customer's specific situation."
                                ],
                                output={
                                    "customer_tips": [
                                        {
                                            "category": "{tip_category}",
                                            "tips": ["{tip1}", "{tip2}", "{tip3}"]
                                        }
                                    ]
                                },
                                context={
                                    "user_context": {"user_id": "{user_id}"},
                                    "condition_reports": [
                                        {
                                            "condition_name": "{condition_name}",
                                            "key_points": ["{key_point1}", "{key_point2}"]
                                        }
                                    ],
                                    "goals": [
                                        "Provide personalized tips for customizing the report based on the customer's specific conditions.",
                                        "Offer advice on preparing for next steps in the customer's process.",
                                        "Ensure the tips are actionable and easy to understand."
                                    ]
                                }
                            ),
                        ),
                    ],
                ),
                Node(
                    name="AggregateCustomerReport",
                    type="model",
                    description="Aggregate all the outputs from CreateConditionReport",
                    context_info=ContextInfo(
                        input_description="The outputs from CreateConditionReport for all conditions.",
                        action_summary="Aggregate all the outputs from CreateConditionReport into a single comprehensive customer report.",
                        outcome_description="A complete customer report that includes all condition reports, personal statements, and supporting documentation.",
                        feedback=[
                            "The ReportAggregator agent should be assigned to this task to ensure all parts of the report are properly combined and formatted."
                        ],
                        output={
                            "customer_report": {
                                "executive_summary": "{executive_summary}",
                                "condition_reports": [
                                    {
                                        "condition_name": "{condition_name}",
                                        "report_content": "{report_content}"
                                    }
                                ],
                                "personal_statements": ["{personal_statement1}", "{personal_statement2}"],
                                "supporting_documents": ["{document1}", "{document2}"]
                            }
                        },
                        context={
                            "user_context": {"user_id": "{user_id}"},
                            "goals": [
                                "Combine all individual condition reports into a single comprehensive document.",
                                "Ensure all personal statements and supporting documents are included.",
                                "Create a well-structured and easy-to-navigate final report."
                            ]
                        }
                    ),
                    collection=[
                        Node(
                            name="ExecutiveSummary",
                            type="step",
                            description="Write an executive summary for the customer's report",
                            context_info=ContextInfo(
                                input_description="The customer's metadata and the customer's supplemental forms.",
                                action_summary="Write an executive summary for the customer's report, highlighting key points from all conditions.",
                                outcome_description="A concise executive summary that provides an overview of the customer's conditions and their impact.",
                                feedback=[
                                    "The ExecutiveSummaryWriter agent should be assigned to this task to ensure the summary is concise yet comprehensive."
                                ],
                                output={
                                    "executive_summary": "{executive_summary_text}"
                                },
                                context={
                                    "user_context": {"user_id": "{user_id}"},
                                    "condition_reports": [
                                        {
                                            "condition_name": "{condition_name}",
                                            "key_points": ["{key_point1}", "{key_point2}"]
                                        }
                                    ],
                                    "goals": [
                                        "Summarize the key points from all condition reports.",
                                        "Highlight the overall impact of the conditions on the customer's life.",
                                        "Provide a concise overview that sets the stage for the detailed report."
                                    ]
                                }
                            ),
                        ),
                        Node(
                            name="SaveResearchIntoReport",
                            type="step",
                            description="Save the research into a report for the customer",
                            context_info=ContextInfo(
                                input_description="The {research} for the customer.",
                                action_summary="Save the research into a report for the customer.",
                                outcome_description="A partial report for the customer.",
                                feedback=[
                                    "The SaveOutput tool should be used to save the research into a report for the customer."
                                ],
                                output={"report": {"research": "{research}"}},
                            ),
                        ),
                    ],
                ),
            ],
        ),
    ]