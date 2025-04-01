import asyncio
import os
import re
from typing import List, Set, Dict, Any, Optional

from crawl4ai import (
    AsyncWebCrawler, 
    BrowserConfig, 
    CacheMode, 
    CrawlerRunConfig,
    LLMExtractionStrategy
)

from config import (
    PAYHAWK_BASE_URL, 
    PAYHAWK_CSS_SELECTOR, 
    CONTACT_KEYWORDS,
    OPENROUTER_API_KEY,
    OPENROUTER_MODEL
)

# Regular expression for finding email addresses
EMAIL_REGEX = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'

def get_browser_config() -> BrowserConfig:
    """Returns the browser configuration for the crawler."""
    return BrowserConfig(
        browser_type="chromium",
        headless=False,
        verbose=True,
    )

def get_llm_strategy() -> LLMExtractionStrategy:
    """Returns the LLM extraction strategy configuration."""
    return LLMExtractionStrategy(
        provider="openrouter",  # Changed from DeepSeek model to OpenRouter provider
        api_token=OPENROUTER_API_KEY,
        model=OPENROUTER_MODEL,  # Specify the model separately when using OpenRouter
        extraction_type="custom",
        instruction=(
            "Extract all email addresses from the content that appear to be contact emails. "
            "Also identify any contact links or support pages. Format your response as a JSON object "
            "with keys 'emails' (array of email addresses) and 'contact_links' (array of objects with 'text' and 'url')."
        ),
        input_format="html",
        verbose=True,
    )

def extract_emails_from_text(text: str) -> List[str]:
    """Extract email addresses from text using regex."""
    if not text:
        return []
    return re.findall(EMAIL_REGEX, text)

async def extract_links_from_page(crawler: AsyncWebCrawler, url: str, session_id: str) -> List[Dict[str, str]]:
    """Extract all links from the page that might lead to contact information."""
    result = await crawler.arun(
        url=url,
        config=CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            session_id=session_id,
        ),
    )
    
    links = []
    if result.success:
        # Use a simple regex to extract links and their text from HTML
        # This is basic and might not catch all links - consider using a proper HTML parser for production
        link_pattern = re.compile(r'<a\s+(?:[^>]*?\s+)?href="([^"]*)"(?:\s+[^>]*?)?>([^<]*)<\/a>', re.IGNORECASE)
        matches = link_pattern.findall(result.cleaned_html)
        
        # Filter for contact-related links
        for href, text in matches:
            text = text.strip()
            if any(keyword.lower() in text.lower() or keyword.lower() in href.lower() for keyword in CONTACT_KEYWORDS):
                # Convert relative URLs to absolute
                if href.startswith('/'):
                    href = PAYHAWK_BASE_URL.rstrip('/') + href
                
                links.append({"text": text, "url": href})
    
    return links

async def scan_page_for_emails(crawler: AsyncWebCrawler, url: str, session_id: str, llm_strategy: Optional[LLMExtractionStrategy] = None) -> List[str]:
    """Scan a page for email addresses using both regex and LLM extraction."""
    print(f"Scanning page: {url}")
    
    emails = []
    
    # First approach: Direct HTML scanning with regex
    result = await crawler.arun(
        url=url,
        config=CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            session_id=session_id,
        ),
    )
    
    if result.success:
        # Extract emails from raw HTML
        emails = extract_emails_from_text(result.cleaned_html)
    
    # Second approach: Use LLM to extract emails if provided
    if llm_strategy and not emails:
        try:
            llm_result = await crawler.arun(
                url=url,
                config=CrawlerRunConfig(
                    cache_mode=CacheMode.BYPASS,
                    extraction_strategy=llm_strategy,
                    session_id=session_id,
                ),
            )
            
            if llm_result.success and llm_result.extracted_content:
                try:
                    # Parse LLM output as JSON
                    import json
                    extracted_data = json.loads(llm_result.extracted_content)
                    if extracted_data and 'emails' in extracted_data:
                        emails.extend(extracted_data['emails'])
                except json.JSONDecodeError:
                    # If not valid JSON, try to extract emails using regex
                    emails.extend(extract_emails_from_text(llm_result.extracted_content))
        except Exception as e:
            print(f"LLM extraction error: {e}")
            print("Falling back to regex extraction only.")
    
    return emails

async def crawl_for_contact_email():
    """Main function to crawl the website for contact email."""
    browser_config = get_browser_config()
    llm_strategy = get_llm_strategy()
    session_id = "payhawk_contact_email_crawl"
    
    visited_urls = set()
    found_emails = set()
    
    async with AsyncWebCrawler(config=browser_config) as crawler:
        # First, check the main page
        print(f"Checking main page: {PAYHAWK_BASE_URL}")
        main_page_emails = await scan_page_for_emails(crawler, PAYHAWK_BASE_URL, session_id, llm_strategy)
        found_emails.update(main_page_emails)
        visited_urls.add(PAYHAWK_BASE_URL)
        
        if main_page_emails:
            print(f"Found emails on main page: {main_page_emails}")
        else:
            print("No emails found on main page. Looking for contact links...")
        
        # Extract and follow potentially useful links
        links_to_check = await extract_links_from_page(crawler, PAYHAWK_BASE_URL, session_id)
        print(f"Found {len(links_to_check)} potential contact links to check")
        
        for link_data in links_to_check:
            link_url = link_data["url"]
            link_text = link_data["text"]
            
            if link_url in visited_urls:
                continue
                
            print(f"Checking link: '{link_text}' at {link_url}")
            visited_urls.add(link_url)
            
            # Pause between requests
            await asyncio.sleep(1)
            
            # Check the linked page for emails
            link_emails = await scan_page_for_emails(crawler, link_url, session_id, llm_strategy)
            
            if link_emails:
                print(f"Found emails on page '{link_text}': {link_emails}")
                found_emails.update(link_emails)
            
            # If we've found emails, we can stop
            if found_emails:
                break
    
    # Display results
    if found_emails:
        print("\nContact emails found:")
        for email in found_emails:
            print(f"- {email}")
        
        # Save to CSV file
        with open("payhawk_contact_info.csv", "w") as f:
            f.write("email\n")
            for email in found_emails:
                f.write(f"{email}\n")
        
        print(f"\nSaved {len(found_emails)} email(s) to 'payhawk_contact_info.csv'")
    else:
        print("\nNo contact emails found. Try adjusting the search parameters or manually inspect the website.")

async def main():
    await crawl_for_contact_email()

if __name__ == "__main__":
    asyncio.run(main())