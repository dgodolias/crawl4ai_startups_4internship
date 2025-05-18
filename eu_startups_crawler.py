"""
EU-Startups Crawler - Gets all company links from a country page
"""
import asyncio
import os
import re
import time
import urllib.parse
from typing import Dict, List, Set, Tuple

import requests
from bs4 import BeautifulSoup

from country_links import load_country_links

class EUStartupsCrawler:
    """Crawler to extract company links from EU-Startups directory"""
    
    def __init__(self):
        self.session = requests.Session()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        }
        self.delay = 2  # seconds between requests
    def _get_page_content(self, url: str) -> str:
        """
        Get HTML content from a URL with proper error handling
        
        Args:
            url: The URL to fetch
            
        Returns:
            HTML content as string
        """
        try:
            response = self.session.get(url, headers=self.headers)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            print(f"Error fetching {url}: {e}")
            return ""
        finally:
            time.sleep(self.delay)  # Be nice to the server
            
    def extract_company_links(self, country_url: str, max_pages: int = 100) -> List[Dict[str, str]]:
        """
        Extract all company links from a country directory page
        
        Args:
            country_url: URL of the country directory page
            max_pages: Maximum number of pages to fetch (default: 100)
            
        Returns:
            List of dictionaries with company details (name, link)
        """
        companies = []
        current_url = country_url
        page_num = 1
        total_pages_found = 0
        
        while True:
            print(f"Fetching page {page_num}: {current_url}")
            html = self._get_page_content(current_url)
            
            if not html:
                print(f"Failed to fetch page {page_num}")
                break
            
            soup = BeautifulSoup(html, 'html.parser')
            
            # Find all company listings
            listings = soup.find_all('div', class_='wpbdp-listing-excerpt')
            
            if not listings:
                print(f"No listings found on page {page_num}. Stopping.")
                break
            
            # Extract links from each listing
            for listing in listings:
                title_div = listing.find('div', class_='listing-title')
                if title_div:
                    link_tag = title_div.find('a')
                    if link_tag:
                        company_name = link_tag.text.strip()
                        company_link = link_tag.get('href', '')
                        if company_link:
                            companies.append({
                                'name': company_name,
                                'link': company_link
                            })
              # Check if there's a next page
            next_span = soup.find('span', class_='next')
            next_page = None
            if next_span:
                next_page = next_span.find('a')
                
            if not next_page:
                print("No more pages available")
                break            # Get URL for the next page
            next_url = next_page.get('href', '')
            if not next_url:
                print("Next page URL is empty. Stopping.")
                break
                
            # Make sure the URL is valid
            if not next_url.startswith('http'):
                # Handle relative URLs
                if next_url.startswith('/'):
                    # Get the base URL from the country_url
                    parsed_url = urllib.parse.urlparse(country_url)
                    base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
                    next_url = f"{base_url}{next_url}"
                else:
                    # Handle other relative URLs
                    next_url = urllib.parse.urljoin(current_url, next_url)
                    
            print(f"Found next page: {next_url}")
            current_url = next_url
            page_num += 1
            total_pages_found += 1
        
        print(f"Extracted {len(companies)} company links from {total_pages_found} pages")
        return companies

async def crawl_all_countries(filter_country: str = None) -> Dict[str, List[Dict[str, str]]]:
    """
    Crawl all countries from the CSV file or a specific country if filter_country is set
    
    Args:
        filter_country: Optional country name to crawl only one country
    
    Returns:
        Dictionary with country names as keys and lists of company dictionaries as values
    """
    crawler = EUStartupsCrawler()
    countries_data = {}
    
    # Load all country links from CSV
    country_links = load_country_links()
    
    # Apply filter if specified
    if filter_country:
        country_links = [(link, country, count) 
                         for link, country, count in country_links 
                         if country.lower() == filter_country.lower()]
        if not country_links:
            print(f"Country '{filter_country}' not found in country links.")
            return {}
    
    # Report on what's being crawled
    if filter_country:
        print(f"Crawling 1 country: {filter_country}")
    else:
        print(f"Crawling {len(country_links)} countries...")
    
    # Process each country
    for link, country, _ in country_links:
        # Check if we already have results for this country
        safe_country = re.sub(r'[^a-zA-Z0-9]', '_', country)
        country_file = f'crawl_results/{safe_country}_companies.txt'
        
        if os.path.exists(country_file) and os.path.getsize(country_file) > 0:
            print(f"\nSkipping {country} - already crawled (found {country_file})")
            
            # Load the existing data for completeness
            companies = []
            with open(country_file, 'r', encoding='utf-8') as f:
                for line in f:
                    parts = line.strip().split('\t')
                    if len(parts) == 2:
                        companies.append({
                            'name': parts[0],
                            'link': parts[1]
                        })
            countries_data[country] = companies
            continue
        
        print(f"\nCrawling {country} ({link})...")
        companies = crawler.extract_company_links(link)
        countries_data[country] = companies
        
        # Save interim results to avoid losing data if the process is interrupted
        save_interim_results(country, companies)
        
        # Add a delay between countries to be nice to the server
        await asyncio.sleep(1)
        
    return countries_data

def save_interim_results(country: str, companies: List[Dict[str, str]]) -> None:
    """
    Save interim results to a file
    
    Args:
        country: Name of the country
        companies: List of company dictionaries
    """
    os.makedirs('crawl_results', exist_ok=True)
    
    # Create a safe filename from the country name
    safe_country = re.sub(r'[^a-zA-Z0-9]', '_', country)
    
    # Save to a text file
    with open(f'crawl_results/{safe_country}_companies.txt', 'w', encoding='utf-8') as f:
        for company in companies:
            f.write(f"{company['name']}\t{company['link']}\n")
    
    print(f"Saved {len(companies)} companies for {country}")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Extract company links from EU-Startups directory')
    parser.add_argument('--country', type=str, help='Process only a specific country (optional)')
    args = parser.parse_args()
    
    print("Starting EU-Startups crawler...")
    
    # Set up asyncio to run the crawler
    async def main():
        countries_data = await crawl_all_countries(filter_country=args.country)
        
        # Print summary
        total_companies = sum(len(companies) for companies in countries_data.values())
        print(f"\nCrawling completed. Total companies found: {total_companies}")
        for country, companies in countries_data.items():
            print(f"{country}: {len(companies)} companies")
    
    # Run the async main function
    asyncio.run(main())