import os
import asyncio
import subprocess
import tempfile

from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher
from aiogram.types import Update, Message
from aiogram import F

BOT_TOKEN = os.environ["BOT_TOKEN"]
WEBHOOK_SECRET = os.environ["WEBHOOK_SECRET"]
PUBLIC_BASE_URL = os.environ["PUBLIC_BASE_URL"]

bot = Bot(BOT_TOKEN)
dp = Dispatcher()
app = FastAPI()

@app.post(f"/tg/{WEBHOOK_SECRET}")
async def tg_webhook(req: Request):
    data = await req.json()
    update = Update.model_validate(data)
    await dp.feed_update(bot, update)
    return {"ok": True}

@dp.message(F.text)
async def handle(m: Message):
    url = (m.text or "").strip()
    if not url.startswith("http"):
        await m.answer("Пришли ссылку на видео.")
        return

    await m.answer("Принял. Пытаюсь скачать… (может занять время)")

    # Скачиваем во временный файл и сразу отдаём "локальную" ссылку-заглушку (ниже объясню)
    # На этом простом шаге мы просто проверяем, что yt-dlp запускается.
    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, "video.%(ext)s")
        try:
            subprocess.check_call(["yt-dlp", "-o", out, "--no-playlist", url])
        except Exception:
            await m.answer("Не получилось скачать (источник может ограничивать доступ).")
            return

    await m.answer("Скачалось (проверка ок). Дальше подключим хранилище и будем выдавать ссылку.")

@app.on_event("startup")
async def on_startup():
    url = f"{PUBLIC_BASE_URL}/tg/{WEBHOOK_SECRET}"
    await bot.set_webhook(url)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
