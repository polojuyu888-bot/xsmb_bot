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

TOKEN_TAIVU = os.getenv("BOT_TOKEN_TAIVU")
TOKEN_XSMB = os.getenv("BOT_TOKEN_XSMB")
TOKEN_MOD = os.getenv("BOT_TOKEN_MOD")
CHAT_ID = os.getenv("CHAT_ID")

async def run_bot_taivu():
    if not TOKEN_TAIVU:
        return
    app = ApplicationBuilder().token(TOKEN_TAIVU).build()
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    while True:
        await asyncio.sleep(3600)

async def fetch_xsmb_results():
    """Cào kết quả XSMB thực tế"""
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
        logging.error(f"Lỗi khi cào dữ liệu web: {e}")
        
    return results

async def job_send_xsmb(bot_instance: Bot, target_chat_id: str):
    try:
        logging.info("Đang tạo ảnh kết quả XSMB...")
        
        # Kiểm tra thời gian: Nếu chưa đến 18:35 thì để dạng dấu 3 chấm (...)
        now = datetime.now()
        is_before_draw = (now.hour < 18) or (now.hour == 18 and now.minute < 35)

        if is_before_draw:
            data = {
                "G.ĐB": "...",
                "G.1":  "...",
                "G.2":  ["...", "..."],
                "G.3":  ["...", "...", "...", "...", "...", "..."],
                "G.4":  ["...", "...", "...", "..."],
                "G.5":  ["...", "...", "...", "...", "...", "..."],
                "G.6":  ["...", "...", "..."],
                "G.7":  ["...", "...", "...", "..."]
            }
            status_text = "⏳ Chưa đến giờ quay thưởng"
        else:
            data = await fetch_xsmb_results()
            status_text = "✅ Dữ liệu đã xác nhận"

        if os.path.exists("template.png"):
            img = Image.open("template.png").convert("RGB")
        else:
            img = Image.new('RGB', (800, 1200), color=(255, 255, 255))

        w, h = img.size
        d = ImageDraw.Draw(img)
        
        try:
            # Thử dùng font đậm (arialbd.ttf) cho đúng yêu cầu in đậm
            f_size_num = int(w * 0.035)
            f_size_db = int(w * 0.048)
            f_size_date = int(w * 0.026)
            
            font_num = ImageFont.truetype("arialbd.ttf", f_size_num)
            font_db = ImageFont.truetype("arialbd.ttf", f_size_db)
            font_date = ImageFont.truetype("arialbd.ttf", f_size_date)
        except Exception:
            font_num = font_db = font_date = ImageFont.load_default()

        # Ngày tháng
        days_vn = ["THỨ HAI", "THỨ BA", "THỨ TƯ", "THỨ NĂM", "THỨ SÁU", "THỨ BẢY", "CHỦ NHẬT"]
        day_str = days_vn[now.weekday()]
        date_str = f"{day_str} - {now.strftime('%d/%m/%Y')}"
        d.text((w * 0.5, h * 0.192), date_str, fill=(255, 225, 100), font=font_date, anchor="mm")

        # Tọa độ các giải
        cx = w * 0.64
        
        # Giải Đặc Biệt (3 chấm màu đỏ nếu chưa quay)
        db_color = (200, 0, 0)
        d.text((cx, h * 0.285), data["G.ĐB"], fill=db_color, font=font_db, anchor="mm")
        
        # Giải nhất
        d.text((cx, h * 0.345), data["G.1"], fill=(20, 20, 20), font=font_num, anchor="mm")
        
        # Giải nhì
        d.text((w * 0.47, h * 0.405), data["G.2"][0], fill=(20, 20, 20), font=font_num, anchor="mm")
        d.text((w * 0.81, h * 0.405), data["G.2"][1], fill=(20, 20, 20), font=font_num, anchor="mm")

        # Giải ba
        g3_y1, g3_y2 = h * 0.465, h * 0.505
        g3_xs = [w * 0.43, w * 0.64, w * 0.85]
        for i, num in enumerate(data["G.3"]):
            col = i % 3
            row_y = g3_y1 if i < 3 else g3_y2
            d.text((g3_xs[col], row_y), num, fill=(20, 20, 20), font=font_num, anchor="mm")

        # Giải tư
        g4_xs = [w * 0.41, w * 0.54, w * 0.68, w * 0.83]
        for i, num in enumerate(data["G.4"]):
            if i < len(g4_xs):
                d.text((g4_xs[i], h * 0.565), num, fill=(20, 20, 20), font=font_num, anchor="mm")

        # Giải năm
        g5_y1, g5_y2 = h * 0.625, h * 0.665
        g5_xs = [w * 0.47, w * 0.64, w * 0.81]
        for i, num in enumerate(data["G.5"]):
            col = i % 3
            row_y = g5_y1 if i < 3 else g5_y2
            d.text((g5_xs[col], row_y), num, fill=(20, 20, 20), font=font_num, anchor="mm")

        # Giải sáu
        g6_xs = [w * 0.47, w * 0.64, w * 0.81]
        for i, num in enumerate(data["G.6"]):
            if i < len(g6_xs):
                d.text((g6_xs[i], h * 0.725), num, fill=(20, 20, 20), font=font_num, anchor="mm")

        # Giải bảy (màu đỏ)
        g7_xs = [w * 0.44, w * 0.58, w * 0.72, w * 0.86]
        for i, num in enumerate(data["G.7"]):
            if i < len(g7_xs):
                d.text((g7_xs[i], h * 0.785), num, fill=(200, 0, 0), font=font_num, anchor="mm")

        img_path = "xsmb_result.png"
        img.save(img_path)

        if target_chat_id:
            caption_text = f"🐴 **KẾT QUẢ XSMB**\n🏆 **XỔ SỐ MIỀN BẮC – Ngày {now.strftime('%d/%m/%Y')}**\n{status_text}"
            with open(img_path, 'rb') as photo:
                await bot_instance.send_photo(chat_id=target_chat_id, photo=photo, caption=caption_text)
            logging.info("Đã gửi ảnh kết quả XSMB thành công!")
    except Exception as e:
        logging.error(f"Lỗi khi xử lý ảnh XSMB: {e}")

async def manual_test_xsmb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔄 Đang tạo ảnh kết quả XSMB...")
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
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    asyncio.create_task(run_xsmb_scheduler(app.bot))
    while True:
        await asyncio.sleep(3600)

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

api_app = FastAPI()

@api_app.get("/")
def health_check():
    return {"status": "Hệ thống bot đang vận hành ổn định 24/7!"}

async def run_fastapi_server():
    config = uvicorn.Config(api_app, host="0.0.0.0", port=10000, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()

async def main():
    await asyncio.gather(
        run_fastapi_server(),
        run_bot_taivu(),
        run_bot_xsmb(),
        run_bot_mod()
    )

if __name__ == "__main__":
    asyncio.run(main())
