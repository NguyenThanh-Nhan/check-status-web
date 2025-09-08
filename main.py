import requests
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from datetime import datetime
import time
import sys
import os
from dotenv import load_dotenv
import logging

# Tải biến môi trường từ file .env
load_dotenv()

# Cấu hình thông tin từ biến môi trường
WEBSITE_URL = os.getenv('WEBSITE_URL', 'https://shalom.vn/')
EMAIL_SENDER = os.getenv('EMAIL_SENDER', 'website_monitor@cms.neko-it.site')
EMAIL_RECEIVER = os.getenv('EMAIL_RECEIVER', 'nhannt200823@gmail.com')
SENDGRID_API_KEY = os.getenv('SENDGRID_API_KEY')
CHECK_INTERVAL = int(os.getenv('CHECK_INTERVAL', '3600'))

# Kiểm tra xem API key có được cung cấp không
if not SENDGRID_API_KEY:
    print(f"[{datetime.now()}] Lỗi: SENDGRID_API_KEY không được tìm thấy trong biến môi trường", file=sys.stderr)
    sys.exit(1)

# Định nghĩa các mức độ lỗi


class ErrorLevel:
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


last_status = None
error_count = 0  # Đếm số lần lỗi liên tiếp


def classify_error(status_code=None, exception=None):
    """
    Phân loại mức độ lỗi dựa trên status code hoặc exception
    """
    if exception:
        # Phân loại theo loại exception
        if isinstance(exception, requests.exceptions.Timeout):
            return ErrorLevel.WARNING, f"Timeout: Không thể kết nối trong 30 giây - {str(exception)}"
        elif isinstance(exception, requests.exceptions.ConnectionError):
            return ErrorLevel.ERROR, f"Connection Error: Không thể kết nối tới server - {str(exception)}"
        elif isinstance(exception, requests.exceptions.HTTPError):
            return ErrorLevel.ERROR, f"HTTP Error: Lỗi HTTP - {str(exception)}"
        elif isinstance(exception, requests.exceptions.RequestException):
            return ErrorLevel.WARNING, f"Request Exception: {str(exception)}"
        else:
            return ErrorLevel.ERROR, f"Unknown Exception: {str(exception)}"

    if status_code:
        # Phân loại theo HTTP status code
        if 200 <= status_code < 300:
            return ErrorLevel.INFO, f"Website hoạt động bình thường (Status: {status_code})"
        elif 300 <= status_code < 400:
            return ErrorLevel.WARNING, f"Redirect: Website chuyển hướng (Status: {status_code})"
        elif status_code == 404:
            return ErrorLevel.WARNING, f"Page Not Found: Trang không tồn tại (Status: {status_code})"
        elif 400 <= status_code < 500:
            return ErrorLevel.ERROR, f"Client Error: Lỗi phía client (Status: {status_code})"
        elif 500 <= status_code < 600:
            return ErrorLevel.CRITICAL, f"Server Error: Lỗi phía server (Status: {status_code})"
        else:
            return ErrorLevel.WARNING, f"Unknown Status Code: {status_code}"

    return ErrorLevel.ERROR, "Unknown error occurred"


def should_send_email(error_level):
    """
    Quyết định có nên gửi email hay không dựa trên mức độ lỗi
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
            f"[{datetime.now()}] Gửi Email thành công: {subject} (Status: {response.status_code})")
        return True
    except Exception as e:
        print(f"[{datetime.now()}] Lỗi khi gửi email: {e}", file=sys.stderr)
        return False


def check_website():
    """
    Kiểm tra website và trả về thông tin chi tiết về trạng thái
    """
    global error_count

    try:
        print(f"[{datetime.now()}] Kiểm tra website {WEBSITE_URL}")
        response = requests.get(WEBSITE_URL, timeout=30)

        error_level, message = classify_error(status_code=response.status_code)

        if error_level == ErrorLevel.INFO:
            print(f"[{datetime.now()}] {error_level}: {message}")
            error_count = 0  # Reset counter khi website hoạt động bình thường
            return True, error_level, message
        else:
            print(f"[{datetime.now()}] {error_level}: {message}")
            error_count += 1
            return False, error_level, message

    except requests.exceptions.RequestException as e:
        error_level, message = classify_error(exception=e)
        print(f"[{datetime.now()}] {error_level}: {message}", file=sys.stderr)
        error_count += 1
        return False, error_level, message


def format_email_body(error_level, message, error_count):
    """
    Tạo nội dung email chi tiết
    """
    body = f"""
