"""
EU-Startups Scraper - Extracts actual website URLs from EU-Startups company pages
"""
import asyncio
import csv
import os
import re
import sys
import time
import concurrent.futures
import threading
from typing import Dict, List, Optional, Set, Tuple
from queue import Queue

import requests
from bs4 import BeautifulSoup

from country_links import load_country_links
from eu_startups_crawler import EUStartupsCrawler

class EUStartupsScraper:
    """Scraper to extract website URLs from EU-Startups company pages"""
    
    def __init__(self):
        # Create a session per thread to avoid contention and locking issues
        self.session_local = threading.local()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        }
        self.delay = 0.5  # seconds between requests - reduced for speed
    def _get_page_content(self, url: str) -> str:
        """
        Get HTML content from a URL with proper error handling
        Uses thread-local sessions to avoid contention between threads
        
        Args:
            url: The URL to fetch
            
        Returns:
            HTML content as string
        """
        # Get or create a thread-local session
        if not hasattr(self.session_local, 'session'):
            self.session_local.session = requests.Session()
        
        try:
            # Each thread has its own session, no lock needed
            response = self.session_local.session.get(url, headers=self.headers)
            response.raise_for_status()
            content = response.text
            # Be nice to the server
            time.sleep(self.delay)
            return content
        except requests.RequestException as e:
            print(f"Error fetching {url}: {e}")
            # If we got a 429 Too Many Requests, wait longer
            if hasattr(e.response, 'status_code') and e.response.status_code == 429:
                print(f"Rate limited. Waiting for 5 seconds...")
                time.sleep(5)
            return ""
        except Exception as e:
            print(f"Unexpected error fetching {url}: {e}")
            return ""
    
    def extract_website_url(self, company_url: str) -> Dict[str, str]:
        """
        Extract the actual website URL from a company page
        
        Args:
            company_url: URL of the company page on EU-Startups
            
        Returns:
            Dictionary with company details (name, eu_startups_url, website_url)
        """
        html = self._get_page_content(company_url)
        if not html:
            return {"eu_startups_url": company_url, "website_url": "", "name": ""}
        
        soup = BeautifulSoup(html, 'html.parser')
          # Extract company name - try multiple possible structures
        name = ""
        
        # First try the td-page-header structure (as provided)
        page_header = soup.find('div', class_='td-page-header')
        if page_header:
            title_element = page_header.find('h1', class_='entry-title')
            if title_element:
                span_element = title_element.find('span')
                if span_element:
                    name = span_element.text.strip()
                else:
                    name = title_element.text.strip()
        
        # If not found, try the alternative wpbdp-listing-title structure
        if not name:
            title_element = soup.find('h1', class_='wpbdp-listing-title')
            if title_element:
                name = title_element.text.strip()
                
        # If still not found, try other common title patterns
        if not name:
            # Try generic h1 as last resort
            h1_elements = soup.find_all('h1')
            if h1_elements:
                name = h1_elements[0].text.strip()
        
        # Find the website field specifically
        website_field = soup.find('div', class_='wpbdp-field-website')
        website_url = ""
        
        if website_field:
            value_div = website_field.find('div', class_='value')
            if value_div:
                website_url = value_div.text.strip()
        
        result = {
            "name": name,
            "eu_startups_url": company_url,
            "website_url": website_url
        }
        
        return result

def process_company(args):
    """
    Process a single company to extract website URL
    
    Args:
        args: Tuple containing (scraper, company, country, index, total, progress_lock)
        
    Returns:
        Dictionary with company details
    """
    scraper, company, country, index, total, progress_lock = args
    # No printing per company - we'll handle this with progress bars instead
    
    result = scraper.extract_website_url(company['link'])
    result['country'] = country
    return result

