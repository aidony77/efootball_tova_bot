import asyncio
import random
import os
import sqlite3

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

# ---------------- DATABASE (SQLite) ----------------
DB_FILE = "bot_database.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    # Пайдаланушылар кестесі: ID, тілі, және ойнаған матчтар саны
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            language TEXT DEFAULT '🇷🇺 Русский',
            matches_played INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

# Базаны іске қосу
init_db()

def get_user(user_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT language, matches_played FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {"language": row[0], "matches_played": row[1]}
    return None

def add_user(user_id, username, language):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO users (user_id, username, language) 
        VALUES (?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET username = ?, language = ?
    """, (user_id, username, language, username, language))
    conn.commit()
    conn.close()

def increment_matches(user_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET matches_played = matches_played + 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def get_top_players():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    # Ең көп матч ойнаған 10 ойыншыны шығару
    cursor.execute("SELECT username, matches_played, user_id FROM users ORDER BY matches_played DESC LIMIT 10")
    rows = cursor.fetchall()
    conn.close()
    return rows

# ---------------- DATA ----------------
queue = []
matches = {}
lock = asyncio.Lock()

# ---------------- LOCALIZATION ----------------
LOCALIZATION = {
    "🇰🇿 Қазақша": {
        "find_match": "🔍 Матч іздеу",
        "end_match": "❌ Матчты аяқтау",
        "profile": "👤 Менің профилім",
        "top_players": "🏆 Топ ойыншылар",
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
        "searching": "🔎 Қарсылас іздеудеміз...",
        "found_host": "🟢 Матч табылды! Сіз ХОСТ (бөлме ашушы)сыз 🎮\n\nБөлме кодын ашып, қарсыласқа осы чатта жазыңыз!",
        "found_player": "🟡 Матч табылды! Сіз ИГРОК (кіруші)сіз 🎮\n\nҚарсыластың бөлме кодын жіберуін күтіңіз!",
        "no_active_match": "❌ Сізде белсенді матч жоқ",
        "search_cancelled": "🛑 Іздеу тоқтатылды",
        "match_ended": "🏁 Матч аяқталды. Статистикаңызға +1 матч қосылды!",
        "opponent_ended": "🏁 Қарсылас матчты аяқтады. Статистикаңызға +1 матч қосылды!",
        "relay_prefix": "💬 Қарсылас:",
        "profile_text": "👤 <b>Сіздің профиліңіз:</b>\n\nАтыңыз: {name}\nТіл: {lang}\n🎮 Ойналған матчтар: <b>{matches}</b>",
        "top_title": "🏆 <b>ЕҢ КӨП МАТЧ ОЙНАҒАН ТОП ОЙЫНШЫЛАР:</b>\n\n"
    },
    "🇷🇺 Русский": {
        "find_match": "🔍 Поиск матча",
        "end_match": "❌ Завершить матч",
        "profile": "👤 Мой профиль",
        "top_players": "🏆 Топ игроки",
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
        "found_host": "🟢 Матч найден! Ты ХОСТ 🎮\n\nСоздай комнату и отправь код сопернику прямо сюда!",
        "found_player": "🟡 Матч найден! Ты ИГРОК 🎮\n\nЖди код комнаты от соперника в этом чате!",
        "no_active_match": "❌ У тебя нет активного матча",
        "search_cancelled": "🛑 Поиск отменен",
        "match_ended": "🏁 Матч завершён. В твою статистику добавлен +1 матч!",
        "opponent_ended": "🏁 Соперник завершил матч. В твою статистику добавлен +1 матч!",
        "relay_prefix": "💬 Соперник:",
        "profile_text": "👤 <b>Твой профиль:</b>\n\nИмя: {name}\nЯзык: {lang}\n🎮 Сыграно матчей: <b>{matches}</b>",
        "top_title": "🏆 <b>ТОП ИГРОКОВ ПО КОЛИЧЕСТВУ МАТЧЕЙ:</b>\n\n"
    },
    "🇬🇧 English": {
        "find_match": "🔍 Find Match",
        "end_match": "❌ End Match",
        "profile": "👤 My Profile",
        "top_players": "🏆 Top Players",
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
        "found_host": "🟢 Match found! You are the HOST 🎮\n\nCreate a room and send the code to your opponent here!",
        "found_player": "🟡 Match found! You are the PLAYER 🎮\n\nWait for the room code from your opponent!",
        "no_active_match": "❌ You don't have an active match",
        "search_cancelled": "🛑 Search cancelled",
        "match_ended": "🏁 Match ended. +1 match added to your stats!",
        "opponent_ended": "🏁 Opponent ended the match. +1 match added to your stats!",
        "relay_prefix": "💬 Opponent:",
        "profile_text": "👤 <b>Your Profile:</b>\n\nName: {name}\nLanguage: {lang}\n🎮 Matches played: <b>{matches}</b>",
        "top_title": "🏆 <b>TOP PLAYERS BY MATCHES PLAYED:</b>\n\n"
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
            [KeyboardButton(text=texts["profile"]), KeyboardButton(text=texts["top_players"])],
            [KeyboardButton(text=texts["end_match"])]
        ],
        resize_keyboard=True
    )

# ---------------- START ----------------
@dp.message(Command("start"))
async def start(message: Message):
    await message.answer(
        "🌐 <b>Тілді таңдаңыз / Выберите язык / Choose language:</b>",
        reply_markup=lang_keyboard
    )

# ---------------- SET LANGUAGE ----------------
@dp.message(F.text.in_({"🇰🇿 Қазақша", "🇷🇺 Русский", "🇬🇧 English"}))
async def set_language(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name
    lang = message.text
    
    # Базаға сақтау немесе тілді жаңарту
    add_user(user_id, username, lang)
    
    texts = LOCALIZATION[lang]
    await message.answer(
        text=texts["welcome"],
        reply_markup=get_main_keyboard(lang)
    )

# ---------------- PROFILE ----------------
@dp.message(F.text.in_({LOCALIZATION["🇰🇿 Қазақша"]["profile"], LOCALIZATION["🇷🇺 Русский"]["profile"], LOCALIZATION["🇬🇧 English"]["profile"]}))
async def show_profile(message: Message):
    user_id = message.from_user.id
    name = message.from_user.first_name
    
    user_data = get_user(user_id)
    lang = user_data["language"] if user_data else "🇷🇺 Русский"
    matches_count = user_data["matches_played"] if user_data else 0
    
    texts = LOCALIZATION[lang]
    formatted_text = texts["profile_text"].format(name=name, lang=lang, matches=matches_count)
    
    await message.answer(formatted_text)

# ---------------- TOP PLAYERS ----------------
@dp.message(F.text.in_({LOCALIZATION["🇰🇿 Қазақша"]["top_players"], LOCALIZATION["🇷🇺 Русский"]["top_players"], LOCALIZATION["🇬🇧 English"]["top_players"]}))
async def show_top(message: Message):
    user_id = message.from_user.id
    user_data = get_user(user_id)
    lang = user_data["language"] if user_data else "🇷🇺 Русский"
    texts = LOCALIZATION[lang]
    
    top_list = get_top_players()
    response = texts["top_title"]
    
    if not top_list:
        response += "📋 Спискок пуст"
    else:
        for index, player in enumerate(top_list, start=1):
            username, matches_count, p_id = player
            display_name = f"@{username}" if username and not username.isdigit() else f"User_{p_id}"
            
            # Алғашқы 3 орынға әдемі медаль қою
            medal = "🥇 " if index == 1 else "🥈 " if index == 2 else "🥉 " if index == 3 else f"{index}. "
            response += f"{medal}{display_name} — <b>{matches_count}</b> матчей\n"
            
    await message.answer(response)

# ---------------- FIND MATCH ----------------
@dp.message(F.text.in_({LOCALIZATION["🇰🇿 Қазақша"]["find_match"], LOCALIZATION["🇷🇺 Русский"]["find_match"], LOCALIZATION["🇬🇧 English"]["find_match"]}))
async def find_match(message: Message):
    user_id = message.from_user.id
    user_data = get_user(user_id)
    lang = user_data["language"] if user_data else "🇷🇺 Русский"
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
            
            op_data = get_user(opponent)
            op_lang = op_data["language"] if op_data else "🇷🇺 Русский"
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
    user_data = get_user(user_id)
    lang = user_data["language"] if user_data else "🇷🇺 Русский"
    texts = LOCALIZATION[lang]

    if user_id in queue:
        queue.remove(user_id)
        await message.answer(texts["search_cancelled"])
        return

    if user_id not in matches:
        await message.answer(texts["no_active_match"])
        return

    opponent = matches[user_id]
    op_data = get_user(opponent)
    op_lang = op_data["language"] if op_data else "🇷🇺 Русский"
    op_texts = LOCALIZATION[op_lang]

    matches.pop(user_id, None)
    matches.pop(opponent, None)

    # Матч сәтті аяқталған соң ЕКІ ойыншының да статистикасына +1 матч қосамыз
    increment_matches(user_id)
    increment_matches(opponent)

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
    op_data = get_user(opponent)
    op_lang = op_data["language"] if op_data else "🇷🇺 Русский"
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
