import hashlib
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from scraper.scraper import BookScraper
from shared.models import BookBase
import aiohttp
from datetime import datetime, timezone

@pytest_asyncio.fixture
async def scraper():
    """Async fixture for the BookScraper"""
    async with BookScraper() as s:
        # Mock the database for testing
        s.db = MagicMock()
        yield s

@pytest.mark.asyncio
async def test_fetch_page_success(scraper):
    """Test successful page fetch"""
    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.text.return_value = "<html>test</html>"
    mock_resp.__aenter__.return_value = mock_resp
    
    with patch('aiohttp.ClientSession.get', return_value=mock_resp):
        result = await scraper.fetch_page("http://test.com")
        assert result == "<html>test</html>"
        mock_resp.raise_for_status.assert_called_once()

@pytest.mark.asyncio
async def test_fetch_page_retry(scraper):
    """Test retry mechanism on failure"""
    # Create mock responses
    mock_fail = AsyncMock()
    mock_fail.__aenter__.side_effect = aiohttp.ClientError("Failed")
    
    mock_success = AsyncMock()
    mock_success_resp = AsyncMock()
    mock_success_resp.status = 200
    mock_success_resp.text.return_value = "<html>test</html>"
    mock_success.__aenter__.return_value = mock_success_resp
    
    with patch('aiohttp.ClientSession.get', side_effect=[mock_fail, mock_fail, mock_success]):
        result = await scraper.fetch_page("http://test.com")
        assert result == "<html>test</html>"
        assert mock_fail.__aenter__.call_count == 2
        

def test_parse_book_page_valid():
    """Test parsing valid book page HTML"""
    scraper = BookScraper()
    html = """
    <html>
        <h1>Test Book</h1>
        <ul class="breadcrumb">
            <li><a href="#">Home</a></li>
            <li><a href="#">Category</a></li>
            <li class="active">Test Book</li>
        </ul>
        <div id="product_description"></div>
        <p>Test description</p>
        <table class="table table-striped">
        <tbody>
            <tr><th>UPC</th><td>311c0dd0e354a33e</td></tr>
            <tr><th>Product Type</th><td>Books</td></tr>
            <tr><th>Price (excl. tax)</th><td>£54.35</td></tr>
            <tr><th>Price (incl. tax)</th><td>£56.35</td></tr>
            <tr><th>Tax</th><td>£0.00</td></tr>
            <tr><th>Availability</th><td>In stock (16 available)</td></tr>
            <tr><th>Number of reviews</th><td>0</td></tr>
        </tbody></table>
        <div class="star-rating Five"></div>
        <div id="product_gallery">
            <div class="item active"><img src="test.jpg"></div>
        </div>
    </html>
    """
    
    book = scraper.parse_book_page(html, "http://test.com/book")
    assert isinstance(book, BookBase)
    assert book.title == "Test Book"
    assert book.price_incl_tax == 56.35
    assert book.price_excl_tax == 54.35
    assert book.availability == 16
    assert book.review_count == 0
    assert book.url == "http://test.com/book"
    assert book.category == "Category"
    assert book.description == "Test description"
    assert book.rating == 5
    assert book.image_url == "http://test.com/test.jpg"

@pytest.mark.asyncio
async def test_process_book_page_new_book(scraper):
    """Test processing a new book page"""
    test_html = "<html>test content</html>"
    test_url = "http://test.com/newbook"
    
    with (
        patch.object(scraper, 'fetch_page', new_callable=AsyncMock) as mock_fetch,
        patch.object(scraper, 'parse_book_page', return_value=BookBase(
            url=test_url,
            title="New Book",
            category="Test",
            description="Test book",
            price_incl_tax=10.0,
            price_excl_tax=9.0,
            availability=5,
            review_count=3,
            image_url="test.jpg",
            rating=5
        )), \
        patch.object(scraper.db.books, 'find_one', new_callable=AsyncMock) as mock_find, \
        patch.object(scraper.db.books, 'insert_one', new_callable=AsyncMock) as mock_insert, \
        patch.object(scraper.db.change_log, 'insert_one', new_callable=AsyncMock) as mock_log
    ):
        mock_fetch.return_value = test_html
        mock_find.return_value = None
        
        result = await scraper.process_book_page(test_url)
        assert result == "created"
        assert mock_insert.called
        assert mock_log.called

@pytest.mark.asyncio
async def test_scrape_category_pagination(scraper):
    """Test category scraping with pagination"""
    first_page = """
    <html>
        <h3><a href="/book1">Book 1</a></h3>
        <li class="next"><a href="/page2">Next</a></li>
    </html>
    """
    
    second_page = """
    <html>
        <h3><a href="/book2">Book 2</a></h3>
    </html>
    """
    
    # Setup mock methods
    scraper.fetch_page = AsyncMock(side_effect=[first_page, second_page])
    scraper.process_book_page = AsyncMock(return_value=None)
    
    await scraper.scrape_category("http://test.com/category")
    assert scraper.process_book_page.call_count == 2
    scraper.process_book_page.assert_any_call("http://test.com/book1")
    scraper.process_book_page.assert_any_call("http://test.com/book2")

@pytest.mark.asyncio
async def test_parse_book_page_invalid_html(scraper):
    """Test parsing invalid book page HTML"""
    result = scraper.parse_book_page("<html></html>", "http://test.com")
    assert result is None

@pytest.mark.asyncio
async def test_process_book_page_unchanged(scraper):
    """Test processing unchanged book page"""
    test_html = "<html>test</html>"
    test_hash = hashlib.sha256(test_html.encode()).hexdigest()
    test_url = "http://test.com/book"
    
    # Create an async mock that returns our test data
    mock_find = AsyncMock(return_value={"url": test_url, "content_hash": test_hash})
    
    with patch.object(scraper, 'fetch_page', return_value=test_html), \
         patch.object(scraper.db.books, 'find_one', new=mock_find):
        
        result = await scraper.process_book_page(test_url)
        assert result is None
        mock_find.assert_awaited_once()

@pytest.mark.asyncio
async def test_fetch_page_failure(scraper):
    """Test complete fetch failure after retries"""
    with patch('aiohttp.ClientSession.get', side_effect=aiohttp.ClientError("Failed")) as mock_get:
        result = await scraper.fetch_page("http://test.com")
        assert result is None
        assert mock_get.call_count == 3