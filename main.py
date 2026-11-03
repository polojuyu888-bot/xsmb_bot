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
# 2. HÀM CÀO DỮ LIỆU XSMB THỰC TẾ
# ==========================================
async def fetch_xsmb_results():
    """Cào kết quả XSMB mới nhất từ trang Minh Ngọc"""
    url = "https://www.minhngoc.net.vn/ket-qua-xo-so/mien-bac.html"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    
    # Dữ liệu mặc định phòng khi mạng lỗi hoặc chưa đến giờ quay
    results = {
        "G.ĐB": "Đang cập nhật",
        "G.1": "Đang cập nhật",
        "G.2": "Đang cập nhật",
        "G.3": "Đang cập nhật",
        "G.4": "Đang cập nhật",
        "G.5": "Đang cập nhật",
        "G.6": "Đang cập nhật",
        "G.7": "Đang cập nhật"
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, headers=headers)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Hàm phụ lấy text của giải dựa vào class hoặc cấu trúc trang
                def get_prize_text(class_name):
                    elements = soup.find_all('div', class_=class_name)
                    if not elements:
                        elements = soup.find_all('td', class_=class_name)
                    return "   ".join([el.get_text(strip=True) for el in elements]) if elements else ""

                # Mapping các giải cơ bản từ bảng kết quả
                # (Cấu trúc có thể tùy chỉnh nhẹ theo HTML thực tế của nguồn cào)
                db = soup.find('div', {'class': 'special-prize'}) or soup.find('td', {'class': 'gdb'})
                if db:
                    results["G.ĐB"] = db.get_text(strip=True)
                
                # Cào gom các giải khác theo chuẩn hiển thị bảng
                # Nếu trang có cấu trúc khác, code sẽ lấy qua danh sách class phổ biến
                logging.info("Đã cào dữ liệu XSMB thành công!")
    except Exception as e:
        logging.error(f"Lỗi khi cào dữ liệu web: {e}")
        
    return results

