"""
Module to load and provide country links from the startups_data.csv file
"""
import csv
import os
from typing import Dict, List, Tuple

def load_country_links() -> List[Tuple[str, str, int]]:
    """
    Load country links from the startups_data.csv file
    
    Returns:
        List of tuples with (link, country_name, number_of_companies)
    """
    csv_path = os.path.join(os.path.dirname(__file__), 'startups_data.csv')
    country_links = []
    
    try:
        with open(csv_path, 'r', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                link = row.get('Link', '')
                country = row.get('Country', '')
                companies = int(row.get('NumberOfCompanies', 0))
                if link and country:
                    country_links.append((link, country, companies))
    except Exception as e:
        print(f"Error loading country links: {e}")
        
    return country_links

def get_countries() -> List[str]:
    """
    Get list of country names from the CSV file
    
    Returns:
        List of country names
    """
    return [country for _, country, _ in load_country_links()]

def get_link_for_country(country_name: str) -> str:
    """
    Get the link for a specific country
    
    Args:
        country_name: The name of the country
        
    Returns:
        The URL for the country's startup listing
    """
    country_links = load_country_links()
    for link, country, _ in country_links:
        if country.lower() == country_name.lower():
            return link
    return ""

if __name__ == "__main__":
    # Test the module by printing all countries and their links
    countries = load_country_links()
    print(f"Loaded {len(countries)} countries:")
    for link, country, companies in countries:
        print(f"{country}: {link} ({companies} companies)")