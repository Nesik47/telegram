import os
import asyncio
import logging
import sqlite3
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message
from aiogram.filters import Command
from datetime import datetime, timedelta
from aiogram.client.default import DefaultBotProperties
from dotenv import load_dotenv

# Завантажуємо змінні з .env
load_dotenv()

TOKEN = os.getenv("TOKEN")
CHAT_ID = int(os.getenv("CHAT_ID"))
ADMIN_IDS = list(map(int, os.getenv("ADMIN_IDS").split(',')))

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()
logging.basicConfig(level=logging.INFO)

# === Ініціалізація БД ===
def init_db():
    with sqlite3.connect("bot_data.db") as conn:
        cursor = conn.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            last_message_time TEXT,
            welcomed INTEGER DEFAULT 0
        )""")
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS banned_users (
            user_id INTEGER PRIMARY KEY,
            ban_until TEXT
        )""")
        conn.commit()

init_db()

# === Функції роботи з баном ===
def ban_user(user_id: int, days: int = 0):
    ban_until = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S") if days > 0 else "permanent"
    with sqlite3.connect("bot_data.db") as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO banned_users (user_id, ban_until) VALUES (?, ?)", (user_id, ban_until))
        conn.commit()

def unban_user(user_id: int):
    with sqlite3.connect("bot_data.db") as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM banned_users WHERE user_id=?", (user_id,))
        conn.commit()

def is_banned(user_id: int) -> bool:
    with sqlite3.connect("bot_data.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT ban_until FROM banned_users WHERE user_id=?", (user_id,))
        result = cursor.fetchone()
        if result:
            if result[0] == "permanent":
                return True
            return datetime.now() < datetime.strptime(result[0], "%Y-%m-%d %H:%M:%S")
        return False

# === Обмеження частоти повідомлень ===
def can_send_message(user_id: int) -> bool:
    with sqlite3.connect("bot_data.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT last_message_time FROM users WHERE user_id=?", (user_id,))
        result = cursor.fetchone()
    
    if result and result[0]:
        try:
            last_message_time = datetime.strptime(result[0], "%Y-%m-%d %H:%M:%S")
            if datetime.now() - last_message_time < timedelta(minutes=5):
                return False  
        except ValueError:
            return True  

    return True

def update_message_time(user_id: int):
    with sqlite3.connect("bot_data.db") as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (user_id, last_message_time) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET last_message_time=excluded.last_message_time", 
                       (user_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()

# === Обробка команди /start ===
@dp.message(Command("start"))
async def start_command(message: Message):
    await message.answer("👋 Вітаємо! Якщо стали свідками важливих подій, надсилайте їх нам.❗️Увага: анонімність гарантована. Якщо надсилаєте цікавий матеріал — дочекайтесь нашої відповіді і не відправляйте його іншим каналам.")

# === Обробка повідомлень ===
@dp.message()
async def forward_message(message: Message):
    if message.chat.id == CHAT_ID or message.text == "/start":
        return  

    if is_banned(message.from_user.id):
        await message.answer("🚫 Ви заблоковані та не можете надсилати повідомлення.")
        return
    
    if not can_send_message(message.from_user.id):
        await message.answer("⏳ Ви можете надіслати наступне повідомлення через 5 хвилин.")
        return
    
    user_info = f"👤 Відправник: {message.from_user.full_name} (@{message.from_user.username})"
    caption = f"{user_info}"
    
    if message.text:
        await bot.send_message(CHAT_ID, f"{caption}\n✉️ {message.text}")
    
    if message.photo:
        caption += f"\n📷 Надіслано фото"
        if message.caption:
            caption += f"\n📝 {message.caption}"
        await bot.send_photo(CHAT_ID, message.photo[-1].file_id, caption=caption)

    if message.video:
        caption += f"\n🎥 Надіслано відео"
        if message.caption:
            caption += f"\n📝 {message.caption}"
        await bot.send_video(CHAT_ID, message.video.file_id, caption=caption)

    if message.document:
        caption += f"\n📂 Надіслано файл"
        if message.caption:
            caption += f"\n📝 {message.caption}"
        await bot.send_document(CHAT_ID, message.document.file_id, caption=caption)
    
    update_message_time(message.from_user.id)
    await message.answer("✅ Ваше повідомлення надіслано! Вдячні, що довіряєте нам 🤝")

# === Запуск бота ===
async def main():
    logging.info("🚀 Запускаємо бота...")
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    asyncio.run(main())