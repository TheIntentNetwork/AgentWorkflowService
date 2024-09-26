from datetime import datetime
from typing import Any, List, Dict, Optional
from app.db.database import Database

class NodeTemplates:
    """
    Data Access Layer for node templates.
    """
    @staticmethod
    async def get_node_templates(node_name: str) -> List[Dict[str, Any]]:
        response = Database.get_instance().supabase.from_('node_templates').select('*').eq('name', node_name).execute()
        return response.data

    @staticmethod
    async def save_node_template(template_id: str, name: str, type: str, description: str, context_info: Dict[str, Any], process_item_level: bool, order_sequence: int):
        response = Database.get_instance().supabase.from_('node_templates').upsert({
            'id': template_id,
            'name': name,
            'type': type,
            'description': description,
            'context_info': context_info,
            'process_item_level': process_item_level,
            'order_sequence': order_sequence,
            'updated_at': datetime.now().isoformat()
        }).execute()
        return response.data

    @staticmethod
    async def get_node_template(template_id: Optional[str] = None, type: Optional[str] = None) -> List[Dict[str, Any]]:
        query = Database.get_instance().supabase.from_('node_templates').select('*')
        if template_id:
            query = query.eq('id', template_id)
        if type:
            query = query.eq('type', type)
        response = query.execute()
        return response.data

    @staticmethod
    async def get_templates_by_type(type: str) -> List[Dict[str, Any]]:
        response = Database.get_instance().supabase.from_('node_templates').select('*').eq('type', type).order('order_sequence').execute()
        return response.data

    @staticmethod
    async def update_order_sequence(template_id: str, new_order: int) -> Dict[str, Any]:
        response = Database.get_instance().supabase.from_('node_templates').update({'order_sequence': new_order, 'updated_at': datetime.now().isoformat()}).eq('id', template_id).execute()
        return response.data[0] if response.data else None

    @staticmethod
    async def delete_node_template(template_id: str) -> bool:
        response = Database.get_instance().supabase.from_('node_templates').delete().eq('id', template_id).execute()
        return len(response.data) > 0
