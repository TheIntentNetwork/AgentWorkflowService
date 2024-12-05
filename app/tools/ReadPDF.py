import logging
import os
import uuid
import tempfile
from typing import Dict, Union
from pydantic import BaseModel, Field
from langchain_community.document_loaders import PyPDFLoader
import requests

from .base_tool import BaseTool as BaseTool

class ReadPDF(BaseTool):
    """
    This tool reads the contents of a PDF file using the Browserless API.
    The content can optionally be stored in the caller agent's context when save=True.
    """
    url: str = Field(..., description="The URL of the PDF file to read.")
    save: bool = Field(default=False, description="Whether to save the content with a UUID reference.")

    def run(self) -> Union[str, dict]:
        """
        Reads PDF content and optionally stores it in the caller agent's context.
        
        Returns:
            Union[str, dict]: If save=True, returns dict with content and content_id.
                            If save=False, returns content string directly.
        """
        url = self.url
        api_token = 'eb401be9-db88-4fc7-842b-edf37ed6a67e'
        content = ""
        
        try:
            response = requests.get(url)
            response.raise_for_status()  # Raise an exception for bad status codes

            # Create a temporary file with a unique name
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_pdf:
                try:
                    # Write the PDF content to the temporary file
                    temp_pdf.write(response.content)
                    temp_pdf.flush()

                    # Load the PDF document into an array of documents
                    pdf_loader = PyPDFLoader(temp_pdf.name)
                    pages = pdf_loader.load_and_split()

                    # Read the contents of the PDF
                    content = ""
                    for page in pages:
                        content += page.page_content

                finally:
                    # Clean up: remove the temporary file
                    temp_pdf_path = temp_pdf.name
                    temp_pdf.close()
                    if os.path.exists(temp_pdf_path):
                        os.unlink(temp_pdf_path)

        except requests.RequestException as e:
            content = f"Error downloading PDF: {str(e)}"
        except Exception as e:
            content = f"Error processing PDF: {str(e)}"

        # If save is True and caller agent exists, store in context
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
