import asyncio
from crawl4ai import AsyncWebCrawler
from config import BASE_URL, CSS_SELECTOR, REQUIRED_KEYS
from utils.data_utils import save_startups_to_csv
from utils.scraper_utils import (
    fetch_and_process_page,
    get_browser_config,
    get_llm_strategy,
)

async def crawl_startups():
    """
    Main function to crawl startup data from F6S.
    """
    # Initialize configurations
    browser_config = get_browser_config()
    llm_strategy = get_llm_strategy()
    session_id = "f6s_startup_crawl"

    # Initialize state variables
    page_number = 1
    all_startups = []
    seen_names = set()

    # Start the web crawler context
    async with AsyncWebCrawler(config=browser_config) as crawler:
        while True:
            # Fetch and process data from the current page
            startups, no_results_found = await fetch_and_process_page(
                crawler,
                page_number,
                BASE_URL,
                CSS_SELECTOR,
                llm_strategy,
                session_id,
                REQUIRED_KEYS,
                seen_names,
            )
            
            if no_results_found:
                print("No more startups found. Ending crawl.")
                break  # Stop crawling when no more results are found
            
            if not startups:
                print(f"No startups extracted from page {page_number}.")
                page_number += 1
                
                # If we've checked 3 empty pages in a row, assume we're done
                if page_number > 3:
                    print("Multiple empty pages. Ending crawl.")
                    break
                    
                continue
            
            # Add the startups from this page to the total list
            all_startups.extend(startups)
            page_number += 1  # Move to the next page
            
            # Pause between requests to be polite and avoid rate limits
            await asyncio.sleep(3)
    
    # Save the collected startups to a CSV file
    if all_startups:
        save_startups_to_csv(all_startups, "startup_websites.csv")
        print(f"Saved {len(all_startups)} startups to 'startup_websites.csv'.")
    else:
        print("No startups were found during the crawl.")
    
    # Display usage statistics for the LLM strategy
    llm_strategy.show_usage()

async def main():
    """
    Entry point of the script.
    """
    await crawl_startups()

if __name__ == "__main__":
    asyncio.run(main())
