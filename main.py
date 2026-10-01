import os
import asyncio
import aiohttp
from maxapi import Bot, Dispatcher
from maxapi.types import MessageCreated

GAS_URL = os.environ.get("GAS_URL", "https://script.google.com/macros/s/AKfycbwwJ3ya_wBShs2g8dak3-zou7cX5KKoXH-o9gYi3wUf7Cft1iik9InoBpGzDAMZ733tWQ/exec")
TOKEN = os.environ["f9LHodD0cOLoKMEsXK-CSol125sjE3325sA-02K30aNIj2R41j8npK8S2G60J2cl8JADQZ4SB64Uq2OVbhTn"].strip()

bot = Bot(token=TOKEN)
dp = Dispatcher()

@dp.message_created()
async def handle_message(event: MessageCreated):
    sender = event.message.sender
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
            print("Ответ GAS:", await resp.json())

    await event.message.answer("Заявка принята! ✅")

async def main():
    print("Токен найден, длина:", len(TOKEN))
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
