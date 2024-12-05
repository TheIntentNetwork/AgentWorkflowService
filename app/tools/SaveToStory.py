from datetime import datetime
import json
import traceback
import os
import httpx
from pydantic import BaseModel, Field
from typing import ClassVar, Dict, Any, List, Optional
from app.tools.base_tool import BaseTool
from app.logging_config import configure_logger
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

class SharedImage(BaseModel):
    alt: str
    sharedMedia: str

class BlogBanner(BaseModel):
    orientation: str = "horizontal"
    Heading: str
    text: str
    backgroundColor: str = "#FFFFFF"
    backgroundImage: str
    label: str
    buttonText: str
    buttonLink: str

class OptIn(BaseModel):
    buttonText: str
    title: str
    description: str
    label: str
    referral: str

class CallToAction(BaseModel):
    buttonText: str
    buttonLink: str
    title: str
    label: str

class StoryMetadata(BaseModel):
    title: str
    slug: str
    createAt: str
    description: str
    metaTitle: str
    metaDescription: str
    featuredImage: str
    sharedImage: SharedImage
    blogBanner: List[BlogBanner]
    optIn: List[OptIn]
    callToAction: List[CallToAction]

class SaveToStory(BaseTool):
    """
    Tool for saving story paragraphs and metadata to context and Strapi.
    The story will be used to construct the final story document.
    """
    result_keys: ClassVar[List[str]] = ['story', 'strapi_response']
    
    story_paragraphs: List[str] = Field(..., description="The paragraphs of the story to save")
    metadata: StoryMetadata = Field(..., description="Story metadata including title, images, and components")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((httpx.ConnectTimeout, httpx.ConnectError, httpx.ReadTimeout))
    )
    async def _make_strapi_request(self, url: str, headers: Dict[str, str], data: Dict[str, Any], method: str = "POST") -> Dict[str, Any]:
        """
        Make HTTP request to Strapi with retry logic and improved error handling
        
        Args:
            url: Strapi API endpoint
            headers: Request headers
            data: Request payload
            method: HTTP method (default: POST)
            
        Returns:
            Dict[str, Any]: Strapi response
            
        Raises:
            httpx.HTTPStatusError: For HTTP errors
            httpx.RequestError: For network/connection errors
        """
        timeout_settings = httpx.Timeout(10.0, connect=5.0)
        async with httpx.AsyncClient(timeout=timeout_settings) as client:
            try:
                if method.upper() == "POST":
                    response = await client.post(url, json=data, headers=headers)
                elif method.upper() == "PUT":
                    response = await client.put(url, json=data, headers=headers)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")

                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger = configure_logger('SaveToStory')
                logger.error(f"HTTP error occurred: {e.response.status_code} - {e.response.text}")
                # Add specific error handling for common Strapi errors
                if e.response.status_code == 413:
                    raise RuntimeError("Content too large for Strapi")
                elif e.response.status_code == 401:
                    raise RuntimeError("Invalid Strapi authentication token")
                raise
            except httpx.RequestError as e:
                logger = configure_logger('SaveToStory')
                logger.error(f"Request error occurred: {str(e)}")
                raise

    def _prepare_strapi_data(self, metadata_dict: Dict[str, Any], story_paragraphs: List[str]) -> Dict[str, Any]:
        """
        Prepare data structure for Strapi API
        
        Args:
            metadata_dict: Story metadata
            story_paragraphs: List of story paragraphs
            
        Returns:
            Dict[str, Any]: Formatted data for Strapi
        """
        return {
            "data": {
                "title": metadata_dict["title"],
                "slug": metadata_dict["slug"],
                "createAt": datetime.now().isoformat(),
                "description": "\n\n".join(story_paragraphs),
                "metaTitle": metadata_dict["metaTitle"],
                "metaDescription": metadata_dict["metaDescription"],
                #"featuredImage": metadata_dict.get("featuredImage"),
                #"sharedImage": metadata_dict.get("sharedImage"),
                #"blogBanner": metadata_dict.get("blogBanner"),
                #"optIn": metadata_dict.get("optIn"),
                #"callToAction": metadata_dict.get("callToAction"),
                #"status": "draft"
            }
        }

    async def run(self) -> Dict[str, Any]:
        logger = configure_logger('SaveToStory')
        logger.info("Running SaveToStory tool")
        
        try:
            # Validate inputs
            if not self.story_paragraphs:
                raise ValueError("No story paragraphs provided")

            # Validate Strapi token
            strapi_token = os.getenv('STRAPI_TOKEN')
            if not strapi_token:
                raise ValueError("STRAPI_TOKEN environment variable is not set")

            # Prepare story data for context
            story = {
                "paragraphs": self.story_paragraphs,
                "last_updated": datetime.now().isoformat(),
                "metadata": self.metadata.model_dump()
            }
            
            # Save to context
            self._caller_agent.context_info.context["story"] = json.dumps(
                story,
                skipkeys=True,
                default=str
            )

            # Prepare Strapi data
            strapi_data = self._prepare_strapi_data(
                self.metadata.model_dump(),
                self.story_paragraphs
            )

            # Send to Strapi
            strapi_url = os.getenv('STRAPI_API_URL', 'https://strapi.dev.vaclaims-academy.com/api/blogs')
            headers = {
                "Authorization": f"Bearer {strapi_token}",
                "Content-Type": "application/json"
            }

            try:
                strapi_response = await self._make_strapi_request(strapi_url, headers, strapi_data)
                logger.info("Story successfully saved to Strapi")
                
                return {
                    "story": story,
                    "strapi_response": strapi_response
                }
            
            except (httpx.HTTPStatusError, httpx.RequestError) as e:
                error_msg = f"Failed to save to Strapi: {str(e)}"
                logger.error(error_msg)
                raise RuntimeError(error_msg)
        
        except Exception as e:
            logger.error(f"Error in SaveToStory: {e}")
            logger.error(traceback.format_exc())
            raise
