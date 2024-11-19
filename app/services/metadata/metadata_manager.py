import json
from typing import Any, Dict, Optional
from app.services.supabase.supabase import Client, Supabase


class MetadataManager:
    def __init__(self, supabase_client: Client):
        self.supabase = supabase_client

    def save_metadata(self, user_id: str, metadata: Dict[str, Any]) -> bool:
        """
        Save or update user metadata in the 'user_metadata' table.

        Args:
            user_id (str): The ID of the user.
            metadata (Dict[str, Any]): The metadata to save.

        Returns:
            bool: True if the operation was successful, False otherwise.
        """
        try:
            metadata_json = json.dumps(metadata)
            response = self.supabase.table('user_metadata').upsert({
                'user_id': user_id,
                'metadata': metadata_json
            }).execute()

            if not response.data:
                print(f"Error response from Supabase: {response} - {response.json()}")
                return False

            print(f"Metadata saved successfully for user {user_id}")
            return True
        except Exception as e:
            print(f"Exception in save_metadata: {str(e)}")
            return False

    def get_metadata(self, user_id: str) -> Dict[str, Any]:
        """
        Retrieve user metadata from the 'user_metadata' table.

        Args:
            user_id (str): The ID of the user.

        Returns:
            Dict[str, Any]: The metadata dictionary or an empty dictionary if not found.
        """
        try:
            response = self.supabase.table('user_metadata').select('metadata').eq('user_id', user_id).execute()
            if not response.data:
                print(f"No metadata found for user {user_id}. Response: {response} - {response.json()}")
                return {}
            return json.loads(response.data[0]['metadata'])
        except Exception as e:
            print(f"Error getting metadata: {str(e)}")
            return {}

    def delete_metadata(self, user_id: str) -> bool:
        """
        Delete user metadata from the 'user_metadata' table.

        Args:
            user_id (str): The ID of the user.

        Returns:
            bool: True if deletion was successful, False otherwise.
        """
        try:
            response = self.supabase.table('user_metadata').delete().eq('user_id', user_id).execute()
            if not response.data:
                print(f"Error deleting metadata for user {user_id}. Response: {response} - {response.json()}")
                return False
            return True
        except Exception as e:
            print(f"Error deleting metadata: {str(e)}")
            return False

    def get_form_data(self, user_id: str, form_type: str) -> Optional[Dict[str, Any]]:
        metadata = self.get_metadata(user_id)
        return metadata.get(form_type)

    def save_form_data(self, user_id: str, form_type: str, form_data: Dict[str, Any]) -> bool:
        metadata = self.get_metadata(user_id)
        metadata[form_type] = form_data
        return self.save_metadata(user_id, metadata)

    def should_run_task(self, user_id: str, task_type: str) -> bool:
        metadata = self.get_metadata(user_id)
        return task_type not in metadata
