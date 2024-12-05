from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class ResearchItem(BaseModel):
    researchTitle: str
    authorName: str
    researchUrl: str
    summaryOfResearch: str

class RatingCriteria(BaseModel):
    """Represents a single rating criteria from 38 CFR"""
    percentage: int = Field(..., description="The percentage rating (e.g. 0, 10, 30, 50, 70, 100)")
    requirements: List[str] = Field(..., description="The specific requirements or criteria required for this rating level. (e.g. Specific hand or finger, or other specific criteria)")
    criteria: str = Field(..., description="The specific severity or other treatment or diagnostic criteria required for this rating level")
    notes: Optional[str] = Field(None, description="Additional notes or clarifications about this rating level")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata about the rating criteria")

class CFRResearchItem(BaseModel):
    cfr_document_location: str
    cfr_reference_link: str
    excerpts: List[str]
    condition_name: str
    rating_table: List[RatingCriteria] = Field(default_factory=list, description="List of rating criteria")
    diagnostic_code: Optional[str] = Field(None, description="The diagnostic code for this condition")
    notes: Optional[str] = Field(None, description="Additional context or notes about this reference")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata about the CFR research")
    effective_date: Optional[str] = Field(None, description="The effective date of this CFR version")
    last_modified: Optional[str] = Field(None, description="The last modification date of this CFR version")
    section_title: Optional[str] = Field(None, description="The title of the CFR section")
    subsection_title: Optional[str] = Field(None, description="The title of the CFR subsection")
    related_conditions: Optional[List[str]] = Field(default_factory=list, description="List of related conditions referenced in this CFR section")
    related_diagnostic_codes: Optional[List[str]] = Field(default_factory=list, description="List of related diagnostic codes")

class Point(BaseModel):
    pointTitle: str
    point: str

class FutureConsideration(BaseModel):
    considerationTitle: str
    consideration: str

class Condition(BaseModel):
    condition_name: str
    research_section: List[ResearchItem]
    PointsFor38CFR: List[Point]
    PointsFor38CFRRequirements: List[Point]
    cfr_research: List[ResearchItem]
    key_points: List[Point]
    future_considerations: List[FutureConsideration]
    executive_summary: str

class Letter(BaseModel):
    title: str
    condition_name: str
    content: str

class LetterFormat(BaseModel):
    salutation: str
    paragraphs: List[str]
    closing: str

class ChecklistSection(BaseModel):
    title: str
    items: List[str]
    tips: List[str]

class Checklist(BaseModel):
    title: str
    sections: List[ChecklistSection]

class MentalCAndPSection(BaseModel):
    title: str
    tips: List[str]

class MentalCAndPTips(BaseModel):
    sections: List[MentalCAndPSection]

class Resource(BaseModel):
    name: str
    url: str

class FilingStep(BaseModel):
    title: str
    description: str
    resources: List[Resource]

class OnlineFilingGuide(BaseModel):
    title: str
    introduction: Optional[str]
    steps: List[FilingStep]
    additionalResources: List[Resource]

class LetterClosing(BaseModel):
    message: str
    signature: str
    title: str

class FullLetter(BaseModel):
    salutation: str
    paragraphs: List[str]
    closing: LetterClosing

class FAQ(BaseModel):
    question: str
    answer: str

class GlossaryItem(BaseModel):
    term: str
    definition: str

class CFRReference(BaseModel):
    """Represents a reference to a specific part of 38 CFR"""
    document_location: str = Field(..., description="The specific location in 38 CFR (e.g. '4.130')")
    reference_link: str = Field(..., description="Link to the specific CFR section")
    excerpt: str = Field(..., description="The relevant excerpt from the CFR")
    condition_name: str = Field(..., description="The name of the condition this reference applies to")
    rating_table: List[RatingCriteria] = Field(default_factory=list, description="List of rating criteria")
    diagnostic_code: Optional[str] = Field(None, description="The diagnostic code for this condition")
    notes: Optional[str] = Field(None, description="Additional context or notes about this reference")

class Report(BaseModel):
    executive_summary: Optional[List[str]] = []
    conditions: Optional[List[Condition]] = []
    personalStatementLetters: Optional[List[Letter]] = []
    nexusLetters: Optional[List[Letter]] = []
    legendExplanation: Optional[str] = ""
    vaBenefitRatingsCriteria: Optional[str] = ""
    standardOperatingProcedure: Optional[List[str]] = []
    checklist: Optional[Checklist] = None
    mentalCAndPTips: Optional[MentalCAndPTips] = None
    onlineFilingGuide: Optional[OnlineFilingGuide] = None
    letter: Optional[FullLetter] = None
    faqs: Optional[List[FAQ]] = []
    howToContestClaim: Optional[str] = ""
    otherPossibleBenefits: Optional[List[str]] = []
    glossary: Optional[List[GlossaryItem]] = []
    
    
    class Config:
        from_attributes = True
        extra = "allow"
