# EU-Startups Email Extractor - Quick Start Guide

This guide provides step-by-step instructions for using the EU-Startups Email Extractor with progress bars and improved UI.

## Quick Start

### 1. Install Requirements

```powershell
pip install -r requirements.txt
```

### 2. Crawl Company Links

First, crawl all countries to get the company links:

```powershell
python eu_startups_crawler.py
```

This will create files in the `crawl_results` directory, one for each country.

### 3. Extract Website URLs with Progress Bars

Run the improved scraper that shows progress bars by country:

```powershell
python eu_startups_scraper.py --threads 15
```

You can also process just one specific country:

```powershell
python eu_startups_scraper.py --threads 15 --country Austria
```

### 4. Extract Emails

Finally, extract emails from the websites:

```powershell
python eu_startups_main.py
```

## Available Commands

### Crawler Options

```powershell
# Default - crawl all countries
python eu_startups_crawler.py

# View available options
python eu_startups_crawler.py --help
```

### Scraper Options

```powershell
# View available options
python eu_startups_scraper.py --help

# Use more threads for faster processing
python eu_startups_scraper.py --threads 20

# Process only specific countries
python eu_startups_scraper.py --country Belgium
```

### Email Extractor Options

```powershell
# Default - process all websites
python eu_startups_main.py

# Process specific countries
python eu_startups_main.py Austria Belgium
```

## Performance Tips

- For faster processing, increase the number of threads (e.g., `--threads 20`)
- For more reliable results, use a lower thread count (e.g., `--threads 8`) 
- Process one country at a time if you encounter rate limiting