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

# ---------------- CONFIG & ADMIN ----------------
TOKEN = os.getenv("TOKEN")
ADMIN_ID = 8093382664  # Сенің Telegram ID-ің

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
            is_banned INTEGER DEFAULT 0
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
    if row:
        return {
            "language": row[0], 
            "matches_played": row[1], 
            "wins": row[2], 
            "draws": row[3], 
            "losses": row[4],
            "is_banned": row[5]
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
        "profile_text": "👤 <b>Your Profile:</b>\n\nName: {name}\n🎮 Matches: <b>{matches}</b>\n✅ Wins: {wins} | 🤝 Draws: {draws} | ❌ Losses: {losses}\n\n📊 <b>Bot Statistics:</b>\n🟢 Online: <b>{online}</b>\n👥 Total Players: <b>{total}</b>",
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
            "You can enter the score using a hyphen or a colon: <code>2-1</code> or <code>2:1</code>. Do not write any extra words. If you lost, you can enter the score accordingly (e.g., 1-3).\n\n"
            "3️⃣ <b>Anti-Cheat System:</b>\n"
            "If the entered scores do not match each other inversely, the bot will reject the entry. If your opponent is lying, take a screenshot and contact the admin.\n\n"
            "4️⃣ <b>No Match Fixing / Boosting:</b>\n"
            "It is strictly forbidden to immediately end a match with a <code>0-0</code> score just to boost your match count. Such matches will not grant any stats.\n\n"
            "5️⃣ <b>Respect:</b>\n"
            "Any insults or toxic behavior towards your opponent via the bot chat will result in a permanent BAN.\n\n"
            "📢 Tournament Channel: kpl_efootball_tournament\n"
            "📢 Bot News: @tova_efootball_bot_news"
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
        "found_host": "🟢 Матч табылды! Сіз ХОСТсыз 🎮\n\nБөлме кодын ашып, қарсыласқа осы чатта жазыңыз!",
        "found_player": "🟡 Матч табылды! Сіз ИГРОКсыз 🎮\n\nҚарсыластың бөлме кодын жіберуін күтіңіз!",
        "no_active_match": "❌ Сізде белсенді матч жоқ",
        "search_cancelled": "🛑 Іздеу тоқтатылды",
        "relay_prefix": "💬 Қарсылас:",
        "profile_text": "👤 <b>Сіздің профиліңіз:</b>\n\nАтыңыз: {name}\n🎮 Матчтар: <b>{matches}</b>\n✅ Жеңіс: {wins} | 🤝 Тең: {draws} | ❌ Жеңіліс: {losses}\n\n📊 <b>Бот статистикасы:</b>\n🟢 Ботта онлайн: <b>{online}</b>\n👥 Барлық ойыншылар: <b>{total}</b>",
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
            "Есепті <code>2-1</code> немесе <code>2:1</code> форматында жазуға болады. Басқа артық сөз жазуға болмайды. Егер сіз ұтылсаңыз, есепті керісінше жазуға болады (мысалы, 1-3).\n\n"
            "3️⃣ <b>Алдамшылықтан қорғау:</b>\n"
            "Егер екі ойыншының есебі бір-біріне айналы (зеркально) сәйкес келмесе, бот ұпай қоспайды. Қарсылас өтірік жазса, скриншотпен админге хабарласыңыз.\n\n"
            "4️⃣ <b>Накруткаға тыйым салу:</b>\n"
            "Ойынды бастап, бірден <code>0-0</code> қылып аяқтай салуға болмайды. Ондай матчтар есептелмейді.\n\n"
            "5️⃣ <b>Сыйластық:</b>\n"
            "Чатта қарсыласты балағаттаған немесе балағат сөз жазған ойыншы боттан мәңгілікке БАН алады.\n\n"
            "📢 Турнир арнасы: kpl_efootball_tournament\n"
            "📢 Бот жаңалықтары: @tova_efootball_bot_news"
        )
    },
    "🇷🇺 Русский": {
        "find_match": "🔍 Поиск матча",
        "end_match": "❌ Завершить матч",
        "profile": "👤 Мой профиль",
        "top_players": "🏆 Топ игроки",
        "rules": "📜 Правила",
        "welcome": "⚽ <b>eFootball Match Bot</b>\n\n🔥 Добро пожаловать!\n📢 Наш канал: @tova_efootball_bot_news",
        "already_in_match": "❌ Ты уже в матче",
        "already_in_queue": "⏳ Ты уже ищешь соперника",
        "searching": "🔎 Ищем соперника...",
        "found_host": "🟢 Match найден! Ты ХОСТ 🎮\n\nСоздай комнату и отправь код сопернику прямо сюда!",
        "found_player": "🟡 Match найден! Ты ИГРОК 🎮\n\nЖди код комнаты от соперника в этом чате!",
        "no_active_match": "❌ У тебя нет активного матча",
        "search_cancelled": "🛑 Поиск отменен",
        "relay_prefix": "💬 Соперник:",
        "profile_text": "👤 <b>Твой профиль:</b>\n\nИмя: {name}\n🎮 Матчей: <b>{matches}</b>\n✅ Побед: {wins} | 🤝 Ничьих: {draws} | ❌ Поражений: {losses}\n\n📊 <b>Статистика бота:</b>\n🟢 В сети: <b>{online}</b>\n👥 Всего игроков: <b>{total}</b>",
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
            "После матча вводите ЧЕСТНЫЙ счет. Первым всегда указываются СВОИ голы.\n\n"
            "2️⃣ <b>Формат ввода счета:</b>\n"
            "Можно писать через дефис или двоеточие: <code>2-1</code> или <code>2:1</code>. Без лишних слов и символов. Если вы проиграли, счет можно ввести наоборот (например, 1-3).\n\n"
            "3️⃣ <b>Защита от обмана:</b>\n"
            "Если счета игроков не сойдутся зеркально, бот потребует ввести счет заново. В случае намеренного обмана пишите админу.\n\n"
            "4️⃣ <b>Запрет на накрутку:</b>\n"
            "Запрещено сразу завершать матч со счетом <code>0-0</code> ради накрутки матчей. Такие игры не засчитываются.\n\n"
            "5️⃣ <b>Уважение:</b>\n"
            "За оскорбление соперника через чат бота — мгновенный и вечный БАН.\n\n"
            "📢 Канал турнира: kpl_efootball_tournament\n"
            "📢 Новости бота: @tova_efootball_bot_news"
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

# ---------------- ADMIN COMMANDS ----------------
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
        await message.answer(f"🚫 Пайдаланушы ID {target_id} сәтті бұғатталды (БАН).")
    except Exception as e:
        await message.answer("❌ Қате формат! Мысалы: `/ban 123456789`")

@dp.message(Command("setscore"))
async def admin_set_score(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        args = message.text.split()
        id1 = int(args[1])
        id2 = int(args[2])
        score = args[3].replace(":", "-")
        
        g1, g2 = map(int, score.split("-"))
        if g1 > g2:
            update_stats(id1, "win")
            update_stats(id2, "loss")
        elif g1 < g2:
            update_stats(id1, "loss")
            update_stats(id2, "win")
        else:
            update_stats(id1, "draw")
            update_stats(id2, "draw")
            
        await message.answer(f"✅ Матч есебі админ арқылы жазылды!\nID {id1} ({g1}) - ({g2}) ID {id2}")
    except Exception as e:
        await message.answer("❌ Қате формат! Мысалы: `/setscore [id1] [id2] [3-1]`")

@dp.message(Command("report"))
async def report_user(message: Message):
    user_id = message.from_user.id
    update_online(user_id)
    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        await message.answer("❌ Қате формат!\nҮлгі: `/report @username Себебін жазыңыз`")
        return
        
    reporter = f"@{message.from_user.username}" if message.from_user.username else f"User_{user_id}"
    target = args[1]
    reason = args[2]
    
   report_text = f"🚨 <b>ЖАҢА ШАҒЫМ (REPORT)!</b>\n\n💬 Кімнен: {reporter} (ID: {user_id})\n🎯 Кімге: {target}\n📝 Себебі: {reason}"
    try:
        await bot.send_message(chat_id=ADMIN_ID, text=report_text)
        await message.answer("✅ Шағымыңыз қабылданды және әкімшіге (админге) жолданды. Тексеріс жүргізіледі!")
    except Exception as e:
        await message.answer("❌ Шағым жіберу кезінде қате кетті.")

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
        queue.remove(user_id)
        await message.answer(texts["search_cancelled"])
        return

    if user_id not in matches:
        await message.answer(texts["no_active_match"])
        return

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
        await state.clear()
        return

    text = message.text.strip()
    text = text.replace(":", "-")

    if not re.match(r"^\d+-\d+$", text):
        await message.answer(texts["bad_format"])
        return

    opponent = matches[user_id]
    op_data = get_user(opponent)
    op_lang = op_data["language"] if op_data else "🇷🇺 Русский"
    op_texts = LOCALIZATION[op_lang]

    score_votes[user_id] = text

    if opponent not in score_votes:
        await message.answer(texts["wait_opponent_score"])
        return

    user_score = score_votes[user_id]
    opponent_score = score_votes[opponent]

    my_goals, his_goals = map(int, user_score.split("-"))
    op_my_goals, op_his_goals = map(int, opponent_score.split("-"))

    if my_goals == op_his_goals and his_goals == op_my_goals:
        if my_goals == 0 and his_goals == 0:
            await message.answer(texts["score_0_0"])
            await bot.send_message(opponent, op_texts["score_0_0"])
        else:
            if my_goals > his_goals:
                update_stats(user_id, "win")
                update_stats(opponent, "loss")
            elif my_goals < his_goals:
                update_stats(user_id, "loss")
                update_stats(opponent, "win")
            else:
                update_stats(user_id, "draw")
                update_stats(opponent, "draw")

            await message.answer(texts["match_saved"].format(score=user_score))
            await bot.send_message(opponent, op_texts["match_saved"].format(score=opponent_score))

        matches.pop(user_id, None)
        matches.pop(opponent, None)
        score_votes.pop(user_id, None)
        score_votes.pop(opponent, None)
        
        await state.clear()
        op_context = dp.fsm.get_context(bot, chat_id=opponent, user_id=opponent)
        await op_context.clear()
    else:
        score_votes.pop(user_id, None)
        score_votes.pop(opponent, None)
        
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
