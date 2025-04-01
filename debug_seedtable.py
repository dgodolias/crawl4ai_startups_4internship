import requests
from bs4 import BeautifulSoup

def analyze_seedtable_page(company_id):
    """
    Fetch and analyze a SeedTable company page to find website links
    """
    url = f"https://www.seedtable.com/startups/{company_id}"
    print(f"Analyzing SeedTable page: {url}")
    
    try:
        response = requests.get(url)
        if response.status_code != 200:
            print(f"Failed to fetch page: {response.status_code}")
            return
            
        # Parse with BeautifulSoup
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Look for overview section
        overview_section = soup.find('div', class_=lambda c: c and 'bg-st-gray-lightest' in c)
        if not overview_section:
            print("Could not find overview section")
            return
            
        # Print the content structure to help debug
        print("\nPage Structure:")
        for child in overview_section.children:
            if child.name:
                print(f"- Element: {child.name}, Classes: {child.get('class', '')}")
                
        # Try different strategies to find website links
        
        # Strategy 1: Look for span with "Websites:" text
        websites_span = soup.find('span', string='Websites:')
        if websites_span:
            print("\nFound 'Websites:' span element")
            parent_li = websites_span.find_parent('li')
            if parent_li:
                print("Found parent <li> element")
                links = parent_li.find_all('a')
                if links:
                    print("Found website links:")
                    for link in links:
                        print(f"  - {link.get('href')}")
                else:
                    print("No links found within the parent <li>")
        else:
            print("\nNo 'Websites:' span element found")
            
        # Strategy 2: Look for any elements with 'website' or 'url' in the text
        website_elements = soup.find_all(text=lambda text: text and ('website' in text.lower() or 'url' in text.lower()))
        if website_elements:
            print("\nFound elements containing 'website' or 'url':")
            for elem in website_elements:
                print(f"  - {elem}")
                # Check parent elements for links
                parent = elem.parent
                if parent:
                    links = parent.find_all('a')
                    if links:
                        print(f"    Found links in parent:")
                        for link in links:
                            print(f"      {link.get('href')}")
        
        # Strategy 3: Find all links in the overview section
        all_links = overview_section.find_all('a')
        if all_links:
            print("\nAll links in overview section:")
            for link in all_links:
                href = link.get('href')
                text = link.get_text().strip()
                print(f"  - {text}: {href}")
        else:
            print("\nNo links found in overview section")
            
    except Exception as e:
        print(f"Error analyzing page: {e}")

if __name__ == "__main__":
    # Test with the examples that are failing
    analyze_seedtable_page("Cellink_AB_%28publ%29-EA8DK8X")
    print("\n" + "="*50 + "\n")
    analyze_seedtable_page("Bambuser-YYM3AW")