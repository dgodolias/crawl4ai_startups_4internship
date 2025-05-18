# Email Processing Module for EU Startups

This document explains how to use the updated `find_contact_email.py` script to process CSV files from the scrape_results directory and extract email contacts from company websites.

## Overview

The script has been updated to:

1. Process all country CSV files in the `scrape_results` directory
2. Extract email contacts from each company website
3. Remove duplicates based on website URLs
4. Save the results to a single CSV file

## Usage Options

### Process All Country CSV Files

To process all country CSV files in the `scrape_results` directory:

```bash
python find_contact_email.py --process-all-csvs --output european_startups_contacts.csv
```

This will:
- Find all `*_websites.csv` files in the `scrape_results` directory
- Deduplicate companies based on website URL
- Visit each website to extract contact emails
- Save the consolidated results to the specified output file

### Process a Consolidated CSV File

If you already have a consolidated CSV file with company data:

```bash
python find_contact_email.py --process-consolidated-csv european_startup_websites.csv --output european_startups_with_emails.csv
```

### Process a Single Website

To extract emails from a single website:

```bash
python find_contact_email.py --website https://example.com
```

### Process a SeedTable Company

To extract emails for a company listed on SeedTable:

```bash
python find_contact_email.py --company CompanyName-ID123
```

## Output Format

The output CSV file has the following columns:
- `name`: Company name
- `country`: Country where the company is based
- `eu_startups_url`: URL of the company's page on EU-Startups
- `website_url`: Actual company website URL
- `emails`: Comma-separated list of email addresses found

## Technical Details

- The script uses both regex pattern matching and AI-based extraction (using Crawl4AI) to find email addresses
- It visits both the company's main website and any contact/support pages
- Duplicate companies are identified based on their website URLs to ensure each company appears only once in the output
- Results are written to the CSV file as they're processed, so progress is preserved even if the script is interrupted

## Limitations

- Some websites may block automated access
- The script is set to limit checking to 3 contact pages per website to avoid excessive crawling
- Extraction quality depends on how contact information is presented on websites
