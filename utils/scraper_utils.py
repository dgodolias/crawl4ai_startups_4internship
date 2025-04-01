import json
import os
import asyncio
from typing import List, Set, Tuple
import re
from bs4 import BeautifulSoup
from crawl4ai import (
    AsyncWebCrawler,
    BrowserConfig,
    CacheMode,
    CrawlerRunConfig,
    LLMExtractionStrategy,
)
from models.venue import Startup
from utils.data_utils import is_complete_startup, is_duplicate_startup
from config import OPENROUTER_API_KEY, MODEL_NAME

def get_browser_config() -> BrowserConfig:
    """
    Returns the browser configuration for the crawler.
    Returns:
        BrowserConfig: The configuration settings for the browser.
    """
    # https://docs.crawl4ai.com/core/browser-crawler-config/
    return BrowserConfig(
        browser_type="chromium",  # Type of browser to simulate
        headless=False,  # Whether to run in headless mode (no GUI)
        verbose=True,  # Enable verbose logging
    )

def get_llm_strategy() -> LLMExtractionStrategy:
    """
    Returns the configuration for the language model extraction strategy.
    Returns:
        LLMExtractionStrategy: The settings for how to extract data using LLM.
    """
    # https://docs.crawl4ai.com/api/strategies/#llmextractionstrategy
    return LLMExtractionStrategy(
        provider="openrouter",
        model=MODEL_NAME,  # Use DeepSeek model from config
        api_token=OPENROUTER_API_KEY,  # API token from config
        schema=Startup.model_json_schema(),  # JSON schema of the data model
        extraction_type="schema",  # Type of extraction to perform
        instruction=(
            "Extract startup information including 'name' and 'website'. "
            "If available, also extract 'description', 'location', and 'industry'. "
            "If the website is not directly visible in the text, look for it in the HTML href attributes."
        ),
        input_format="markdown",  # Format of the input content
        verbose=True,  # Enable verbose logging
    )

