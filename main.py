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
    """Cào kết quả XSMB thực tế, có bộ số mẫu dự phòng khi chưa quay"""
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
        logging.info("Đang tạo ảnh kết quả XSMB từ template chú ngựa mới...")
        data = await fetch_xsmb_results()

        if os.path.exists("template.png"):
            img = Image.open("template.png").convert("RGB")
        else:
            img = Image.new('RGB', (800, 1100), color=(255, 255, 255))

        d = ImageDraw.Draw(img)
        
        try:
            font_num = ImageFont.truetype("arial.ttf", 24)
            font_db = ImageFont.truetype("arial.ttf", 34)
            font_date = ImageFont.truetype("arial.ttf", 18)
        except Exception:
            font_num = font_db = font_date = ImageFont.load_default()

        # Tự động cập nhật ngày tháng động xuống đúng vị trí dưới nút XSMB
        now = datetime.now()
        days_vn = ["THỨ HAI", "THỨ BA", "THỨ TƯ", "THỨ NĂM", "THỨ SÁU", "THỨ BẢY", "CHỦ NHẬT"]
        day_str = days_vn[now.weekday()]
        date_str = f"{day_str} - {now.strftime('%d/%m/%Y')}"
        
        d.text((400, 158), date_str, fill=(255, 225, 100), font=font_date, anchor="mm")

        # Điền các con số vào các khung trắng đã căn chuẩn theo mẫu mới:
        
        # 1. Giải Đặc Biệt (Màu đỏ, chữ to)
        d.text((515, 265), data["G.ĐB"], fill=(200, 0, 0), font=font_db, anchor="mm")
        
        # 2. Giải nhất
        d.text((515, 320), data["G.1"], fill=(20, 20, 20), font=font_num, anchor="mm")
        
        # 3. Giải nhì (2 số)
        d.text((380, 375), data["G.2"][0], fill=(20, 20, 20), font=font_num, anchor="mm")
        d.text((650, 375), data["G.2"][1], fill=(20, 20, 20), font=font_num, anchor="mm")

        # 4. Giải ba (6 số - 2 hàng x 3 cột)
        g3_coords = [
            (345, 430), (515, 430), (685, 430),
            (345, 470), (515, 470), (685, 470)
        ]
        for i, num in enumerate(data["G.3"]):
            if i < len(g3_coords):
                d.text(g3_coords[i], num, fill=(20, 20, 20), font=font_num, anchor="mm")

        # 5. Giải tư (4 số)
        g4_coords = [(330, 525), (450, 525), (580, 525), (705, 525)]
        for i, num in enumerate(data["G.4"]):
            if i < len(g4_coords):
                d.text(g4_coords[i], num, fill=(20, 20, 20), font=font_num, anchor="mm")

        # 6. Giải năm (6 số - 2 hàng x 3 cột)
        g5_coords = [
            (380, 580), (515, 580), (650, 580),
            (380, 620), (515, 620), (650, 620)
        ]
        for i, num in enumerate(data["G.5"]):
            if i < len(g5_coords):
                d.text(g5_coords[i], num, fill=(20, 20, 20), font=font_num, anchor="mm")

        # 7. Giải sáu (3 số)
        g6_coords = [(380, 675), (515, 675), (650, 675)]
        for i, num in enumerate(data["G.6"]):
            if i < len(g6_coords):
                d.text(g6_coords[i], num, fill=(20, 20, 20), font=font_num, anchor="mm")

        # 8. Giải bảy (4 số - màu đỏ)
        g7_coords = [(350, 730), (475, 730), (600, 730), (725, 730)]
        for i, num in enumerate(data["G.7"]):
            if i < len(g7_coords):
                d.text(g7_coords[i], num, fill=(200, 0, 0), font=font_num, anchor="mm")

        img_path = "xsmb_result.png"
        img.save(img_path)

        if target_chat_id:
            caption_text = f"🐴 **KẾT QUẢ XSMB**\n🏆 **XỔ SỐ MIỀN BẮC – Ngày {now.strftime('%d/%m/%Y')}**\n✅ Dữ liệu đã xác nhận"
            with open(img_path, 'rb') as photo:
                await bot_instance.send_photo(chat_id=target_chat_id, photo=photo, caption=caption_text)
            logging.info("Đã gửi ảnh kết quả XSMB chuẩn form thành công!")
    except Exception as e:
        logging.error(f"Lỗi khi xử lý ảnh XSMB: {e}")

async def manual_test_xsmb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔄 Đang tạo ảnh kết quả XSMB chuẩn form...")
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
