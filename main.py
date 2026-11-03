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
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters, ContextTypes
from apscheduler.schedulers.asyncio import AsyncScheduler

# Cấu hình logging
logging.basicConfig(level=logging.INFO)

# Lấy các Token và Chat ID từ biến môi trường trên Render
TOKEN_TAIVU = os.getenv("BOT_TOKEN_TAIVU")       # Bot 1: Tài vụ / Thống kê nạp rút
TOKEN_XSMB = os.getenv("BOT_TOKEN_XSMB")         # Bot 2: Xổ số Miền Bắc hằng ngày
TOKEN_MOD = os.getenv("BOT_TOKEN_MOD")           # Bot 3: Quản lý, chống spam & Captcha
CHAT_ID = os.getenv("CHAT_ID")                   # Nhóm Telegram chung

# ==========================================
# 1. BOT TÀI VỤ (Thống kê nạp rút, minh bạch điểm)
# ==========================================
async def run_bot_taivu():
    if not TOKEN_TAIVU:
        logging.warning("Chưa cấu hình BOT_TOKEN_TAIVU, bỏ qua Bot Tài Vụ.")
        return
    app = ApplicationBuilder().token(TOKEN_TAIVU).build()
    
    # Thêm các Handler cho Bot tài vụ ở đây (ví dụ: lệnh nạp/rút điểm)
    
    logging.info("Bot 1 (Tài vụ) đang khởi động...")
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    while True:
        await asyncio.sleep(3600)

# ==========================================
# 2. BOT XSMB DAILY TRACKER (Gửi lúc 18:35 hàng ngày + Lệnh test)
# ==========================================
async def job_send_xsmb(bot_instance: Bot, target_chat_id: str):
    """Hàm cào dữ liệu, tạo ảnh kết quả và gửi vào nhóm"""
    try:
        logging.info("Đang thực hiện cào dữ liệu và vẽ ảnh kết quả XSMB...")
        
        # --- LOGIC CÀO DỮ LIỆU & VẼ ẢNH VỚI PILOW & arial.ttf ---
        # (Ví dụ tạo một ảnh thông báo đơn giản, hoặc code vẽ kết quả chi tiết của bạn)
        img = Image.new('RGB', (800, 600), color=(255, 255, 255))
        d = ImageDraw.Draw(img)
        
        try:
            font = ImageFont.truetype("arial.ttf", 24)
            font_bold = ImageFont.truetype("arial.ttf", 32)
        except Exception:
            font = ImageFont.load_default()
            font_bold = font

        d.text((50, 40), "KẾT QUẢ XỔ SỐ MIỀN BẮC", fill=(255, 0, 0), font=font_bold)
        d.text((50, 100), f"Ngày cập nhật: {datetime.now().strftime('%d/%m/%Y')}", fill=(0, 0, 0), font=font)
        d.text((50, 160), "Đặc biệt: [Đang cập nhật từ hệ thống]", fill=(0, 0, 255), font=font)
        
        img_path = "xsmb_result.png"
        img.save(img_path)

        # Gửi ảnh vào nhóm Telegram
        if target_chat_id:
            with open(img_path, 'rb') as photo:
                await bot_instance.send_photo(chat_id=target_chat_id, photo=photo, caption="🎲 Kết quả XSMB tự động hàng ngày!")
            logging.info("Đã gửi ảnh kết quả XSMB thành công!")
    except Exception as e:
        logging.error(f"Lỗi khi gửi kết quả XSMB: {e}")

async def manual_test_xsmb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lệnh /test_xsmb để kiểm tra thủ công ngay lập tức"""
    await update.message.reply_text("🔄 Đang tiến hành cào dữ liệu và gửi ảnh test XSMB...")
    bot_instance = context.bot
    target_chat = update.effective_chat.id
    await job_send_xsmb(bot_instance, target_chat)

async def run_bot_xsmb():
    if not TOKEN_XSMB:
        logging.warning("Chưa cấu hình BOT_TOKEN_XSMB, bỏ qua Bot XSMB.")
        return
    
    app = ApplicationBuilder().token(TOKEN_XSMB).build()
    # Đăng ký lệnh test nhanh qua chat
    app.add_handler(CommandHandler("test_xsmb", manual_test_xsmb))

    # Cấu hình lịch trình tự động chạy lúc 18:35 hàng ngày (11:35 UTC)
    scheduler = AsyncScheduler()
    @scheduler.scheduled_job('cron', hour=11, minute=35)
    async def scheduled_task():
        if CHAT_ID:
            bot_inst = Bot(token=TOKEN_XSMB)
            await job_send_xsmb(bot_inst, CHAT_ID)
            
    scheduler.start()
    logging.info("Bot 2 (XSMB Tracker & Scheduler) đang chạy...")
    
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    while True:
        await asyncio.sleep(3600)

# ==========================================
# 3. BOT QUẢN LÝ / CHỐNG SPAM & CAPTCHA
# ==========================================
async def mod_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message or not message.text:
        return
    
    # Logic kiểm tra link rác hoặc từ khóa spam
    text_lower = message.text.lower()
    if "http" in text_lower or "t.me" in text_lower:
        try:
            await message.delete()
            logging.info("Đã phát hiện và xóa tin nhắn chứa link spam.")
        except Exception as e:
            logging.error(f"Không thể xóa tin nhắn spam (có thể bot thiếu quyền Admin): {e}")

async def run_bot_mod():
    if not TOKEN_MOD:
        logging.warning("Chưa cấu hình BOT_TOKEN_MOD, bỏ qua Bot Quản Lý.")
        return
    
    app = ApplicationBuilder().token(TOKEN_MOD).build()
    # Lọc tất cả tin nhắn văn bản không phải là lệnh
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), mod_message_handler))
    
    logging.info("Bot 3 (Quản lý / Chống spam) đang chạy...")
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    while True:
        await asyncio.sleep(3600)

# ==========================================
# 4. WEB SERVICE (FastAPI - Giữ Render thức 24/7)
# ==========================================
api_app = FastAPI()

@api_app.get("/")
def health_check():
    return {"status": "Hệ thống 4 con bot đang vận hành ổn định 24/7!"}

async def run_fastapi_server():
    config = uvicorn.Config(api_app, host="0.0.0.0", port=10000, log_level="info")
    server = uvicorn.Server(config)
    logging.info("Web Service (FastAPI) đang mở cổng 10000...")
    await server.serve()

# ==========================================
# HÀM CHÍNH: CHẠY SONG SONG TẤT CẢ TIẾN TRÌNH
# ==========================================
async def main():
    await asyncio.gather(
        run_fastapi_server(),
        run_bot_taivu(),
        run_bot_xsmb(),
        run_bot_mod()
    )

if __name__ == "__main__":
    asyncio.run(main())
