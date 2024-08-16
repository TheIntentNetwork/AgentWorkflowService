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
                    name="CollectConditionsAndProcess",
                    description="Collect the supplemental intake for our customer specifically for {condition}.",
                    type="workflow",
                    context_info=ContextInfo(
                        input_description="The {object_context} of the supplemental intake that provides the {condition} and details about the particular condition.",
                        action_summary="Process the intake by saving the output of the supplemental intake then work with the BrowsingAgent to research the condition.",
                        outcome_description="Saved research and supplemental intake details.",
                        feedback=[
                            "This task should be broken down into at least 2 nodes. One with the SupplementalReviewAgent and another node with the BrowsingAgent to research the condition and save our research into a condition report for the particular condition."
                        ],
                        output={},
                        context={
                            "user_context": {},
                            "goals": [
                                "Process the intake by Saving the output of the supplemental intake then work with the BrowsingAgent to research the condition.",
                                "Save the research and supplemental intake details.",
                            ],
                        },
                    ),
                    collection=[
                        Node(
                            name="CollectConditionsFromUserMeta",
                            description="Collect the conditions from the user's metadata from the UserMeta.",
                            type="step",
                            context_info=ContextInfo(
                                input_description="The user's metadata from the UserMeta will be retrieved using the GetUserContext tool.",
                                action_summary="Collect the conditions from the user's metadata from the UserMeta.",
                                outcome_description="The conditions from the user's metadata from the UserMeta.",
                                feedback=[
                                    "The UniverseAgent should be assigned to this task to collect the conditions from the user's metadata from the UserMeta.",
                                    "This node does not require dependencies as the conditions will be loaded from UserMeta.",
                                    "UniverseAgent will load the conditions into user_context and the conditions will be provided in the output.",
                                    "This node should be assigned to the UniverseAgent with the SaveOutput in order to send the conditions to downstream nodes."
                                ],
                                output={"conditions": ["{condition}"]},
                                context={
                                    "user_context": {"user_id": "{user_id}"},
                                    "goals": [
                                        "Collect the conditions from the user's metadata from the UserMeta.",
                                        "Output the conditions in the specified format.",
                                    ],
                                },
                            ),
                        ),
                        Node(
                            name="CreateSupplementalReviewAndResearchWorkflow",
                            description="Create the supplemental review and research workflow for our customer specifically for each of the {conditions}.",
                            type="step",
                            context_info=ContextInfo(
                                input_description="The {conditions} output from the previous node.",
                                action_summary="Create the supplemental review and research workflow for our customer specifically for each of the {conditions}.",
                                outcome_description="The supplemental review and research workflow (e.g. Set of Nodes) for our customer specifically for each of the {conditions}.",
                                feedback=[
                                    "The UniverseAgent can handle this task specific to creating the supplemental review and research workflow for our customer specifically for each of the {conditions}.",
                                    "The UniverseAgent should create a set of nodes for each condition provided by the previous node."
                                ],
                                output={"research_report": { "user_id": "{user_id}", "report": "{report}"}},
                                context={
                                    "user_context": {},
                                    "goals": [
                                        "Collect the supplemental intake for the user_id and condition",
                                    ],
                                },
                            ),
                        ),
                    ],
                ),
                Node(
                    name="ReviewAndResearchSupplementalIntake",
                    description="Collect the supplemental intake for our customer specifically for {condition}.",
                    type="workflow",
                    context_info=ContextInfo(
                        input_description="The {condition} for this particular workflow creation.",
                        action_summary="Process the intake by saving the output of the supplemental intake then work with the BrowsingAgent to research the condition.",
                        outcome_description="Saved research and supplemental intake details.",
                        feedback=[
                            "These nodes can only be created with an input condition provided to the UniverseAgent. You should only create the nodes within this workflow if you can creating a set of the nodes for each condition provided.",
                            "This task should be broken down into at least 2 nodes. One with the SupplementalReviewAgent and another node with the BrowsingAgent to research the condition and save our research into a condition report for the particular condition."
                        ],
                        output={
                            "supplemental_intake": {
                                "condition": "{condition}",
                                "questions": [
                                    {"question": "{question}", "answer": "{answer}"}
                                ],
                            },
                            "research": {
                                "title": "{title}",
                                "author": "{author}",
                                "journal": "{journal}",
                                "summary_of_the_study": "{summary_of_the_study}",
                                "excerpts": [
                                    {"excerpt": "{excerpt1}"},
                                    {"excerpt": "{excerpt2}"},
                                    {"excerpt": "{excerpt3}"},
                                ],
                                "date": "{date}",
                                "url": "{url}",
                            },
                        },
                        context={
                            "user_context": {},
                            "goals": [
                                "Process the intake by Saving the output of the supplemental intake then work with the BrowsingAgent to research the condition.",
                                "Save the research and supplemental intake details.",
                            ],
                        },
                    ),
                    collection=[
                        Node(
                            name="RetrieveDiscoveryCallNotesForCondition",
                            description="Retrieve the discovery call notes for the customer specifically for {condition}.",
                            type="step",
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
                                    ],
                                },
                            ),
                        ),
                        Node(
                            name="ReviewSupplementalIntake",
                            description="Collect the supplemental intake for our customer specifically for {condition}.",
                            type="step",
                            context_info=ContextInfo(
                                input_description="Retrieve the Supplemental using the GetSupplemental tool for the {condition} and details about the particular condition.",
                                action_summary="Process the intake by outputting the details of the supplemental intake.",
                                outcome_description="Use the SaveOutput tool with the results in the provided format, reply with the results in the same format to the user.",
                                feedback=[
                                    "The SupplementalReviewAgent can handle this task specific to processing the supplemental intake for a single condition.",
                                    "This step is primarily used when we receive a supplemental intake with a submission_approved status, meaning that the input has been reviewed and is ready to process.",
                                ],
                                output={"processed_supplemental_intake": {"condition": "{condition}", "details": "{notes}"} },
                                context={
                                    "user_context": {},
                                    "goals": [
                                        "Collect the supplemental intake for the user_id and condition"
                                    ],
                                },
                            ),
                        ),
                        Node(
                            name="ResearchCondition",
                            description="Research the condition information from {processed_supplemental_intake} and discovery call {notes} by browsing the internet and output a summary of findings.",
                            type="step",
                            context_info=ContextInfo(
                                input_description="The condition information from the {processed_supplemental_intake} and discovery call {notes}.",
                                action_summary="Research the condition information from the {processed_supplemental_intake} and discovery call {notes} and output a summary of findings.",
                                outcome_description="A summary of findings in the specified format.",
                                feedback=[
                                    "The BrowsingAgent should be assigned to research the condition information from the {processed_supplemental_intake} and discovery call {notes}.",
                                    "This step is primarily used once we information from our intake and supplemental intake that has been approved and is ready to process.",
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
                                            {"excerpt": "{excerpt3}"},
                                        ],
                                        "date": "{date}",
                                        "url": "{url}",
                                    }
                                },
                                context={
                                    "user_context": {"user_id": "{user_id}"},
                                    "goals": [
                                        "Research the condition information from the supplemental forms.",
                                        "Output a summary of findings in the specified format.",
                                    ],
                                },
                            ),
                        ),
                    ],
                ),
            ],
        ),
        Node(
            name="SaveIntakeAndCreateSupplementalForms",
            description="""
            Process the user's intake information to generate metadata for the customer then save the metadata into the UserMeta.
            Next, using the conditions from the UserMeta, create supplemental forms for each condition.
            """,
            type="workflow",
            context_info=ContextInfo(
                input_description="The user intake form will be used to understand the conditions for the customer.",
                action_summary="Process the user's intake information to generate metadata for the customer and save the metadata into the UserMeta. Then using the conditions from the UserMeta, create supplemental forms for each condition.",
                outcome_description="At the end of this workflow, you will have supplemental forms for the customer for each condition.",
                feedback=[
                    "UniverseAgent should be assigned to this task to break down the task into multiple nodes with the CreateNodes tool as we do not want to SaveUserMeta and CreateSupplementalForms in a single node.",
                    "Saving UserMeta should be done by a single node.",
                    "Creating supplemental forms should be done by a single node.",
                    "This is a complex task and should be assigned to the UniverseAgent.",
                ],
                output={
                    "supplemental_forms": [
                        {
                            "condition_name": "{condition_name}",
                            "supplemental_form": "{supplemental_form}",
                        }
                    ]
                },
                context={
                    "user_context": {"user_id": "{user_id}"},
                    "goals": [
                        "Process the user's intake form to create metadata for the customer.",
                        "Save the metadata into the UserMeta.",
                        "Create a new node for each condition to create a supplemental form for the customer.",
                        "Save the supplemental forms for the customer.",
                        "Save the final outputs",
                    ],
                },
            ),
            collection=[
                Node(
                    name="SaveUserMetaFromIntake",
                    description="Save the user's information from their intake form which can be found within the node context metadata into the UserMeta.",
                    type="step",
                    context_info=ContextInfo(
                        input_description="The user_context which contains their intake form will be used to understand the conditions for the customer.",
                        action_summary="Save the user's information from their intake form which can be found within the node context metadata into the UserMeta.",
                        outcome_description="At the end of this step, you will have saved the user's information from their intake form into the UserMeta.",
                        feedback=[
                            "The ProcessIntakeAgent should be assigned to this task to save the user's information from their intake form into the UserMeta.",
                            "You should not try to save the user_meta if the key already exists within the user_context.",
                        ],
                        output={"processed_intake": True},
                        context={
                            "user_context": {"user_id": "{user_id}"},
                            "goals": [
                                "Save the user's information from their intake form into the UserMeta.",
                                "Save the conditions into the UserMeta and as an output.",
                            ],
                        },
                    ),
                ),
                Node(
                    name="CreateSupplementalFormsFromUserMeta",
                    description="""
                    1.) Retrieve the user's metadata from the UserMeta.
                    2.) Save the supplemental forms using the CreateSupplementalIntakes tool.
                    """,
                    type="step",
                    context_info=ContextInfo(
                        input_description="The user's metadata from the UserMeta will be retrieved using the GetUserContext tool.",
                        action_summary="Create a supplemental intake for each condition found in the user's metadata. Then save the supplemental intakes using the CreateSupplementalIntakes tool.",
                        outcome_description="Supplemental intakes will be saved into the Forms table.",
                        feedback=[
                            "The SupplementalIntakeCreator agent should be assigned to create a supplemental intake for each condition found in the user meta.",
                            "We should only create new supplemental forms when we are processing a new intake form with a list of conditions. If we are processing a supplemental intake with submission_approved status, then we should not create any new supplemental forms.",
                        ],
                        output={"created_supplemental_intakes": ["{condition_name}"]},
                        context={
                            "user_context": {"user_id": "{user_id}"},
                            "goals": [
                                "Create a supplemental intake for each condition found in the user's metadata found with the GetUserContext.",
                                "Save the supplemental intakes into the Forms table.",
                            ],
                        },
                    ),
                ),
            ],
        ),
        Node(
            name="WriteNexusLetter",
            description="Write a Nexus letter using context information about the user, condition information from the intake form, supplemental forms, and research from browsing the internet.",
            type="step",
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
                            {"reference": "{reference2}"},
                        ],
                        "date": "{date}",
                    }
                },
                context={
                    "user_context": {"user_id": "{user_id}"},
                    "condition_info": {
                        "intake_form": "{intake_form}",
                        "supplemental_forms": "{supplemental_forms}",
                        "research": "{research}",
                    },
                    "goals": [
                        "Write a Nexus letter using the provided context and condition information.",
                        "Ensure the letter is written in a professional and complete manner.",
                        "Save the final output.",
                    ],
                },
            ),
        ),
        Node(
            name="SaveResearchIntoReport",
            description="Save the research into a report for the customer.",
            type="step",
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
    ]
