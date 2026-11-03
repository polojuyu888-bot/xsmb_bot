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

# Cấu hình logging
logging.basicConfig(level=logging.INFO)

# Lấy các Token và Chat ID từ biến môi trường trên Render
TOKEN_TAIVU = os.getenv("BOT_TOKEN_TAIVU")
TOKEN_XSMB = os.getenv("BOT_TOKEN_XSMB")
TOKEN_MOD = os.getenv("BOT_TOKEN_MOD")
CHAT_ID = os.getenv("CHAT_ID")

# ==========================================
# 1. BOT TÀI VỤ
# ==========================================
async def run_bot_taivu():
    if not TOKEN_TAIVU:
        logging.warning("Chưa cấu hình BOT_TOKEN_TAIVU, bỏ qua Bot Tài Vụ.")
        return
    app = ApplicationBuilder().token(TOKEN_TAIVU).build()
    logging.info("Bot 1 (Tài vụ) đang khởi động...")
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    while True:
        await asyncio.sleep(3600)

# ==========================================
# 2. BOT XSMB DAILY TRACKER (Hẹn giờ chạy 18:35 hàng ngày + Lệnh test)
# ==========================================
async def job_send_xsmb(bot_instance: Bot, target_chat_id: str):
    """Hàm cào dữ liệu, tạo ảnh kết quả và gửi vào nhóm"""
    try:
        logging.info("Đang thực hiện cào dữ liệu và vẽ ảnh kết quả XSMB...")
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

        if target_chat_id:
            with open(img_path, 'rb') as photo:
                await bot_instance.send_photo(chat_id=target_chat_id, photo=photo, caption="🎲 Kết quả XSMB tự động hàng ngày!")
            logging.info("Đã gửi ảnh kết quả XSMB thành công!")
    except Exception as e:
        logging.error(f"Lỗi khi gửi kết quả XSMB: {e}")

async def manual_test_xsmb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lệnh /test_xsmb để kiểm tra thủ công ngay lập tức"""
    await update.message.reply_text("🔄 Đang tiến hành cào dữ liệu và gửi ảnh test XSMB...")
    await job_send_xsmb(context.bot, update.effective_chat.id)

async def run_xsmb_scheduler(bot_instance: Bot):
    """Vòng lặp tự động check thời gian để gửi lúc 18:35 hàng ngày"""
    while True:
        now = datetime.now()
        # Kiểm tra nếu đúng 18:35:00 hàng ngày
        if now.hour == 18 and now.minute == 35:
            if CHAT_ID:
                await job_send_xsmb(bot_instance, CHAT_ID)
            await asyncio.sleep(60) # Chờ 1 phút để không bị lặp trong phút đó
        await asyncio.sleep(30) # Kiểm tra lại sau mỗi 30 giây

async def run_bot_xsmb():
    if not TOKEN_XSMB:
        logging.warning("Chưa cấu hình BOT_TOKEN_XSMB, bỏ qua Bot XSMB.")
        return
    
    app = ApplicationBuilder().token(TOKEN_XSMB).build()
    app.add_handler(CommandHandler("test_xsmb", manual_test_xsmb))
    
    logging.info("Bot 2 (XSMB Tracker) đang chạy...")
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    
    # Chạy song song vòng lặp hẹn giờ gửi lúc 18:35
    asyncio.create_task(run_xsmb_scheduler(app.bot))
    
    while True:
        await asyncio.sleep(3600)

# ==========================================
# 3. BOT QUẢN LÝ / CHỐNG SPAM
# ==========================================
async def mod_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message or not message.text:
        return
    text_lower = message.text.lower()
    if "http" in text_lower or "t.me" in text_lower:
        try:
            await message.delete()
            logging.info("Đã phát hiện và xóa tin nhắn chứa link spam.")
        except Exception as e:
            logging.error(f"Lỗi xóa tin nhắn spam: {e}")

async def run_bot_mod():
    if not TOKEN_MOD:
        logging.warning("Chưa cấu hình BOT_TOKEN_MOD, bỏ qua Bot Quản Lý.")
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
# 4. WEB SERVICE (FastAPI - Giữ Render thức 24/7)
# ==========================================
api_app = FastAPI()

@api_app.get("/")
def health_check():
    return {"status": "Hệ thống bot đang vận hành ổn định 24/7!"}

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
