import asyncio
import os
import re
import csv
import requests
from typing import List, Dict, Any
from bs4 import BeautifulSoup
from find_contact_email import get_company_info_from_seedtable, get_browser_config, get_llm_strategy, scan_page_for_emails, extract_links_from_page

from crawl4ai import (
    AsyncWebCrawler, 
    BrowserConfig, 
    CacheMode, 
    CrawlerRunConfig
)

# URL of the SeedTable page listing AI startups in Sweden
SEEDTABLE_LIST_URL = "https://www.seedtable.com/best-ai-startups-in-sweden"

def extract_company_links(url: str) -> List[Dict[str, str]]:
    """
    Extract all company links from the SeedTable list page.
    
    Args:
        url: The URL of the SeedTable list page
        
    Returns:
        A list of dictionaries with company name and link to their SeedTable page
    """
    print(f"Fetching startups list from: {url}")
    
    companies = []
    
    try:
        response = requests.get(url)
        if response.status_code != 200:
            print(f"Failed to access SeedTable list page: {url}")
            return companies
        
        # Parse the HTML with BeautifulSoup
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Find all company profile containers - more generic approach
        company_profiles = soup.find_all('div', class_=lambda c: c and 'border-gray-300 border rounded-lg' in c)
        print(f"Found {len(company_profiles)} company profiles on the page")
        
        for profile in company_profiles:
            # Look for the company name heading and link
            name_link = profile.select_one('h3.text-2xl.font-bold')
            
            if name_link:
                # Try to find the parent 'a' tag that contains the link to the company profile
                parent_a = name_link.find_parent('a')
                
                if parent_a and 'href' in parent_a.attrs and '/startups/' in parent_a['href']:
                    company_name = name_link.get_text().strip()
                    company_url = parent_a['href']
                    company_id = company_url.split('/')[-1]  # Get the company ID from the URL
                    
                    # Add to our list
                    companies.append({
                        "name": company_name,
                        "id": company_id
                    })
                    print(f"Found company: {company_name} (ID: {company_id})")
            else:
                # Alternative approach: look directly for links to company profiles
                company_links = profile.select('a[href*="/startups/"]')
                for link in company_links:
                    if link.get_text().strip():
                        company_name = link.get_text().strip()
                        company_url = link['href']
                        company_id = company_url.split('/')[-1]  # Get the company ID
                        
                        # Only add if this is likely the main company link (contains title)
                        # This helps avoid duplicates when there are multiple links to the same company
                        if len(company_name) > 1:  # Avoid empty or single character links
                            companies.append({
                                "name": company_name,
                                "id": company_id
                            })
                            print(f"Found company (alt method): {company_name} (ID: {company_id})")
                            # Once found, break to avoid duplicates from the same profile
                            break
        
        # Remove any duplicates (by ID)
        unique_companies = []
        seen_ids = set()
        for company in companies:
            if company["id"] not in seen_ids:
                seen_ids.add(company["id"])
                unique_companies.append(company)
        
        print(f"Found {len(unique_companies)} unique companies out of {len(companies)} total links")
        return unique_companies
        
    except Exception as e:
        print(f"Error fetching companies list: {e}")
        return companies

async def process_company(crawler, company_id: str, session_id: str, llm_strategy) -> Dict[str, Any]:
    """
    Process a single company to extract its information and contact emails.
    
    Args:
        crawler: The web crawler instance
        company_id: The company ID from SeedTable
        session_id: The crawler session ID
        llm_strategy: The LLM extraction strategy
    
    Returns:
        A dictionary with company information including name, website, LinkedIn URL, and emails
    """
    # Get company information from SeedTable
    company_info = get_company_info_from_seedtable(company_id)
    
    if not company_info["websites"]:
        print(f"No website found for {company_info['name']}. Skipping.")
        return company_info
    
    visited_urls = set()
    
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
    
    return company_info

async def process_all_companies():
    """Process all companies from the SeedTable list and gather their contact information."""
    # First, get all company links from the list page
    companies = extract_company_links(SEEDTABLE_LIST_URL)
    
    if not companies:
        print("No companies found to process.")
        return
    
    print(f"\nFound {len(companies)} companies to process.")
    
    # Create a CSV file to store all contact information
    output_file = "sweden_ai_startups_contact_info.csv"
    
    # Initialize master list to collect all company data
    all_companies_data = []
    
    # Set up the crawler
    browser_config = get_browser_config()
    llm_strategy = get_llm_strategy()
    session_id = "email_finder_session"
    
    async with AsyncWebCrawler(config=browser_config) as crawler:
        # Process each company
        for i, company in enumerate(companies):
            print(f"\n[{i+1}/{len(companies)}] Processing company: {company['name']}")
            
            try:
                # Process the company and get its information
                company_info = await process_company(crawler, company['id'], session_id, llm_strategy)
                
                # Add to our master list
                if company_info:
                    all_companies_data.append(company_info)
                    print(f"Processed {company['name']} successfully. Found {len(company_info['emails'])} email(s).")
                
            except Exception as e:
                print(f"Error processing {company['name']}: {e}")
    
    # Save all data to the CSV file
    with open(output_file, "w", newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["name", "website", "linkedin", "email"])
        
        for company in all_companies_data:
            websites_str = ",".join(company["websites"]) if company["websites"] else ""
            emails_str = ",".join(company["emails"]) if company["emails"] else ""
            
            writer.writerow([
                company["name"],
                websites_str,
                company["linkedin"] or "",
                emails_str
            ])
    
    print(f"\nAll companies processed. Results saved to {output_file}")

async def main():
    await process_all_companies()

if __name__ == "__main__":
    asyncio.run(main())