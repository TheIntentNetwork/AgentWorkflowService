from typing import Dict, Any, List
from app.interfaces.service import IService

class BaseContextManager(IService):
    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name=name, config=config)

    async def get_context(self, key: str) -> Dict[str, Any]:
        raise NotImplementedError

    async def update_context(self, key: str, value: Dict[str, Any]) -> None:
        raise NotImplementedError

    async def delete_context(self, key: str) -> None:
        raise NotImplementedError

    async def fetch_data(self, query: str, params: Dict[str, Any], context_type: str) -> List[Dict[str, Any]]:
        raise NotImplementedError
    
    async def execute_query(self, query: str, params: Dict[str, Any], context_type: str) -> None:
        raise NotImplementedError
