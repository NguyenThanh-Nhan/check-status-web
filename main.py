import requests
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from datetime import datetime
import time
import sys
import os
from dotenv import load_dotenv

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

last_status = None


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
    try:
        print(f"[{datetime.now()}] Kiểm tra website {WEBSITE_URL}")
        response = requests.get(WEBSITE_URL, timeout=10)
        if response.status_code == 200:
            print(
                f"[{datetime.now()}] Website {WEBSITE_URL} is UP (Status: {response.status_code})")
            return True
        else:
            print(
                f"[{datetime.now()}] Website {WEBSITE_URL} is DOWN (Status: {response.status_code})")
            return False
    except requests.exceptions.RequestException as e:
        print(
            f"[{datetime.now()}] Website {WEBSITE_URL} is DOWN (Error: {e})", file=sys.stderr)
        return False


if __name__ == "__main__":
    last_status = None  # Khởi tạo trạng thái ban đầu
    print(f"[{datetime.now()}] Bắt đầu giám sát website {WEBSITE_URL}")
    print(f"[{datetime.now()}] Kiểm tra mỗi {CHECK_INTERVAL} giây")

    while True:
        try:
            is_up = check_website()
            if is_up:
                if last_status is not None and not last_status:
                    # Gửi email khi website từ DOWN chuyển sang UP
                    subject = f"Website {WEBSITE_URL} is BACK UP"
                    body = f"Website {WEBSITE_URL} is back up at {datetime.now()}."
                    send_email(subject, body)
                else:
                    print(
                        f"[{datetime.now()}] Website vẫn đang hoạt động - không gửi email.")
            else:
                # Gửi email mỗi khi website DOWN, bất kể trạng thái trước đó
                subject = f"Website {WEBSITE_URL} is DOWN"
                body = f"Website của bạn đã ngừng hoạt động vào lúc {datetime.now()}. Please check!"
                send_email(subject, body)
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
