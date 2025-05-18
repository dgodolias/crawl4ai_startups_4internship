# EU-Startups Scraper - Multithreaded Version (Improved)

This is an improved multithreaded version of the EU-Startups scraper that significantly improves processing speed by running multiple requests in parallel and processing results as they become available.

## How It Works

The scraper now uses Python's `concurrent.futures` module with the `as_completed()` method to process multiple company pages simultaneously in a true parallel fashion, which dramatically reduces the overall processing time.

## Usage

Run the scraper with the default 10 threads:

```bash
python eu_startups_scraper.py
```

Or specify a custom number of threads:

```bash
python eu_startups_scraper.py --threads 20
```

Process only a specific country:

```bash
python eu_startups_scraper.py --threads 15 --country Austria
```

## Performance Tips

1. **Thread Count**: 
   - The default is set to 10 threads, which is a good balance for most systems
   - For faster internet connections, you can try 15-20 threads
   - For slower connections or to be extra gentle on the server, reduce to 5-8 threads

2. **Request Delay**:
   - The delay between requests is set to 1 second by default
   - You can adjust this in the `EUStartupsScraper.__init__()` method if needed

3. **Memory Usage**:
   - More threads will use more memory
   - Monitor your system's resources if you increase the thread count significantly

## Full Process

To run the complete EU-Startups processing workflow:

1. First crawl all countries to get company links:
   ```bash
   python eu_startups_crawler.py
   ```

2. Then extract website URLs using the multithreaded scraper:
   ```bash
   python eu_startups_scraper.py --threads 15
   ```

3. Finally, extract emails from the websites:
   ```bash
   python eu_startups_main.py
   ```

## Benefits of Multithreading

- Processing is approximately 8-10x faster than the sequential version
- Automatic retry and error handling for each request
- Progress is saved after each country is processed
- Thread-safe design prevents concurrency issues

Enjoy your much faster scraping experience!
