"""
Main script for EU-Startups email extraction process
"""
import asyncio
import csv
import os
import sys
from typing import Dict, List, Set, Optional

from country_links import load_country_links
from eu_startups_crawler import EUStartupsCrawler, crawl_all_countries
from eu_startups_scraper import EUStartupsScraper, process_companies_from_files
from find_contact_email import (
    find_emails_for_domain, 
    get_browser_config, 
    get_llm_strategy,
    extract_emails_from_text
)

CRAWL_RESULTS_DIR = 'crawl_results'
SCRAPE_RESULTS_DIR = 'scrape_results'
FINAL_OUTPUT_CSV = 'european_ai_startups_contact_info.csv'

async def run_complete_process(selected_countries: Optional[List[str]] = None) -> None:
    """
    Run the complete process of crawling, scraping, and email extraction
    
    Args:
        selected_countries: Optional list of country names to process. If None, process all countries.
    """
    os.makedirs(CRAWL_RESULTS_DIR, exist_ok=True)
    os.makedirs(SCRAPE_RESULTS_DIR, exist_ok=True)
    
    # Step 1: Load country links
    countries = load_country_links()
    if selected_countries:
        countries = [(link, country, count) 
                    for link, country, count in countries 
                    if country in selected_countries]
    
    if not countries:
        print("No countries found to process.")
        return
    
    print(f"Starting process for {len(countries)} countries...")
    
    # Step 2: Crawl each country to get company links
    crawler = EUStartupsCrawler()
    for link, country, _ in countries:
        print(f"\nCrawling {country} ({link})...")
        
        # Check if we already have results for this country
        safe_country = country.replace(' ', '_')
        country_file = f'{CRAWL_RESULTS_DIR}/{safe_country}_companies.txt'
        
        if os.path.exists(country_file):
            print(f"Using existing crawl results for {country}")
        else:
            companies = crawler.extract_company_links(link)
            # Save interim results
            os.makedirs(CRAWL_RESULTS_DIR, exist_ok=True)
            with open(country_file, 'w', encoding='utf-8') as f:
                for company in companies:
                    f.write(f"{company['name']}\t{company['link']}\n")
    
    # Step 3: Scrape company pages to get actual website URLs
    print("\nExtracting website URLs from company pages...")
    company_websites = process_companies_from_files()
    
    if not company_websites:
        print("No company websites found to process.")
        return
    
    # Step 4: Extract emails from each website using crawl4ai
    print("\nExtracting emails from websites...")
    
    # Prepare the output CSV file
    fieldnames = ['name', 'country', 'eu_startups_url', 'website_url', 'emails']
    
    with open(FINAL_OUTPUT_CSV, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        # Process each company website
        for i, company in enumerate(company_websites):
            website_url = company.get('website_url', '').strip()
            
            if not website_url:
                print(f"No website URL for {company.get('name', 'Unknown')}, skipping...")
                # Still write to CSV but with empty emails
                company['emails'] = ''
                writer.writerow(company)
                continue
            
            print(f"Processing {i+1}/{len(company_websites)}: {company['name']} ({website_url})")
            
            # Extract emails using your crawl4ai functionality
            try:
                emails = await find_emails_for_domain(website_url)
                
                # Format emails as comma-separated string
                if emails:
                    company['emails'] = ','.join(emails)
                else:
                    company['emails'] = ''
                
                # Write to CSV immediately to preserve progress
                writer.writerow(company)
            except Exception as e:
                print(f"Error processing {website_url}: {e}")
                company['emails'] = f'ERROR: {str(e)}'
                writer.writerow(company)
    
    print(f"\nProcess completed. Results saved to {FINAL_OUTPUT_CSV}")

async def find_emails_for_domain(website_url: str) -> List[str]:
    """
    Find emails for a domain using crawl4ai
    
    Args:
        website_url: The website URL to process
        
    Returns:
        List of email addresses found
    """
    from crawl4ai import AsyncWebCrawler, CacheMode, CrawlerRunConfig
    
    # Create browser and LLM configurations
    browser_config = get_browser_config()
    llm_strategy = get_llm_strategy()
    
    # Create run configuration
    run_config = CrawlerRunConfig(
        max_pages=10,            # Max pages to crawl for each domain
        cache_mode=CacheMode.PREFER_CACHE,  # Prefer cached pages if available
        follow_links=True,       # Follow internal links
        max_depth=2,             # Don't go too deep
        max_total_links=10,      # Limit the total number of links to follow
        additional_paths=[       # Additional paths to check for contact information
            "contact", "about", "about-us", "team", "contact-us", "support"
        ],
    )
    
    emails = set()
    
    try:
        async with AsyncWebCrawler(config=browser_config) as crawler:
            # Run the crawler on the website
            result = await crawler.run(
                url=website_url,
                extraction_strategy=llm_strategy,
                run_config=run_config,
            )
            
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
    
    except Exception as e:
        print(f"Error in crawler: {e}")
    
    return list(emails)

async def main():
    """
    Main entry point for the application
    """
    # Check for command line arguments for specific countries
    selected_countries = None
    if len(sys.argv) > 1:
        selected_countries = sys.argv[1:]
        print(f"Processing only selected countries: {', '.join(selected_countries)}")
    
    await run_complete_process(selected_countries)

if __name__ == "__main__":
    asyncio.run(main())
