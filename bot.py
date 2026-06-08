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
