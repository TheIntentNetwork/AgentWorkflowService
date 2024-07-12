import logging
import os
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
    This tool reads the text contents of an HTML file using the Browserless API. If the retrieval fails, we will use selenium to retrieve the text contents of the page.
    """
    url: str = Field(..., description="The URL of the HTML file to read.")

    def run(self) -> None:
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
        # Return the content of the page
        return content
