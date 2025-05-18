import asyncio
import os
import re
import sys
import csv
import time
import requests
from typing import List, Set, Dict, Any, Optional, Tuple
import urllib.parse
from bs4 import BeautifulSoup
import glob

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

# List of file extensions to exclude from email results
EXCLUDED_EXTENSIONS = ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.ico', '.pdf', '.doc', '.docx']

def is_valid_email(email: str) -> bool:
    """Check if an email is valid and not a filename with excluded extension."""
    if not email:
        return False
        
    # Check if the email ends with any excluded extension
    for ext in EXCLUDED_EXTENSIONS:
        if email.lower().endswith(ext):
            return False
    
    # Additional validation could be added here
    return True

def get_browser_config() -> BrowserConfig:
    """Returns the browser configuration for the crawler."""
    return BrowserConfig(
        browser_type="chromium",
        headless=True,  # Run in headless mode for better performance
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
    
    # Find all email-like patterns
    potential_emails = re.findall(EMAIL_REGEX, text)
    
    # Filter out non-valid emails (filenames, etc.)
    return [email for email in potential_emails if is_valid_email(email)]

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
        emails = extract_emails_from_text(result.cleaned_html)    # Second approach: Use LLM to extract emails if provided
    if llm_strategy and not emails:
        try:
            # Maximum retries for LLM extraction
            max_retries = 2
            attempt = 0
            llm_success = False
            while attempt < max_retries and not llm_success:
                try:
                    attempt += 1
                    
                    # Add timeout to avoid hanging requests
                    llm_result = await asyncio.wait_for(
                        crawler.arun(
                            url=url,
                            config=CrawlerRunConfig(
                                cache_mode=CacheMode.BYPASS,
                                extraction_strategy=llm_strategy,
                                session_id=session_id,
                            ),
                        ), 
                        timeout=45  # 45 second timeout to give more time for LLM processing
                    )
                    
                    if llm_result.success and llm_result.extracted_content:
                        try:                            # Parse LLM output as JSON
                            import json
                            extracted_data = json.loads(llm_result.extracted_content)
                            if extracted_data and 'emails' in extracted_data:
                                # Filter out invalid emails (filenames, etc.)
                                valid_emails = [email for email in extracted_data['emails'] if is_valid_email(email)]
                                emails.extend(valid_emails)
                                llm_success = True
                                print(f"LLM extraction successful: found {len(valid_emails)} valid emails from {len(extracted_data['emails'])} candidates")
                        except json.JSONDecodeError:                            # If not valid JSON, try to extract emails using regex
                            print(f"LLM returned invalid JSON. Falling back to regex extraction.")
                            additional_emails = extract_emails_from_text(llm_result.extracted_content)
                            if additional_emails:
                                emails.extend(additional_emails)
                                llm_success = True
                                print(f"Extracted {len(additional_emails)} valid emails from LLM raw output using regex")
                except asyncio.TimeoutError:
                    print(f"LLM extraction timed out after 45 seconds")
                    break  # Don't retry on timeout
                except Exception as e:                    
                    error_msg = str(e).lower()
                    if "litellm.badrequest" in error_msg or "list index out of range" in error_msg or "getllmprovider" in error_msg:
                        print(f"LiteLLM API error encountered: {e}")
                        print("This is likely due to an issue with the OpenRouter API key or model configuration")
                        # Log more details to help debug the issue
                        print(f"Model being used: {llm_strategy.model}")
                        print(f"Provider being used: {llm_strategy.provider}")
                        print(f"API Token (first few chars): {llm_strategy.api_token[:8]}...")
                        
                        # Skip LLM-based extraction but continue with regex results
                        print("Skipping LLM extraction and proceeding with regex results only.")
                        llm_success = True  # Mark as successful to avoid further retries
                        break  # Don't retry on API configuration errors
                    elif attempt < max_retries:
                        print(f"LLM extraction attempt {attempt} failed: {e}, retrying...")
                        await asyncio.sleep(2)  # Longer wait before retry
                    else:
                        print(f"All LLM extraction attempts failed for {url}")
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

def process_all_country_csvs():
    """Process all country CSVs and consolidate results."""
    all_emails = set()
    all_contact_links = set()
    
    for csv_file in glob.glob("*.csv"):
        with open(csv_file, "r", newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                emails = row.get("email", "").split(",")
                all_emails.update(emails)
                contact_links = row.get("contact_links", "").split(",")
                all_contact_links.update(contact_links)
    
    # Save consolidated results to a new CSV file
    with open("consolidated_contact_info.csv", "w", newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["email", "contact_link"])
        for email in all_emails:
            writer.writerow([email, ""])
        for contact_link in all_contact_links:
            writer.writerow(["", contact_link])
    
    print("Consolidated contact information saved to 'consolidated_contact_info.csv'")

async def find_emails_for_company(website_url: str) -> List[str]:
    """
    Find email addresses for a company using the website URL.
    
    Args:
        website_url: The website URL to check for emails
        
    Returns:
        List of email addresses found
    """
    browser_config = get_browser_config()
    llm_strategy = get_llm_strategy()
    session_id = "email_finder_session"
    emails = []
    
    # Skip if no website URL
    if not website_url:
        return emails
    
    # Skip if URL is invalid
    if not website_url.startswith(('http://', 'https://')):
        return emails
        
    try:
        async with AsyncWebCrawler(config=browser_config) as crawler:
            # Step 1: Check main page
            try:
                main_emails = await scan_page_for_emails(crawler, website_url, session_id, llm_strategy)
                emails.extend(main_emails)
                
                # Step 2: Check for contact links
                links_to_check, mailto_emails = await extract_links_from_page(crawler, website_url, session_id)
                emails.extend(mailto_emails)
                
                # Step 3: Check contact pages (up to 3)
                checked_count = 0
                for link_data in links_to_check:
                    if checked_count >= 3:  # Limit to 3 contact pages to avoid excessive crawling
                        break
                        
                    link_url = link_data["url"]
                    
                    # Skip invalid URLs
                    if not link_url.startswith(('http://', 'https://')) or link_url.startswith('mailto:'):
                        continue
                        
                    try:
                        # Check for emails on contact page
                        link_emails = await scan_page_for_emails(crawler, link_url, session_id, llm_strategy)
                        emails.extend(link_emails)
                        checked_count += 1
                        
                        # Pause between requests
                        await asyncio.sleep(0.5)
                    except Exception as e:
                        print(f"Error checking link {link_url}: {e}")
                        continue
            except Exception as e:
                print(f"Error processing website {website_url}: {e}")
    except Exception as e:
        print(f"Error creating crawler for {website_url}: {e}")
        
    # Remove duplicates and return
    return list(set(emails))

async def process_country_csv_files(output_csv: str = 'all_european_startups_emails.csv') -> None:
    """
    Process all country CSV files in the scrape_results directory and extract emails.
    
    Args:
        output_csv: The path for the consolidated output CSV
    """
    # Find all CSV files in scrape_results directory
    csv_pattern = os.path.join('scrape_results', '*_websites.csv')
    csv_files = glob.glob(csv_pattern)
    
    if not csv_files:
        print(f"No CSV files found matching pattern: {csv_pattern}")
        return
    
    print(f"Found {len(csv_files)} country CSV files to process")
    
    # Track unique companies to avoid duplicates
    unique_companies = {}  # website_url -> {name, country, eu_startups_url, emails}
    
    # Process each CSV file
    for csv_file in csv_files:
        country_name = os.path.basename(csv_file).split('_')[0]
        print(f"\nProcessing {country_name} from {csv_file}")
        
        try:
            with open(csv_file, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                country_companies = list(reader)
                
                print(f"Found {len(country_companies)} companies in {country_name}")
                
                # Process each company in the CSV
                for company in country_companies:
                    website_url = company.get('website_url', '')
                    
                    # Skip if no website URL
                    if not website_url:
                        continue
                    
                    # Use website_url as deduplication key
                    if website_url in unique_companies:
                        print(f"Duplicate found: {company.get('name')} - {website_url}")
                        continue
                    
                    # Add to unique companies
                    unique_companies[website_url] = {
                        'name': company.get('name', ''),
                        'country': company.get('country', country_name),
                        'eu_startups_url': company.get('eu_startups_url', ''),
                        'website_url': website_url,
                        'emails': []  # Will be filled later
                    }
        except Exception as e:
            print(f"Error processing CSV file {csv_file}: {e}")
    
    print(f"\nFound {len(unique_companies)} unique companies across all countries")
    
    # Now process emails for each unique company
    companies_list = list(unique_companies.values())
    total_companies = len(companies_list)
    
    # Create the output CSV file and write header
    with open(output_csv, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['name', 'country', 'eu_startups_url', 'website_url', 'emails']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        # Process each company to find emails
        for i, company in enumerate(companies_list):
            website_url = company['website_url']
            
            # Calculate progress
            progress = (i + 1) / total_companies * 100
            
            # Print progress
            print(f"\r[{i+1}/{total_companies}] ({progress:.1f}%) - Processing: {company['name']} ({website_url})", end='')
            
            try:
                # Extract emails
                emails = await find_emails_for_company(website_url)
                company['emails'] = ','.join(emails) if emails else ''
                
                if emails:
                    print(f"\nFound {len(emails)} emails for {company['name']}: {', '.join(emails[:3])}{'...' if len(emails) > 3 else ''}")
                
                # Write to CSV immediately to preserve progress
                writer.writerow(company)
                
                # Small delay to avoid overloading
                await asyncio.sleep(0.5)
            except Exception as e:
                print(f"\nError finding emails for {website_url}: {e}")
                company['emails'] = f"ERROR: {str(e)}"
                writer.writerow(company)
    
    print(f"\n\nAll processing complete! Results saved to {output_csv}")
    print(f"Processed {total_companies} unique companies from {len(csv_files)} countries")

async def process_company(company, writer, stats):
    """
    Process a single company to extract emails.
    
    Args:
        company: Dictionary with company information
        writer: CSV writer to write results
        stats: Dictionary to track statistics
    """
    website_url = company.get('website_url', '')
    
    # Skip if no website URL
    if not website_url:
        print(f"No website URL for {company.get('name', 'Unknown')}")
        company['emails'] = ''
        # Thread-safe write to CSV
        async with stats['csv_lock']:
            writer.writerow(company)
        stats['skip_count'] += 1
        return
    
    try:
        # Extract emails
        emails = await find_emails_for_company(website_url)
        company['emails'] = ','.join(emails) if emails else ''
        
        if emails:
            stats['success_count'] += 1
            print(f"\nFound {len(emails)} emails for {company.get('name', '')}: {', '.join(emails[:3])}{'...' if len(emails) > 3 else ''}")
        
        # Thread-safe write to CSV
        async with stats['csv_lock']:
            writer.writerow(company)
        
    except Exception as e:
        stats['error_count'] += 1
        print(f"\nError finding emails for {website_url}: {e}")
        company['emails'] = f"ERROR: {str(e)}"
        async with stats['csv_lock']:
            writer.writerow(company)

async def update_progress(stats, total_companies, start_time):
    """Update progress bar periodically."""
    while stats['processed_count'] < total_companies:
        processed = stats['processed_count']
        progress = processed / total_companies * 100
        elapsed = time.time() - start_time
        
        # Calculate ETA
        if processed > 0:
            eta_seconds = (elapsed / processed) * (total_companies - processed)
            eta_minutes = int(eta_seconds // 60)
            eta_seconds = int(eta_seconds % 60)
            eta_str = f"{eta_minutes}m {eta_seconds}s"
            rate = processed / (elapsed / 60)  # companies per minute
        else:
            eta_str = "calculating..."
            rate = 0
        
        # Create progress bar
        bar_length = 30
        filled_length = int(bar_length * processed / total_companies)
        bar = '█' * filled_length + '░' * (bar_length - filled_length)
        
        # Print progress
        print(f"\r[{bar}] {processed}/{total_companies} ({progress:.1f}%) ETA: {eta_str} Rate: {rate:.1f}/min - Active workers: {stats['active_workers']}", end='')
        
        await asyncio.sleep(1)  # Update every second

async def process_consolidated_csv(input_csv: str, output_csv: str = 'european_startups_with_emails.csv', workers: int = 1) -> None:
    """
    Process a consolidated CSV file and add emails for each company.
    
    Args:
        input_csv: The input CSV file with company data
        output_csv: The output CSV file with added emails
        workers: Number of concurrent workers
    """
    companies = []
    
    # Read the input CSV
    try:
        with open(input_csv, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            companies = list(reader)
            print(f"Found {len(companies)} companies in {input_csv}")
    except Exception as e:
        print(f"Error reading CSV file {input_csv}: {e}")
        return
    
    # Check for existing output file to support resuming
    existing_processed = set()
    if os.path.exists(output_csv):
        try:
            with open(output_csv, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    if row.get('website_url'):
                        existing_processed.add(row['website_url'])
            print(f"Found existing output file with {len(existing_processed)} processed websites")
            
            # Ask for confirmation to resume
            response = input(f"Resume processing from where we left off? [y/n]: ")
            if response.lower() not in ['y', 'yes']:
                print("Starting from the beginning (existing file will be overwritten)...")
                existing_processed = set()
            else:
                print(f"Resuming processing (skipping {len(existing_processed)} already processed websites)...")
        except Exception as e:
            print(f"Error reading existing output file: {e}")
            print("Starting from the beginning...")
            existing_processed = set()
    
    # Filter out already processed websites if resuming
    if existing_processed:
        companies = [c for c in companies if c.get('website_url') not in existing_processed]
    
    total_companies = len(companies)
    if total_companies == 0:
        print("No companies to process!")
        return
    
    # Create the output CSV file and write header
    mode = 'a' if existing_processed and os.path.exists(output_csv) else 'w'
    csvfile = open(output_csv, mode, newline='', encoding='utf-8')
    fieldnames = ['name', 'country', 'eu_startups_url', 'website_url', 'emails']
    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
    
    # Write header only if we're not appending
    if mode == 'w':
        writer.writeheader()
    
    # Statistics for tracking progress
    start_time = time.time()
    stats = {
        'success_count': 0,
        'error_count': 0,
        'skip_count': 0,
        'processed_count': 0,
        'active_workers': 0,
        'csv_lock': asyncio.Lock()  # Lock for thread-safe CSV writing
    }
    
    # Process companies with worker pool
    try:
        # Limit number of workers to reasonable values
        workers = max(1, min(workers, 20))  # Between 1 and 20 workers
        print(f"Starting processing with {workers} concurrent workers")
        
        # Start the progress updater task
        progress_task = asyncio.create_task(update_progress(stats, total_companies, start_time))
        
        # Create a queue of companies to process
        queue = asyncio.Queue()
        for company in companies:
            await queue.put(company)
        
        # Define worker function
        async def worker():
            stats['active_workers'] += 1
            try:
                while not queue.empty():
                    company = await queue.get()
                    await process_company(company, writer, stats)
                    stats['processed_count'] += 1
                    queue.task_done()
            finally:
                stats['active_workers'] -= 1
        
        # Start workers
        worker_tasks = [asyncio.create_task(worker()) for _ in range(workers)]
        
        # Wait for all work to complete
        await asyncio.gather(*worker_tasks)
        
        # Cancel the progress updater
        progress_task.cancel()
        try:
            await progress_task
        except asyncio.CancelledError:
            pass
        
    finally:
        # Always close the CSV file
        csvfile.close()
    
    # Print final statistics
    total_time = time.time() - start_time
    minutes, seconds = divmod(total_time, 60)
    
    print("\n" + "=" * 60)
    print(f"Email extraction completed in {int(minutes)} minutes and {int(seconds)} seconds.")
    print(f"Total companies processed: {total_companies}")
    processed_with_email = stats['success_count']
    print(f"Successful extractions: {processed_with_email} ({processed_with_email/total_companies*100:.1f}% of processed)")
    print(f"Errors: {stats['error_count']} ({stats['error_count']/total_companies*100:.1f}% of processed)")
    print(f"Skipped (no URL): {stats['skip_count']}")
    print(f"Already processed (resumed): {len(existing_processed)}")
    print("=" * 60)

async def main():
    """Main entry point with command-line argument parsing."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Contact Email Finder for EU Startups")
    parser.add_argument("--input", type=str, default="european_startup_websites.csv", 
                        help="Input CSV file with company data (default: european_startup_websites.csv)")
    parser.add_argument("--output", type=str, default="european_startups_with_emails.csv", 
                        help="Output CSV filename (default: european_startups_with_emails.csv)")
    parser.add_argument("--website", type=str, help="Direct website URL to process (single mode)")
    parser.add_argument("--company", type=str, help="SeedTable company ID to process (single mode)")
    parser.add_argument("--workers", type=int, default=1, 
                        help="Number of concurrent workers (default: 1, recommended: 5-10 for faster processing)")
    args = parser.parse_args()
    
    if args.website:
        print("=" * 80)
        print(f"PROCESSING SINGLE WEBSITE: {args.website}")
        print("=" * 80)
        await crawl_for_contact_email(website_url=args.website)
        
    elif args.company:
        print("=" * 80)
        print(f"PROCESSING SEEDTABLE COMPANY: {args.company}")
        print("=" * 80)
        await crawl_for_contact_email(seedtable_company_id=args.company)
        
    else:
        print("=" * 80)
        print(f"PROCESSING CONSOLIDATED CSV FILE: {args.input}")
        print(f"OUTPUT WILL BE SAVED TO: {args.output}")
        print(f"USING {args.workers} CONCURRENT WORKERS")
        print("=" * 80)
        await process_consolidated_csv(args.input, output_csv=args.output, workers=args.workers)

if __name__ == "__main__":
    asyncio.run(main())