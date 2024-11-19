from typing import List, Optional
from pydantic import BaseModel

class ResearchItem(BaseModel):
    researchTitle: str
    authorName: str
    researchUrl: str
    summaryOfResearch: str

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
        orm_mode = True
        extra = "allow"
