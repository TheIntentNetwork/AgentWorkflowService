# SpecializedBrowsingAgent Manual

## Overview

The `SpecializedBrowsingAgent` is designed to perform advanced web browsing tasks using a suite of specialized tools. This agent is ideal for tasks that require detailed web navigation and content extraction.

## Tools

### Content Reading Tools
- **ReadPageText**: Reads and saves webpage content. Returns a content_id that must be used with SaveToStoryResearch.
- **ReadPDF**: Extracts content from PDF documents. Returns a content_id for use with SaveToStoryResearch.

### Content Processing Tools
- **SaveToStoryResearch**: Processes saved content (using content_id) and extracts metadata including:
  - Facts
  - Key Points
  - Excerpts
  - Summaries

### Navigation Tools
- **Scroll**: Scrolls the web page up or down.
- **SendKeys**: Sends keystrokes to input fields.
- **ClickElement**: Clicks on specified elements on the page.
- **ReadURL**: Opens a specified URL in the browser.
- **GoBack**: Navigates back to the previous page.
- **SelectDropdown**: Selects options from dropdown menus.
- **SolveCaptcha**: Solves captchas encountered on web pages.

## Instructions

1. **Content Reading Process**:
   - First use ReadPageText to read the webpage content
   - Save the content_id returned by ReadPageText
   - This content_id is required for SaveToStoryResearch

2. **Content Processing**:
   - Use SaveToStoryResearch with the saved content_id
   - Provide the content_id in the research_items parameter
   - Wait for the metadata extraction to complete

3. **Example Workflow**:
   ```python
   # Step 1: Read content
   content_result = await ReadPageText(url="https://example.com", save=True).run()
   content_id = content_result['content_id']

   # Step 2: Process content
   research_result = await SaveToStoryResearch(
       research_items=[{
           'content_id': content_id,
           'url': 'https://example.com',
           'title': 'Example Title'
       }]
   ).run()
   ```

## Best Practices

- Always save content using ReadPageText before using SaveToStoryResearch
- Ensure content_id is properly passed between tools
- Verify content is saved before attempting to process it
- Process content in sequential order

## Troubleshooting

- If SaveToStoryResearch fails, verify that:
  1. ReadPageText was called first
  2. content_id was saved
  3. content_id was passed correctly to SaveToStoryResearch
- For navigation issues, verify the URL and page load status
- Check logs for any content reading or processing errors
  