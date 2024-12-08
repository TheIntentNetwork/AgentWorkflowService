import os
import logging
import traceback
from pydantic import BaseModel, Field
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from .base_tool import BaseTool


class SearchTool(BaseTool):
    """
    Use this tool to search for a query on Google and return a list of sites. You can also specify a list of reputable sites to search within if you want to limit the search results to those sites.
    """
    reputable_sites: list[str] = Field(None, description="List of reputable sites to search within.")
    query: str = Field(..., description="The query to search for.")

    def build_service(self):
        return build("customsearch", "v1", developerKey='AIzaSyBvDNixmNIvOp__LkGDa56bTEmAxZ4hvQw')

    def perform_search(self, service, query, site):
        if not site:
            return service.cse().list(
                q=query, 
                cx='e0ad9c99aee184d6a',
            ).execute()
        else:
            return service.cse().list(
                q=query + " site:" + site, 
                cx='e0ad9c99aee184d6a'
            ).execute()

    async def run(self):
        try:
            service = self.build_service()
            titles_and_links = []
            if not self.reputable_sites:
                result = self.perform_search(service, self.query, "")
                titles_and_links.extend(
                    [{'title': item['title'], 'link': item['link']} for item in result.get('items', [])]
                )
            else:
                for site in self.reputable_sites:
                    result = self.perform_search(service, self.query, site)
                    titles_and_links.extend(
                        [{'title': item['title'], 'link': item['link']} for item in result.get('items', [])]
                    )
        except HttpError as e:
            logging.error(f"HTTP Error during search: {e.resp.status}, {e.content}")
            return None, f"HTTP Error: {e.resp.status}"
        except Exception as e:
            logging.error(f"Failed to search: {str(e)}")
            logging.error(traceback.format_exc())
            return None, "Search failed."

        return titles_and_links, "Search completed successfully."