def extract_elements(html_content, css_selector):
    """
    Extract elements from HTML content using BeautifulSoup.
    Args:
        html_content (str): The HTML content to extract elements from.
        css_selector (str): The CSS selector to use for extraction.
    Returns:
        list: A list of dictionaries with extracted element data.
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    elements = soup.select(css_selector)
    
    result = []
    for element in elements:
        # Extract text and href attributes from the element
        element_data = {
            "text": element.get_text(strip=True),
            "html": str(element),
        }
        
        # Extract href if this is a link
        if element.name == 'a' and element.has_attr('href'):
            element_data["href"] = element['href']
            
        result.append(element_data)
    
    return result

async def check_no_results(
    crawler: AsyncWebCrawler,
    url: str,
    session_id: str,
) -> bool:
    """
    Checks if the "No Results Found" message is present on the page.
    Args:
        crawler (AsyncWebCrawler): The web crawler instance.
        url (str): The URL to check.
        session_id (str): The session identifier.
    Returns:
        bool: True if no results are found, False otherwise.
    """
    # Fetch the page without any CSS selector or extraction strategy
    result = await crawler.arun(
        url=url,
        config=CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            session_id=session_id,
        ),
    )
    if result.success:
        # F6S specific check for no results
        if "No companies found" in result.cleaned_html:
            return True
    else:
        print(
            f"Error fetching page for 'No Results' check: {result.error_message}"
        )
    return False

async def get_startup_website(
    crawler: AsyncWebCrawler,
    startup_page_url: str,
    session_id: str,
) -> str:
    """
    Navigate to a startup's page and extract its website.
    Args:
        crawler (AsyncWebCrawler): The web crawler instance.
        startup_page_url (str): The URL of the startup's page.
        session_id (str): The session identifier.
    Returns:
        str: The website URL if found, empty string otherwise.
    """
    result = await crawler.arun(
        url=startup_page_url,
        config=CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            session_id=session_id,
        ),
    )
    
    if not result.success:
        print(f"Error fetching startup page: {result.error_message}")
        return ""
    
    # Look for website link on the startup's page using BeautifulSoup
    soup = BeautifulSoup(result.cleaned_html, 'html.parser')
    website_candidates = soup.select("a[href^='http']:not([href*='f6s.com'])")
    
    # Filter for likely website links
    for candidate in website_candidates:
        href = candidate.get('href', '')
        if href and href.startswith("http") and "f6s.com" not in href:
            return href
    
    return ""

async def fetch_and_process_page(
    crawler: AsyncWebCrawler,
    page_number: int,
    base_url: str,
    css_selector: str,
    llm_strategy: LLMExtractionStrategy,
    session_id: str,
    required_keys: List[str],
    seen_names: Set[str],
) -> Tuple[List[dict], bool]:
    """
    Fetches and processes a single page of startup data.
    Args:
        crawler (AsyncWebCrawler): The web crawler instance.
        page_number (int): The page number to fetch.
        base_url (str): The base URL of the website.
        css_selector (str): The CSS selector to target the content.
        llm_strategy (LLMExtractionStrategy): The LLM extraction strategy.
        session_id (str): The session identifier.
        required_keys (List[str]): List of required keys in the startup data.
        seen_names (Set[str]): Set of startup names that have already been seen.
    Returns:
        Tuple[List[dict], bool]:
            - List[dict]: A list of processed startups from the page.
            - bool: A flag indicating if no more results were found.
    """
    url = base_url
    if page_number > 1:
        url = f"{base_url}?page={page_number}"
    
    print(f"Loading page {page_number}...")
    
    # Check if no results are found
    no_results = await check_no_results(crawler, url, session_id)
    if no_results:
        return [], True  # No more results, signal to stop crawling
    
    # Fetch page content
    result = await crawler.arun(
        url=url,
        config=CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            session_id=session_id,
        ),
    )
    
    if not result.success:
        print(f"Error fetching page {page_number}: {result.error_message}")
        return [], False
    
    # Extract startup items on the page using BeautifulSoup
    soup = BeautifulSoup(result.cleaned_html, 'html.parser')
    startup_items = soup.select(css_selector)
    
    if not startup_items:
        print(f"No startup items found on page {page_number}.")
        return [], False
    
    complete_startups = []
    for item in startup_items:
        # Extract startup name from the item
        name_element = item.select_one("h3")
        if not name_element:
            continue
        
        startup_name = name_element.get_text(strip=True)
        if not startup_name or is_duplicate_startup(startup_name, seen_names):
            continue
        
        # Find "See Full Profile" link
        profile_links = item.select("a.viewProfileLink, a[href*='profile']")
        if not profile_links:
            continue
            
        profile_url = ""
        for link in profile_links:
            href = link.get('href', '')
            if href and ("profile" in href.lower() or "view" in href.lower()):
                # Make sure it's a full URL
                if href.startswith("/"):
                    profile_url = f"https://www.f6s.com{href}"
                else:
                    profile_url = href
                break
                
        if not profile_url:
            continue
            
        # Visit the startup's profile page to get the website
        print(f"Visiting profile for: {startup_name}")
        website = await get_startup_website(crawler, profile_url, session_id)
        
        # Create startup object
        startup = {
            "name": startup_name,
            "website": website,
        }
        
        # Extract additional information if available
        description_element = item.select_one(".description, .summary")
        if description_element:
            startup["description"] = description_element.get_text(strip=True)
            
        location_element = item.select_one(".location")
        if location_element:
            startup["location"] = location_element.get_text(strip=True)
            
        industry_element = item.select_one(".industry, .category")
        if industry_element:
            startup["industry"] = industry_element.get_text(strip=True)
        
        # Check if we have required fields
        if is_complete_startup(startup, required_keys):
            seen_names.add(startup_name)
            complete_startups.append(startup)
            print(f"Added startup: {startup_name} with website: {website}")
        
        # Be polite and avoid rate limiting
        await asyncio.sleep(2)
    
    if not complete_startups:
        print(f"No complete startup data found on page {page_number}.")
    else:
        print(f"Extracted {len(complete_startups)} startups from page {page_number}.")
    
    return complete_startups, False  # Continue crawling
