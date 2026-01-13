import os
import uuid
import asyncio
import subprocess

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import FileResponse
from aiogram import Bot, Dispatcher, F
from aiogram.types import Update, Message

BOT_TOKEN = os.environ["BOT_TOKEN"]
WEBHOOK_SECRET = os.environ["WEBHOOK_SECRET"]
PUBLIC_BASE_URL = os.environ["PUBLIC_BASE_URL"]

FILES_DIR = "files"
os.makedirs(FILES_DIR, exist_ok=True)

bot = Bot(BOT_TOKEN)
dp = Dispatcher()
app = FastAPI()

# ---------- Telegram webhook ----------
@app.post(f"/tg/{WEBHOOK_SECRET}")
async def tg_webhook(req: Request):
    data = await req.json()
    update = Update.model_validate(data)
    await dp.feed_update(bot, update)
    return {"ok": True}

# ---------- Download endpoint ----------
@app.get("/download/{file_id}")
def download(file_id: str):
    path = os.path.join(FILES_DIR, file_id)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path, filename=file_id)

# ---------- Bot logic ----------
@dp.message(F.text)
async def handle(m: Message):
    url = (m.text or "").strip()
    if not url.startswith("http"):
        await m.answer("Пришли ссылку на видео.")
        return

    await m.answer("Скачиваю видео, подожди…")

    file_id = f"{uuid.uuid4().hex}.mp4"
    filepath = os.path.join(FILES_DIR, file_id)

    try:
        subprocess.check_call([
            "yt-dlp",
            "-f", "mp4",
            "-o", filepath,
            "--no-playlist",
            url
        ])
    except Exception:
        await m.answer("❌ Не удалось скачать видео.")
        return

    link = f"{PUBLIC_BASE_URL}/download/{file_id}"
    await m.answer(f"✅ Готово!\nСсылка на скачивание:\n{link}")

# ---------- Startup ----------
@app.on_event("startup")
async def on_startup():
    await bot.set_webhook(f"{PUBLIC_BASE_URL}/tg/{WEBHOOK_SECRET}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
