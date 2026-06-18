import asyncio
import time

from crawl.crawler.ffl_crawl import FFLPlaywrightCrawler

INTERVAL = 60


async def main():
    while True:
        print("\nStart crawling FFL...")

        crawler = FFLPlaywrightCrawler()

        try:
            await crawler.run(
                category="tin-tuc",
                max_pages=1,
                fetch_detail=True,
                auto_import=True
            )

        except Exception as e:
            print(f"Error: {e}")

        print(f"Sleep {INTERVAL} seconds...")
        await asyncio.sleep(INTERVAL)


if __name__ == "__main__":
    asyncio.run(main())