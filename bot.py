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
user_languages = {}  # {user_id: "🇰🇿 Қазақша" / "🇷🇺 Русский" / "🇬🇧 English"}
lock = asyncio.Lock()

# ---------------- LOCALIZATION ----------------
LOCALIZATION = {
    "🇰🇿 Қазақша": {
        "find_match": "🔍 Матч іздеу",
        "end_match": "❌ Матчты аяқтау",
        "welcome": (
            "⚽ <b>eFootball Match Bot</b>\n\n"
            "🔥 Қош келдіңіз!\n"
            "🎮 Осы жерде қарсылас тауып, матч ойнай аласыз\n\n"
            "🏆 Турнирлерге қатысыңыз\n"
            "💰 Жүлделі ойындар болуы мүмкін\n\n"
            "📢 Біздің турнир каналымыз:\n"
            "@kpl_efootball_tournament\n\n"
            "👇 Төмендегі батырманы басып, ойынды бастаңыз!"
        ),
        "already_in_match": "❌ Сіз қазір ойындасыз",
        "already_in_queue": "⏳ Сіз қарсылас іздеп жатырсыз",
        "searching": "🔎 Қрсылас іздеудеміз...",
        "found_host": "🟢 Матч табылды! Сіз ХОСТ (бөлме ашушы)сыз 🎮",
        "found_player": "🟡 Матч табылды! Сіз ИГРОК (кіруші)сіз 🎮",
        "no_active_match": "❌ Сізде белсенді матч жоқ",
        "search_cancelled": "🛑 Іздеу тоқтатылды",
        "match_ended": "🏁 Матч аяқталды",
        "opponent_ended": "🏁 Қарсылас матчты аяқтады",
        "relay_prefix": "💬 Қарсылас:"
    },
    "🇷🇺 Русский": {
        "find_match": "🔍 Поиск матча",
        "end_match": "❌ Завершить матч",
        "welcome": (
            "⚽ <b>eFootball Match Bot</b>\n\n"
            "🔥 Добро пожаловать!\n"
            "🎮 Здесь ты можешь найти соперника и играть матчи\n\n"
            "🏆 Участвуй в турнирах\n"
            "💰 Возможны призовые игры\n\n"
            "📢 Наш канал турниров:\n"
            "@kpl_efootball_tournament\n\n"
            "👇 Нажми кнопку ниже и начинай игру!"
        ),
        "already_in_match": "❌ Ты уже в матче",
        "already_in_queue": "⏳ Ты уже ищешь соперника",
        "searching": "🔎 Ищем соперника...",
        "found_host": "🟢 Матч найден! Ты ХОСТ 🎮",
        "found_player": "🟡 Матч найден! Ты ИГРОК 🎮",
        "no_active_match": "❌ У тебя нет активного матча",
        "search_cancelled": "🛑 Поиск отменен",
        "match_ended": "🏁 Матч завершён",
        "opponent_ended": "🏁 Соперник завершил матч",
        "relay_prefix": "💬 Соперник:"
    ),
    "🇬🇧 English": {
        "find_match": "🔍 Find Match",
        "end_match": "❌ End Match",
        "welcome": (
            "⚽ <b>eFootball Match Bot</b>\n\n"
            "🔥 Welcome!\n"
            "🎮 Here you can find an opponent and play matches\n\n"
            "🏆 Participate in tournaments\n"
            "💰 Prize games are possible\n\n"
            "📢 Our tournament channel:\n"
            "@kpl_efootball_tournament\n\n"
            "👇 Press the button below and start the game!"
        ),
        "already_in_match": "❌ You are already in a match",
        "already_in_queue": "⏳ You are already searching for an opponent",
        "searching": "🔎 Searching for an opponent...",
        "found_host": "🟢 Match found! You are the HOST 🎮",
        "found_player": "🟡 Match found! You are the PLAYER 🎮",
        "no_active_match": "❌ You don't have an active match",
        "search_cancelled": "🛑 Search cancelled",
        "match_ended": "🏁 Match ended",
        "opponent_ended": "🏁 Opponent ended the match",
        "relay_prefix": "💬 Opponent:"
    }
}

# ---------------- KEYBOARDS ----------------
lang_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🇰🇿 Қазақша"), KeyboardButton(text="🇷🇺 Русский")],
        [KeyboardButton(text="🇬🇧 English")]
    ],
    resize_keyboard=True
)

