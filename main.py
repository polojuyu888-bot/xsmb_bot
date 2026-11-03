import os
import asyncio
import logging
from datetime import datetime
import httpx
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont
from fastapi import FastAPI
import uvicorn
from telegram import Bot, Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
from apscheduler.schedulers.asyncio import AsyncScheduler

# Cấu hình logging
logging.basicConfig(level=logging.INFO)

# Lấy các Token từ biến môi trường trên Render
TOKEN_TAIVU = os.getenv("9101852807:AAEAVBFPIVaLMKQPMZZDbMHehww51YaRScM")       # Bot 1: Tài vụ / Thống kê nạp rút
TOKEN_XSMB = os.getenv("9271618928:AAHF4QGDouZKdEkoYcG9n0TJC4XIpacyJZY")         # Bot 2: Xổ số Miền Bắc hằng ngày
TOKEN_MOD = os.getenv("9044201612:AAH0ev-9LXL9Pxs3QhO-ySAl4QJJSWrJZr8")           # Bot 3: Quản lý, chống spam & Captcha
CHAT_ID = os.getenv("CHAT_ID")                   # Nhóm Telegram chung

# ==========================================
# 1. BOT TÀI VỤ (Thống kê nạp rút, minh bạch điểm)
# ==========================================
async def run_bot_taivu():
    if not TOKEN_TAIVU:
        logging.warning("Chưa cấu hình BOT_TOKEN_TAIVU, bỏ qua Bot 1.")
        return
    app = ApplicationBuilder().token(TOKEN_TAIVU).build()
    # Thêm các handler xử lý lệnh nạp/rút điểm của người chơi ở đây
    logging.info("Bot 1 (Tài vụ) đang chạy...")
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    while True:
        await asyncio.sleep(3600)

# ==========================================
# 2. BOT XSMB DAILY TRACKER (Gửi lúc 18:35 hàng ngày)
# ==========================================
async def job_send_xsmb():
    if not TOKEN_XSMB or not CHAT_ID:
        return
    bot = Bot(token=TOKEN_XSMB)
    logging.info("Đang thực hiện cào dữ liệu và tạo ảnh kết quả XSMB...")
    # (Đưa logic cào web, dùng Pillow vẽ ảnh với font arial.ttf vào đây)
    # Sau đó dùng: await bot.send_photo(chat_id=CHAT_ID, photo=..., caption="Kết quả XSMB...")

async def run_xsmb_scheduler():
    if not TOKEN_XSMB:
        logging.warning("Chưa cấu hình BOT_TOKEN_XSMB, bỏ qua Bot XSMB.")
        return
    scheduler = AsyncScheduler()
    # Đặt lịch chạy lúc 18:35 hàng ngày (11:35 UTC)
    @scheduler.scheduled_job('cron', hour=11, minute=35)
    async def scheduled_task():
        await job_send_xsmb()
        
    scheduler.start()
    logging.info("Bot 2 (XSMB Scheduler) đang chạy ngầm...")
    while True:
        await asyncio.sleep(3600)

# ==========================================
# 3. BOT QUẢN LÝ / CHỐNG SPAM & CAPTCHA
# ==========================================
async def mod_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message or not message.text:
        return
    # Logic kiểm tra link rác, từ khóa spam hoặc xác thực thành viên mới
    if "http" in message.text.lower() or "t.me" in message.text.lower():
        try:
            await message.delete()
            logging.info("Đã lọc và xóa tin nhắn spam.")
        except Exception as e:
            logging.error(f"Lỗi xóa tin nhắn: {e}")

async def run_bot_mod():
    if not TOKEN_MOD:
        logging.warning("Chưa cấu hình BOT_TOKEN_MOD, bỏ qua Bot 3.")
        return
    app = ApplicationBuilder().token(TOKEN_MOD).build()
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), mod_message_handler))
    logging.info("Bot 3 (Quản lý / Chống spam) đang chạy...")
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    while True:
        await asyncio.sleep(3600)

# ==========================================
# 4. BOT DỰ BỊ (Chưa kích hoạt)
# ==========================================
# Bot số 4 hiện tại chưa cần chạy, khi nào cần bạn có thể bổ sung code vào đây.

# ==========================================
# WEB SERVICE (Giúp Render mở cổng duy trì 24/7)
# ==========================================
api_app = FastAPI()

@api_app.get("/")
def health_check():
    return {"status": "Hệ thống 4 con bot đang hoạt động ổn định!"}

async def run_fastapi_server():
    config = uvicorn.Config(api_app, host="0.0.0.0", port=10000, log_level="info")
    server = uvicorn.Server(config)
    logging.info("Web Service đang chạy trên cổng 10000...")
    await server.serve()

# ==========================================
# HÀM CHÍNH: GỘP VÀ CHẠY SONG SONG TẤT CẢ
# ==========================================
async def main():
    await asyncio.gather(
        run_fastapi_server(),
        run_bot_taivu(),
        run_xsmb_scheduler(),
        run_bot_mod()
    )

if __name__ == "__main__":
    asyncio.run(main())