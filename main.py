import asyncio
import aiohttp
from maxapi import Bot, Dispatcher
from maxapi.types import MessageCreated

GAS_URL = "https://script.google.com/macros/s/XXXXX/exec"

bot = Bot(token="ВАШ_ТОКЕН_БОТА_MAX")
dp = Dispatcher()

@dp.message_created()
async def handle_message(event: MessageCreated):
    sender = event.message.sender
    
    # Собираем имя из доступных полей
    first_name = getattr(sender, 'first_name', '') or ''
    last_name = getattr(sender, 'last_name', '') or ''
    user_name = f"{first_name} {last_name}".strip() or "Без имени"
    
    user_id = sender.user_id
    text = event.message.body.text

    payload = {
        "user_id": str(user_id),
        "user_name": user_name,
        "phone": "",
        "message": text
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(GAS_URL, json=payload) as resp:
            result = await resp.json()
            print(f"Ответ GAS: {result}")

    await event.message.answer("Заявка принята! ✅")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
