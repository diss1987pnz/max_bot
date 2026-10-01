import os
import asyncio
import aiohttp
from maxapi import Bot, Dispatcher
from maxapi.types import MessageCreated

GAS_URL = os.environ["GAS_URL"]
TOKEN = os.environ["MAX_BOT_TOKEN"].strip()

bot = Bot(token=TOKEN)
dp = Dispatcher()
processed_ids = set()

@dp.message_created()
async def handle_message(event: MessageCreated):
    sender = event.message.sender

    if getattr(sender, "is_bot", False):
        return

    msg_id = getattr(event.message, "message_id", None)
    if msg_id and msg_id in processed_ids:
        return
    if msg_id:
        processed_ids.add(msg_id)

    first_name = getattr(sender, "first_name", "") or ""
    last_name = getattr(sender, "last_name", "") or ""
    user_name = f"{first_name} {last_name}".strip() or "Без имени"

    payload = {
        "user_id": str(sender.user_id),
        "user_name": user_name,
        "phone": "",
        "message": event.message.body.text,
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(GAS_URL, json=payload) as resp:
            print(f"Статус GAS: {resp.status}")
            print(f"Ответ GAS: {(await resp.text())[:300]}")

    await event.message.answer("Заявка принята! ✅")

async def main():
    print("Токен найден, длина:", len(TOKEN))
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
