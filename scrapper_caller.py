import asyncio

from scraper import scraper

if __name__ == "__main__":
	# Run the scraper
	asyncio.run(scraper.main())
	
	print("Scraper completed successfully.")