import asyncio
import os
import re
import sys
import requests
from typing import List, Set, Dict, Any, Optional, Tuple
import urllib.parse
from bs4 import BeautifulSoup

from crawl4ai import (
    AsyncWebCrawler, 
    BrowserConfig, 
    CacheMode, 
    CrawlerRunConfig,
    LLMExtractionStrategy
)

from config import (
    SEEDTABLE_BASE_URL,
    PAYHAWK_CSS_SELECTOR as CSS_SELECTOR, 
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
        provider="openrouter",
        api_token=OPENROUTER_API_KEY,
        model=OPENROUTER_MODEL,
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

def get_company_website_from_seedtable(company_id: str) -> Optional[str]:
    """
    Extract the company's website URL from a SeedTable page using BeautifulSoup.
    
    Args:
        company_id: The company ID/slug in SeedTable URL 
        
    Returns:
        The company's website URL if found, otherwise None
    """
    seedtable_url = f"{SEEDTABLE_BASE_URL}{company_id}"
    print(f"Fetching company website from: {seedtable_url}")
    
    try:
        response = requests.get(seedtable_url)
        if response.status_code != 200:
            print(f"Failed to access SeedTable page: {seedtable_url}")
            return None
        
        # Parse the HTML with BeautifulSoup
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # APPROACH 1: Look for website links in the structured format (with "Websites:" label)
        websites_section = soup.find('span', string='Websites:')
        if websites_section:
            # Find the parent li element that contains the websites list
            parent_li = websites_section.find_parent('li')
            if parent_li:
                # Find the ul element inside that contains the website links
                websites_ul = parent_li.find('ul', class_='flex-1')
                if websites_ul:
                    # Get the first website link
                    first_link = websites_ul.find('a')
                    if first_link and 'href' in first_link.attrs:
                        website_url = first_link['href']
                        print(f"Found company website (from Websites section): {website_url}")
                        return website_url
        
        # APPROACH 2: Look for any social links (LinkedIn, Twitter, etc.)
        social_links_section = soup.find('span', string='Social accounts:')
        if social_links_section:
            parent_li = social_links_section.find_parent('li')
            if parent_li:
                linkedin_link = parent_li.find('a', href=lambda href: href and 'linkedin.com' in href)
                if linkedin_link:
                    # We found a LinkedIn link, extract company name from it
                    linkedin_url = linkedin_link['href']
                    print(f"Found LinkedIn URL: {linkedin_url}")
                    
                    # Try to extract company name and construct website URL
                    company_path = linkedin_url.split('linkedin.com/company/')[-1].split('/')[0].strip()
                    if company_path:
                        # Remove common suffixes like -inc, -gmbh, etc.
                        company_name = re.sub(r'-(inc|gmbh|llc|ltd|ab|co|group)$', '', company_path)
                        
                        # Try common domain formats
                        website_guesses = [
                            f"https://{company_name}.com",
                            f"https://www.{company_name}.com"
                        ]
                        
                        # Try each guess and see if it's valid
                        for guess in website_guesses:
                            try:
                                verify_resp = requests.head(guess, timeout=3)
                                if verify_resp.status_code < 400:  # Valid website
                                    print(f"Found company website (guessed from LinkedIn): {guess}")
                                    return guess
                            except:
                                continue
        
        # APPROACH 3: Check if company name is directly embedded in the page somewhere
        # Extract company name from URL or title
        company_name = company_id.split('-')[0] if '-' in company_id else company_id
        # Remove any encodings/special chars
        company_name = re.sub(r'_+', '', company_name)
        company_name = re.sub(r'%[0-9A-Fa-f]{2}', '', company_name)
        company_name = company_name.lower()
        
        # Try common domain formats
        website_guesses = [
            f"https://{company_name}.com",
            f"https://www.{company_name}.com",
            f"https://{company_name}.io",
            f"https://www.{company_name}.io",
            f"https://{company_name}.co",
            f"https://www.{company_name}.co"
        ]
        
        # Try each guess and see if it's valid
        for guess in website_guesses:
            try:
                print(f"Trying URL guess: {guess}")
                verify_resp = requests.head(guess, timeout=3)
                if verify_resp.status_code < 400:  # Valid website
                    print(f"Found company website (guessed from company name): {guess}")
                    return guess
            except Exception as e:
                print(f"Error checking {guess}: {e}")
                continue
        
        print("No company website found on SeedTable page.")
        return None
        
    except Exception as e:
        print(f"Error fetching company website: {e}")
        return None

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
        link_pattern = re.compile(r'<a\s+(?:[^>]*?\s+)?href="([^"]*)"(?:\s+[^>]*?)?>([^<]*)<\/a>', re.IGNORECASE)
        matches = link_pattern.findall(result.cleaned_html)
        
        # Filter for contact-related links
        for href, text in matches:
            text = text.strip()
            # Skip mailto links for scraping as they're not valid URLs for crawling
            if href.startswith('mailto:'):
                # Extract email from mailto link
                email_match = re.search(r'mailto:([^?]+)', href)
                if email_match:
                    email = email_match.group(1)
                    print(f"Found email in mailto link: {email}")
                continue
                
            if any(keyword.lower() in text.lower() or keyword.lower() in href.lower() for keyword in CONTACT_KEYWORDS):
                # Convert relative URLs to absolute
                if href.startswith('/'):
                    base_url = urllib.parse.urlparse(url)
                    href = f"{base_url.scheme}://{base_url.netloc}{href}"
                
                links.append({"text": text, "url": href})
    
    return links

async def scan_page_for_emails(crawler: AsyncWebCrawler, url: str, session_id: str, llm_strategy: Optional[LLMExtractionStrategy] = None) -> List[str]:
    """Scan a page for email addresses using both regex and LLM extraction."""
    print(f"Scanning page: {url}")
    
    # Check if this is a mailto link, which we can't crawl
    if url.startswith('mailto:'):
        email_match = re.search(r'mailto:([^?]+)', url)
        if email_match:
            return [email_match.group(1)]
        return []
        
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

async def crawl_for_contact_email(seedtable_company_id: Optional[str] = None, website_url: Optional[str] = None):
    """
    Main function to crawl the website for contact email.
    
    Args:
        seedtable_company_id: The ID/slug of the company on SeedTable
        website_url: Optional direct website URL (bypassing SeedTable)
    """
    browser_config = get_browser_config()
    llm_strategy = get_llm_strategy()
    session_id = "email_finder_session"
    
    visited_urls = set()
    found_emails = set()
    
    # First step: Determine the target website URL outside the crawler context
    company_website = None
    company_name = None
    
    if seedtable_company_id:
        # Extract company website from SeedTable using BeautifulSoup
        company_website = get_company_website_from_seedtable(seedtable_company_id)
        company_name = seedtable_company_id.split('-')[0] if '-' in seedtable_company_id else seedtable_company_id
    elif website_url:
        # Use provided website URL directly
        company_website = website_url
        # Extract domain for company name
        domain = re.search(r'https?://(?:www\.)?([^/]+)', website_url)
        company_name = domain.group(1) if domain else "website"
    else:
        print("Error: Either seedtable_company_id or website_url must be provided.")
        return

    if not company_website:
        print("Could not determine company website URL. Exiting.")
        return
    
    # Format output filename
    domain_name = re.sub(r'[^\w]', '_', company_name.lower())
    output_file = f"{domain_name}_contact_info.csv"
    
    # Begin crawling with crawl4ai
    async with AsyncWebCrawler(config=browser_config) as crawler:
        # Second step: Check the main website page
        print(f"\nChecking main company website: {company_website}")
        main_page_emails = await scan_page_for_emails(crawler, company_website, session_id, llm_strategy)
        found_emails.update(main_page_emails)
        visited_urls.add(company_website)
        
        if main_page_emails:
            print(f"Found emails on main page: {main_page_emails}")
        else:
            print("No emails found on main page. Looking for contact links...")
        
        # Extract and follow potentially useful links
        links_to_check = await extract_links_from_page(crawler, company_website, session_id)
        print(f"Found {len(links_to_check)} potential contact links to check")
        
        for link_data in links_to_check:
            link_url = link_data["url"]
            link_text = link_data["text"]
            
            # Skip invalid URLs or already visited URLs
            if link_url in visited_urls or link_url.startswith('mailto:'):
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
    
    # Display results
    if found_emails:
        print("\nContact emails found:")
        for email in found_emails:
            print(f"- {email}")
        
        # Save to CSV file
        with open(output_file, "w") as f:
            f.write("email\n")
            for email in found_emails:
                f.write(f"{email}\n")
        
        print(f"\nSaved {len(found_emails)} email(s) to '{output_file}'")
    else:
        print("\nNo contact emails found. Try adjusting the search parameters or manually inspect the website.")

async def main():
    # Check if a SeedTable company ID was provided as a command-line argument
    if len(sys.argv) > 1:
        seedtable_company_id = sys.argv[1]
        await crawl_for_contact_email(seedtable_company_id=seedtable_company_id)
    else:
        # Default to the example in the prompt
        seedtable_company_id = "Elastic-K4P4WYM"
        print(f"No company ID provided, using default example: {seedtable_company_id}")
        await crawl_for_contact_email(seedtable_company_id=seedtable_company_id)

if __name__ == "__main__":
    asyncio.run(main())