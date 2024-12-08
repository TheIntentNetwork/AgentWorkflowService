import logging
import os
import uuid
from typing import Dict, Union
from pydantic import BaseModel, Field
from langchain_community.document_loaders import BrowserlessLoader
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from .base_tool import BaseTool

class ReadPageText(BaseTool):
    """
    This tool reads the text contents of an HTML file using the Browserless API. If the retrieval fails, 
    we will use selenium to retrieve the text contents of the page. The content is stored in Redis
    when save=True.
    """
    url: str = Field(..., description="The URL of the HTML file to read.")
    save: bool = Field(default=False, description="Whether to save the content with a UUID reference.")

    async def run(self) -> Union[str, dict]:
        """
        Reads webpage content and optionally stores it in Redis.
        
        Returns:
            Union[str, dict]: If save=True, returns dict with content and content_id.
                            If save=False, returns content string directly.
        """
        logging.debug('URL: %s', self.url)
        api_token = 'eb401be9-db88-4fc7-842b-edf37ed6a67e'
        logging.debug('API Token: %s', api_token)
        
        
        from containers import get_container
        from app.services.cache.redis import RedisService
        redis: RedisService = get_container().redis()
        
        urls = [self.url]
        content = ""
        
        try:
            # Load the HTML using the Browserless API
            loader = BrowserlessLoader(api_token, urls, text_content=True)
            page_text = loader.load()
            logging.debug('HTML Data: %s', page_text)
            content = page_text[0].page_content
        except:
            # Load the HTML using Selenium
            try: 
                options = Options()
                options.add_argument('--headless')
                options.add_argument('--disable-gpu')
                options.add_argument('--no-sandbox')
                options.add_argument('--disable-dev-shm-usage')
                wd = webdriver.Chrome(options=options)
                wd.get(self.url)
                WebDriverWait(wd, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
                content = wd.find_element_by_tag_name('body').text
                wd.quit()
            except:
                content = "Error: Could not retrieve the text contents of the page."

        # If save is True, generate UUID and store content in Redis
        if self.save:
            content_id = str(uuid.uuid4())
            content_key = f"content:{content_id}"
            await redis.client.set(content_key, content)
            
            return {
                "content": content,
                "content_id": content_id
            }
        
        # If save is False, return content directly
        return content

    @classmethod
    async def get_stored_content(cls, content_id: str) -> str:
        """
        Retrieve stored content by UUID from Redis.
        
        Args:
            content_id: The UUID of the stored content
            
        Returns:
            str: The stored content or error message if not found
        """
        from containers import get_container
        redis = get_container().redis()
        content_key = f"content:{content_id}"
        content = await redis.client.get(content_key)
        return content if content else "Error: Content not found"

    @classmethod
    async def clear_stored_content(cls, content_id: str = None) -> None:
        """
        Clear stored content from Redis. If no content_id is provided, clears all content keys.
        
        Args:
            content_id: Optional UUID of specific content to clear
        """
        from containers import get_container
        redis = get_container().redis()
        if content_id:
            content_key = f"content:{content_id}"
            await redis.client.delete(content_key)
        else:
            # Delete all content keys
            pattern = "content:*"
            keys = await redis.client.keys(pattern)
            if keys:
                await redis.client.delete(*keys)
