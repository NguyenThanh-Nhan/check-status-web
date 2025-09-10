import requests
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from datetime import datetime
import time
import sys
import os
from dotenv import load_dotenv
import logging

# Load environment variables from .env file
load_dotenv()

# Configure settings from environment variables
WEBSITE_URL = os.getenv('WEBSITE_URL', 'https://shalom.vn/')
EMAIL_SENDER = os.getenv('EMAIL_SENDER', 'website_monitor@cms.neko-it.site')
EMAIL_RECEIVER = os.getenv('EMAIL_RECEIVER', 'nhannt200823@gmail.com')
SENDGRID_API_KEY = os.getenv('SENDGRID_API_KEY')
CHECK_INTERVAL = int(os.getenv('CHECK_INTERVAL', '3600'))
REQUEST_TIMEOUT = int(os.getenv('REQUEST_TIMEOUT', '30'))

# Check if API key is provided
if not SENDGRID_API_KEY:
    print(f"[{datetime.now()}] Error: SENDGRID_API_KEY not found in environment variables", file=sys.stderr)
    sys.exit(1)

# Define error levels


class ErrorLevel:
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


last_status = None
error_count = 0  # Count consecutive errors


def classify_error(status_code=None, exception=None):
    """
    Classify error level based on status code or exception
    """
    if exception:
        # Classify based on exception type
        if isinstance(exception, requests.exceptions.Timeout):
            return ErrorLevel.WARNING, f"⚠️ Timeout: Could not connect within {REQUEST_TIMEOUT} seconds - {str(exception)} "
        elif isinstance(exception, requests.exceptions.ConnectionError):
            return ErrorLevel.ERROR, f"🚫 Connection Error: Could not connect to server - {str(exception)}"
        elif isinstance(exception, requests.exceptions.HTTPError):
            return ErrorLevel.ERROR, f"🚫 HTTP Error: HTTP issue - {str(exception)}"
        elif isinstance(exception, requests.exceptions.RequestException):
            return ErrorLevel.WARNING, f"⚠️ Request Exception: {str(exception)}"
        else:
            return ErrorLevel.ERROR, f"🚫 Unknown Exception: {str(exception)}"

    if status_code:
        # Classify based on HTTP status code
        if 200 <= status_code < 300:
            return ErrorLevel.INFO, f"🆗 Website is running normally (Status: {status_code})"
        elif 300 <= status_code < 400:
            return ErrorLevel.WARNING, f"⚠️ Redirect: Website redirected (Status: {status_code})"
        elif status_code == 404:
            return ErrorLevel.WARNING, f"⚠️ Page Not Found: Page does not exist (Status: {status_code})"
        elif 400 <= status_code < 500:
            return ErrorLevel.ERROR, f"⚠️ Client Error: Client-side error (Status: {status_code})"
        elif 500 <= status_code < 600:
            return ErrorLevel.CRITICAL, f"❌ Server Error: Server-side error (Status: {status_code})"
        else:
            return ErrorLevel.WARNING, f"⚠️ Unknown Status Code: {status_code}"

    return ErrorLevel.ERROR, "🚫 Unknown error occurred"


def should_send_email(error_level):
    """
    Decide whether to send an email based on error level
    """
    return error_level in [ErrorLevel.WARNING, ErrorLevel.ERROR, ErrorLevel.CRITICAL]


def send_email(subject, body):
    try:
        message = Mail(
            from_email=EMAIL_SENDER,
            to_emails=EMAIL_RECEIVER,
            subject=subject,
            plain_text_content=body)
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        response = sg.send(message)
        print(
            f"📩🆗 [{datetime.now()}] Email sent successfully: {subject} (Status: {response.status_code})")
        return True
    except Exception as e:
        print(f"📩❗ [{datetime.now()}] Error sending email: {e}", file=sys.stderr)
        return False


