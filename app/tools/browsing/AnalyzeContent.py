import base64

from app.tools.base_tool import BaseTool as BaseTool
from pydantic import Field

from app.tools.browsing.util import get_web_driver, set_web_driver, get_b64_screenshot
from app.utilities import get_openai_client


class AnalyzeContent(BaseTool):
    """
    This tool analyzes the current web page to help understand how to navigate but not to actually navigate. Use the ReadPDF tools to review the actual contents of the page. Make sure to read 
    the URL first with ReadURL tool or navigate to the right page with ClickElement tool. Do not use this tool to get 
    direct links to other pages. It is not intended to be used for navigation.
    """
    question: str = Field(
        ..., description="Question to ask about the elements of the current webpage to understand where to navigate next and where elements are located."
    )

    def run(self):
        wd = get_web_driver()

        client = get_openai_client()

        screenshot = get_b64_screenshot(wd)

        # save screenshot locally
        with open("screenshot.png", "wb") as fh:
            fh.write(base64.b64decode(screenshot))

        messages = [
            {
                "role": "system",
                "content": "As a web scraping tool, your primary task is to accurately extract and provide information in response to user queries based on webpage screenshots. When a user asks a question, analyze the provided screenshot of the webpage for relevant information. Your goal is to ensure relevant data retrieval from webpages. If some elements are obscured by pop ups, notify the user about how to close them. If there might be additional information on the page regarding the user's question by scrolling up or down, notify the user about it as well. Once you have found the information you are looking for, you will use the 'ReadPageText' or 'ReadPDF' tool to gather the contents of the page or PDF for analysis to read and understand the actual contents to report or write a summary of the page.",
            },
            {
                "role": "user", 
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{screenshot}"
                        }
                    },
                    {
                        "type": "text",
                        "text": f"{self.question}",
                    }
                ]
            }
        ]

        response = client.chat.completions.create(
            model="gpt-4o", # Updated from deprecated gpt-4-vision-preview
            messages=messages,
            max_tokens=1024,
        )

        message = response.choices[0].message
        message_text = message.content

        set_web_driver(wd)

        return message_text
