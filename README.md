# 📚 Books to Scrape Aggregation System

A **production-grade content aggregation pipeline** that scrapes, monitors, and exposes data from [books.toscrape.com](https://books.toscrape.com). This platform includes a robust crawler, scheduler with change detection, and a secure FastAPI backend for delivering book-related insights.

---

## 🌟 Key Features

### 🕸️ Asynchronous Web Crawler
- Built with `aiohttp`, `BeautifulSoup`, and retry logic
- Scrapes:
  - ✅ Book title, description, and category
  - 💰 Prices (incl./excl. tax)
  - 📦 Availability and number of reviews
  - ⭐ Rating, image URL, and raw HTML
- Stores crawl metadata with timestamp, URL, and content hash
- Supports **resume from failure** and **idempotent updates**

### 🗓️ Scheduler with Change Detection
- Scheduled via cron in Docker
- Detects:
  - New books (first-seen)
  - Updated fields (price, availability, etc.)
- Logs changes and diffs in MongoDB
- Sends **email alerts** and supports **CSV daily reports**

### 🔐 FastAPI Backend
- Endpoints for querying books, changes, and reports
- API Key-based authentication with rate limits
- Query filters, sorting, and pagination
- Interactive Swagger documentation

---

## 🗂️ Project Structure

```

.
├── API/               # FastAPI server (v1 routes, key management, reporting)
├── scraper/           # Crawler and scheduler
├── shared/            # Pydantic models, config, utilities
├── tests/             # Test suite (pytest-ready)
├── .env               # Runtime configuration
├── docker-compose.yml # Multi-container orchestrator
├── scrapper\_caller.py # Entry point for crawler
├── api\_server\_caller.py # Entry point for API server
└── README.md

````

---

## ⚙️ Configuration

Create a `.env` file using the `.env.example` template:

```env
MONGO_URI=mongodb://localhost:27017
SMTP_HOST=smtp.mailtrap.io
SMTP_PORT=587
SMTP_USER=username
SMTP_PASS=password
EMAIL_TO=admin@example.com

DEFAULT_ADMIN_API_KEY=your-secret-key
API_PORT=8080
API_HOST=0.0.0.0
````

---

## 🚀 Quick Start

### 🧪 Local Environment

```bash
# Setup virtualenv
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### ▶ Run the Scraper

```bash
python scrapper_caller.py
# or to resume from last run
python scrapper_caller.py --resume
```

### ▶ Run the API

```bash
python api_server_caller.py
# or for production
uvicorn API:app --host 0.0.0.0 --port 8080
```

### 🐳 Docker-based Setup

```bash
docker-compose up --build
```

---

## 🔍 API Overview

All endpoints require an API key via `X-API-KEY` header.

### 📚 Books

```http
GET /api/v1/books
```

#### Query Parameters

| Param      | Description                    |
| ---------- | ------------------------------ |
| category   | Filter by category             |
| min\_price | Minimum price                  |
| max\_price | Maximum price                  |
| rating     | Minimum rating (1-5)           |
| sort\_by   | One of: rating, price, reviews |
| page       | Page number                    |
| per\_page  | Items per page (max 100)       |

**Example:**

```http
GET /api/v1/books?category=Science&min_price=10&sort_by=rating
X-API-KEY: your-api-key
```

---

### 📘 Book Detail

```http
GET /api/v1/books/{book_id}
```

Returns full book details including raw HTML and timestamps.

---

### 🔄 Change Logs

```http
GET /api/v1/books/changes?days=7&limit=50
```

See what books were added/updated recently.

---

### 📊 Reports

```http
GET /api/v1/reports/daily
GET /api/v1/reports/daily/csv
```

Download or view daily report of changes.

---

### 🔑 API Key Management (Admin Only)

```http
POST   /api/v1/keys
GET    /api/v1/keys
PATCH  /api/v1/keys/{key}
DELETE /api/v1/keys/{key}
```

---

## 🧬 MongoDB Book Entry Example

```json
{
  "_id": "ObjectId(...)",
  "title": "The Requiem",
  "category": "Mystery",
  "description": "A gripping tale...",
  "price_incl_tax": 34.55,
  "price_excl_tax": 30.00,
  "availability": 8,
  "review_count": 12,
  "rating": 4,
  "image_url": "https://books.toscrape.com/media/...",
  "content_hash": "ae1d8f...",
  "raw_html": "<html>...</html>",
  "url": "https://books.toscrape.com/catalogue/the-requiem_66/index.html",
  "first_seen": "2025-06-29T12:01:00Z",
  "last_updated": "2025-06-30T02:21:00Z"
}
```

---

## 📬 Email Alerts

* Daily summaries of new/changed books
* Categorized by:

  * 📗 New additions
  * 💰 Price changes
  * 📦 Stock updates
  * 🔄 Other metadata changes

---

## 🧪 Testing

```bash
pytest
```

Supports full async testing with mocked DB via fixtures.

---

## 📄 License

Licensed under the MIT License.
Feel free to fork, contribute, or use in production projects.

---

## 👤 Maintainer

**Ratul Hasan**
🔗 [GitHub](https://github.com/rasan147)

---

## 🙏 Acknowledgments

* [Books to Scrape](https://books.toscrape.com) for the dataset
* FastAPI, BeautifulSoup, aiohttp, MongoDB for core tools
* ChatGPT and Deepseek for assistance in development and documentation

---


