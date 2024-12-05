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

from .base_tool import BaseTool as BaseTool

class ReadPageText(BaseTool):
    """
    This tool reads the text contents of an HTML file using the Browserless API. If the retrieval fails, 
    we will use selenium to retrieve the text contents of the page. The content can optionally be stored 
    in the caller agent's context when save=True.
    """
    url: str = Field(..., description="The URL of the HTML file to read.")
    save: bool = Field(default=False, description="Whether to save the content with a UUID reference.")

    def run(self) -> Union[str, dict]:
        """
        Reads webpage content and optionally stores it in the caller agent's context.
        
        Returns:
            Union[str, dict]: If save=True, returns dict with content and content_id.
                            If save=False, returns content string directly.
        """
        logging.debug('URL: %s', self.url)
        api_token = 'eb401be9-db88-4fc7-842b-edf37ed6a67e'
        logging.debug('API Token: %s', api_token)
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

        # If save is True, generate UUID and store content in caller's context
        if self.save and hasattr(self, '_caller_agent'):
            content_id = str(uuid.uuid4())
            if not hasattr(self._caller_agent.context_info, 'context'):
                self._caller_agent.context_info.context = {}
            self._caller_agent.context_info.context[content_id] = content
            
            return {
                "content": content,
                "content_id": content_id
            }
        
        # If save is False or no caller agent, return content directly
        return content

    @classmethod
    def get_stored_content(cls, content_id: str) -> str:
        """
        Retrieve stored content by UUID.
        
        Args:
            content_id: The UUID of the stored content
            
        Returns:
            str: The stored content or error message if not found
        """
        return cls._page_contents.get(content_id, "Error: Content not found")

    @classmethod
    def clear_stored_content(cls, content_id: str = None) -> None:
        """
        Clear stored content. If no content_id is provided, clears all stored content.
        
        Args:
            content_id: Optional UUID of specific content to clear
        """
        if content_id:
            cls._page_contents.pop(content_id, None)
        else:
            cls._page_contents.clear()
