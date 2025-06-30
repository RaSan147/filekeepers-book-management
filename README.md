
# 📚 Book Scraper & Monitoring System  
_A Production-Grade Web Scraper, Scheduler, and RESTful API for Books to Scrape_

## 🚀 Overview

This project is a complete content aggregation and monitoring platform for product-related websites, with a production-ready pipeline built around [https://books.toscrape.com](https://books.toscrape.com). It includes:

- 🌐 **Asynchronous Web Crawler** with robust retry, resume, and change detection logic.
- 🕓 **Daily Scheduler** for automatic monitoring and change logging.
- 🔐 **Secure RESTful API Server** with authentication, filtering, and rate-limiting.
- 💾 **MongoDB Integration** for scalable, document-based storage.
- 📊 **Reporting Interface** to track daily changes with optional CSV export.
- ✅ **Testable, Modular, and Well-Structured** codebase for easy maintenance and deployment.

> Designed with fault-tolerance, performance, and clean design in mind.

---

## 📁 Project Structure

```

.
├── API/                 # FastAPI server (routes, auth, reports)
├── scraper/             # Async web crawler and scheduler
├── shared/              # Shared models, config, utilities
├── tests/               # (Optional) Unit & integration tests
├── .env                 # Environment variables
├── docker-compose.yml   # Docker-based orchestration
├── scrapper_caller.py   # Entrypoint to run the crawler
├── api_server_caller.py # Entrypoint to run the API server
└── README.md

````

---

## 🧰 Features

### ✅ Part 1: Crawler
- Asynchronous & fault-tolerant (`aiohttp`, retry with backoff)
- Crawls:
  - Book Title, Description, Category
  - Prices (incl. & excl. tax)
  - Availability & Reviews
  - Rating, Image URL, Raw HTML snapshot
- Metadata stored: crawl timestamp, content hash, source URL
- Automatically resumes from last success if interrupted

### ⏰ Part 2: Scheduler + Change Detection
- Scheduled daily with `cron` or `APScheduler`
- Detects:
  - Newly added books
  - Updated records (price, availability, etc.)
- Stores:
  - Change log with timestamps and diffs
  - Daily reports (JSON and downloadable CSV)
- Email alerts for significant changes (e.g., price updates)

### 🧩 Part 3: Secure RESTful API
- Built with **FastAPI**, fully documented via Swagger (`/docs`)
- Endpoints:
  - `GET /books`: Filter, search, paginate
  - `GET /books/{id}`: Book details
  - `GET /changes`: View recent updates
  - `GET /reports/daily`: Daily monitoring report
- Security:
  - API key-based authentication
  - Rate limiting with `slowapi`
  - Admin scopes for key management

---

## 🧑‍💻 Developer Setup

### 🔧 Requirements

- Python ≥ 3.10
- MongoDB (local or cloud)
- [Docker](https://www.docker.com/) (recommended for easy setup)

### 📦 Install Dependencies

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
````

### ⚙️ Environment Configuration

Create a `.env` file with:

```env
# Example .env
MONGO_URI=mongodb://localhost:27017
API_HOST=0.0.0.0
API_PORT=8080
SMTP_HOST=smtp.mailtrap.io
SMTP_PORT=587
SMTP_USER=your_user
SMTP_PASS=your_pass
DEFAULT_ADMIN_API_KEY=your_api_key
DEFAULT_ADMIN_TASK_NAME=admin
CHANGELOG_LIMIT=100
REQUEST_TIMEOUT=30
ENV_LOADED_SUCCESSFULLY=1
```

---

## 🧪 Run the Project

### ▶️ Run the Scraper

```bash
python scrapper_caller.py
```

To resume from last session (run if interrupted) (if completed, will skip through already processed books):

```bash
python scrapper_caller.py --resume
```

### ▶️ Run the API Server

```bash
python api_server_caller.py
```
or Uvicorn for production:
```bash
uvicorn API:app --host "0.0.0.0" --port 8080
```

### 🐳 Docker

```bash
docker-compose up --build
```

---

## 🔐 API Documentation

Interactive API docs:

* Swagger UI: [http://localhost:8080/docs](http://localhost:8080/docs)
* Redoc: [http://localhost:8080/redoc](http://localhost:8080/redoc)

Authentication:

* All endpoints require a valid `X-API-KEY` header.
* Use `/keys` (admin-only) to manage API keys.


### 📊 API Endpoints (Summary)

| Method | Endpoint             | Description                      |
| ------ | -------------------- | -------------------------------- |
| GET    | `/books`             | Filter, paginate, and sort books |
| GET    | `/books/{book_id}`   | Get full book details            |
| GET    | `/changes`           | Recent updates in books          |
| GET    | `/reports/daily`     | Daily summary (JSON)             |
| GET    | `/reports/daily/csv` | Daily summary (CSV download)     |
| POST   | `/keys`              | Create API key (admin)           |
| GET    | `/keys`              | List all keys (admin)            |
| PATCH  | `/keys/{key_id}`     | Update a key (admin)             |
| DELETE | `/keys/{key_id}`     | Remove a key (admin)             |

---

## 📤 Sample MongoDB Document

```json
{
  "_id": "60c72b2f9b1e8d001c8e4f3a",
  "url": "https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html",
  "title": "A Light in the Attic",
  "category": "Poetry",
  "description": "A touching book by Shel Silverstein...",
  "price_incl_tax": 51.77,
  "price_excl_tax": 47.45,
  "availability": 19,
  "review_count": 0,
  "image_url": "https://books.toscrape.com/media/cache/...",
  "rating": 3,
  "content_hash": "abcd1234...",
  "raw_html": "<html>...</html>",
  "first_seen": "2024-01-01T00:00:00Z",
  "last_updated": "2024-01-03T12:00:00Z"
}
```

---

## 🧪 Testing

```bash
pytest
```

---

## 📬 Postman Collection

A Postman collection for testing the API is included in the `/docs` folder or can be exported from `/docs` Swagger UI.

---

## 🧠 Concepts & Tools Used

* **Python Async** (`asyncio`, `aiohttp`)
* **FastAPI**, **MongoDB**, **Motor**
* **Retry with Exponential Backoff**
* **Content Hashing** for change detection
* **Rate Limiting** via `slowapi`
* **API Key Authentication**
* **Modular & Layered Architecture**
* **Docker Compose** setup for services
* **Email Alerting** via `aiosmtplib` (optional)

---

## 📄 License

This project is licensed under the MIT License.
Feel free to fork and modify for educational or production use.

---

## 💼 Author & Contact

**Ratul Hasan**
- [GitHub](www.github.com/rasan147)
---

## 🙌 Acknowledgments

* [Books to Scrape](https://books.toscrape.com) — the mock e-commerce site
* FastAPI, MongoDB, BeautifulSoup — for making this project possible

