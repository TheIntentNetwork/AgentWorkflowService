from app.models.Dependency import OneToOneDependency
from app.models.Event import Event
from app.models.Goal import Goal
from app.models.Intent import Intent
from app.models.Step import Step
from app.models.StepOutput import StepOutput
from app.models.Workflow import Workflow

# Initialize Report Step
initialize_report_step = Step(
    step_id="initialize_report",
    name="Initialize Report",
    description="Set up the basic structure of the condition report and identify the medical condition.",
    execution_actor="ReportInitializer"
)

# Outputs for Initialize Report Step
initialize_report_output = StepOutput(
    step_id="initialize_report",
    output_key="report_structure",
    output_value="Basic structure of the condition report initialized."
)

initialize_report_step.add_output(initialize_report_output)

# Gather Condition Details Step
gather_condition_details_step = Step(
    step_id="gather_condition_details",
    name="Gather Condition Details",
    description="Collect detailed information about the medical condition.",
    execution_actor="ConditionDetailsCollector"
)

# Define dependencies based on the outputs of previous steps
gather_condition_details_dependency = OneToOneDependency(
    name="ConditionDetailsDependency",
    description="Depends on the initialization of the report to gather condition details.",
    output=initialize_report_output
)

# Add dependencies to the steps
gather_condition_details_step.add_dependencies([gather_condition_details_dependency])


# Outputs for Gather Condition Details Step
condition_name_output = StepOutput(
    step_id="gather_condition_details",
    output_key="condition_name",
    output_value=""  # Value to be filled after execution
)

condition_description_output = StepOutput(
    step_id="gather_condition_details",
    output_key="condition_description",
    output_value=""  # Value to be filled after execution
)

condition_approval_rate_output = StepOutput(
    step_id="gather_condition_details",
    output_key="condition_approval_rate",
    output_value=""  # Value to be filled after execution
)

condition_severity_output = StepOutput(
    step_id="gather_condition_details",
    output_key="condition_severity",
    output_value=""  # Value to be filled after execution
)

condition_color_output = StepOutput(
       step_id="gather_condition_details",
       output_key="condition_color",
       output_value=""
)

condition_short_descriptor_output = StepOutput(
    step_id="gather_condition_details",
    output_key="condition_short_descriptor",
    output_value=""
)

condition_type_output = StepOutput(
    step_id="gather_condition_details",
    output_key="condition_type",
    output_value=""
)

gather_condition_details_step.add_output(condition_name_output)
gather_condition_details_step.add_output(condition_description_output)
gather_condition_details_step.add_output(condition_approval_rate_output)
gather_condition_details_step.add_output(condition_severity_output)
gather_condition_details_step.add_output(condition_color_output)
gather_condition_details_step.add_output(condition_short_descriptor_output)
gather_condition_details_step.add_output(condition_type_output)


# Research Summary Step
research_summary_step = Step(
    step_id="research_summary",
    name="Research Summary",
    description="Summarize relevant research findings related to the medical condition.",
    execution_actor="ResearchSummarizer"
)

# Outputs for Research Summary Step
research_findings_output = StepOutput(
    step_id="research_summary",
    output_key="research_findings",
    output_value=""  # Value to be filled after execution
)

research_summary_step.add_output(research_findings_output)

research_summary_dependency = OneToOneDependency(
    name="ResearchSummaryDependency",
    description="Depends on gathering condition details.",
    output=gather_condition_details_step.outputs[0]  # Assuming the first output is relevant
)
research_summary_step.add_dependencies([research_summary_dependency])

# Regulatory Considerations Step
regulatory_considerations_step = Step(
    step_id="regulatory_considerations",
    name="Regulatory Considerations",
    description="Identify and summarize regulatory considerations related to the medical condition.",
    execution_actor="RegulatoryConsiderationsIdentifier"
)

# Outputs for Regulatory Considerations Step
cfr_points_output = StepOutput(
    step_id="regulatory_considerations",
    output_key="cfr_points",
    output_value=""  # Value to be filled after execution
)

