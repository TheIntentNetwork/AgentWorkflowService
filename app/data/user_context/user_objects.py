# app/data/user_objects/user_objects.py
from datetime import datetime
from typing import List, Dict, Optional
from app.db.database import Database

class UserObjects:
    """
    Data Access Layer for user objects such as forms.
    """
    @staticmethod
    async def get_user_forms(user_id: str) -> List[Dict[str, str]]:
        response = Database.get_instance().supabase.from_('decrypted_forms').select('id, title, status, type, decrypted_form as form, created_at, updated_at').eq('user_id', user_id).execute()
        return response.data
    
    @staticmethod
    async def save_user_forms(user_id: str, form_id: str, title: str, form: str, status: str, type: str):
        response = Database.get_instance().supabase.from_('forms').upsert({'id': form_id, 'user_id': user_id, 'title': title, 'form': form, 'status': status, 'type': type, 'created_at': datetime.now().isoformat(), 'updated_at': datetime.now().isoformat()}).execute()
        return response.data
    
    @staticmethod
    async def get_user_form(user_id: str, form_id: Optional[str] = None, type: Optional[str] = None) -> List[Dict[str, str]]:
        query = Database.get_instance().supabase.from_('decrypted_forms').select('id, title, status, type, decrypted_form as form, created_at, updated_at').eq('user_id', user_id)
        if form_id:
            query = query.eq('id', form_id)
        if type:
            query = query.eq('type', type)
        response = query.execute()
        return response.data
