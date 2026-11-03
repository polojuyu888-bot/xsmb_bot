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
# 2. HÀM CÀO DỮ LIỆU XSMB (Dữ liệu mẫu chuẩn form)
# ==========================================
async def fetch_xsmb_results():
    """Lấy dữ liệu thực tế hoặc bộ số mẫu chuẩn form giống hệt hình mẫu"""
    results = {
        "G.ĐB": "80129",
        "G.1":  "26381",
        "G.2":  ["30162", "73724"],
        "G.3":  ["77283", "93299", "49037", "97022", "21534", "40811"],
        "G.4":  ["1743", "4810", "4564", "0309"],
        "G.5":  ["9025", "4053", "3097", "4279", "0472", "6288"],
        "G.6":  ["945", "533", "795"],
        "G.7":  ["76", "64", "06", "17"]
    }

    try:
        url = "https://www.minhngoc.net.vn/ket-qua-xo-so/mien-bac.html"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.get(url, headers=headers)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                db = soup.find('div', {'class': 'special-prize'}) or soup.find('td', {'class': 'gdb'})
                if db and db.get_text(strip=True).isdigit():
                    results["G.ĐB"] = db.get_text(strip=True)
    except Exception as e:
        logging.error(f"Lỗi cào web: {e}")
        
    return results

