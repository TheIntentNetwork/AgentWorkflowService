import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

class Supabase:
    url: str = os.environ.get("SUPABASE_URL")
    key: str = os.environ.get("SUPABASE_AUTH_SERVICE_ROLE_KEY")
    supabase: Client = create_client(url, key)

