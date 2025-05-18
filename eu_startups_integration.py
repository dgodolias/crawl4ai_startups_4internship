"""
Let's ensure a proper integration with our EU Startups crawler system
We'll integrate our find_contact_email.py with the rest of the EU-Startups scraper code
"""

import asyncio
import os
import re
import sys
import csv
import time
from typing import List, Set, Dict, Any, Optional, Tuple
import urllib.parse
from bs4 import BeautifulSoup

from find_contact_email import (
    get_browser_config,
    get_llm_strategy,
    extract_emails_from_text,
    find_emails_for_company
)

from eu_startups_crawler import crawl_all_countries
from eu_startups_scraper import process_companies_from_files

async def process_eu_startups(recrawl: bool = False, max_workers: int = 15, filter_country: str = None):
    """
    Main function to process EU Startups
    1. Crawl countries
    2. Extract company links
    3. Get actual website URLs
    4. Extract emails using crawl4ai
    
    Args:
        recrawl: If True, recrawl company links even if cached data exists 
        max_workers: Number of worker threads for website extraction
        filter_country: Optional country name to process only one country
    """
    print("=" * 60)
    print("Starting EU Startups processing pipeline...")
    print("=" * 60)
    
    # Step 1: Crawl countries if needed
    if recrawl:
        print("\nStep 1: Crawling country directories...")
        await crawl_all_countries(filter_country=filter_country)
    else:
        print("\nStep 1: Using existing country crawl data...")
    
    # Step 2: Process company websites
    print("\nStep 2: Extracting website URLs from company pages...")
    companies = process_companies_from_files(max_workers=max_workers, filter_country=filter_country)
    
    if not companies:
        print("No companies found to process. Please check if crawl results exist.")
        return
    
    # Step 3: Extract emails using crawl4ai
    print("\nStep 3: Extracting emails from websites using crawl4ai...")
    output_csv = 'european_ai_startups_contact_info.csv'
    await extract_emails_from_websites(companies, output_csv)
    
    print("\n" + "=" * 60)
    print(f"Process completed successfully. Results saved to {output_csv}")
    print("=" * 60)

async def extract_emails_from_websites(companies: List[Dict[str, str]], output_csv: str) -> None:
    """
    Extract emails from company websites using crawl4ai
    
    Args:
        companies: List of company dictionaries
        output_csv: Output CSV filename
    """
    # Deduplicate companies based on website_url
    unique_companies = []
    seen_urls = set()
    
    for company in companies:
        url = company.get('website_url', '')
        eu_url = company.get('eu_startups_url', '')
        
        # Skip empty URLs
        if not url:
            continue
            
        # Use both URLs for deduplication to be safe
        dedup_key = f"{url}|{eu_url}"
        
        if dedup_key not in seen_urls:
            seen_urls.add(dedup_key)
            unique_companies.append(company)
    
    print(f"Deduplication: Found {len(companies)} total companies, {len(unique_companies)} unique")
    
    fieldnames = ['name', 'country', 'eu_startups_url', 'website_url', 'emails']
    
    # Track statistics
    start_time = time.time()
    success_count = 0
    error_count = 0
    
    # Create or open the output CSV file
    with open(output_csv, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        # Process each company
        for i, company in enumerate(unique_companies):
            website_url = company.get('website_url', '')
            if not website_url:
                print(f"No website URL for {company.get('name', 'Unknown')}")
                company['emails'] = ''
                writer.writerow(company)
                continue
            
            # Calculate progress percentage and ETA
            progress = (i + 1) / len(unique_companies) * 100
            elapsed = time.time() - start_time
            if i > 0:
                eta_seconds = (elapsed / i) * (len(unique_companies) - i)
                eta_minutes = int(eta_seconds // 60)
                eta_seconds = int(eta_seconds % 60)
                eta_str = f"{eta_minutes}m {eta_seconds}s"
            else:
                eta_str = "calculating..."
            
            # Create progress bar visualization
            bar_length = 30
            filled_length = int(bar_length * (i + 1) // len(unique_companies))
            bar = '█' * filled_length + '░' * (bar_length - filled_length)
            
            # Display progress with company details
            print(f"\r[{bar}] {i+1}/{len(unique_companies)} ({progress:.1f}%) ETA: {eta_str} - Processing: {company['name']} ({website_url})", end='')
            
            # Extract emails using crawl4ai
            try:
                emails = await find_emails_for_company(website_url)
                company['emails'] = ','.join(emails) if emails else ''
                
                if emails:
                    success_count += 1
                    print(f"\nFound {len(emails)} emails: {', '.join(emails[:3])}{'...' if len(emails) > 3 else ''}")
                
            except Exception as e:
                error_count += 1
                print(f"\nError processing {website_url}: {e}")
                company['emails'] = f"ERROR: {str(e)}"
            
            # Write to CSV immediately to preserve progress
            writer.writerow(company)
            
            # Calculate processing rate
            if i > 0:
                rate = i / elapsed
                print(f" | Rate: {rate:.2f} companies/min")
            
            # Add a small delay between requests to avoid overloading
            await asyncio.sleep(0.5)
    
    # Print final statistics
    total_time = time.time() - start_time
    minutes, seconds = divmod(total_time, 60)
    
    print("\n" + "=" * 60)
    print(f"Email extraction completed in {int(minutes)} minutes and {int(seconds)} seconds.")
    print(f"Total companies processed: {len(unique_companies)}")
    print(f"Successful extractions: {success_count} ({success_count/len(unique_companies)*100:.1f}%)")
    print(f"Errors: {error_count}")
    print("=" * 60)

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="EU Startups email extraction pipeline")
    parser.add_argument("--recrawl", action="store_true", help="Force recrawling of company links")
    parser.add_argument("--country", type=str, help="Process only a specific country")
    parser.add_argument("--threads", type=int, default=15, help="Number of worker threads (default: 15)")
    args = parser.parse_args()
    
    print(f"Starting with {args.threads} threads" + 
          (f", filtering for {args.country}" if args.country else "") +
          (", recrawling data" if args.recrawl else ""))
    
    asyncio.run(process_eu_startups(
        recrawl=args.recrawl,
        max_workers=args.threads,
        filter_country=args.country
    ))
