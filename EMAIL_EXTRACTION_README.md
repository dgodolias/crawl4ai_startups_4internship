# EU Startups Email Extraction Pipeline

This document explains the two-step process for extracting contact emails from EU startup websites.

## Overview

The email extraction process is split into two separate programs:

1. **duplicate_remover.py**: Consolidates all country CSV files from the `scrape_results` directory into a single CSV without duplicates.
2. **find_contact_email.py**: Processes the consolidated CSV file to find contact emails for each company.

This separation of concerns makes the process more robust and efficient, allowing you to:
- Run the consolidation step once and the email extraction multiple times if needed
- Resume the email extraction process if it's interrupted

## Step 1: Duplicate Removal & Consolidation

First, run the `duplicate_remover.py` script to process all CSV files in the `scrape_results` directory:

```powershell
python duplicate_remover.py --output european_startup_websites.csv
```

This will:
- Read all `*_websites.csv` files in the `scrape_results` directory
- Remove duplicates based on website URL
- Create a consolidated CSV file with columns: `name`, `country`, `eu_startups_url`, `website_url`

## Step 2: Email Extraction

After creating the consolidated CSV, run the `find_contact_email.py` script to extract emails:

```powershell
python find_contact_email.py --input european_startup_websites.csv --output european_startups_with_emails.csv
```

This will:
- Process each company website to find contact emails
- Use both regex pattern matching and LLM extraction
- Save results to a CSV file with columns: `name`, `country`, `eu_startups_url`, `website_url`, `emails`

## Running the Complete Pipeline

For convenience, you can run the entire pipeline with a single PowerShell script:

```powershell
.\run_email_extraction.ps1
```

This script will run both steps in sequence, ensuring the correct files are used.

## Technical Details

- The browser runs in headless mode for better performance
- The LLM extraction uses retries to handle potential API failures
- Results are written to the CSV file as they're processed, so progress is preserved even if the script is interrupted
- Both scripts include command-line arguments for customization

## Command Line Options

### duplicate_remover.py
```
--output   Output CSV filename (default: european_startup_websites.csv)
```

### find_contact_email.py
```
--input    Input CSV file with company data (default: european_startup_websites.csv)
--output   Output CSV filename (default: european_startups_with_emails.csv)
--website  Direct website URL to process (single mode)
--company  SeedTable company ID to process (single mode)
```

## Single Website Mode

You can also use `find_contact_email.py` to process a single website:

```powershell
python find_contact_email.py --website https://example.com
```

This is useful for testing or processing individual websites outside the batch process.
