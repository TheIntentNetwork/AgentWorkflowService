import json
from typing import Any, Dict, Optional, Union, List
from pydantic import BaseModel

class SessionContext(BaseModel):
    session_id: str
    contexts: List[Any] = None

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "contexts": json.dumps(self.contexts)
        }
    
    def from_dict(cls, data: Dict[str, Union[str, List[Any]]]) -> 'SessionContext':
        
        return cls(
            session_id=data['session_id'],
            contexts=json.loads(data['contexts'])
        )

