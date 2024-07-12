# app/tools/UserHistory.py
from app.models import Session
from app.tools.base_tool import BaseTool



class RetrieveUserHistory(BaseTool):
    async def run(self, session: Session, context: dict) -> dict:
        # Retrieve historical data for the new user
        user_history = ...  # some operation to retrieve history
        context['user_history'] = user_history
        await session.add_to_session_history("RetrieveUserHistory", context)
        return context