Cảnh báo từ hệ thống giám sát website:

Thời gian: {datetime.now()}
Mức độ lỗi: {error_level}
Chi tiết lỗi: {message}
Số lần lỗi liên tiếp: {error_count}
---
Thông tin bổ sung:
- Script sẽ tiếp tục kiểm tra mỗi {CHECK_INTERVAL} giây
- Email được gửi khi có lỗi mức WARNING, ERROR hoặc CRITICAL
- Cần kiểm tra ngay lập tức nếu đây là lỗi CRITICAL
- Vui lòng kiểm tra website và server của bạn.
    """
    return body.strip()


if __name__ == "__main__":
    last_status = None
    error_count = 0
    print(f"[{datetime.now()}] Bắt đầu giám sát website {WEBSITE_URL}")
    print(f"[{datetime.now()}] Kiểm tra mỗi {CHECK_INTERVAL} giây")
    print(
        f"[{datetime.now()}] Email được gửi khi có lỗi mức WARNING, ERROR hoặc CRITICAL")

    while True:
        try:
            is_up, error_level, message = check_website()

            if is_up:
                # Website hoạt động bình thường
                if last_status is not None and not last_status:
                    # Website từ DOWN chuyển sang UP
                    subject = f"✅ Website {WEBSITE_URL} is BACK UP"
                    body = format_email_body(
                        ErrorLevel.INFO, "Website đã hoạt động trở lại", 0)
                    send_email(subject, body)
                    print(
                        f"[{datetime.now()}] Website đã phục hồi - đã gửi email thông báo")
                else:
                    print(
                        f"[{datetime.now()}] Website vẫn đang hoạt động bình thường - không gửi email")
            else:
                # Website có vấn đề
                if should_send_email(error_level):
                    # Gửi email cho WARNING, ERROR hoặc CRITICAL
                    if error_level == ErrorLevel.CRITICAL:
                        subject = f"🔴 CRITICAL - Website {WEBSITE_URL} is DOWN"
                    elif error_level == ErrorLevel.ERROR:
                        subject = f"⚠️ ERROR - Website {WEBSITE_URL} has issues"
                    else:  # WARNING
                        subject = f"⚠️ WARNING - Website {WEBSITE_URL} has issues"

                    body = format_email_body(error_level, message, error_count)

                    # Gửi email ngay lập tức cho lỗi CRITICAL, hoặc sau 2 lần lỗi WARNING/ERROR liên tiếp
                    if error_level == ErrorLevel.CRITICAL or error_count >= 2:
                        send_email(subject, body)
                        print(
                            f"[{datetime.now()}] Đã gửi email cảnh báo: {error_level}")
                    else:
                        print(
                            f"[{datetime.now()}] Lỗi {error_level} - chưa gửi email (lần {error_count}/2)")
                else:
                    # INFO level - chỉ log, không gửi email
                    print(
                        f"[{datetime.now()}] {error_level}: {message} - không gửi email")

            last_status = is_up
            print(
                f"[{datetime.now()}] Đợi {CHECK_INTERVAL} giây trước khi kiểm tra tiếp")
            time.sleep(CHECK_INTERVAL)

        except KeyboardInterrupt:
            print(f"[{datetime.now()}] Script dừng bởi người dùng")
            sys.exit(0)
        except Exception as e:
            print(
                f"[{datetime.now()}] Lỗi không xác định trong vòng lặp chính: {e}", file=sys.stderr)
            time.sleep(CHECK_INTERVAL)
