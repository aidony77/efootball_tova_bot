# Чтобы при пересылке текста сохранялся язык получателя
    op_lang = user_languages.get(opponent, "🇷🇺 Русский")
    op_texts = LOCALIZATION[op_lang]

    try:
        if message.text:
            # Префикс "Соперник:" на языке получателя
            await bot.send_message(opponent, f"{op_texts['relay_prefix']}\n{message.text}")
        else:
            # Фотографии или стикеры пересылаются как есть
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
