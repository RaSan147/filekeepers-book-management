import asyncio
import argparse

from scraper import scraper

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the scraper.")
    parser.add_argument("--resume", action="store_true", help="Resume from the last checkpoint")
    args = parser.parse_args()

    # Pass the resume argument to the scraper
    asyncio.run(scraper.main(resume=args.resume))

    print("Scraper completed successfully.")