regulatory_considerations_step.add_output(cfr_points_output)

regulatory_considerations_dependency = OneToOneDependency(
    name="RegulatoryConsiderationsDependency",
    description="Depends on gathering condition details.",
    output=gather_condition_details_step.outputs[0]  # Assuming the first output is relevant
)

regulatory_considerations_step.add_dependencies([regulatory_considerations_dependency])

# Identify Key Points Step
identify_key_points_step = Step(
    step_id="identify_key_points",
    name="Identify Key Points",
    description="Identify and summarize key points about the medical condition.",
    execution_actor="KeyPointsIdentifier"
)

# Outputs for Identify Key Points Step
key_points_output = StepOutput(
    step_id="identify_key_points",
    output_key="key_points",
    output_value=""  # Value to be filled after execution
)

identify_key_points_step.add_output(key_points_output)

identify_key_points_dependency = OneToOneDependency(
    name="KeyPointsDependency",
    description="Depends on gathering condition details.",
    output=gather_condition_details_step.outputs[0]  # Assuming the first output is relevant
)

identify_key_points_step.add_dependencies([identify_key_points_dependency])

# Compile Executive Summary Step
compile_executive_summary_step = Step(
    step_id="compile_executive_summary",
    name="Compile Executive Summary",
    description="Compile an executive summary based on the condition details.",
    execution_actor="SummaryCompiler"
)


compile_executive_summary_dependency = OneToOneDependency(
    name="ExecutiveSummaryDependency",
    description="Depends on gathering condition details.",
    output=gather_condition_details_step.outputs[0]  # Assuming the first output is relevant
)

compile_executive_summary_step.add_dependencies([compile_executive_summary_dependency])

# Outputs for Compile Executive Summary Step
executive_summary_output = StepOutput(
    step_id="compile_executive_summary",
    output_key="executive_summary",
    output_value=""
)

compile_executive_summary_step.add_output(executive_summary_output)

# Future Considerations Analysis Step
future_considerations_step = Step(
    step_id="future_considerations",
    name="Future Considerations Analysis",
    description="Analyze and outline future considerations for the management or treatment of the medical condition.",
    execution_actor="FutureAnalyzer"
)

# Outputs for Future Considerations Analysis Step
future_considerations_output = StepOutput(
    step_id="future_considerations",
    output_key="future_considerations",
    output_value=""
)

future_considerations_step.add_output(future_considerations_output)

# Compile Final Report Step
compile_final_report_step = Step(
    step_id="compile_final_report",
    name="Compile Final Report",
    description="Compile the final condition report with all the gathered information.",
    execution_actor="ReportCompiler"
)

# Outputs for Compile Final Report Step
final_report_output = StepOutput(
    step_id="compile_final_report",
    output_key="final_report",
    output_value=""  # Value to be filled after execution
)

compile_final_report_step.add_output(final_report_output)



event = Event(
    name="ConditionReportEvent",
    description="Event to trigger the generation of a condition report."
)

intent = Intent(
    name="GenerateConditionReport",
    description="Intent to generate a detailed report on a medical condition."
)

#Goals
goal1 = Goal(
    name="Understand the Medical Condition",
    description="Goal to understand the medical condition being reported."
)

goal2 = Goal(
    name="Generate a Detailed Report",
    description="Generate a detailed report on the medical condition."
)

goal3 = Goal(
    name="Ensure each section is complete and accurate",
    description="Ensure that each section of the report is complete and accurate."
)

condition_report_workflow = Workflow(
    event=event,
    intent=intent,
    goals=[goal1, goal2, goal3],
    steps=[
        initialize_report_step,
        gather_condition_details_step,
        compile_executive_summary_step,
        identify_key_points_step,
        research_summary_step,
        regulatory_considerations_step,
        future_considerations_step,
        compile_final_report_step
    ],
)