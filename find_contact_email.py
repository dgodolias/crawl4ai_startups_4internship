import asyncio
import os
import re
import sys
import csv
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

def get_company_info_from_seedtable(company_id: str) -> Dict[str, Any]:
    """
    Extract company information from a SeedTable page using BeautifulSoup.
    
    Args:
        company_id: The company ID/slug in SeedTable URL 
        
    Returns:
        Dictionary with company information including name, website(s), and social accounts
    """
    company_info = {
        "name": company_id.split('-')[0] if '-' in company_id else company_id,
        "websites": [],
        "linkedin": None,
        "emails": []
    }
    
    # Clean up company name by removing special characters and URL encodings
    company_info["name"] = re.sub(r'_+', ' ', company_info["name"])
    company_info["name"] = re.sub(r'%[0-9A-Fa-f]{2}', '', company_info["name"])
    company_info["name"] = company_info["name"].strip()
    
    seedtable_url = f"{SEEDTABLE_BASE_URL}{company_id}"
    print(f"Fetching company info from: {seedtable_url}")
    
    try:
        response = requests.get(seedtable_url)
        if response.status_code != 200:
            print(f"Failed to access SeedTable page: {seedtable_url}")
            return company_info
        
        # Parse the HTML with BeautifulSoup
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Look for website links - first find the "Websites:" label then get the links
        websites_section = soup.find('span', string='Websites:')
        if websites_section:
            # Find the parent li element that contains the websites list
            parent_li = websites_section.find_parent('li')
            if parent_li:
                # Find the ul element inside that contains the website links
                websites_ul = parent_li.find('ul', class_='flex-1')
                if websites_ul:
                    # Get all website links
                    website_links = websites_ul.find_all('a')
                    for link in website_links:
                        if 'href' in link.attrs:
                            website_url = link['href']
                            company_info["websites"].append(website_url)
                    
                    if company_info["websites"]:
                        print(f"Found company websites: {company_info['websites']}")
        
        # Look for social links to find LinkedIn
        social_links_section = soup.find('span', string='Social accounts:')
        if social_links_section:
            parent_li = social_links_section.find_parent('li')
            if parent_li:
                linkedin_link = parent_li.find('a', href=lambda href: href and 'linkedin.com' in href)
                if linkedin_link:
                    company_info["linkedin"] = linkedin_link['href']
                    print(f"Found LinkedIn URL: {company_info['linkedin']}")
        
        # If no websites found, try to guess from LinkedIn or company name
        if not company_info["websites"] and company_info["linkedin"]:
            # Try to extract company name from LinkedIn URL
            company_path = company_info["linkedin"].split('linkedin.com/company/')[-1].split('/')[0].strip()
            if company_path:
                # Remove common suffixes like -inc, -gmbh, etc.
                clean_name = re.sub(r'-(inc|gmbh|llc|ltd|ab|co|group)$', '', company_path)
                
                # Try common domain formats
                website_guesses = [
                    f"https://{clean_name}.com",
                    f"https://www.{clean_name}.com"
                ]
                
                # Try each guess and see if it's valid
                for guess in website_guesses:
                    try:
                        verify_resp = requests.head(guess, timeout=3)
                        if verify_resp.status_code < 400:  # Valid website
                            company_info["websites"].append(guess)
                            print(f"Found company website (guessed from LinkedIn): {guess}")
                            break
                    except:
                        continue
        
        # If still no websites found, try to guess from company name
        if not company_info["websites"]:
            # Clean up the company name for URL guessing
            clean_name = re.sub(r'[^\w]', '', company_info["name"].lower())
            
            # Try common domain formats
            website_guesses = [
                f"https://{clean_name}.com",
                f"https://www.{clean_name}.com",
                f"https://{clean_name}.io",
                f"https://www.{clean_name}.io",
                f"https://{clean_name}.co",
                f"https://www.{clean_name}.co"
            ]
            
            # Try each guess and see if it's valid
            for guess in website_guesses:
                try:
                    print(f"Trying URL guess: {guess}")
                    verify_resp = requests.head(guess, timeout=3)
                    if verify_resp.status_code < 400:  # Valid website
                        company_info["websites"].append(guess)
                        print(f"Found company website (guessed from company name): {guess}")
                        break
                except Exception as e:
                    print(f"Error checking {guess}: {e}")
                    continue
        
        if not company_info["websites"]:
            print("No company website found on SeedTable page.")
        
        return company_info
        
    except Exception as e:
        print(f"Error fetching company info: {e}")
        return company_info

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
    emails_from_mailto = []
    
    if result.success:
        # Use a simple regex to extract links and their text from HTML
        link_pattern = re.compile(r'<a\s+(?:[^>]*?\s+)?href="([^"]*)"(?:\s+[^>]*?)?>([^<]*)<\/a>', re.IGNORECASE)
        matches = link_pattern.findall(result.cleaned_html)
        
        # Filter for contact-related links
        for href, text in matches:
            text = text.strip()
            # Extract emails from mailto links
            if href.startswith('mailto:'):
                email_match = re.search(r'mailto:([^?]+)', href)
                if email_match:
                    email = email_match.group(1)
                    print(f"Found email in mailto link: {email}")
                    emails_from_mailto.append(email)
                continue
                
            if any(keyword.lower() in text.lower() or keyword.lower() in href.lower() for keyword in CONTACT_KEYWORDS):
                # Convert relative URLs to absolute
                if href.startswith('/'):
                    base_url = urllib.parse.urlparse(url)
                    href = f"{base_url.scheme}://{base_url.netloc}{href}"
                
                links.append({"text": text, "url": href})
    
    return links, emails_from_mailto

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
    
    # First step: Get company information
    company_info = None
    
    if seedtable_company_id:
        # Extract company info from SeedTable using BeautifulSoup
        company_info = get_company_info_from_seedtable(seedtable_company_id)
    elif website_url:
        # Use provided website URL directly
        company_info = {
            "name": "",
            "websites": [website_url],
            "linkedin": None,
            "emails": []
        }
        # Extract domain for company name
        domain = re.search(r'https?://(?:www\.)?([^/]+)', website_url)
        if domain:
            domain_parts = domain.group(1).split('.')
            if len(domain_parts) > 1:
                company_info["name"] = domain_parts[0]
    else:
        print("Error: Either seedtable_company_id or website_url must be provided.")
        return

    if not company_info or not company_info["websites"]:
        print("Could not determine company website URL. Exiting.")
        return
    
    # Format output filename
    domain_name = re.sub(r'[^\w]', '_', company_info["name"].lower())
    output_file = f"{domain_name}_contact_info.csv"
    
    # Begin crawling with crawl4ai
    async with AsyncWebCrawler(config=browser_config) as crawler:
        # Check each website in the list if multiple are available
        for website in company_info["websites"]:
            print(f"\nChecking company website: {website}")
            main_page_emails = await scan_page_for_emails(crawler, website, session_id, llm_strategy)
            company_info["emails"].extend(main_page_emails)
            visited_urls.add(website)
            
            if main_page_emails:
                print(f"Found emails on main page: {main_page_emails}")
            else:
                print("No emails found on main page. Looking for contact links...")
            
            # Extract and follow potentially useful links
            links_to_check, mailto_emails = await extract_links_from_page(crawler, website, session_id)
            company_info["emails"].extend(mailto_emails)  # Add emails from mailto links
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
                    company_info["emails"].extend(link_emails)
        
        # Remove duplicate emails
        company_info["emails"] = list(set(company_info["emails"]))
    
    # Display results
    if company_info["emails"]:
        print("\nContact emails found:")
        for email in company_info["emails"]:
            print(f"- {email}")
        
        # Save to CSV file with all company information
        with open(output_file, "w", newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["name", "website", "linkedin", "email"])
            
            # Format data for CSV
            websites_str = ",".join(company_info["websites"]) if company_info["websites"] else ""
            emails_str = ",".join(company_info["emails"]) if company_info["emails"] else ""
            
            writer.writerow([
                company_info["name"],
                websites_str,
                company_info["linkedin"] or "",
                emails_str
            ])
        
        print(f"\nSaved company information to '{output_file}'")
    else:
        print("\nNo contact emails found. Try adjusting the search parameters or manually inspect the website.")

