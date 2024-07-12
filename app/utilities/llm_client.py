import openai
import anthropic
import threading
import os
import instructor

from dotenv import load_dotenv

load_dotenv("../../.env")

client_lock = threading.Lock()
client = None

def get_openai_client():
    global client
    with client_lock:
        if client is None:
            # Check if the API key is set
            api_key = openai.api_key or os.getenv('OPENAI_API_KEY')
            if api_key is None:
                raise ValueError("OpenAI API key is not set. Please set it using set_openai_key.")
            client = instructor.patch(openai.OpenAI(api_key='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',
                                                    max_retries=5, default_headers={"OpenAI-Beta": "assistants=v2"}))
    return client

def set_openai_client(new_client):
    global client
    with client_lock:
        client = new_client

def set_openai_key(key):
    if not key:
        raise ValueError("Invalid API key. The API key cannot be empty.")
    openai.api_key = key

def get_anthropic_client():
    # Check if the API key is set
    api_key = os.getenv('ANTHROPIC_API_KEY')
    if api_key is None:
        raise ValueError("Anthropic API key is not set. Please set it using set_anthropic_key.")
    return instructor.patch(instructor.Anthropic(api_key=api_key, max_retries=5))

def set_anthropic_client(new_client):
    global anthropic_client
    with client_lock:
        anthropic_client = new_client

def set_anthropic_key(key):
    if not key:
        raise ValueError("Invalid API key. The API key cannot be empty.")
    anthropic.Client.api_key = key