def check_website():
    """
    Check website and return detailed status information
    """
    global error_count

    try:
        print(f"🍀 [{datetime.now()}] Checking website {WEBSITE_URL}")
        # Use timeout from .env
        response = requests.get(WEBSITE_URL, timeout=REQUEST_TIMEOUT)

        error_level, message = classify_error(status_code=response.status_code)

        if error_level == ErrorLevel.INFO:
            print(f"🎇 [{datetime.now()}] {error_level}: {message}")
            error_count = 0  # Reset counter when website is running normally
            return True, error_level, message
        else:
            print(f"🎇 [{datetime.now()}] {error_level}: {message}")
            error_count += 1
            return False, error_level, message

    except requests.exceptions.RequestException as e:
        error_level, message = classify_error(exception=e)
        print(f"[{datetime.now()}] {error_level}: {message}", file=sys.stderr)
        error_count += 1
        return False, error_level, message


def format_email_body(error_level, message, error_count):
    """
    Create detailed email content
    """
    body = f"""
Alert from website monitoring system:

Time: {datetime.now()}
Error Level: {error_level}
Error Details: {message}
Consecutive Error Count: {error_count}
---
Additional Information:
- Script will continue checking every {CHECK_INTERVAL} seconds
- Emails are sent for WARNING, ERROR, or CRITICAL level issues
- Immediate action is required for CRITICAL errors
- Please check your website and server.
    """
    return body.strip()


if __name__ == "__main__":
    last_status = None
    error_count = 0
    print(f"🍻 [{datetime.now()}] Starting website monitoring for {WEBSITE_URL}")
    print(f"⏰ [{datetime.now()}] Checking every {CHECK_INTERVAL} seconds")
    print(f"📩 [{datetime.now()}] Emails sent for WARNING, ERROR, or CRITICAL errors")

    while True:
        try:
            is_up, error_level, message = check_website()

            if is_up:
                # Website is up
                if last_status is not None and not last_status:
                    # Website transitioned from DOWN to UP
                    subject = f"🌸 Website {WEBSITE_URL} is BACK UP"
                    body = format_email_body(
                        ErrorLevel.INFO, "🌸 Website is back online", 0)
                    send_email(subject, body)
                    print(
                        f"💔 [{datetime.now()}] Website recovered - notification email sent")
                else:
                    print(
                        f"💌 [{datetime.now()}] Website is still running normally - no email sent")
            else:
                # Website has issues
                if should_send_email(error_level):
                    # Send email for WARNING, ERROR, or CRITICAL
                    if error_level == ErrorLevel.CRITICAL:
                        subject = f"❌ CRITICAL - Website {WEBSITE_URL} is DOWN"
                    elif error_level == ErrorLevel.ERROR:
                        subject = f"🚫 ERROR - Website {WEBSITE_URL} has issues"
                    else:  # WARNING
                        subject = f"⚠️ WARNING - Website {WEBSITE_URL} has issues"

                    body = format_email_body(error_level, message, error_count)

                    # Send email immediately for CRITICAL or after 2 consecutive WARNING/ERROR
                    if error_level == ErrorLevel.CRITICAL or error_count >= 2:
                        send_email(subject, body)
                        print(
                            f"💢 [{datetime.now()}] Alert email sent: {error_level}")
                    else:
                        print(
                            f"💢 [{datetime.now()}] {error_level} error - email not sent yet (count {error_count}/2)")
                else:
                    # INFO level - log only, no email
                    print(
                        f"🌸[{datetime.now()}] {error_level}: {message} - no email sent")

            last_status = is_up
            print(
                f"🎇 [{datetime.now()}] Waiting {CHECK_INTERVAL} seconds before next check")
            time.sleep(CHECK_INTERVAL)

        except KeyboardInterrupt:
            print(f"🎇 [{datetime.now()}] Script stopped by user")
            sys.exit(0)
        except Exception as e:
            print(
                f"🎇 [{datetime.now()}] Unhandled error in main loop: {e}", file=sys.stderr)
            time.sleep(CHECK_INTERVAL)
