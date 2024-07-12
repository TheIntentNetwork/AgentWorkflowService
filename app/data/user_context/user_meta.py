# app/dal/user_meta_dal.py
from typing import List, Dict, Optional
from supabase import create_client
from app.services.supabase.supabase import Supabase

class UserMeta:
    """
    Data Access Layer for user metadata.
    """
    @staticmethod
    async def get_user_metadata(user_id: str) -> List[Dict[str, str]]:
        response = Supabase.supabase.from_('user_meta').select('meta_key, meta_value').eq('user_id', user_id).execute()
        return response.data
    
    @staticmethod
    async def save_user_metadata(user_id: str, meta_key: str, meta_value: str):
        response = Supabase.supabase.from_('user_meta').upsert({'user_id': user_id, 'meta_key': meta_key, 'meta_value': meta_value}).execute()
        return response.data
    
    @staticmethod
    async def get_user_meta(user_id: str, meta_key: str, meta_key_pattern: Optional[str] = None) -> List[Dict[str, str]]:
        if meta_key_pattern:
            query += f"AND meta_key LIKE '%{meta_key_pattern}%'"
        else:
            query += f"AND meta_key = '{meta_key}'"
            
        response = Supabase.supabase.from_('user_meta').select('meta_value').eq('user_id', user_id).in_('meta_key', meta_key).execute()
        return response.data