async def find_emails_for_company(website_url: str, max_retries: int = 3) -> List[str]:
    """
    Find emails for a company using crawl4ai with improved error handling and retry logic
    
    Args:
        website_url: The website URL to process
        max_retries: Maximum number of retry attempts on failure
        
    Returns:
        List of email addresses found
    """
    from crawl4ai import AsyncWebCrawler, CacheMode, CrawlerRunConfig
    import aiohttp
    
    # Clean and validate the URL
    website_url = website_url.strip()
    
    # Check if URL has a scheme, add https if missing
    if not website_url.startswith(('http://', 'https://')):
        if website_url.startswith('www.'):
            website_url = 'https://' + website_url
        else:
            website_url = 'https://www.' + website_url
    
    print(f"Processing website: {website_url}")
    
    # Create browser and LLM configurations
    browser_config = get_browser_config()
    llm_strategy = get_llm_strategy()
    
    # Create run configuration with optimized settings
    run_config = CrawlerRunConfig(
        max_pages=10,                    # Max pages to crawl for each domain
        cache_mode=CacheMode.PREFER_CACHE,  # Prefer cached pages if available
        follow_links=True,               # Follow internal links
        max_depth=2,                     # Don't go too deep
        max_total_links=10,              # Limit the total number of links to follow
        additional_paths=[               # Paths likely to contain contact information
            "contact", "about", "about-us", "team", "contact-us", "support",
            "impressum", "imprint", "kontakt", "info", "reach-us"
        ],
        crawl_timeout=90,                # Timeout in seconds for the entire crawl
        page_load_timeout=20,            # Timeout in seconds for individual page loads
        respect_robots_txt=True,         # Respect robots.txt directives
    )
    
    emails = set()
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            async with AsyncWebCrawler(config=browser_config) as crawler:
                # Run the crawler on the website
                result = await crawler.run(
                    url=website_url,
                    extraction_strategy=llm_strategy,
                    run_config=run_config,
                )
                
                # Check if we got any results
                if not result.page_results:
                    print(f"No pages were crawled for {website_url}")
                    retry_count += 1
                    continue
                
                # Process each page result
                for page_result in result.page_results:
                    # Extract emails from content using regex
                    if page_result.content:
                        found_emails = extract_emails_from_text(page_result.content)
                        if found_emails:
                            emails.update(found_emails)
                    
                    # Also check extraction results if available
                    if page_result.extraction_result:
                        try:
                            extracted_data = page_result.extraction_result
                            if isinstance(extracted_data, dict) and 'emails' in extracted_data:
                                if isinstance(extracted_data['emails'], list):
                                    emails.update(extracted_data['emails'])
                        except Exception as e:
                            print(f"Error processing extraction result: {e}")
                
                # Success - break out of retry loop
                break
                
        except aiohttp.ClientConnectionError as e:
            print(f"Connection error for {website_url}: {e}")
            retry_count += 1
            await asyncio.sleep(2 * retry_count)  # Exponential backoff
        except asyncio.TimeoutError:
            print(f"Timeout while processing {website_url}")
            retry_count += 1
            await asyncio.sleep(2)
        except Exception as e:
            print(f"Error in crawler for {website_url}: {str(e)}")
            retry_count += 1
            await asyncio.sleep(1)
    
    # Filter out common false positives and invalid emails
    valid_emails = []
    for email in emails:
        if len(email) > 4 and '@' in email and '.' in email.split('@')[1]:
            # Skip emails that don't match typical email patterns
            if email.endswith('.png') or email.endswith('.jpg') or email.endswith('.gif'):
                continue
            
            # Skip placeholder emails
            if 'example.com' in email or 'youremail' in email:
                continue
                
            valid_emails.append(email)
    
    if valid_emails:
        print(f"Found {len(valid_emails)} valid emails for {website_url}")
    else:
        print(f"No valid emails found for {website_url}")
    
    return valid_emails

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