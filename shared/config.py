import os
from dotenv import load_dotenv

load_dotenv(override=False)  # Always load .env at import time

class Config:
	"""Configuration class for the application."""
	BASE_URL = 'https://books.toscrape.com'
	API_HOST = os.getenv("API_HOST", "0.0.0.0")
	API_PORT = int(os.getenv("API_PORT", 0))
	SMTP_HOST = os.getenv("SMTP_HOST")
	SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
	SMTP_USER = os.getenv("SMTP_USER")
	SMTP_PASS = os.getenv("SMTP_PASS")
	CHANGELOG_LIMIT = int(os.getenv("CHANGELOG_LIMIT", -1)) # Limit for change log entries, -1 for no limit
	REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", 30))


	APP_TITLE = os.getenv("APP_TITLE", "Books Scraper API")
	APP_DESCRIPTION = os.getenv("APP_DESCRIPTION", "API for scraping books from Books to Scrape")
	APP_VERSION = os.getenv("APP_VERSION", "1.0.0")

	DEFAULT_ADMIN_RATE_LIMIT = os.getenv("DEFAULT_ADMIN_RATE_LIMIT", "500/hour")  # Default rate limit for admin users
	DEFAULT_USER_RATE_LIMIT = os.getenv("DEFAULT_USER_RATE_LIMIT", "100/hour")  # Default rate limit for regular users
	DEFAULT_IP_RATE_LIMIT = os.getenv("DEFAULT_IP_RATE_LIMIT", "200/hour")  # Default rate limit for IPs

	DEFAULT_ADMIN_TASK_NAME = os.getenv("DEFAULT_ADMIN_TASK_NAME", '')
	DEFAULT_ADMIN_API_KEY = os.getenv("DEFAULT_ADMIN_API_KEY", '')

	MONGO_URI = os.getenv("MONGO_URI", '')
	MONGO_USERNAME = os.getenv("MONGO_USERNAME", None)
	MONGO_PASSWORD = os.getenv("MONGO_PASSWORD", None)

	if MONGO_USERNAME and MONGO_PASSWORD:
		if MONGO_URI.startswith(f"mongodb://{MONGO_USERNAME}:{MONGO_PASSWORD}@"):
			pass # If the URI already contains credentials, we don't modify it
		else:
			MONGO_URI = MONGO_URI.replace("mongodb://", f"mongodb://{MONGO_USERNAME}:{MONGO_PASSWORD}@")

	ENV_LOADED_SUCCESSFULLY = int(os.getenv("ENV_LOADED_SUCCESSFULLY", 0)) == 1

	if not ENV_LOADED_SUCCESSFULLY or not all([
		MONGO_URI,
		API_HOST,
		API_PORT,
		SMTP_HOST,
		SMTP_PORT,
		SMTP_USER,
		SMTP_PASS,
		DEFAULT_ADMIN_TASK_NAME,
		DEFAULT_ADMIN_API_KEY,
		APP_TITLE,
		APP_DESCRIPTION,
		APP_VERSION,
		DEFAULT_ADMIN_RATE_LIMIT,
		DEFAULT_USER_RATE_LIMIT
	]):
		raise EnvironmentError("Environment variables not loaded successfully. Please check your .env file.")

config = Config()

if __name__ == "__main__":
	# For debugging purposes, print the configuration
	print("Configuration loaded successfully:")
	for key, value in vars(Config).items():
		if not key.startswith('__'):
			print(f"{key}: {value}")
	
	if not config.ENV_LOADED_SUCCESSFULLY:
		print("Warning: Environment variables may not have loaded correctly. Check your .env file.")
	else:
		print("Environment variables loaded successfully.")