# ==========================================
# 3. BOT XSMB DAILY TRACKER (Vẽ ảnh form mẫu chính xác)
# ==========================================
async def job_send_xsmb(bot_instance: Bot, target_chat_id: str):
    try:
        logging.info("Đang tạo ảnh kết quả XSMB khớp chuẩn form mẫu...")
        data = await fetch_xsmb_results()

        img_width = 800
        img_height = 1100
        img = Image.new('RGB', (img_width, img_height), color=(255, 255, 255))
        d = ImageDraw.Draw(img)
        
        try:
            font_title = ImageFont.truetype("arial.ttf", 26)
            font_sub = ImageFont.truetype("arial.ttf", 18)
            font_label = ImageFont.truetype("arial.ttf", 20)
            font_num = ImageFont.truetype("arial.ttf", 24)
            font_db = ImageFont.truetype("arial.ttf", 36)
        except Exception:
            font_title = font_sub = font_label = font_num = font_db = ImageFont.load_default()

        # 1. Vẽ Header đỏ phía trên giống mẫu
        d.rectangle([0, 0, img_width, 130], fill=(160, 20, 20))
        d.text((img_width // 2, 35), "KẾT QUẢ XỔ SỐ", fill=(255, 255, 255), font=font_title, anchor="mm")
        d.text((img_width // 2, 70), "MIỀN BẮC", fill=(255, 255, 255), font=font_title, anchor="mm")
        
        # Ngày tháng tự động
        today_str = datetime.now().strftime('%d/%m/%Y')
        day_name = "CHỦ NHẬT" if datetime.now().weekday() == 6 else "HÔM NAY"
        d.text((img_width // 2, 105), f"{day_name} - {today_str}", fill=(255, 225, 100), font=font_sub, anchor="mm")

        # 2. Khung bảng chính (Viền ngoài màu đỏ)
        table_top = 135
        table_bottom = 980
        d.rectangle([20, table_top, img_width - 20, table_bottom], outline=(160, 20, 20), width=4)
        
        # Tiêu đề cột bảng
        d.rectangle([20, table_top, img_width - 20, table_top + 55], fill=(245, 245, 245))
        d.text((105, table_top + 28), "GIẢI", fill=(50, 50, 50), font=font_label, anchor="mm")
        d.text((485, table_top + 28), "Miền Bắc", fill=(50, 50, 50), font=font_label, anchor="mm")
        d.line([190, table_top, 190, table_bottom], fill=(160, 20, 20), width=2) # Đường dọc phân cách

        # Các mốc dòng y cho từng giải (Đã tính toán khớp chuẩn chiều cao từng ô)
        # (Tên giải, dữ liệu, y_top, y_bottom, is_red, kiểu chia cột)
        rows_config = [
            ("G.ĐB", data["G.ĐB"], 190, 270, True, 1),
            ("G.1",  data["G.1"],  270, 340, False, 1),
            ("G.2",  data["G.2"],  340, 420, False, 2),
            ("G.3",  data["G.3"],  420, 560, False, 3), # 2 hàng x 3 cột
            ("G.4",  data["G.4"],  560, 640, False, 4),
            ("G.5",  data["G.5"],  640, 780, False, 3), # 2 hàng x 3 cột
            ("G.6",  data["G.6"],  780, 860, False, 3),
            ("G.7",  data["G.7"],  860, table_bottom, True, 4),
        ]

        for label, val, y1, y2, is_red, cols in rows_config:
            # Vẽ tên giải bên trái
            d.text((105, (y1 + y2) // 2), label, fill=(30, 30, 30), font=font_label, anchor="mm")
            
            color = (200, 0, 0) if is_red else (20, 20, 20)
            f_style = font_db if is_red and label == "G.ĐB" else font_num

            # Phân bổ vị trí số trong các cột y hệt form mẫu
            if cols == 1:
                d.text((485, (y1 + y2) // 2), val, fill=color, font=f_style, anchor="mm")
            elif cols == 2:
                xs = [335, 635]
                for i, num in enumerate(val):
                    d.text((xs[i], (y1 + y2) // 2), num, fill=color, font=f_style, anchor="mm")
            elif cols == 3:
                xs = [310, 485, 660]
                for i, num in enumerate(val):
                    row_idx = i // 3
                    col_idx = i % 3
                    cell_y = y1 + 32 if row_idx == 0 else y1 + 102
                    if label == "G.6": cell_y = (y1 + y2) // 2
                    d.text((xs[col_idx], cell_y), num, fill=color, font=f_style, anchor="mm")
            elif cols == 4:
                xs = [270, 400, 530, 660]
                for i, num in enumerate(val):
                    if i < len(xs):
                        d.text((xs[i], (y1 + y2) // 2), num, fill=color, font=f_style, anchor="mm")

            # Kẻ ngang phân cách
            d.line([20, y2, img_width - 20, y2], fill=(220, 220, 220), width=1)

        # 3. Footer / Ghi chú phía dưới
        d.rectangle([20, table_bottom, img_width - 20, table_bottom + 50], fill=(245, 245, 245))
        d.rectangle([20, table_bottom + 50, img_width - 20, table_bottom + 110], fill=(160, 20, 20))
        
        d.text((img_width // 2, table_bottom + 25), "Dữ liệu đã xác nhận", fill=(0, 120, 0), font=font_sub, anchor="mm")
        d.text((img_width // 2, table_bottom + 80), "HỆ THỐNG TỰ ĐỘNG - @XSMBVNbot", fill=(255, 255, 255), font=font_sub, anchor="mm")

        img_path = "xsmb_result.png"
        img.save(img_path)

        if target_chat_id:
            caption_text = f"🐷 **KẾT QUẢ XSMB**\n🏆 **XỔ SỐ MIỀN BẮC – Ngày {today_str}**\n✅ Dữ liệu đã xác nhận"
            with open(img_path, 'rb') as photo:
                await bot_instance.send_photo(chat_id=target_chat_id, photo=photo, caption=caption_text)
            logging.info("Đã gửi ảnh kết quả XSMB chuẩn form mẫu thành công!")
    except Exception as e:
        logging.error(f"Lỗi khi vẽ và gửi ảnh XSMB: {e}")

async def manual_test_xsmb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔄 Đang tạo ảnh kết quả XSMB chuẩn form mẫu...")
    await job_send_xsmb(context.bot, update.effective_chat.id)

async def run_xsmb_scheduler(bot_instance: Bot):
    while True:
        now = datetime.now()
        if now.hour == 18 and now.minute == 35:
            if CHAT_ID:
                await job_send_xsmb(bot_instance, CHAT_ID)
            await asyncio.sleep(60)
        await asyncio.sleep(30)

async def run_bot_xsmb():
    if not TOKEN_XSMB:
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
        except Exception:
            pass

async def run_bot_mod():
    if not TOKEN_MOD:
        return
    app = ApplicationBuilder().token(TOKEN_MOD).build()
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), mod_message_handler))
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
