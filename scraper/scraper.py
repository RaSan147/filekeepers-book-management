import os
import asyncio
import hashlib
import logging
from datetime import datetime, timezone
import traceback
from typing import Optional

import aiohttp
from bs4 import BeautifulSoup
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import IndexModel

from shared.models import BookBase, BookInDB, BookChangeLog
from shared.config import config

from .utils import send_email_alert, exponential_backoff
from .network_utils import resolve_relative_link, tag_to_absolute_url

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_URL = config.BASE_URL
MONGO_URI = config.MONGO_URI
SMTP_CONFIG = {
    'host': config.SMTP_HOST,
    'port': config.SMTP_PORT,
    'username': config.SMTP_USER,
    'password': config.SMTP_PASS,
}
CHANGELOG_LIMIT = config.CHANGELOG_LIMIT  # Limit for change log entries, -1 for no limit
REQUEST_TIMEOUT = config.REQUEST_TIMEOUT  # Timeout for HTTP requests in seconds

class BookScraper:
    def __init__(self, base_url=BASE_URL, mongo_uri=MONGO_URI):
        self.base_url = base_url
        self.client = AsyncIOMotorClient(mongo_uri)
        self.db = self.client.book_db
        self.session = None
        self.current_page = 1
        self.max_pages = None

        self.ratings = {
            "one": 1,
            "two": 2,
            "three": 3,
            "four": 4,
            "five": 5
        }

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        await self._ensure_indexes()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.session.close()

    async def _ensure_indexes(self):
        await self.db.books.create_indexes([
            IndexModel([("url", 1)], unique=True),
            IndexModel([("category", 1)]),
            IndexModel([("price_incl_tax", 1)]),
            IndexModel([("rating", 1)]),
            IndexModel([("last_updated", -1)]),
        ])
        await self.db.change_log.create_index([("timestamp", -1)])

    @exponential_backoff(retries=3, retry_on_None=True, raise_on_failure=False)
    async def fetch_page(self, url: str) -> Optional[str]:
        """
        Fetch a page using aiohttp with error handling and retries.
        Args:
            url (str): The URL to fetch.
        Returns:
            Optional[str]: The HTML content of the page or None if an error occurs.
        """
        try:
            async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)) as response:
                response.raise_for_status()  # Raise for HTTP errors
                return await response.text()
        except asyncio.TimeoutError:
            logger.warning(f"Timeout fetching {url}")
        except Exception as e:
            logger.error(f"Error fetching {url}: {e.__class__.__name__}: {str(e)}")
        return None

    def parse_book_page(self, html: str, url: str) -> Optional[BookBase]:
        """
        Parse the book page HTML and extract book details.
        Returns a BookBase object or None if parsing fails.
        Args:
            html (str): The HTML content of the book page.
            url (str): The URL of the book page.
        Returns:
            Optional[BookBase]: Parsed book data or None if an error occurs.
        """
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            title = soup.select_one('h1').text
            category = soup.select('.breadcrumb li:nth-last-child(2) a')[0].text
            description = soup.select('#product_description + p')
            description = description[0].text if description else "No description"
            
            price_incl_tax = float(soup.select('.table-striped tr:nth-child(4) td')[0].text[1:])
            price_excl_tax = float(soup.select('.table-striped tr:nth-child(3) td')[0].text[1:])
            
            availability = soup.select('.table-striped tr:nth-child(6) td')[0].text
            availability = int(availability.split()[2].strip("(")) if availability else 0
            
            review_count = int(soup.select('.table-striped tr:nth-child(7) td')[0].text)
            image_obj = soup.select_one('#product_gallery img')
            image_url = tag_to_absolute_url(
                image_obj, 'src', current_url=url, base_url=self.base_url,
                default_return=''  # Return empty string if no image found
            ) if image_obj else ''

            rating_class_set = soup.select_one('.star-rating')
            rating_class = rating_class_set['class'] if rating_class_set else []
            for rating in rating_class:
                rating = rating.strip().lower()
                if rating in self.ratings:
                    break
            else:
                rating = "zero"
            rating_score = self.ratings.get(rating, 0)

            return BookBase(
                url=url,
                title=title,
                category=category,
                description=description,
                price_incl_tax=price_incl_tax,
                price_excl_tax=price_excl_tax,
                availability=availability,
                review_count=review_count,
                image_url=image_url,
                rating=rating_score
            )
        except Exception as e:
            traceback.print_exc()
            logger.error(f"Error parsing book page {url}: {e}")
            return None

    async def process_book_page(self, book_url: str):
        """ Process a single book page, checking for changes and updating the database.
        Args:
            book_url (str): The URL of the book page to process.
        Returns:
            Optional[str]: 'created' if a new book was added, 'updated' if an existing book was updated, or None if no changes were detected.
        """
        html = await self.fetch_page(book_url)
        if not html:
            return None

        content_hash = hashlib.sha256(html.encode()).hexdigest()
        existing_book = await self.db.books.find_one({"url": book_url})

        # Skip if unchanged
        if existing_book and existing_book.get('content_hash') == content_hash:
            return None

        book_data = self.parse_book_page(html, book_url)
        if not book_data:
            return None

        now = datetime.now(tz=timezone.utc)

        book_dict = book_data.model_dump()
        book_in_db = BookInDB(
            **book_dict,
            _id='',  # MongoDB will assign this
            content_hash=content_hash,
            raw_html=html,
            first_seen=now,  # Will be set later
            last_updated=now  # Will be set later
        )
        book_in_db.content_hash = content_hash
        book_in_db.raw_html = html

        if existing_book:
            # Find changed fields
            changed_fields = {
                k: (existing_book.get(k), v)
                for k, v in book_dict.items()
                if k in existing_book and existing_book[k] != v
            }
            
            if changed_fields:
                # Update book
                # book_dict['last_updated'] = now
                book_in_db.last_updated = now
                book_in_db.id = str(existing_book["_id"])  # Use existing ID
                await self.db.books.update_one(
                    {"_id": existing_book["_id"]},
                    {"$set": book_in_db.model_dump()}
                )
                
                # Log change
                change_log = BookChangeLog(
                    book_id=str(existing_book["_id"]),
                    change_type="updated",
                    changed_fields=changed_fields,
                    timestamp=now
                )
                await self.db.change_log.insert_one(change_log.model_dump())
                
                # Send alert for significant changes
                if 'price_incl_tax' in changed_fields or 'availability' in changed_fields:
                    await send_email_alert(
                        f"Book updated: {book_data.title}",
                        f"Changed fields: {changed_fields}",
                        "admin@example.com",
                        smtp_config=SMTP_CONFIG
                    )
                
                return "updated"
        else:
            # Insert new book
            book_in_db.first_seen = now
            book_in_db.last_updated = now
            result = await self.db.books.insert_one(book_in_db.model_dump())
            
            # Log creation
            change_log = BookChangeLog(
                book_id=str(result.inserted_id),
                change_type="created",
                changed_fields={"new_book": True},
                timestamp=now
            )
            await self.db.change_log.insert_one(change_log.model_dump())
            
            await send_email_alert(
                f"New book added: {book_data.title}",
                f"Category: {book_data.category}\nPrice: £{book_data.price_incl_tax}",
                "admin@example.com",
                smtp_config=SMTP_CONFIG
            )
            
            return "created"

    def paginate_url(self, soup: BeautifulSoup, base_url: str) -> Optional[str]:
        next_page = soup.select_one('li.next a')

        return tag_to_absolute_url(
            next_page, 'href', current_url=base_url, base_url=self.base_url
        ) if next_page else None

    async def scrape_category(self, category_url: str):
        html = await self.fetch_page(category_url)
        if not html:
            return []

        soup = BeautifulSoup(html, 'html.parser')

        book_links = [
            tag_to_absolute_url(a, 'href', current_url=category_url, base_url=self.base_url)
            for a in soup.select('h3 a')
        ]

        book_links = [link for link in book_links if link]
        
        # Process all book pages concurrently
        tasks = [self.process_book_page(link) for link in book_links]
        results = await asyncio.gather(*tasks)

        next_page_url = self.paginate_url(soup, category_url)
        if next_page_url:
            logger.info(f"Found next page: {category_url} \t->\t {next_page_url}")
            # Recursively scrape the next page
            results += await self.scrape_category(next_page_url)

        return results

    async def scrape_all_books(self):
        logger.info("Starting book scraping")
        start_time = datetime.now(tz=timezone.utc)
        
        # Get all categories
        index_url = resolve_relative_link('/index.html', self.base_url)
        html = await self.fetch_page(index_url)
        if not html:
            return

        soup = BeautifulSoup(html, 'html.parser')
        category_links = [
            tag_to_absolute_url(a, 'href', current_url=self.base_url) for a in soup.select('.side_categories ul ul li a')
        ]

        category_links = [x for x in category_links if x]
        
        # Scrape all categories concurrently
        tasks = [self.scrape_category(link) for link in category_links]
        await asyncio.gather(*tasks)
        
        # Generate daily report
        await self.generate_daily_report(start_time)
        
        logger.info(f"Finished scraping in {datetime.now(tz=timezone.utc) - start_time} seconds")

    async def generate_daily_report(self, since: datetime):
        new_books = await self.db.books.count_documents({
            "first_seen": {"$gte": since}
        })
        
        updated_books = await self.db.change_log.count_documents({
            "change_type": "updated",
            "timestamp": {"$gte": since}
        })
        
        changes = self.db.change_log.find({
            "timestamp": {"$gte": since}
        }).sort("timestamp", -1)

        if CHANGELOG_LIMIT > 0:
            changes = await changes.limit(CHANGELOG_LIMIT).to_list(None)
        elif CHANGELOG_LIMIT == -1:
            changes = await changes.to_list(None)
        else:
            changes = []
        
        report = {
            "date": datetime.now(timezone.utc).isoformat(),
            "new_books": new_books,
            "updated_books": updated_books,
            "changes": [BookChangeLog(**change).model_dump() for change in changes]
        }
        
        # Store report
        await self.db.reports.insert_one(report)
        
        # Optionally send email with report
        await send_email_alert(
            "Daily Scraping Report",
            f"New books: {new_books}\nUpdated books: {updated_books}",
            "admin@example.com",
            smtp_config=SMTP_CONFIG
        )

async def main():
    async with BookScraper() as scraper:
        await scraper.scrape_all_books()

if __name__ == "__main__":
    asyncio.run(main())