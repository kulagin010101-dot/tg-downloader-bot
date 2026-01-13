import os
import uuid
import asyncio
import subprocess

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import FileResponse

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Update,
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

# =========================
# НАСТРОЙКИ
# =========================
BOT_TOKEN = os.environ["BOT_TOKEN"]
WEBHOOK_SECRET = os.environ["WEBHOOK_SECRET"]
PUBLIC_BASE_URL = os.environ["PUBLIC_BASE_URL"]

# 🔴 ОБЯЗАТЕЛЬНАЯ ПОДПИСКА НА ЭТОТ КАНАЛ
REQUIRED_CHANNEL = "@otkritki_today"

# Папка для временных файлов
FILES_DIR = "files"
os.makedirs(FILES_DIR, exist_ok=True)

# Время жизни файлов (10 минут)
FILE_TTL_SECONDS = 10 * 60

# =========================
# BOT + WEB
# =========================
bot = Bot(BOT_TOKEN)
dp = Dispatcher()
app = FastAPI()

# =========================
# ПРОВЕРКА ПОДПИСКИ
# =========================
async def is_subscribed(user_id: int) -> bool:
    """
    Проверяет, подписан ли пользователь на REQUIRED_CHANNEL.
    ВАЖНО: бот должен быть администратором канала.
    """
    try:
        member = await bot.get_chat_member(REQUIRED_CHANNEL, user_id)
        return member.status in ("member", "administrator", "creator")
    except Exception:
        return False


def subscribe_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(
                text="📢 Подписаться на канал",
                url="https://t.me/otkritki_today"
            )
        ]]
    )

# =========================
# АВТОУДАЛЕНИЕ ФАЙЛОВ
# =========================
async def delete_file_later(path: str, delay_seconds: int = FILE_TTL_SECONDS):
    await asyncio.sleep(delay_seconds)
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception:
        pass

# =========================
# TELEGRAM WEBHOOK
# =========================
@app.post(f"/tg/{WEBHOOK_SECRET}")
async def tg_webhook(req: Request):
    data = await req.json()
    update = Update.model_validate(data)
    await dp.feed_update(bot, update)
    return {"ok": True}

# =========================
# СКАЧИВАНИЕ ФАЙЛА
# =========================
@app.get("/download/{file_id}")
def download(file_id: str):
    path = os.path.join(FILES_DIR, file_id)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path, filename=file_id)

# =========================
# ОСНОВНАЯ ЛОГИКА БОТА
# =========================
@dp.message(F.text)
async def handle(m: Message):
    user_id = m.from_user.id

    # 1) Проверка подписки
    if not await is_subscribed(user_id):
        await m.answer(
            "❗ Чтобы пользоваться ботом, нужно подписаться на канал:",
            reply_markup=subscribe_keyboard()
        )
        return

    # 2) Проверяем ссылку
    url = (m.text or "").strip()
    if not url.startswith("http"):
        await m.answer("Пришли ссылку на видео.")
        return

    await m.answer("⏳ Скачиваю видео, подожди…")

    # 3) Скачиваем видео
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
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
        except Exception:
            pass

        await m.answer("❌ Не удалось скачать видео. Возможно, источник ограничивает доступ.")
        return

    # 4) Отдаём ссылку
    link = f"{PUBLIC_BASE_URL}/download/{file_id}"
    await m.answer(
        f"✅ Готово!\n\n"
        f"📥 Ссылка на скачивание (действует ~10 минут):\n{link}"
    )

    # 5) Планируем автоудаление
    asyncio.create_task(delete_file_later(filepath, FILE_TTL_SECONDS))

# =========================
# STARTUP: WEBHOOK
# =========================
@app.on_event("startup")
async def on_startup():
    await bot.set_webhook(f"{PUBLIC_BASE_URL}/tg/{WEBHOOK_SECRET}")

# =========================
# ЗАПУСК
# =========================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8000))
    )
