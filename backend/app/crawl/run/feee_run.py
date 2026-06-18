import asyncio
import time
from crawl.crawler.feee_crawl import FEEEPlaywrightCrawler

INTERVAL = 60

async def main():
    crawler = FEEEPlaywrightCrawler()

    while True:
        print("\nStart crawling...")
        try:
            await crawler.run(max_pages=1)
        except Exception as e:
            print(f"Error: {e}")

        print(f"Sleep {INTERVAL} seconds...")
        time.sleep(INTERVAL)


if __name__ == "__main__":
    asyncio.run(main())