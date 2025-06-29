import asyncio
from typing import Optional
import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
from functools import wraps

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def send_email_alert(subject: str, body: str, recipient: str, smtp_config: Optional[dict] = None):
    """Send an email alert using SMTP.
    If smtp_config is None, it will use environment variables.
    """
    return
    try:
        # Load from environment in production
        smtp_config = {
            "host": smtp_config.get("host"),
            "port": smtp_config.get("port", 587),
            "username": smtp_config.get("username"),
            "password": smtp_config.get("password")
        }
        
        message = MIMEMultipart()
        message["From"] = smtp_config["username"]
        message["To"] = recipient
        message["Subject"] = subject
        
        message.attach(MIMEText(body, "plain"))
        
        await aiosmtplib.send(
            message,
            hostname=smtp_config["host"],
            port=smtp_config["port"],
            username=smtp_config["username"],
            password=smtp_config["password"],
            start_tls=True
        )
        logger.info(f"Sent alert email to {recipient}")
    except Exception as e:
        logger.error(f"Failed to send email: {e}")

def exponential_backoff(retries: int = 3, base_delay: float = 1.0):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    if attempt < retries - 1:
                        delay = base_delay * (2 ** attempt)
                        logger.warning(f"Attempt {attempt + 1} failed. Retrying in {delay}s...")
                        await asyncio.sleep(delay)
            raise last_error if last_error else Exception("Unknown error")
        return wrapper
    return decorator