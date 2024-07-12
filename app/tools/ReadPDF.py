import logging
import os
from pydantic import BaseModel, Field
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.document_loaders import UnstructuredAPIFileLoader
from langchain_community.document_loaders import BrowserlessLoader
import requests

from .base_tool import BaseTool as BaseTool

class ReadPDF(BaseTool):
    """
    This tool reads the contents of a PDF file using the Browserless API.
    """
    url: str = Field(..., description="The URL of the PDF file to read.")

    def run(self) -> None:

        # Download the PDF file from the URL
        ## curl -X POST \
        #  https://chrome.browserless.io/pdf?token=MY_API_TOKEN \
        #  -H 'Cache-Control: no-cache' \
        #  -H 'Content-Type: application/json' \
        #  -d '{
        #  "url": "https://example.com/",
        #  "options": {
        #    "displayHeaderFooter": true,
        #    "printBackground": false,
        #    "format": "A0"
        #  }
        #}'
        url = self.url
        
        api_token = 'eb401be9-db88-4fc7-842b-edf37ed6a67e'
        
        response = requests.get(url)

        #Write the PDF file to disk
        with open('pdf.pdf', 'wb') as f:
            f.write(response.content)

        # Load the PDF document into an array of documents
        pdf_loader = PyPDFLoader('pdf.pdf')
        pages = pdf_loader.load_and_split()

        # Read the contents of the PDF
        content = ""
        for page in pages:
            content += page.page_content

        return content
