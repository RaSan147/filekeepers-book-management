import asyncio
import hashlib
import logging
from datetime import datetime, timezone
import traceback
from typing import Optional
from uuid import uuid4

import aiohttp
from bs4 import BeautifulSoup
from bson import ObjectId
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
    def __init__(self, base_url=BASE_URL, mongo_uri=MONGO_URI, resume: bool = False):
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

        self.scraped_links = set()  # Track already scraped links
        self.resume = resume
        self.session_id = str(uuid4())  # Unique session ID for this scraping run

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

        await self.db.session_log.create_indexes([
            IndexModel([("session_id", 1)]),
            IndexModel([("timestamp", -1)]),
        ])

    async def _ensure_resume(self):
        """ Ensure we can resume from the last point if needed. """
        if self.resume:
            # Load last scraped lsession_id from the database
            last_session = await self.db.session_log.find_one({"session_id": self.session_id}, sort=[("timestamp", -1)])
            if last_session:
                # add the scraped links (links with the session id) to the set
                self.scraped_links = set(await self.db.books.find({"session_id": last_session}, {"url": 1}).distinct("url"))
                logger.info(f"Resuming from last session: {last_session}, found {len(self.scraped_links)} previously scraped links.")
            else:
                logger.info(f"No previous session found, starting fresh with session ID: {self.session_id}")

        else:
            # Start a new session, clear scraped links and db activity
            await self.db.session_log.delete_many({})

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
                #NOTE: causes warning for not waiting in pytest. but its not a promise return, so can't be awaited
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
        if book_url in self.scraped_links:
            logger.info(f"Skipping already scraped book: {book_url}")
            return None

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
                
                self.scraped_links.add(book_url)  # Mark as scraped
                # Log activity
                activity_log = {
                    "session_id": self.session_id,
                    "url": book_url,
                    "timestamp": now,
                }
                await self.db.session_log.insert_one(activity_log)
                
                return "updated"
        else:
            # Insert new book
            book_in_db.first_seen = now
            book_in_db.last_updated = now
            result = await self.db.books.insert_one(book_in_db.model_dump())
            
            # Log creation
            change_log = BookChangeLog(
                book_id=str(result.inserted_id),
                change_type="added",
                changed_fields={"new_book": True},
                timestamp=now
            )
            await self.db.change_log.insert_one(change_log.model_dump())
            
            self.scraped_links.add(book_url)  # Mark as scraped
            # Log activity
            activity_log = {
                "session_id": self.session_id,
                "url": book_url,
                "timestamp": now,
            }
            await self.db.session_log.insert_one(activity_log)
            
            return "created"

    def paginate_url(self, soup: BeautifulSoup, base_url: str) -> Optional[str]:
        """
        Find the next page URL from the pagination links.
        Args:
            soup (BeautifulSoup): The BeautifulSoup object containing the page HTML.
            base_url (str): The base URL to resolve relative links.
        Returns:
            Optional[str]: The absolute URL of the next page or None if no next page is found.
        """
        next_page = soup.select_one('li.next a')

        return tag_to_absolute_url(
            next_page, 'href', current_url=base_url, base_url=self.base_url
        ) if next_page else None

    async def scrape_category(self, category_url: str):
        """
        Scrape a category page for book links and process each book concurrently.
        Args:
            category_url (str): The URL of the category page to scrape.
        Returns:
            List[Optional[str]]: A list of results from processing each book page.
        """
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
        """
        Scrape all books from all categories starting from the index page.
        This method fetches the index page, extracts category links, and scrapes each category concurrently.
        It also generates a daily report of new and updated books.
        """
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
        """ Generate a daily report of new and updated books since the given date.
        This method counts new and updated books, retrieves change logs, and stores the report in the database.
        Args:
            since (datetime): The date from which to count new and updated books.
        """
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

        # Send notifications for changes
        listed_changes = await changes.to_list(None)
        if changes:
            await self.send_change_notifications(listed_changes)
    
        if CHANGELOG_LIMIT > 0:
            changes = listed_changes[:CHANGELOG_LIMIT]
        elif CHANGELOG_LIMIT == -1:
            changes = listed_changes
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
            subject="Daily Scraping Report",
            body=f"<b>New books:</b> {new_books}\n<b>Updated books:</b> {updated_books}",
            recipient=config.EMAIL_TO,
            smtp_config=SMTP_CONFIG,
            html=True
        )

    async def send_change_notifications(self, changes: list):
        """Group and send change notifications in a more organized way."""
        new_books = []
        price_changes = []
        availability_changes = []
        other_changes = []
        
        for change in changes:
            if change['change_type'] == "added":
                new_books.append(change)
            elif change['change_type'] == "updated":
                if 'price_incl_tax' in change['changed_fields']:
                    price_changes.append(change)
                elif 'availability' in change['changed_fields']:
                    availability_changes.append(change)
                else:
                    other_changes.append(change)
        
        # Send separate emails for each category
        if new_books:
            await self._send_new_books_email(new_books)
        if price_changes:
            await self._send_price_changes_email(price_changes)
        if availability_changes:
            await self._send_availability_changes_email(availability_changes)
        if other_changes:
            await self._send_other_changes_email(other_changes)

    async def _send_new_books_email(self, new_books: list):
        """Send email about new books added."""
        subject = f"📚 {len(new_books)} New Book(s) Added"
        body = ["<h2>New Books Added</h2>", "<ul>"]
        
        for book in new_books:
            book_data = await self.db.books.find_one({"_id": ObjectId(book['book_id'])})
            if book_data:
                body.append(
                    f"<li><b>{book_data['title']}</b> in <i>{book_data['category']}</i> "
                    f"(Price: <b>£{book_data['price_incl_tax']:.2f}</b>)"
                    f"<br>▥ <a href='{book_data['url']}'>View Book</a></li>"
                )
        
        body.append("</ul>")
        await send_email_alert(
            subject=subject,
            body="\n".join(body),
            recipient=config.EMAIL_TO,
            smtp_config=SMTP_CONFIG,
            html=True
        )

    async def _send_price_changes_email(self, price_changes: list):
        """Send email about price changes."""
        subject = f"💰 {len(price_changes)} Book Price Change(s)"
        body = ["<h2>Price Changes</h2>", "<ul>"]
        
        for change in price_changes:
            book_data = await self.db.books.find_one({"_id": ObjectId(change['book_id'])})
            if book_data:
                old_price, new_price = change['changed_fields']['price_incl_tax']
                price_diff = new_price - old_price
                arrow = "↑" if price_diff > 0 else "↓"
                
                body.append(
                    f"<li><b>{book_data['title']}</b> "
                    f"<span style='color: {'red' if price_diff > 0 else 'green'}'>"
                    f"({arrow}£{abs(price_diff):.2f})</span> "
                    f"from <s>£{old_price:.2f}</s> to <b>£{new_price:.2f}</b>"
                    f"<br>▥ <a href='{book_data['url']}'>View Book</a></li>"
                )
        
        body.append("</ul>")
        await send_email_alert(
            subject=subject,
            body="\n".join(body),
            recipient=config.EMAIL_TO,
            smtp_config=SMTP_CONFIG,
            html=True
        )

    async def _send_availability_changes_email(self, availability_changes: list):
        """Send email about availability changes."""
        subject = f"📦 {len(availability_changes)} Stock Level Change(s)"
        body = ["<h2>Availability Changes</h2>", "<ul>"]
        
        for change in availability_changes:
            book_data = await self.db.books.find_one({"_id": ObjectId(change['book_id'])})
            if book_data:
                old_stock, new_stock = change['changed_fields']['availability']
                stock_diff = new_stock - old_stock
                
                body.append(
                    f"<li><b>{book_data['title']}</b> "
                    f"<span style='color: {'green' if stock_diff > 0 else 'red'}'>"
                    f"({'+' if stock_diff > 0 else ''}{stock_diff})</span> "
                    f"from {old_stock} to <b>{new_stock}</b> in stock"
                    f"<br>▥ <a href='{book_data['url']}'>View Book</a></li>"
                )
        
        body.append("</ul>")
        await send_email_alert(
            subject=subject,
            body="\n".join(body),
            recipient=config.EMAIL_TO,
            smtp_config=SMTP_CONFIG,
            html=True
        )

    async def _send_other_changes_email(self, other_changes: list):
        """Send email about other changes."""
        subject = f"ℹ️ {len(other_changes)} Other Book Change(s)"
        body = ["<h2>Other Changes</h2>", "<ul>"]
        
        for change in other_changes:
            book_data = await self.db.books.find_one({"_id": ObjectId(change['book_id'])})
            if book_data:
                changes = []
                for field, (old_val, new_val) in change['changed_fields'].items():
                    changes.append(f"{field}: {old_val} → <b>{new_val}</b>")
                
                body.append(
                    f"<li><b>{book_data['title']}</b><br>"
                    f"{'<br>'.join(changes)}"
                    f"<br>▥ <a href='{book_data['url']}'>View Book</a></li>"
                )
        
        body.append("</ul>")
        await send_email_alert(
            subject=subject,
            body="\n".join(body),
            recipient=config.EMAIL_TO,
            smtp_config=SMTP_CONFIG,
            html=True
        )

async def main(resume: bool = False):
    """ Main entry point for the scraper.
    If `resume` is True, it will resume scraping from the last point.
    Otherwise, it will start from the beginning.
    Args:
        resume (bool): Whether to resume scraping from the last point.
    """
    async with BookScraper(resume=resume) as scraper:
        await scraper.scrape_all_books()

if __name__ == "__main__":
    asyncio.run(main())