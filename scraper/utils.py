import asyncio
import os
from typing import Optional
import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
from functools import wraps

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MAX_EMAILS = 5

async def send_email_alert(
    subject: str,
    body: str,
    recipient: Optional[str] = None,
    smtp_config: Optional[dict] = None,
    html: bool = False,
    max_retries: int = 3,
    retry_delay: float = 1.0
) -> bool:
    """Send an email alert using SMTP with HTML support and retry logic.
    
    Args:
        subject: Email subject
        body: Email body content
        recipient: Recipient email address
        smtp_config: SMTP configuration dictionary (uses env vars if None)
        html: Whether to send as HTML (default: False)
        max_retries: Maximum number of retry attempts
        retry_delay: Initial delay between retries in seconds (exponential backoff)
    
    Returns:
        bool: True if email was sent successfully, False otherwise
    """
    global MAX_EMAILS
    
    # Check email limit
    if MAX_EMAILS <= 0 or recipient is None:
        # logger.warning("Maximum email limit reached. Not sending email.")
        return False
    
    # Load SMTP config from environment if not provided
    if smtp_config is None:
        smtp_config = {
            "host": os.getenv("SMTP_HOST"),
            "port": int(os.getenv("SMTP_PORT", 587)),
            "username": os.getenv("SMTP_USER"),
            "password": os.getenv("SMTP_PASS")
        }
    
    # Validate required config
    required_keys = ["host", "username", "password"]
    if not all(smtp_config.get(k) for k in required_keys):
        logger.error("Missing required SMTP configuration")
        return False
    
    # Create email message
    message = MIMEMultipart()
    message["From"] = smtp_config["username"]
    message["To"] = recipient
    message["Subject"] = subject
    
    # Add body with appropriate content type
    content_type = "html" if html else "plain"
    message.attach(MIMEText(body, content_type))
    
    # Retry logic with exponential backoff
    last_exception = None
    for attempt in range(max_retries):
        try:
            await aiosmtplib.send(
                message,
                hostname=smtp_config["host"],
                port=smtp_config.get("port", 587),
                username=smtp_config["username"],
                password=smtp_config["password"],
                start_tls=True,
                timeout=10  # Add timeout to prevent hanging
            )
            logger.info(f"Sent email to {recipient} with subject: {subject}")
            MAX_EMAILS -= 1
            return True
            
        except Exception as e:
            last_exception = e
            wait_time = retry_delay * (2 ** attempt)  # Exponential backoff
            logger.warning(
                f"Email send attempt {attempt + 1} failed. "
                f"Retrying in {wait_time:.1f} seconds. Error: {str(e)}"
            )
            await asyncio.sleep(wait_time)
    
    # All retries failed
    logger.error(
        f"Failed to send email after {max_retries} attempts. "
        f"Last error: {str(last_exception)}"
    )
    return False

def exponential_backoff(retries: int = 3, base_delay: float = 1.0, retry_on_None: bool = False, raise_on_failure: bool = True):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(retries):
                try:
                    return_value = await func(*args, **kwargs)
                    if return_value is None and retry_on_None:
                        last_error = ValueError("Function returned None")
                        raise last_error
                    return return_value
                except Exception as e:
                    last_error = e
                    if attempt < retries - 1:
                        delay = base_delay * (2 ** attempt)
                        logger.warning(f"Attempt {attempt + 1} failed. Retrying in {delay}s...")
                        await asyncio.sleep(delay)

            if raise_on_failure:
                raise last_error if last_error else Exception("Unknown error")
            else:
                logger.error(f"Function failed after {retries} attempts: {last_error}")
                return None
        return wrapper
    return decorator