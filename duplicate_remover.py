#!/usr/bin/env python
"""
Duplicate Remover for EU Startups CSV files

This script combines all country CSV files from the scrape_results directory,
removes duplicates based on website URL, and creates a single consolidated CSV file.
"""

import csv
import os
import glob
import sys
from typing import Dict, List, Set

def consolidate_csv_files(output_csv: str = "european_startup_websites.csv") -> None:
    """
    Consolidate all country CSV files in the scrape_results directory into a single CSV,
    removing duplicates based on website URL.
    
    Args:
        output_csv: Path for the output consolidated CSV file
    """
    # Find all CSV files in scrape_results directory
    csv_pattern = os.path.join('scrape_results', '*_websites.csv')
    csv_files = glob.glob(csv_pattern)
    
    if not csv_files:
        print(f"No CSV files found matching pattern: {csv_pattern}")
        return
    
    print(f"Found {len(csv_files)} country CSV files to process")
    
    # Track unique companies to avoid duplicates
    unique_companies = {}  # website_url -> {name, country, eu_startups_url, website_url}
    
    # Process each CSV file
    for csv_file in csv_files:
        country_name = os.path.basename(csv_file).split('_')[0]
        print(f"Processing {country_name} from {csv_file}")
        
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
                        # If duplicate found, keep the one with more information
                        existing = unique_companies[website_url]
                        if (not existing.get('name') and company.get('name')) or \
                           (not existing.get('eu_startups_url') and company.get('eu_startups_url')):
                            unique_companies[website_url] = {
                                'name': company.get('name', ''),
                                'country': company.get('country', country_name),
                                'eu_startups_url': company.get('eu_startups_url', ''),
                                'website_url': website_url
                            }
                        continue
                    
                    # Add to unique companies
                    unique_companies[website_url] = {
                        'name': company.get('name', ''),
                        'country': company.get('country', country_name),
                        'eu_startups_url': company.get('eu_startups_url', ''),
                        'website_url': website_url
                    }
        except Exception as e:
            print(f"Error processing CSV file {csv_file}: {e}")
    
    # Convert to list for easier processing
    companies_list = list(unique_companies.values())
    
    print(f"Found {len(companies_list)} unique companies across all countries")
    
    # Sort by country and then by name for better readability
    companies_list.sort(key=lambda x: (x['country'], x['name']))
    
    # Create the output CSV file and write header
    with open(output_csv, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['name', 'country', 'eu_startups_url', 'website_url']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        # Write each unique company to CSV
        for company in companies_list:
            writer.writerow(company)
    
    print(f"Successfully created consolidated CSV file: {output_csv}")
    print(f"Total unique companies: {len(companies_list)}")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Consolidate country CSV files and remove duplicates")
    parser.add_argument("--output", type=str, default="european_startup_websites.csv", 
                      help="Output CSV filename (default: european_startup_websites.csv)")
    args = parser.parse_args()
    
    consolidate_csv_files(args.output)
