from pydantic import BaseModel
from typing import Dict, List, Optional, Any
from datetime import datetime

class SectionMetadata(BaseModel):
    section_name: str
    last_updated: datetime
    status: str
    item_count: int
    additional_info: Optional[Dict[str, Any]] = None

class ConditionMetadata(BaseModel):
    condition_name: str
    sections: Dict[str, SectionMetadata]
    last_updated: datetime

class ReportMetadata(BaseModel):
    user_id: str
    report_id: Optional[str]
    creation_date: datetime
    last_updated: datetime
    conditions: List[ConditionMetadata]
    static_sections: Dict[str, SectionMetadata]
    status: str
    version: str = "1.0"