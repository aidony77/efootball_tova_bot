import asyncio
import random
import os
import sqlite3
import re
import time
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

# ---------------- CONFIG ----------------
TOKEN = os.getenv("TOKEN")
ADMIN_ID = 8093382664 

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

class MatchState(StatesGroup):
    entering_score = State()

DB_FILE = "bot_database.db"
queue, matches, score_votes, user_last_activity = [], {}, {}, {}
lock = asyncio.Lock()

# ---------------- DATABASE ----------------
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY, username TEXT, language TEXT DEFAULT '🇷🇺 Русский',
            matches_played INTEGER DEFAULT 0, wins INTEGER DEFAULT 0,
            draws INTEGER DEFAULT 0, losses INTEGER DEFAULT 0, is_banned INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

init_db()

def get_user(user_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT language, matches_played, wins, draws, losses, is_banned FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return {"language": row[0], "matches_played": row[1], "wins": row[2], "draws": row[3], "losses": row[4], "is_banned": row[5]} if row else None

def add_user(user_id, username, language):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id, username, language) VALUES (?, ?, ?)", (user_id, username, language))
    conn.commit()
    conn.close()

def update_stats(user_id, result_type):
    conn = sqlite3.connect(DB_FILE)
    if result_type == "win": conn.execute("UPDATE users SET matches_played = matches_played + 1, wins = wins + 1 WHERE user_id = ?", (user_id,))
    elif result_type == "loss": conn.execute("UPDATE users SET matches_played = matches_played + 1, losses = losses + 1 WHERE user_id = ?", (user_id,))
    elif result_type == "draw": conn.execute("UPDATE users SET matches_played = matches_played + 1, draws = draws + 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def get_top_players():
    conn = sqlite3.connect(DB_FILE)
    rows = conn.execute("SELECT username, wins, matches_played, user_id FROM users ORDER BY wins DESC, matches_played DESC LIMIT 10").fetchall()
    conn.close()
    return rows

def get_total_users_count():
    conn = sqlite3.connect(DB_FILE)
    count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    conn.close()
    return count

def update_online(user_id): user_last_activity[user_id] = time.time()
def get_online_users_count(): return max(1, sum(1 for last_time in user_last_activity.values() if time.time() - last_time < 300))

# ---------------- LOCALIZATION ----------------
LOCALIZATION = {
    "🇰🇿 Қазақша": {"find_match": "🔍 Матч іздеу", "end_match": "❌ Матчты аяқтау", "profile": "👤 Менің профилім", "top_players": "🏆 Топ ойыншылар", "rules": "📜 Ережелер", "welcome": "🔥 Қош келдіңіз!", "already_in_match": "❌ Сіз қазір ойындасыз", "already_in_queue": "⏳ Сіз қарсылас іздеп жатырсыз", "searching": "🔎 Қарсылас іздеудеміз...", "found_host": "🟢 Матч табылды! Сіз ХОСТсыз", "found_player": "🟡 Матч табылды! Сіз ИГРОКсыз", "no_active_match": "❌ Сізде белсенді матч жоқ", "search_cancelled": "🛑 Іздеу тоқтатылды", "relay_prefix": "💬 Қарсылас:", "profile_text": "👤 <b>Профиль:</b> {matches} матч.", "top_title": "🏆 <b>ТОП:</b>", "ask_score": "⚽ Есепті енгізіңіз (мысалы: 3-2):", "bad_format": "❌ Қате формат!", "wait_opponent_score": "⏳ Күтіңіз...", "score_mismatch": "⚠️ Есеп сәйкес келмеді!", "match_saved": "✅ Тіркелді!", "score_0_0": "❌ 0-0 есептелмейді.", "rules_text": "📜 <b>Ережелер:</b>..."},
    "🇷🇺 Русский": {"find_match": "🔍 Поиск матча", "end_match": "❌ Завершить матч", "profile": "👤 Мой профиль", "top_players": "🏆 Топ игроки", "rules": "📜 Правила", "welcome": "🔥 Добро пожаловать!", "already_in_match": "❌ Ты уже в матче", "already_in_queue": "⏳ Ты уже ищешь соперника", "searching": "🔎 Ищем соперника...", "found_host": "🟢 Матч найден! Ты ХОСТ", "found_player": "🟡 Матч найден! Ты ИГРОК", "no_active_match": "❌ У тебя нет матча", "search_cancelled": "🛑 Поиск отменен", "relay_prefix": "💬 Соперник:", "profile_text": "👤 <b>Профиль:</b> {matches} матчей.", "top_title": "🏆 <b>ТОП:</b>", "ask_score": "⚽ Введите счет (например: 3-2):", "bad_format": "❌ Неверный формат!", "wait_opponent_score": "⏳ Ожидайте...", "score_mismatch": "⚠️ Счет не совпал!", "match_saved": "✅ Засчитано!", "score_0_0": "❌ 0-0 не засчитывается.", "rules_text": "📜 <b>Правила:</b>..."},
    "🇬🇧 English": {"find_match": "🔍 Find Match", "end_match": "❌ End Match", "profile": "👤 My Profile", "top_players": "🏆 Top Players", "rules": "📜 Rules", "welcome": "🔥 Welcome!", "already_in_match": "❌ You are already in a match", "already_in_queue": "⏳ Already searching", "searching": "🔎 Searching...", "found_host": "🟢 Match found! You are HOST", "found_player": "🟡 Match found! You are PLAYER", "no_active_match": "❌ No active match", "search_cancelled": "🛑 Search cancelled", "relay_prefix": "💬 Opponent:", "profile_text": "👤 <b>Profile:</b> {matches} matches.", "top_title": "🏆 <b>TOP:</b>", "ask_score": "⚽ Enter score (e.g., 3-2):", "bad_format": "❌ Invalid format!", "wait_opponent_score": "⏳ Waiting...", "score_mismatch": "⚠️ Mismatch!", "match_saved": "✅ Saved!", "score_0_0": "❌ 0-0 not counted.", "rules_text": "📜 <b>Rules:</b>..."}
}

# ---------------- ADMIN COMMANDS ----------------
@dp.message(Command("ban"))
async def admin_ban(message: Message):
    if message.from_user.id != ADMIN_ID: return
    try:
        target_id = int(message.text.split()[1])
        sqlite3.connect(DB_FILE).execute("UPDATE users SET is_banned = 1 WHERE user_id = ?", (target_id,))
        await message.answer(f"🚫 ID {target_id} забанен.")
    except: await message.answer("❌ Формат: /ban [id]")

@dp.message(Command("report"))
async def report_user(message: Message):
    if len(message.text.split()) < 2: return await message.answer("❌ Формат: /report @user [причина]")
    await bot.send_message(ADMIN_ID, f"🚨 <b>Жалоба:</b> @{message.from_user.username}\n{message.text}")
    await message.answer("✅ Шағым қабылданды.")

# ---------------- MATCH LOGIC ----------------
@dp.message(F.text.in_({"🔍 Матч іздеу", "🔍 Поиск матча", "🔍 Find Match"}))
async def find_match(message: Message):
    user_id = message.from_user.id
    if (user := get_user(user_id)) and user['is_banned']: return await message.answer("❌ Сіз БАНдасыз.")
    
    async with lock:
        if queue:
            opponent = queue.pop(0)
            matches[user_id], matches[opponent] = opponent, user_id
            u_name = (await bot.get_chat(user_id)).username or "User"
            o_name = (await bot.get_chat(opponent)).username or "User"
            await bot.send_message(user_id, f"🟢 Матч табылды! Қарсылас: @{o_name}")
            await bot.send_message(opponent, f"🟢 Матч табылды! Қарсылас: @{u_name}")
        else:
            queue.append(user_id)
            await message.answer("🔎 Іздеудеміз...")

# --- (Мұнда қалған барлық функцияларыңды қоя бересің) ---

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