def get_main_keyboard(lang: str) -> ReplyKeyboardMarkup:
    texts = LOCALIZATION.get(lang, LOCALIZATION["🇷🇺 Русский"])
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=texts["find_match"])],
            [KeyboardButton(text=texts["end_match"])]
        ],
        resize_keyboard=True
    )

# ---------------- START ----------------
@dp.message(Command("start"))
async def start(message: Message):
    users.add(message.from_user.id)
    user_languages.pop(message.from_user.id, None)
    
    await message.answer(
        "🌐 <b>Тілді таңдаңыз / Выберите язык / Choose language:</b>",
        reply_markup=lang_keyboard
    )

# ---------------- SET LANGUAGE ----------------
@dp.message(F.text.in_({"🇰🇿 Қазақша", "🇷🇺 Русский", "🇬🇧 English"}))
async def set_language(message: Message):
    user_id = message.from_user.id
    lang = message.text
    user_languages[user_id] = lang
    
    texts = LOCALIZATION[lang]
    await message.answer(
        text=texts["welcome"],
        reply_markup=get_main_keyboard(lang)
    )

# ---------------- FIND MATCH ----------------
@dp.message(F.text.in_({LOCALIZATION["🇰🇿 Қазақша"]["find_match"], LOCALIZATION["🇷🇺 Русский"]["find_match"], LOCALIZATION["🇬🇧 English"]["find_match"]}))
async def find_match(message: Message):
    user_id = message.from_user.id
    lang = user_languages.get(user_id, "🇷🇺 Русский")
    texts = LOCALIZATION[lang]

    if user_id in matches:
        await message.answer(texts["already_in_match"])
        return

    if user_id in queue:
        await message.answer(texts["already_in_queue"])
        return

    async with lock:
        if queue:
            opponent = queue.pop(0)

            if opponent == user_id:
                queue.append(user_id)
                await message.answer(texts["searching"])
                return

            matches[user_id] = opponent
            matches[opponent] = user_id

            host = random.choice([user_id, opponent])
            op_lang = user_languages.get(opponent, "🇷🇺 Русский")
            op_texts = LOCALIZATION[op_lang]

            if host == user_id:
                await bot.send_message(user_id, texts["found_host"])
                await bot.send_message(opponent, op_texts["found_player"])
            else:
                await bot.send_message(user_id, texts["found_player"])
                await bot.send_message(opponent, op_texts["found_host"])
        else:
            queue.append(user_id)
            await message.answer(texts["searching"])

# ---------------- END MATCH ----------------
@dp.message(F.text.in_({LOCALIZATION["🇰🇿 Қазақша"]["end_match"], LOCALIZATION["🇷🇺 Русский"]["end_match"], LOCALIZATION["🇬🇧 English"]["end_match"]}))
async def end_match(message: Message):
    user_id = message.from_user.id
    lang = user_languages.get(user_id, "🇷🇺 Русский")
    texts = LOCALIZATION[lang]

    if user_id in queue:
        queue.remove(user_id)
        await message.answer(texts["search_cancelled"])
        return

    if user_id not in matches:
        await message.answer(texts["no_active_match"])
        return

    opponent = matches[user_id]
    op_lang = user_languages.get(opponent, "🇷🇺 Русский")
    op_texts = LOCALIZATION[op_lang]

    matches.pop(user_id, None)
    matches.pop(opponent, None)

    await bot.send_message(user_id, texts["match_ended"])
    try:
        await bot.send_message(opponent, op_texts["opponent_ended"])
    except Exception:
        pass

# ---------------- RELAY ----------------
@dp.message()
async def relay(message: Message):
    user_id = message.from_user.id

    if user_id not in matches:
        return

    opponent = matches[user_id]
    op_lang = user_languages.get(opponent, "🇷🇺 Русский")
    op_texts = LOCALIZATION[op_lang]

    try:
        if message.text:
            await bot.send_message(opponent, f"{op_texts['relay_prefix']}\n{message.text}")
        else:
            await message.send_copy(chat_id=opponent)
    except Exception as e:
        print(f"Ошибка пересылки: {e}")

# ---------------- MAIN ----------------
async def main():
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    except Exception as e:
        print("ERROR:", e)

# ---------------- RUN ----------------
if __name__ == "__main__":
    asyncio.run(main())
