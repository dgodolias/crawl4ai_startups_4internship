# EU-Startups Crawler and Email Extractor

This project crawls the EU-Startups directory to find company information and extract contact emails using the crawl4ai library.

## Overview

The system works in 3 main steps:
1. **Crawl Country Pages**: Extract all company links from country-specific pages on EU-Startups
2. **Extract Website URLs**: Visit each company's EU-Startups page to get their actual website URL
3. **Extract Emails**: Use crawl4ai to find contact emails on each company's website

## Files

- `country_links.py`: Module to read country links from the CSV file
- `eu_startups_crawler.py`: Crawler to extract company links from country pages
- `eu_startups_scraper.py`: Scraper to extract actual website URLs from company pages
- `eu_startups_main.py`: Main script that runs the entire process
- `eu_startups_integration.py`: Integration script for existing email extractor
- `find_contact_email.py`: Module for extracting emails using crawl4ai

## Requirements

- Python 3.7+
- Packages listed in `requirements.txt`
- crawl4ai library

## Usage

### Run the complete process

```bash
python eu_startups_main.py
```

This will:
1. Load country links from `startups_data.csv`
2. Crawl each country to extract company links
3. Visit each company page to extract website URLs
4. Use crawl4ai to extract emails from each website

### Run for specific countries

```bash
python eu_startups_main.py Austria Germany
```

The results will be saved to `european_ai_startups_contact_info.csv`.

## Directories

The system creates the following directories:
- `crawl_results`: Contains files with company links for each country
- `scrape_results`: Contains files with website URLs for each country

## How It Works

### Step 1: Crawling Country Pages

For each country in the CSV file (`startups_data.csv`), the system:
1. Visits the country-specific EU-Startups directory page
2. Extracts all company links using the pattern:
   ```html
   <div class="listing-title">
       <h3><a href="https://www.eu-startups.com/directory/company-name/" target="_self">Company Name</a></h3>
   </div>
   ```
3. Handles pagination to get all companies

### Step 2: Extracting Website URLs

For each company link, the system:
1. Visits the company's page on EU-Startups
2. Extracts the actual website URL using the pattern:
   ```html
   <div class="wpbdp-field-display wpbdp-field wpbdp-field-value field-display field-value wpbdp-field-website">
       <span class="field-label">Website:</span>
       <div class="value">https://company-website.com</div>
   </div>
   ```

### Step 3: Extracting Emails

For each company website URL, the system:
1. Uses crawl4ai to visit the website
2. Extracts email addresses using regex and LLM-based extraction
3. Saves the results to a CSV file

## Error Handling

The system includes robust error handling:
- Failed requests are logged but don't stop the process
- Progress is saved incrementally to prevent data loss
- Each step can be run independently if needed

## Final Output

The final output is a CSV file (`european_ai_startups_contact_info.csv`) with the following columns:
- `name`: Company name
- `country`: Country of the company
- `eu_startups_url`: Link to the company page on EU-Startups
- `website_url`: Actual website URL
- `emails`: Comma-separated list of extracted emails