import asyncio
from typing import Type

from crawl.crawler.fce_crawl import FCEPlaywrightCrawler
from crawl.crawler.fae_crawl import FAEPlaywrightCrawler
from crawl.crawler.fas_crawl import FASPlaywrightCrawler
from crawl.crawler.fcft_crawl import FCFTPlaywrightCrawler
from crawl.crawler.fe_crawl import FEPlaywrightCrawler
from crawl.crawler.feee_crawl import FEEEPlaywrightCrawler
from crawl.crawler.feet_crawl import FEETPlaywrightCrawler
from crawl.crawler.ffl_crawl import FFLPlaywrightCrawler
from crawl.crawler.fgam_crawl import FGAMPlaywrightCrawler
from crawl.crawler.fgtfd_crawl import FGTFDPlaywrightCrawler
from crawl.crawler.fit_crawl import FITPlaywrightCrawler
from crawl.crawler.fme_crawl import FMEPlaywrightCrawler
from crawl.crawler.fpi_crawl import FPIPlaywrightCrawler
from crawl.crawler.ite_crawl import ITEPlaywrightCrawler


INTERVAL = 300
MAX_PAGES = 1


async def run_crawler_loop(
    name: str,
    crawler_cls: Type,
    interval: int = INTERVAL,
    max_pages: int = MAX_PAGES
):
    while True:
        print(f"🚀 Start crawling {name}...")
        print(f"==============================")

        crawler = crawler_cls()

        try:
            await crawler.run(max_pages=max_pages)
            print(f"✅ {name} crawl done")

        except Exception as e:
            print(f"❌ {name} crawl error: {e}")

        print(f"💤 {name} sleep {interval} seconds...")
        await asyncio.sleep(interval)


async def main():
    tasks = [
        run_crawler_loop("FCE", FCEPlaywrightCrawler),
        run_crawler_loop("FAE", FAEPlaywrightCrawler),
        run_crawler_loop("FAS", FASPlaywrightCrawler),
        run_crawler_loop("FCFT", FCFTPlaywrightCrawler),
        run_crawler_loop("FE", FEPlaywrightCrawler),
        run_crawler_loop("FEEE", FEEEPlaywrightCrawler),
        run_crawler_loop("FEET", FEETPlaywrightCrawler),
        run_crawler_loop("FFL", FFLPlaywrightCrawler),
        run_crawler_loop("FGAM", FGAMPlaywrightCrawler),
        run_crawler_loop("FGTFD", FGTFDPlaywrightCrawler),
        run_crawler_loop("FIT", FITPlaywrightCrawler),
        run_crawler_loop("FME", FMEPlaywrightCrawler),
        run_crawler_loop("FPI", FPIPlaywrightCrawler),
        run_crawler_loop("ITE", ITEPlaywrightCrawler),
    ]

    await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())