# Web Browsing Tools
from .browsing import (
    AnalyzeContent,
    ClickElement,
    GoBack,
    ReadURL,
    Scroll,
    SelectDropdown,
    SendKeys,
    SolveCaptcha
)

# File and Document Url Reading Tools
from .ReadPageText import ReadPageText
from .ReadPDF import ReadPDF

# Search and Retrieval Tools
# OpenAI Tools
from .oai.FileSearch import FileSearch
from .oai.code_interpreter import CodeInterpreter
from .oai.retrieval import Retrieval

# Search Tool
from .SearchTool import SearchTool

# Retrieve Tools
from .RetrieveOutputs import RetrieveOutputs
from .RetrieveContext import RetrieveContext


# Data Management Tools
from .SaveOutput import SaveOutput
from .SaveUserMeta import SaveUserMeta
from .SaveIntakeInformation import SaveIntakeInformation
from .SaveSupplementalInformation import AggregateIntakes
from .SaveResearch import SaveResearch
from .SaveNotesInformation import SaveNotesInformation
from .SetContext import SetContext

# Intake and Form Tools
from .GetIntake import GetIntake
from .GetSupplemental import GetSupplemental
from .GetSupplementals import GetSupplementals
from .CreateSupplementalIntakes import CreateSupplementalIntakes
from .GenerateQuestionnaire import GenerateQuestionnaire

# Agent Management Tools
from .AssignAgents import AssignAgents
from .GetAvailableAgents import GetAvailableAgents

# Context Management Tools
from .LoadUserContext import LoadUserContext, GetUserContext
from .RegisterDependencies import RegisterDependencies

# Report Section Tools
from .SaveToNexusLetters import SaveToNexusLetters
from .SaveToPersonalStatements import SaveToPersonalStatements
from .SaveToConditionExecutiveSummary import SaveToConditionExecutiveSummary
from .SaveToFutureConsiderations import SaveToFutureConsiderations
from .SaveToKeyPoints import SaveToKeyPoints
from .SaveToPointsFor38CFR import SaveToPointsFor38CFR
from .SaveToReportExecutiveSummary import SaveToReportExecutiveSummary
from .SaveToResearchSection import SaveToResearchSection
from .SaveToStaticSections import SaveToStaticSections
from .SaveTo38CFRResearch import SaveTo38CFRResearch


# Report Writing Tools
from .WriteReport import WriteReport
from .WriteConditionReport import WriteConditionReport
from .WriteKeyPoints import WriteKeyPoints
from .Write38CFRPoints import Write38CFRPoints
from .WriteFutureConsiderations import WriteFutureConsiderations
from .WriteResearchSection import WriteResearchSection
from .WriteExecutiveSummary import WriteExecutiveSummary

# Story Tools
from .SaveToStory import SaveToStory
from .SaveToStoryResearch import SaveToStoryResearch
from .SaveStoryURLs import SaveStoryURLs

# Report Generation and Compilation
from .GetReport import GetReport
from .GetNotes import GetNotes
from .CompileDocument import CompileDocument
from .CompileConditionSection import CompileConditionSection



def __getattr__(name):
    if name == 'RetrieveOutputs':
        from .RetrieveOutputs import RetrieveOutputs
        return RetrieveOutputs
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    # File and Document Processing
    "ReadPageText", "ReadPDF", "FileSearch",
    
    # Web Browsing
    "AnalyzeContent", "ClickElement", "GoBack", "ReadURL", 
    "Scroll", "SelectDropdown", "SendKeys", "SolveCaptcha",
    
    # Search and Retrieval
    "SearchTool", "RetrieveOutputs", "RetrieveContext", "Retrieval",
    
    # Data Management
    "SaveOutput", "SaveUserMeta", "SaveIntakeInformation", 
    "SaveSupplementalInformation", "SaveResearch", "SaveNotesInformation",
    "SetContext",
    
    # Intake and Form
    "GetIntake", "GetSupplemental", "GetSupplementals",
    "CreateSupplementalIntakes", "GenerateQuestionnaire",
    
    # Agent Management
    "AssignAgents", "GetAvailableAgents",
    
    # Context Management
    "LoadUserContext", "GetUserContext", "RegisterDependencies",
    
    # Report Section
    "SaveToNexusLetters", "SaveToPersonalStatements",
    "SaveToConditionExecutiveSummary", "SaveToFutureConsiderations",
    "SaveToKeyPoints", "SaveToPointsFor38CFR", "SaveToReportExecutiveSummary",
    "SaveToResearchSection", "SaveToStaticSections", "SaveTo38CFRResearch",
    
    # Report Writing
    "WriteReport", "WriteConditionReport", "WriteKeyPoints",
    "Write38CFRPoints", "WriteFutureConsiderations", "WriteResearchSection",
    "WriteExecutiveSummary",
    
    # Report Generation and Compilation
    "GetReport", "GetNotes", "CompileDocument", "CompileConditionSection",
    
    # OpenAI Tools
    "FileSearch", "Retrieval", "CodeInterpreter",
    
    # Aggregation Tools
    "AggregateIntakes",
    
    # Story Tools
    "SaveToStory", "SaveToStoryResearch", "SaveStoryURLs"
]