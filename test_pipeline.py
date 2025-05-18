# test_pipeline.py
"""
Simple test script to verify the EU-Startups email extraction pipeline with deduplication
"""

import asyncio
import time
import argparse
from eu_startups_integration import process_eu_startups

async def test_pipeline():
    """
    Test the email extraction pipeline with a specific country
    """
    print("\n" + "=" * 60)
    print("🧪 Testing EU-Startups Pipeline with Deduplication")
    print("=" * 60)
    
    start_time = time.time()
    
    # Test with a small country to verify all parts work together
    test_country = "Luxembourg"
    max_workers = 10
    
    print(f"Testing with country: {test_country}, using {max_workers} worker threads")
    
    # Run the pipeline with the test country
    await process_eu_startups(
        recrawl=False,  # Use cached data if available
        max_workers=max_workers,
        filter_country=test_country
    )
    
    # Calculate and report execution time
    elapsed_time = time.time() - start_time
    minutes, seconds = divmod(elapsed_time, 60)
    
    print("\n" + "=" * 60)
    print(f"✅ Test completed in {int(minutes)} minutes and {int(seconds)} seconds")
    print("=" * 60)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test the EU-Startups pipeline")
    parser.add_argument("--recrawl", action="store_true", help="Force recrawling of company data")
    parser.add_argument("--country", type=str, default="Luxembourg", help="Country to test with (default: Luxembourg)")
    parser.add_argument("--threads", type=int, default=10, help="Number of worker threads (default: 10)")
    
    args = parser.parse_args()
    
    # Run the test with command line arguments
    async def run_test():
        print("\n" + "=" * 60)
        print("🧪 Testing EU-Startups Pipeline with Deduplication")
        print("=" * 60)
        
        start_time = time.time()
        
        print(f"Testing with country: {args.country}, using {args.threads} worker threads")
        print(f"Recrawl enabled: {args.recrawl}")
        
        # Run the pipeline with the provided arguments
        await process_eu_startups(
            recrawl=args.recrawl,
            max_workers=args.threads,
            filter_country=args.country
        )
        
        # Calculate and report execution time
        elapsed_time = time.time() - start_time
        minutes, seconds = divmod(elapsed_time, 60)
        
        print("\n" + "=" * 60)
        print(f"✅ Test completed in {int(minutes)} minutes and {int(seconds)} seconds")
        print("=" * 60)
    
    # Run the test
    asyncio.run(run_test())
