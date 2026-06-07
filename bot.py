import asyncio
import random
import os

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

# ---------------- TOKEN ----------------
TOKEN = os.getenv("TOKEN")

# ---------------- BOT ----------------
bot = Bot(
    token=TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

dp = Dispatcher()

# ---------------- DATA ----------------
queue = []
matches = {}
users = set()

# ---------------- KEYBOARD ----------------
keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🔍 Поиск матча")],
        [KeyboardButton(text="❌ Завершить матч")]
    ],
    resize_keyboard=True
)

# ---------------- START ----------------
@dp.message(Command("start"))
async def start(message: Message):
    users.add(message.from_user.id)

    await message.answer(
        "⚽ <b>eFootball Match Bot</b>\n\n"
        "🔥 Добро пожаловать!\n"
        "🎮 Поиск соперников доступен ниже",
        "🏆 Участвуй в турнирах \n"
        "💰 Возможны призовые игры\n\n"
        "📢 И Наш канал турниров: \n"
        "@kpl_efootball_tournament\n\n"
        " 👇 Нажми кнопку ниже и начинай игру! ",
        reply_markup=keyboard
    )  

# ---------------- FIND MATCH ----------------
@dp.message(F.text == "🔍 Поиск матча")
async def find_match(message: Message):
    user_id = message.from_user.id

    if user_id in matches:
        await message.answer("❌ Ты уже в матче")
        return

    if user_id in queue:
        await message.answer("⏳ Ты уже ищешь соперника")
        return

    if queue:
        opponent = queue.pop(0)

        matches[user_id] = opponent
        matches[opponent] = user_id

        host = random.choice([user_id, opponent])

        await bot.send_message(host, "🟢 Матч найден! Ты ХОСТ 🎮")
        await bot.send_message(opponent, "🟡 Матч найден! Ты ИГРОК 🎮")

    else:
        queue.append(user_id)
        await message.answer("🔎 Ищем соперника...")

# ---------------- END MATCH ----------------
@dp.message(F.text == "❌ Завершить матч")
async def end_match(message: Message):
    user_id = message.from_user.id

    if user_id not in matches:
        await message.answer("❌ У тебя нет активного матча")
        return

    opponent = matches[user_id]

    del matches[user_id]
    del matches[opponent]

    await bot.send_message(user_id, "🏁 Матч завершён")
    await bot.send_message(opponent, "🏁 Соперник завершил матч")

# ---------------- RELAY ----------------
@dp.message()
async def relay(message: Message):
    user_id = message.from_user.id

    if user_id not in matches:
        return

    opponent = matches[user_id]

    await bot.send_message(opponent, f"💬 Соперник:\n{message.text}")

# ---------------- MAIN (ANTI-CONFLICT) ----------------
async def main():
    try:
        # 🔥 убираем старые апдейты и webhook
        await bot.delete_webhook(drop_pending_updates=True)

        # 🚀 запускаем polling
        await dp.start_polling(bot)

    except Exception as e:
        print("ERROR:", e)

# ---------------- RUN ----------------
if __name__ == "__main__":
    asyncio.run(main())