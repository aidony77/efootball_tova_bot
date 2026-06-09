import asyncio
import random
import os
import sqlite3
import re
import time
import json

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

# ---------------- CONFIG & ADMIN ----------------
TOKEN = os.getenv("TOKEN")
ADMIN_ID = 8093382664  # Сенің Telegram ID-ің
ADMIN_USERNAME = "@sarmanchik01"  # Сенің Телеграм юзернеймің

# ---------------- BOT ----------------
bot = Bot(
    token=TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

dp = Dispatcher()

# ---------------- STATES FOR SCORE ----------------
class MatchState(StatesGroup):
    entering_score = State()

# ---------------- DATABASE (SQLite) ----------------
if os.path.exists("/data"):
    DB_FILE = "/data/bot_database.db"
else:
    DB_FILE = "bot_database.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            language TEXT DEFAULT '🇷🇺 Русский',
            matches_played INTEGER DEFAULT 0,
            wins INTEGER DEFAULT 0,
            draws INTEGER DEFAULT 0,
            losses INTEGER DEFAULT 0,
            is_banned INTEGER DEFAULT 0,
            warns INTEGER DEFAULT 0
        )
    """)
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN warns INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass
        
    conn.commit()
    conn.close()

init_db()

def get_user(user_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT language, matches_played, wins, draws, losses, is_banned, warns FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {
            "language": row[0], 
            "matches_played": row[1], 
            "wins": row[2], 
            "draws": row[3], 
            "losses": row[4],
            "is_banned": row[5],
            "warns": row[6]
        }
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

def update_stats(user_id, result_type):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    if result_type == "win":
        cursor.execute("UPDATE users SET matches_played = matches_played + 1, wins = wins + 1 WHERE user_id = ?", (user_id,))
    elif result_type == "draw":
        cursor.execute("UPDATE users SET matches_played = matches_played + 1, draws = draws + 1 WHERE user_id = ?", (user_id,))
    elif result_type == "loss":
        cursor.execute("UPDATE users SET matches_played = matches_played + 1, losses = losses + 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def get_top_players():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT username, wins, matches_played, user_id FROM users ORDER BY wins DESC, matches_played DESC LIMIT 10")
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_total_users_count():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    count = cursor.fetchone()[0]
    conn.close()
    return count

def get_all_user_ids():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    rows = cursor.fetchall()
    conn.close()
    return [row[0] for row in rows]

# ---------------- DATA & ONLINE SYSTEM ----------------
queue = []
matches = {}       
score_votes = {}   
user_last_activity = {}  # {user_id: timestamp}
lock = asyncio.Lock()

def update_online(user_id):
    user_last_activity[user_id] = time.time()

def get_online_users_count():
    current_time = time.time()
    online_count = 0
    for uid, last_time in user_last_activity.items():
        if current_time - last_time < 300:  # 5 минут
            online_count += 1
    return max(1, online_count)

# ---------------- LOCALIZATION ----------------
LOCALIZATION = {
    "🇬🇧 English": {
        "find_match": "🔍 Find Match",
        "end_match": "❌ End Match",
        "profile": "👤 My Profile",
        "top_players": "🏆 Top Players",
        "rules": "📜 Rules",
        "welcome": "⚽ <b>eFootball Match Bot</b>\n\n🔥 Welcome!\n📢 Our Channel: @tova_efootball_bot_news",
        "already_in_match": "❌ You are already in a match",
        "already_in_queue": "⏳ You are already looking for an opponent",
        "searching": "🔎 Searching for an opponent...",
        "found_host": "🟢 Match found! You are the HOST 🎮\n\nOpen a room and send the code to your opponent in this chat!",
        "found_player": "🟡 Match found! You are the PLAYER 🎮\n\nWait for your opponent to send the room code in this chat!",
        "no_active_match": "❌ You have no active match",
        "search_cancelled": "🛑 Search cancelled",
        "relay_prefix": "💬 Opponent:",
        "profile_text": "👤 <b>Your Profile:</b>\n\nName: {name}\n🎮 Matches: <b>{matches}</b>\n✅ Wins: {wins} | 🤝 Draws: {draws} | ❌ Losses: {losses}\n⚠️ Warns: <b>{warns}/3</b>\n\n📊 <b>Bot Statistics:</b>\n🟢 Online: <b>{online}</b>\n👥 Total Players: <b>{total}</b>",
        "top_title": "🏆 <b>TOP PLAYERS (BY WINS):</b>\n\n",
        "ask_score": "⚽ Match ended! Please enter the score from your side.\nFormat: <code>3-2</code> or <code>3:2</code> (YOUR goals first):",
        "bad_format": "❌ Invalid format! Enter the score like: 2-1 or 2:1",
        "wait_opponent_score": "⏳ Your score is saved. Waiting for your opponent to enter the score...",
        "score_mismatch": "⚠️ Score mismatch! You entered [{u_score}], but opponent entered different data. Re-enter correctly (Your goals first):",
        "match_saved": "✅ Match successfully saved! Score: {score}. Your stats are updated!",
        "score_0_0": "❌ If the match is ended without playing (0-0), stats will not be counted.",
        "rules_text": (
            "📜 <b>OFFICIAL BOT RULES</b>\n\n"
            "1️⃣ <b>Fair Play:</b>\n"
            "After the match ends, both players must enter the HONEST score. Always put YOUR goals first.\n\n"
            "2️⃣ <b>Score Format:</b>\n"
            "You can enter the score using a hyphen or a colon: <code>2-1</code> or <code>2:1</code>.\n\n"
            "3️⃣ <b>Anti-Cheat System:</b>\n"
            "If the entered scores do not match, the bot will reject them. Take a screenshot if needed.\n\n"
            "4️⃣ <b>No Match Fixing:</b>\n"
            "Ending a match with <code>0-0</code> immediately to boost stats is forbidden.\n\n"
            "💡 <b>Questions, Ideas & Feedback:</b>\n"
            "If you have any questions, bugs, or interesting ideas to improve the bot, feel free to share them! You can contact the admin directly: {ADMIN_USERNAME}.\n\n"
            "Alternatively, use the built-in feedback command directly in this chat:\n"
            "👉 <code>/feedback [your text]</code>\n"
            "<i>Example: /feedback I have a great tournament idea...</i>"
        )
    },
    "🇰🇿 Қазақша": {
        "find_match": "🔍 Матч іздеу",
        "end_match": "❌ Матчты аяқтау",
        "profile": "👤 Менің профилім",
        "top_players": "🏆 Топ ойыншылар",
        "rules": "📜 Ережелер",
        "welcome": "⚽ <b>eFootball Match Bot</b>\n\n🔥 Қош келдіңіз!\n📢 Каналымыз: @tova_efootball_bot_news",
        "already_in_match": "❌ Сіз қазір ойындасыз",
        "already_in_queue": "⏳ Сіз қарсылас іздеп жатырсыз",
        "searching": "🔎 Қарсылас іздеудеміз...",
        "found_host": "🟢 Match табылды! Сіз ХОСТсыз 🎮\n\nБөлме кодын ашып, қарсыласқа осы чатта жазыңыз!",
        "found_player": "🟡 Match табылды! Сіз ИГРОКсыз 🎮\n\nҚарсыластың бөлме кодын жіберуін күтіңіз!",
        "no_active_match": "❌ Сізде белсенді матч жоқ",
        "search_cancelled": "🛑 Іздеу тоқтатылды",
        "relay_prefix": "💬 Қарсылас:",
        "profile_text": "👤 <b>Сіздің профиліңіз:</b>\n\nАтыңыз: {name}\n🎮 Матчтар: <b>{matches}</b>\n✅ Жеңіс: {wins} | 🤝 Тең: {draws} | ❌ Жеңіліс: {losses}\n⚠️ Ескертулер (Warns): <b>{warns}/3</b>\n\n📊 <b>Бот статистикасы:</b>\n🟢 Ботта онлайн: <b>{online}</b>\n👥 Барлық ойыншылар: <b>{total}</b>",
        "top_title": "🏆 <b>ТОП ОЙЫНШЫЛАР (ЖЕҢІС САНЫ БОЙЫНША):</b>\n\n",
        "ask_score": "⚽ Матч аяқталды! Өтініш, өз тарапыңыздан болған матч есебін енгізіңіз.\nФормат: <code>3-2</code> немесе <code>3:2</code> (Бірінші ӨЗ голыңыз):",
        "bad_format": "❌ Қате формат! Есепті тек мына үлгіде жазыңыз: 2-1 немесе 2:1",
        "wait_opponent_score": "⏳ Сіздің есебіңіз қабылданды. Қарсыластың есеп енгізуін күтіңіз...",
        "score_mismatch": "⚠️ Есеп сәйкес келмеді! Сіз [{u_score}] енгіздіңіз, ал қарсылас басқаша жазды. Өз голдарыңызды бірінші қойып, қайта енгізіңіз:",
        "match_saved": "✅ Матч сәтті тіркелді! Есеп: {score}. Статистикаңыз жаңартылды!",
        "score_0_0": "❌ Ойын ойналмай бірден аяқталса (0-0), статистика есептелмейді.",
        "rules_text": (
            "📜 <b>БОТТЫҢ РЕСМИ ЕРЕЖЕЛЕРІ</b>\n\n"
            "1️⃣ <b>Әділ ойын (Fair Play):</b>\n"
            "Матч біткен соң екі ойыншы да есепті ТУРА енгізуі тиіс. Бірінші ӨЗІҢІЗДІҢ салған голыңыз жазылады.\n\n"
            "2️⃣ <b>Есепті енгізу форматы:</b>\n"
            "Есепті <code>2-1</code> немесе <code>2:1</code> форматында жазуға болады.\n\n"
            "3️⃣ <b>Алдамшылықтан қорғау:</b>\n"
            "Егер екі ойыншының есебі сәйкес келмесе, бот ұпай қоспайды.\n\n"
            "4️⃣ <b>Накруткаға тыйым салу:</b>\n"
            "Ойынды бастап, бірден <code>0-0</code> қылып аяқтай салуға болмайды.\n\n"
            "💡 <b>Сұрақтар, Идеялар мен Шағымдар:</b>\n"
            "Егер сізде ботқа қатысты сұрақтар немесе қызықты идеялар туындаса, админге тікелей жаза аласыз: {ADMIN_USERNAME}.\n\n"
            "Немесе боттың өзінде мына арнайы команда арқылы хабарлама жіберіңіз:\n"
            "👉 <code>/feedback [сіздің мәтініңіз]</code>\n"
            "<i>Үлгі: /feedback Менде турнир бойынша жаңа идея бар еді...</i>"
        )
    },
    "🇷🇺 Русский": {
        "find_match": "🔍 Поиск матча",
        "end_match": "❌ Завершить матч",
        "profile": "👤 Мой профиль",
        "top_players": "🏆 Top игроки",
        "rules": "📜 Правила",
        "welcome": "⚽ <b>eFootball Match Bot</b>\n\n🔥 Добро пожаловать!\n📢 Наш канал: @tova_efootball_bot_news",
        "already_in_match": "❌ Ты уже в матче",
        "already_in_queue": "⏳ Ты уже ищешь соперника",
        "searching": "🔎 Ищем соперника...",
        "found_host": "🟢 Match найден! Ты ХОСТ 🎮\n\nСоздай комнату и отправь код сопернику прямо сюда!",
        "found_player": "🟡 Match найден! Ты ИГКОК 🎮\n\nЖди код комнаты от соперника в этом чате!",
        "no_active_match": "❌ У тебя нет active матча",
        "search_cancelled": "🛑 Поиск отменен",
        "relay_prefix": "💬 Соперник:",
        "profile_text": "👤 <b>Твой профиль:</b>\n\nИмя: {name}\n🎮 Матчей: <b>{matches}</b>\n✅ Побед: {wins} | 🤝 Ничьих: {draws} | ❌ Поражений: {losses}\n⚠️ Предупреждения (Warns): <b>{warns}/3</b>\n\n📊 <b>Статистика бота:</b>\n🟢 В сети: <b>{online}</b>\n👥 Всего игроков: <b>{total}</b>",
        "top_title": "🏆 <b>ТОП ИГРОКОВ (ПО ПОБЕДАМ):</b>\n\n",
        "ask_score": "⚽ Match завершен! Пожалуйста, введите счет со своей стороны.\nFormat: <code>3-2</code> или <code>3:2</code> (Первым СВОИ голы):",
        "bad_format": "❌ Неверный формат! Введите счет в виде: 2-1 или 2:1",
        "wait_opponent_score": "⏳ Ваш счет принят. Ожидайте, пока соперник введет свой счет...",
        "score_mismatch": "⚠️ Счет не совпал! Вы ввели [{u_score}], а соперник ввел другие данные. Введите правильный счет заново (Свои голы первыми):",
        "match_saved": "✅ Матч успешно засчитан! Счет: {score}. Статистика обновлена!",
        "score_0_0": "❌ Если матч завершен без игры (0-0), статистика не начисляется.",
        "rules_text": (
            "📜 <b>ОФИЦИАЛЬНЫЕ ПРАВИЛА БОТА</b>\n\n"
            "1️⃣ <b>Честная игра (Fair Play):</b>\n"
            "После матча вводите СВОИ голы первыми.\n\n"
            "2️⃣ <b>Формат ввода счета:</b>\n"
            "Можно писать через дефис или двоеточие: <code>2-1</code> или <code>2:1</code>.\n\n"
            "3️⃣ <b>Защита от обмана:</b>\n"
            "Если счета игроков не сойдутся зеркально, бот потребует ввести счет заново.\n\n"
            "4️⃣ <b>Запрет на накрутку:</b>\n"
            "Запрещено завершать матч со счетом <code>0-0</code> ради накрутки.\n\n"
            "💡 <b>Вопросы, Идеи и Обратная связь:</b>\n"
            "Если у вас есть вопросы, жалобы или предложения, вы можете написать админу напрямую: {ADMIN_USERNAME}.\n\n"
            "Также вы можете отправить сообщение админу через встроенную команду прямо здесь:\n"
            "👉 <code>/feedback [ваше сообщение]</code>\n"
            "<i>Пример: /feedback У меня есть идея для улучшения системы топа...</i>"
        )
    }
}

# ---------------- KEYBOARDS ----------------
lang_keyboard = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="🇰🇿 Қазақша"), KeyboardButton(text="🇷🇺 Русский"), KeyboardButton(text="🇬🇧 English")]],
    resize_keyboard=True
)

def get_main_keyboard(lang: str) -> ReplyKeyboardMarkup:
    texts = LOCALIZATION.get(lang, LOCALIZATION["🇷🇺 Русский"])
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=texts["find_match"])],
            [KeyboardButton(text=texts["profile"]), KeyboardButton(text=texts["top_players"])],
            [KeyboardButton(text=texts["rules"])],  
            [KeyboardButton(text=texts["end_match"])]
        ],
        resize_keyboard=True
    )

# ---------------- USER FEEDBACK / SUGGESTIONS ----------------
@dp.message(Command("feedback"))
async def user_feedback(message: Message):
    user_id = message.from_user.id
    update_online(user_id)
    
    # Командадан кейінгі мәтінді дұрыс бөліп алу (артық бос орындарды trim/strip етеміз)
    args = message.text.split(maxsplit=1)
    feedback_text = args[1].strip() if len(args) > 1 else ""
    
    user_data = get_user(user_id)
    lang = user_data["language"] if user_data else "🇷🇺 Русский"
    
    if not feedback_text:
        if lang == "🇰🇿 Қазақша":
            await message.answer("❌ Мәтін бос! Үлгі:\n<code>/feedback Менде жаңа идея бар...</code>")
        elif lang == "🇬🇧 English":
            await message.answer("❌ Text is empty! Example:\n<code>/feedback I have an idea...</code>")
        else:
            await message.answer("❌ Текст пуст! Пример:\n<code>/feedback У меня есть идея...</code>")
        return
        
    user_display = f"@{message.from_user.username}" if message.from_user.username else f"User_{user_id}"
    admin_notif = f"💡 <b>ЖАҢА ИДЕЯ / СҰРАҚ (FEEDBACK)!</b>\n\n👤 Кімнен: {user_display} (ID: <code>{user_id}</code>)\n📝 Мәтіні: {feedback_text}"
    
    try:
        await bot.send_message(chat_id=ADMIN_ID, text=admin_notif)
        if lang == "🇰🇿 Қазақша":
            await message.answer("✅ Шағымыңыз/идеяңыз сәтті жіберілді! Админ міндетті түрде оқиды. Рахмет!")
        elif lang == "🇬🇧 English":
            await message.answer("✅ Your feedback has been sent successfully! The admin will read it. Thank you!")
        else:
            await message.answer("✅ Ваше сообщение/идея успешно отправлены! Админ обязательно прочитает. Спасибо!")
    except Exception as e:
        print(f"Feedback қатесі: {e}")
        await message.answer("❌ Қате кетті. Бот админіне тікелей жазыңыз.")

# ---------------- ADMIN EXPORT / IMPORT ----------------
@dp.message(Command("export_db"))
async def admin_export_db(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, username, language, matches_played, wins, draws, losses, is_banned, warns FROM users")
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        await message.answer("❌ База бос, экспорттайтын ештеңе жоқ.")
        return
        
    data_list = []
    for r in rows:
        data_list.append({
            "uid": r[0], "uname": r[1], "lang": r[2],
            "mp": r[3], "w": r[4], "d": r[5], "l": r[6],
            "ban": r[7], "warn": r[8]
        })
        
    json_text = json.dumps(data_list, ensure_ascii=False)
    await message.answer("📋 <b>БАЗА ДЕРЕКТЕРІНІҢ КӨШІРМЕСІ (EXPORT):</b>")
    await message.answer(f"<code>{json_text}</code>")

@dp.message(Command("import_db"))
async def admin_import_db(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        json_data_raw = message.text.replace("/import_db", "").strip()
        if not json_data_raw:
            await message.answer("❌ Қате формат! Бұлай жаз: `/import_db [экспортталған_мәтін]`")
            return
            
        data_list = json.loads(json_data_raw)
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        imported_count = 0
        for item in data_list:
            cursor.execute("""
                INSERT INTO users (user_id, username, language, matches_played, wins, draws, losses, is_banned, warns)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    username=excluded.username, language=excluded.language,
                    matches_played=excluded.matches_played, wins=excluded.wins,
                    draws=excluded.draws, losses=excluded.losses,
                    is_banned=excluded.is_banned, warns=excluded.warns
            """, (item["uid"], item["uname"], item["lang"], item["mp"], item["w"], item["d"], item["l"], item["ban"], item["warn"]))
            imported_count += 1
            
        conn.commit()
        conn.close()
        await message.answer(f"✅ <b>Импорт сәтті аяқталды!</b>\n📊 Базаға {imported_count} ойыншының статистикасы көшірілді.")
    except Exception as e:
        await message.answer(f"❌ Импорт кезінде қате кетті. Қате: {e}")

# ---------------- ADMIN CONTROL COMMANDS ----------------
@dp.message(Command("cancelmatch"))
async def admin_cancel_match(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        args = message.text.split()
        if len(args) < 2:
            await message.answer("❌ Қате формат!\nҮлгі: `/cancelmatch [Ойыншы_ID]`")
            return
            
        target_id = int(args[1])
        if target_id not in matches:
            await message.answer("❌ Бұл ойыншы қазір белсенді матчта емес.")
            return
            
        opponent_id = matches[target_id]
        
        ctx1 = dp.fsm.get_context(bot, chat_id=target_id, user_id=target_id)
        ctx2 = dp.fsm.get_context(bot, chat_id=opponent_id, user_id=opponent_id)
        await ctx1.clear()
        await ctx2.clear()
        
        score_votes.pop(target_id, None)
        score_votes.pop(opponent_id, None)
        matches.pop(target_id, None)
        matches.pop(opponent_id, None)
        
        await message.answer(f"✅ ID {target_id} және ID {opponent_id} арасындағы матч сәтті тоқтатылды.")
        
        try:
            await bot.send_message(target_id, "🛑 <b>Әкімші (Админ) сіздің ағымдағы матчыңызды тоқтатты (Отмена жасады).</b>")
            await bot.send_message(opponent_id, "🛑 <b>Әкімші (Админ) сіздің ағымдағы матчыңызды тоқтатты (Отмена жасады).</b>")
        except Exception:
            pass
    except Exception as e:
        await message.answer(f"❌ Қате орындалды: {e}")

@dp.message(Command("ban"))
async def admin_ban(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        target_id = int(message.text.split()[1])
        conn = sqlite3.connect(DB_FILE)
        conn.execute("UPDATE users SET is_banned = 1 WHERE user_id = ?", (target_id,))
        conn.commit()
        conn.close()
        await message.answer(f"🚫 Пайдаланушы ID {target_id} сәтті бұғатталды.")
        try:
            await bot.send_message(target_id, "❌ <b>Сіз бот ережесін бұзғаныңыз үшін админ тарапынан мәңгілікке БАН алдыңыз!</b>")
        except Exception:
            pass
    except Exception as e:
        await message.answer("❌ Қате формат! Мысалы: `/ban 123456789`")

@dp.message(Command("unban"))
async def admin_unban(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        target_id = int(message.text.split()[1])
        conn = sqlite3.connect(DB_FILE)
        conn.execute("UPDATE users SET is_banned = 0, warns = 0 WHERE user_id = ?", (target_id,))
        conn.commit()
        conn.close()
        await message.answer(f"✅ Пайдаланушы ID {target_id} бұғаттаудан шығарылды.")
        try:
            await bot.send_message(target_id, "🔓 <b>Админ сіздің бұғаттауыңызды ашты! Қайтадан ойнай аласыз.</b>")
        except Exception:
            pass
    except Exception as e:
        await message.answer("❌ Қате формат! Мысалы: `/unban 123456789`")

@dp.message(Command("warn"))
async def admin_warn(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        parts = message.text.split(maxsplit=2)
        target_id = int(parts[1])
        reason = parts[2] if len(parts) > 2 else "Себебі көрсетілмеген"
        
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET warns = warns + 1 WHERE user_id = ?", (target_id,))
        cursor.execute("SELECT warns FROM users WHERE user_id = ?", (target_id,))
        current_warns = cursor.fetchone()[0]
        
        if current_warns >= 3:
            cursor.execute("UPDATE users SET is_banned = 1 WHERE user_id = ?", (target_id,))
            conn.commit()
            conn.close()
            await message.answer(f"⚠️ ID {target_id} варн алды. Варн: {current_warns}/3.\n🛑 <b>Автоматты БАН!</b>")
            try:
                await bot.send_message(target_id, f"⚠️ <b>ВАРН берілді!</b>\n📝 Себебі: {reason}\n\n🛑 <b>Ескерту саны 3/3-ке жетті! БАН!</b>")
            except Exception:
                pass
        else:
            conn.commit()
            conn.close()
            await message.answer(f"⚠️ ID {target_id}-ге ескерту берілді. Варн саны: {current_warns}/3.")
            try:
                await bot.send_message(target_id, f"⚠️ <b>ВАРН берілді!</b>\n📝 Себебі: {reason}\n📉 Саны: <b>{current_warns}/3</b>.")
            except Exception:
                pass
    except Exception as e:
        await message.answer("❌ Қате формат! Мысалы: `/warn [ID] [Себебі]`")

@dp.message(Command("unwarn"))
async def admin_unwarn(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        target_id = int(message.text.split()[1])
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT warns FROM users WHERE user_id = ?", (target_id,))
        row = cursor.fetchone()
        
        if row:
            current_warns = max(0, row[0] - 1)
            cursor.execute("UPDATE warns FROM users WHERE user_id = ?", (current_warns, target_id))
            conn.commit()
            await message.answer(f"✅ ID {target_id}-ден 1 варн алынды. Варн: {current_warns}/3.")
        else:
            await message.answer("❌ Табылмады.")
        conn.close()
    except Exception as e:
        await message.answer("❌ Қате формат!")

@dp.message(Command("banlist"))
async def admin_banlist(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, username FROM users WHERE is_banned = 1")
    rows = cursor.fetchall()
    conn.close()
    if not rows:
        await message.answer("📋 <b>Банлист бос.</b>")
        return
    text = "🚫 <b>BANLIST:</b>\n\n"
    for idx, row in enumerate(rows, start=1):
        uid, uname = row
        display = f"@{uname}" if uname and not uname.isdigit() else "Жасырын"
        text += f"{idx}. ID: <code>{uid}</code> — {display}\n"
    await message.answer(text)

@dp.message(Command("warnlist"))
async def admin_warnlist(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, username, warns FROM users WHERE warns > 0 AND is_banned = 0")
    rows = cursor.fetchall()
    conn.close()
    if not rows:
        await message.answer("📋 <b>Ескертуі бар ойыншылар тізімі бос.</b>")
        return
    text = "⚠️ <b>WARNLIST:</b>\n\n"
    for idx, row in enumerate(rows, start=1):
        uid, uname, warns = row
        display = f"@{uname}" if uname and not uname.isdigit() else "Жасырын"
        text += f"{idx}. ID: <code>{uid}</code> — {display} | ВАРН: <b>{warns}/3</b>\n"
    await message.answer(text)

@dp.message(Command("setscore"))
async def admin_set_score(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        args = message.text.split()
        if len(args) < 4:
            await message.answer("❌ Үлгі: `/setscore [ID_1] [ID_2] [Есеп]`")
            return
        id1, id2 = int(args[1]), int(args[2])
        score = args[3].replace(":", "-")
        if not re.match(r"^\d+-\d+$", score):
            await message.answer("❌ Қате есеп форматы!")
            return
        g1, g2 = map(int, score.split("-"))
        if g1 > g2:
            update_stats(id1, "win"); update_stats(id2, "loss")
        elif g1 < g2:
            update_stats(id1, "loss"); update_stats(id2, "win")
        else:
            update_stats(id1, "draw"); update_stats(id2, "draw")
        await message.answer(f"✅ Тіркелді: ID {id1} [{g1}] - [{g2}] ID {id2}")
    except Exception as e:
        await message.answer(f"❌ Қате: {e}")

@dp.message(Command("broadcast"))
async def admin_broadcast(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    broadcast_text = message.text.replace("/broadcast", "").strip()
    if not broadcast_text:
        await message.answer("❌ Мәтін бос!")
        return
    user_ids = get_all_user_ids()
    await message.answer(f"📢 Рассылка басталды... (Барлығы: {len(user_ids)})")
    success, failed = 0, 0
    for uid in user_ids:
        try:
            await bot.send_message(chat_id=uid, text=broadcast_text)
            success += 1
            await asyncio.sleep(0.05)
        except Exception:
            failed += 1
    await message.answer(f"✅ Аяқталды!\n🟢 Сәтті: {success}\n🔴 Сәтсіз: {failed}")

@dp.message(Command("report"))
async def report_user(message: Message):
    user_id = message.from_user.id
    update_online(user_id)
    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        await message.answer("❌ Үлгі: `/report @username Себебі`")
        return
    reporter = f"@{message.from_user.username}" if message.from_user.username else f"User_{user_id}"
    target, reason = args[1], args[2]
    report_text = f"🚨 <b>ЖАҢА ШАҒЫМ!</b>\n\n💬 Кімнен: {reporter}\n🎯 Кімге: {target}\n📝 Себебі: {reason}"
    try:
        await bot.send_message(chat_id=ADMIN_ID, text=report_text)
        await message.answer("✅ Шағымыңыз админге жолданды!")
    except Exception:
        await message.answer("❌ Қате кетті.")

# ---------------- START & LANG ----------------
@dp.message(Command("start"))
async def start(message: Message, state: FSMContext):
    update_online(message.from_user.id)
    await state.clear()
    await message.answer("🌐 Тілді таңдаңыз / Выберите язык / Select language:", reply_markup=lang_keyboard)

@dp.message(F.text.in_({"🇰🇿 Қазақша", "🇷🇺 Русский", "🇬🇧 English"}))
async def set_language(message: Message):
    user_id = message.from_user.id
    update_online(user_id)
    username = message.from_user.username or message.from_user.first_name
    lang = message.text
    add_user(user_id, username, lang)
    await message.answer(text=LOCALIZATION[lang]["welcome"], reply_markup=get_main_keyboard(lang))

# ---------------- RULES BUTTON ----------------
@dp.message(F.text.in_({LOCALIZATION["🇰🇿 Қазақша"]["rules"], LOCALIZATION["🇷🇺 Русский"]["rules"], LOCALIZATION["🇬🇧 English"]["rules"]}))
async def show_rules(message: Message):
    user_id = message.from_user.id
    update_online(user_id)
    user_data = get_user(user_id)
    lang = user_data["language"] if user_data else "🇷🇺 Русский"
    await message.answer(LOCALIZATION[lang]["rules_text"])

# ---------------- PROFILE & TOP ----------------
@dp.message(F.text.in_({LOCALIZATION["🇰🇿 Қазақша"]["profile"], LOCALIZATION["🇷🇺 Русский"]["profile"], LOCALIZATION["🇬🇧 English"]["profile"]}))
async def show_profile(message: Message):
    user_id = message.from_user.id
    update_online(user_id)
    user_data = get_user(user_id)
    lang = user_data["language"] if user_data else "🇷🇺 Русский"
    texts = LOCALIZATION[lang]
    online_count = get_online_users_count()
    total_count = get_total_users_count()

    formatted_text = texts["profile_text"].format(
        name=message.from_user.first_name,
        matches=user_data["matches_played"] if user_data else 0,
        wins=user_data["wins"] if user_data else 0,
        draws=user_data["draws"] if user_data else 0,
        losses=user_data["losses"] if user_data else 0,
        warns=user_data["warns"] if user_data else 0,
        online=online_count,
        total=total_count
    )
    await message.answer(formatted_text)

@dp.message(F.text.in_({LOCALIZATION["🇰🇿 Қазақша"]["top_players"], LOCALIZATION["🇷🇺 Русский"]["top_players"], LOCALIZATION["🇬🇧 English"]["top_players"]}))
async def show_top(message: Message):
    user_id = message.from_user.id
    update_online(user_id)
    user_data = get_user(user_id)
    lang = user_data["language"] if user_data else "🇷🇺 Русский"
    texts = LOCALIZATION[lang]
    top_list = get_top_players()
    response = texts["top_title"]
    
    if not top_list:
        response += "📋 Список пуст / Тізім бос"
    else:
        for index, player in enumerate(top_list, start=1):
            username, wins, matches_count, p_id = player
            display_name = f"@{username}" if username and not username.isdigit() else f"User_{p_id}"
            medal = "🥇 " if index == 1 else "🥈 " if index == 2 else "🥉 " if index == 3 else f"{index}. "
            response += f"{medal}{display_name} — <b>{wins}</b> ({matches_count})\n"
    await message.answer(response)

# ---------------- FIND MATCH ----------------
@dp.message(F.text.in_({LOCALIZATION["🇰🇿 Қазақша"]["find_match"], LOCALIZATION["🇷🇺 Русский"]["find_match"], LOCALIZATION["🇬🇧 English"]["find_match"]}))
async def find_match(message: Message):
    user_id = message.from_user.id
    update_online(user_id)
    user_data = get_user(user_id)
    if user_data and user_data.get("is_banned", 0) == 1:
        await message.answer("❌ <b>Сіз бұғатталғансыз (БАН)!</b> Матч іздеу мүмкін емес.")
        return
    lang = user_data["language"] if user_data else "🇷🇺 Русский"
    texts = LOCALIZATION[lang]
    if user_id in matches:
        await message.answer(texts["already_in_match"]); return
    if user_id in queue:
        await message.answer(texts["already_in_queue"]); return

    async with lock:
        if queue:
            opponent = queue.pop(0)
            if opponent == user_id:
                queue.append(user_id)
                await message.answer(texts["searching"]); return
            matches[user_id] = opponent
            matches[opponent] = user_id
            host = random.choice([user_id, opponent])
            op_data = get_user(opponent)
            op_lang = op_data["language"] if op_data else "🇷🇺 Русский"
            u_chat = await bot.get_chat(user_id)
            o_chat = await bot.get_chat(opponent)
            u_name = f"@{u_chat.username}" if u_chat.username else u_chat.first_name
            o_name = f"@{o_chat.username}" if o_chat.username else o_chat.first_name

            if host == user_id:
                await bot.send_message(user_id, f"{texts['found_host']}\n\n🎮 <b>Соперник:</b> {o_name} (ID: {opponent})")
                await bot.send_message(opponent, f"{LOCALIZATION[op_lang]['found_player']}\n\n🎮 <b>Соперник:</b> {u_name} (ID: {user_id})")
            else:
                await bot.send_message(user_id, f"{texts['found_player']}\n\n🎮 <b>Соперник:</b> {o_name} (ID: {opponent})")
                await bot.send_message(opponent, f"{LOCALIZATION[op_lang]['found_host']}\n\n🎮 <b>Соперник:</b> {u_name} (ID: {user_id})")
        else:
            queue.append(user_id)
            await message.answer(texts["searching"])

# ---------------- END MATCH ----------------
@dp.message(F.text.in_({LOCALIZATION["🇰🇿 Қазақша"]["end_match"], LOCALIZATION["🇷🇺 Русский"]["end_match"], LOCALIZATION["🇬🇧 English"]["end_match"]}))
async def end_match_request(message: Message, state: FSMContext):
    user_id = message.from_user.id
    update_online(user_id)
    user_data = get_user(user_id)
    lang = user_data["language"] if user_data else "🇷🇺 Русский"
    texts = LOCALIZATION[lang]
    if user_id in queue:
        queue.remove(user_id); await message.answer(texts["search_cancelled"]); return
    if user_id not in matches:
        await message.answer(texts["no_active_match"]); return

    opponent = matches[user_id]
    op_data = get_user(opponent)
    op_lang = op_data["language"] if op_data else "🇷🇺 Русский"
    await state.set_state(MatchState.entering_score)
    op_context = dp.fsm.get_context(bot, chat_id=opponent, user_id=opponent)
    await op_context.set_state(MatchState.entering_score)
    await message.answer(texts["ask_score"])
    await bot.send_message(opponent, LOCALIZATION[op_lang]["ask_score"])

# ---------------- PROCESS SCORE ----------------
@dp.message(MatchState.entering_score)
async def process_score(message: Message, state: FSMContext):
    user_id = message.from_user.id
    update_online(user_id)
    user_data = get_user(user_id)
    lang = user_data["language"] if user_data else "🇷🇺 Русский"
    texts = LOCALIZATION[lang]
    if user_id not in matches:
        await state.clear(); return
    text = message.text.strip().replace(":", "-")
    if not re.match(r"^\d+-\d+$", text):
        await message.answer(texts["bad_format"]); return

    opponent = matches[user_id]
    op_data = get_user(opponent)
    op_lang = op_data["language"] if op_data else "🇷🇺 Русский"
    op_texts = LOCALIZATION[op_lang]
    score_votes[user_id] = text

    if opponent not in score_votes:
        await message.answer(texts["wait_opponent_score"]); return

    user_score, opponent_score = score_votes[user_id], score_votes[opponent]
    my_goals, his_goals = map(int, user_score.split("-"))
    op_my_goals, op_his_goals = map(int, opponent_score.split("-"))

    if my_goals == op_his_goals and his_goals == op_my_goals:
        if my_goals == 0 and his_goals == 0:
            await message.answer(texts["score_0_0"]); await bot.send_message(opponent, op_texts["score_0_0"])
        else:
            if my_goals > his_goals:
                update_stats(user_id, "win"); update_stats(opponent, "loss")
            elif my_goals < his_goals:
                update_stats(user_id, "loss"); update_stats(opponent, "win")
            else:
                update_stats(user_id, "draw"); update_stats(opponent, "draw")
            await message.answer(texts["match_saved"].format(score=user_score))
            await bot.send_message(opponent, op_texts["match_saved"].format(score=opponent_score))

        matches.pop(user_id, None); matches.pop(opponent, None)
        score_votes.pop(user_id, None); score_votes.pop(opponent, None)
        await state.clear()
        op_context = dp.fsm.get_context(bot, chat_id=opponent, user_id=opponent)
        await op_context.clear()
    else:
        score_votes.pop(user_id, None); score_votes.pop(opponent, None)
        await message.answer(texts["score_mismatch"].format(u_score=user_score))
        await bot.send_message(opponent, op_texts["score_mismatch"].format(u_score=opponent_score))

# ---------------- RELAY CHAT ----------------
@dp.message()
async def relay(message: Message, state: FSMContext):
    user_id = message.from_user.id
    update_online(user_id)
    if user_id not in matches:
        return
    current_state = await state.get_state()
    if current_state == MatchState.entering_score:
        return
    opponent = matches[user_id]
    op_data = get_user(opponent)
    op_lang = op_data["language"] if op_data else "🇷🇺 Русский"
    try:
        if message.text:
            await bot.send_message(opponent, f"{LOCALIZATION[op_lang]['relay_prefix']}\n{message.text}")
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

if __name__ == "__main__":
    asyncio.run(main())