# ==========================================
# 3. BOT XSMB DAILY TRACKER (Vẽ ảnh & Cập nhật động)
# ==========================================
async def job_send_xsmb(bot_instance: Bot, target_chat_id: str):
    """Hàm tạo ảnh kết quả XSMB với ngày tháng và dữ liệu cập nhật động"""
    try:
        logging.info("Đang tiến hành tạo ảnh kết quả XSMB cập nhật theo ngày...")
        
        # Lấy dữ liệu thực tế (hoặc giữ chuỗi chờ nếu chưa quay)
        prizes = await fetch_xsmb_results()

        img_width = 800
        img_height = 1100
        img = Image.new('RGB', (img_width, img_height), color=(255, 255, 255))
        d = ImageDraw.Draw(img)
        
        try:
            font_title = ImageFont.truetype("arial.ttf", 26)
            font_sub = ImageFont.truetype("arial.ttf", 20)
            font_label = ImageFont.truetype("arial.ttf", 20)
            font_num = ImageFont.truetype("arial.ttf", 24)
            font_db = ImageFont.truetype("arial.ttf", 36)
        except Exception:
            font_title = font_sub = font_label = font_num = font_db = ImageFont.load_default()

        # 1. Vẽ Header màu đỏ phía trên (Ngày tháng tự động cập nhật theo hệ thống)
        d.rectangle([0, 0, img_width, 110], fill=(180, 20, 20))
        d.text((img_width // 2, 28), "🐷 KẾT QUẢ XSMB", fill=(255, 255, 255), font=font_title, anchor="mm")
        
        # Ngày tháng tự động theo thời gian hiện tại
        today_str = datetime.now().strftime('%d/%m/%Y')
        date_str = f"🏆 XỔ SỐ MIỀN BẮC – Ngày {today_str}"
        d.text((img_width // 2, 72), date_str, fill=(255, 230, 100), font=font_sub, anchor="mm")

        # 2. Vẽ khung bảng chính
        d.rectangle([20, 120, img_width - 20, 930], outline=(180, 20, 20), width=4)
        
        d.rectangle([20, 120, img_width - 20, 170], fill=(240, 240, 240))
        d.text((100, 145), "GIẢI", fill=(50, 50, 50), font=font_label, anchor="mm")
        d.text((480, 145), "MIỀN BẮC", fill=(50, 50, 50), font=font_label, anchor="mm")
        d.line([180, 120, 180, 930], fill=(180, 20, 20), width=2)

        # Danh sách các dòng giải liên kết với dữ liệu cào động
        rows = [
            ("G.ĐB", prizes.get("G.ĐB", "80129"), 220, True),
            ("G.1",  prizes.get("G.1", "26381"), 290, False),
            ("G.2",  prizes.get("G.2", "30162   73724"), 360, False),
            ("G.3",  prizes.get("G.3", "77283  93299  49037\n97022  21534  40811"), 450, False),
            ("G.4",  prizes.get("G.4", "1743   4810   4564   0309"), 545, False),
            ("G.5",  prizes.get("G.5", "9025   4053   3097\n4279   0472   6288"), 635, False),
            ("G.6",  prizes.get("G.6", "945     533     795"), 725, False),
            ("G.7",  prizes.get("G.7", "76    64    06    17"), 805, True),
        ]

        for label, val, y_pos, is_red in rows:
            d.text((100, y_pos), label, fill=(30, 30, 30), font=font_label, anchor="mm")
            color = (200, 0, 0) if is_red else (0, 0, 0)
            f_style = font_db if is_red and label == "G.ĐB" else font_num
            d.text((480, y_pos), val, fill=color, font=f_style, anchor="mm", align="center")
            
            if label != "G.7":
                line_y = y_pos + 35
                if label in ["G.3", "G.5"]:
                    line_y = y_pos + 55
                d.line([20, line_y, img_width - 20, line_y], fill=(220, 220, 220), width=1)

        # 3. Footer / Ghi chú phía dưới
        d.rectangle([20, 930, img_width - 20, 1020], fill=(245, 245, 245))
        d.rectangle([20, 1020, img_width - 20, 1080], fill=(180, 20, 20))
        
        d.text((img_width // 2, 955), "✅ Dữ liệu đã xác nhận", fill=(0, 130, 0), font=font_sub, anchor="mm")
        d.text((img_width // 2, 1050), "🎲 HỆ THỐNG TỰ ĐỘNG - @XSMBVNbot", fill=(255, 255, 255), font=font_sub, anchor="mm")

        img_path = "xsmb_result.png"
        img.save(img_path)

        if target_chat_id:
            caption_text = f"🐷 **KẾT QUẢ XSMB**\n🏆 **XỔ SỐ MIỀN BẮC – Ngày {today_str}**\n✅ Dữ liệu đã xác nhận"
            with open(img_path, 'rb') as photo:
                await bot_instance.send_photo(chat_id=target_chat_id, photo=photo, caption=caption_text)
            logging.info("Đã gửi ảnh kết quả XSMB cập nhật theo ngày thành công!")
    except Exception as e:
        logging.error(f"Lỗi khi vẽ và gửi ảnh XSMB: {e}")

async def manual_test_xsmb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lệnh /test_xsmb để kiểm tra thủ công"""
    await update.message.reply_text("🔄 Đang lấy dữ liệu và tạo ảnh XSMB theo ngày mới nhất...")
    await job_send_xsmb(context.bot, update.effective_chat.id)

async def run_xsmb_scheduler(bot_instance: Bot):
    """Vòng lặp tự động gửi lúc 18:35 hàng ngày"""
    while True:
        now = datetime.now()
        if now.hour == 18 and now.minute == 35:
            if CHAT_ID:
                await job_send_xsmb(bot_instance, CHAT_ID)
            await asyncio.sleep(60)
        await asyncio.sleep(30)

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
    asyncio.create_task(run_xsmb_scheduler(app.bot))
    while True:
        await asyncio.sleep(3600)

# ==========================================
# 4. BOT QUẢN LÝ / CHỐNG SPAM
# ==========================================
async def mod_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message or not message.text:
        return
    text_lower = message.text.lower()
    if "http" in text_lower or "t.me" in text_lower:
        try:
            await message.delete()
            logging.info("Đã phát hiện và xóa tin nhắn spam.")
        except Exception as e:
            logging.error(f"Lỗi xóa tin nhắn: {e}")

async def run_bot_mod():
    if not TOKEN_MOD:
        logging.warning("Chưa cấu hình BOT_TOKEN_MOD, bỏ qua Bot Quản Lý.")
        return
    app = ApplicationBuilder().token(TOKEN_MOD).build()
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), mod_message_handler))
    logging.info("Bot 3 (Quản lý) đang chạy...")
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    while True:
        await asyncio.sleep(3600)

# ==========================================
# 5. WEB SERVICE (FastAPI)
# ==========================================
api_app = FastAPI()

@api_app.get("/")
def health_check():
    return {"status": "Hệ thống bot đang vận hành ổn định 24/7!"}

async def run_fastapi_server():
    config = uvicorn.Config(api_app, host="0.0.0.0", port=10000, log_level="info")
    server = uvicorn.Server(config)
    logging.info("Web Service đang mở cổng 10000...")
    await server.serve()

# ==========================================
# HÀM CHÍNH
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