def process_companies_from_files(max_workers: int = 10, filter_country: str = None) -> List[Dict[str, str]]:
    """
    Process all company files saved from the crawler using multithreading
    
    Args:
        max_workers: Maximum number of worker threads (default: 10)
        filter_country: Optional country name to process only one country
        
    Returns:
        List of dictionaries with company details including website URLs
    """
    os.makedirs('scrape_results', exist_ok=True)
    all_companies = []
    # Track unique companies by URL to avoid duplicates
    seen_urls = set()
    scraper = EUStartupsScraper()
    
    # Check for existing crawl results
    crawl_dir = 'crawl_results'
    if not os.path.exists(crawl_dir):
        print(f"Crawl results directory '{crawl_dir}' not found.")
        return all_companies
      # Process each file in the directory
    for filename in os.listdir(crawl_dir):
        if not filename.endswith('_companies.txt'):
            continue
        
        country = filename.replace('_companies.txt', '').replace('_', ' ')
        
        # Skip if we're filtering by country and this isn't the one
        if filter_country and filter_country.lower() != country.lower():        
            continue
            
        company_file = os.path.join(crawl_dir, filename)
        
        # Process companies in the file
        companies = []
        with open(company_file, 'r', encoding='utf-8') as f:
            for line in f:
                parts = line.strip().split('\t')
                if len(parts) == 2:
                    companies.append({
                        'name': parts[0],
                        'link': parts[1]
                    })
        print(f"\n{country}: Processing {len(companies)} companies using {max_workers} threads")
        
        # Create a progress lock for threadsafe updates
        progress_lock = threading.RLock()
        
        # Initialize progress tracking
        processed_count = 0
        last_progress_update = time.time()
        
        # Function to update the progress bar
        def update_progress_bar(increment=1):
            nonlocal processed_count, last_progress_update
            with progress_lock:
                processed_count += increment
                current_time = time.time()
                
                # Don't update too frequently to avoid console spam
                if current_time - last_progress_update >= 1.0 or processed_count == len(companies):
                    last_progress_update = current_time
                    
                    progress_percent = (processed_count / len(companies)) * 100
                    bar_length = 30
                    filled_length = int(bar_length * processed_count // len(companies))
                    bar = '█' * filled_length + '░' * (bar_length - filled_length)
                    
                    # Use carriage return to update in-place
                    sys.stdout.write(f"\r{country}: [{bar}] {processed_count}/{len(companies)} ({progress_percent:.1f}%)")
                    sys.stdout.flush()
                    
                    # Add newline when complete
                    if processed_count == len(companies):
                        sys.stdout.write('\n')
                        sys.stdout.flush()
        
        # Process companies in parallel using ThreadPoolExecutor
        country_results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Prepare arguments for each company
            args_list = [(scraper, company, country, i, len(companies), progress_lock) for i, company in enumerate(companies)]
            
            # Start all tasks and track their futures
            futures = [executor.submit(process_company, args) for args in args_list]
            
            # Process results as they complete (in any order)
            for i, future in enumerate(concurrent.futures.as_completed(futures)):
                try:
                    result = future.result()
                      # Skip duplicates based on eu_startups_url (which should be unique)
                    if result['eu_startups_url'] in seen_urls:
                        update_progress_bar()
                        continue
                    
                    # Add to seen URLs
                    seen_urls.add(result['eu_startups_url'])
                    
                    # Add to country results
                    country_results.append(result)
                    
                    # Update progress bar
                    update_progress_bar()
                    
                    # Save interim results periodically
                    if (len(country_results) % 20 == 0) or (len(country_results) == len(companies)):
                        save_interim_scrape_results(country, country_results)
                except Exception as e:
                    with progress_lock:
                        print(f"\nError processing a company: {e}")
                    update_progress_bar()
          # Filter country results for duplicates again (extra safety)
        unique_country_results = []
        seen_country_urls = set()
        
        for company in country_results:
            if company['eu_startups_url'] not in seen_country_urls:
                seen_country_urls.add(company['eu_startups_url'])
                unique_country_results.append(company)
        
        duplicates_count = len(companies) - len(country_results)
        print(f"\n{country}: Found {len(unique_country_results)} unique companies out of {len(companies)} total")
        print(f"{country}: Removed {duplicates_count} duplicates during processing")
        all_companies.extend(unique_country_results)
    
    return all_companies

def save_interim_scrape_results(country: str, companies: List[Dict[str, str]]) -> None:
    """
    Save interim scraping results to a CSV file
    
    Args:
        country: Name of the country
        companies: List of company dictionaries with website URLs
    """
    # Create a safe filename from the country name
    safe_country = re.sub(r'[^a-zA-Z0-9]', '_', country)
    csv_file = f'scrape_results/{safe_country}_websites.csv'
    
    # Ensure the directory exists
    os.makedirs('scrape_results', exist_ok=True)
    
    # Save to CSV
    fieldnames = ['name', 'country', 'eu_startups_url', 'website_url']
    
    # Determine if we need to write headers (only for new files)
    write_header = not os.path.exists(csv_file)
    
    with open(csv_file, 'a', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()
        for company in companies:
            writer.writerow({field: company.get(field, '') for field in fieldnames})

def save_all_results(companies: List[Dict[str, str]]) -> None:
    """
    Save all scraping results to a single CSV file
    
    Args:
        companies: List of company dictionaries with website URLs
    """    # Deduplicate companies based on eu_startups_url
    unique_companies = []
    seen_urls = set()
    
    for company in companies:
        url = company.get('eu_startups_url', '')
        if url and url not in seen_urls:
            seen_urls.add(url)
            unique_companies.append(company)
    
    duplicates = len(companies) - len(unique_companies)
    print(f"Final Deduplication Summary:")
    print(f"- Total companies processed: {len(companies)}")
    print(f"- Unique companies: {len(unique_companies)}")
    print(f"- Duplicates removed: {duplicates} ({(duplicates/len(companies)*100):.1f}% of total)")
    
    csv_file = 'european_startup_websites.csv'
    fieldnames = ['name', 'country', 'eu_startups_url', 'website_url']
    
    with open(csv_file, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for company in unique_companies:
            writer.writerow({field: company.get(field, '') for field in fieldnames})
    
    print(f"Saved {len(unique_companies)} unique companies to {csv_file}")

if __name__ == "__main__":
    print("Starting EU-Startups website scraper...")
    
    import argparse
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Extract website URLs from EU-Startups company pages')
    parser.add_argument('--threads', type=int, default=10, help='Number of worker threads (default: 10)')
    parser.add_argument('--country', type=str, help='Process only a specific country (optional)')
    args = parser.parse_args()
    print(f"Using {args.threads} worker threads")
    if args.country:
        print(f"Filtering for country: {args.country}")
    
    try:
        # Print a header
        print("\n" + "=" * 60)
        print(f"🚀 STARTING EU-STARTUPS WEBSITE EXTRACTION")
        print("=" * 60)
        
        start_time = time.time()
        
        # Process company files to extract website URLs
        companies = process_companies_from_files(max_workers=args.threads, filter_country=args.country)
        
        if companies:
            # Save all results to a single file
            save_all_results(companies)
            
            # Calculate processing time
            elapsed_time = time.time() - start_time
            minutes, seconds = divmod(elapsed_time, 60)
            
            # Print summary
            print("\n" + "=" * 60)
            print(f"✅ Scraping completed in {int(minutes)} minutes and {seconds:.2f} seconds.")
            print(f"📊 Total companies processed: {len(companies)}")
            
            # Count companies with non-empty website URLs
            websites_found = sum(1 for company in companies if company.get('website_url'))
            success_rate = (websites_found / len(companies)) * 100 if len(companies) > 0 else 0
            print(f"🔗 Companies with website URLs: {websites_found} ({success_rate:.1f}%)")
            
            # Calculate scraping speed
            if elapsed_time > 0:
                speed = len(companies) / elapsed_time
                print(f"⚡ Processing speed: {speed:.2f} companies/second")
        else:
            print("No companies found to process.")
    except KeyboardInterrupt:
        print("\n⚠️ Process interrupted by user.")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        # Print detailed traceback for debugging
        import traceback
        traceback.print_exc()
    finally:
        # Always print end time
        print(f"\n📅 Process finished at: {time.strftime('%Y-%m-%d %H:%M:%S')}")