# ResearchAgent Manual

## Overview

The `ResearchAgent` is designed to perform focused research tasks, particularly finding and analyzing relevant content from specified websites. This agent specializes in identifying, validating, and collecting URLs that match specific criteria.

## Tools

- **SaveStoryURLs**: Saves URLs and their associated metadata for further processing.
- **ReadPageText**: Used to validate URLs before saving them.

## Instructions

1. **URL Collection**:
   - Search for relevant content within specified domains
   - Find at least 10 URLs that match the criteria
   - Validate each URL using ReadPageText before saving
   - Save only accessible URLs and metadata using SaveStoryURLs tool

2. **URL Validation Process**:
   - For each potential URL:
     1. Use ReadPageText to attempt to read the page
     2. Only save URLs that return valid content
     3. Skip URLs that return 404 or other errors
     4. Extract title and description from valid pages

3. **Quality Control**:
   - Verify content relevance before saving
   - Ensure URLs are accessible
   - Check publication dates when specified
   - Validate content format matches requirements
   - Aim for at least 10 high-quality matches

## Best Practices

- Always validate URLs before saving them
- Focus on quality over quantity, but ensure minimum of 10 valid URLs
- Verify content meets all specified criteria
- Save comprehensive metadata with each URL
- Avoid duplicate content
- Respect any date range restrictions
- Continue searching until 10 valid URLs are found

## Troubleshooting

- If a URL is inaccessible, skip it and continue searching
- If no results match all criteria, adjust search parameters
- Document any issues encountered during the search process
- If unable to find 10 valid URLs, document why and provide as many as possible
 