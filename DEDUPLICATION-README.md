# EU-Startups Web Scraper with Deduplication

This document explains how to run the EU-Startups scraper pipeline with improved deduplication to eliminate duplicate company entries.

## Overview of Deduplication

The updated pipeline includes several layers of deduplication:

1. **During extraction**: Company links from EU-Startups are deduplicated based on their URLs
2. **During website extraction**: Company websites are deduplicated to ensure we don't process the same company twice
3. **Before email extraction**: Final deduplication is performed before the resource-intensive process of email extraction

## Running the Pipeline

### Complete Pipeline with Deduplication

To run the complete pipeline with all deduplication steps:

```powershell
python eu_startups_integration.py
```

### With Additional Options

The integration script supports several command-line options:

- `--recrawl`: Force recrawling of company links (bypasses cached results)
- `--country`: Process only a specific country
- `--threads`: Number of worker threads for website extraction (default: 15)

Examples:

```powershell
# Process only German startups
python eu_startups_integration.py --country Germany

# Process French startups with 20 worker threads
python eu_startups_integration.py --country France --threads 20

# Recrawl all countries and process with default settings
python eu_startups_integration.py --recrawl
```

### Running Individual Steps

You can also run individual components of the pipeline:

1. **Extract company links** from country pages:
   ```powershell
   python eu_startups_crawler.py --country Germany
   ```

2. **Extract website URLs** from company pages:
   ```powershell
   python eu_startups_scraper.py --country Germany --threads 15
   ```

3. **Extract emails** from websites (uses the integration script):
   ```powershell
   python eu_startups_integration.py
   ```

## Output Files

The pipeline generates several output files:

- `crawl_results/[Country]_companies.txt`: Company links extracted from each country
- `scrape_results/[Country]_websites.csv`: Website URLs extracted for each country
- `european_ai_startups_contact_info.csv`: Final output with company information and extracted emails

## Deduplication Details

### Duplicate Sources

Duplicates may appear in the data for several reasons:
- Companies appearing in multiple country directory pages
- Companies with multiple listings on EU-Startups
- Crawling errors causing the same page to be processed multiple times

### Deduplication Methods

The updated pipeline implements these deduplication strategies:

1. **URL-based deduplication**: Uses the EU-Startups URL as a unique identifier
2. **Website-based deduplication**: Uses the actual company website URL as an additional identifier
3. **Combined deduplication**: Uses both URLs together for maximum effectiveness

## Performance Improvements

- Multi-threading support for faster website extraction
- Progressive saving to preserve progress on interruption
- Memory-efficient processing to handle large datasets
