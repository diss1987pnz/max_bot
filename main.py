import asyncio
import aiohttp
from maxapi import Bot, Dispatcher
from maxapi.types import MessageCreated

# URL веб-приложения из Шага 1
GAS_URL = "https://script.google.com/macros/s/AKfycbwwJ3ya_wBShs2g8dak3-zou7cX5KKoXH-o9gYi3wUf7Cft1iik9InoBpGzDAMZ733tWQ/exec"
bot = Bot(token="f9LHodD0cOLoKMEsXK-CSol125sjE3325sA-02K30aNIj2R41j8npK8S2G60J2cl8JADQZ4SB64Uq2OVbhTn")
dp = Dispatcher()

@dp.message_created()
async def handle_message(event: MessageCreated):
    # Извлекаем данные из сообщения
    user_id = event.message.sender.user_id
    user_name = event.message.sender.name
    text = event.message.body.text

    # Формируем данные для отправки
    payload = {
        "user_id": str(user_id),
        "user_name": user_name,
        "phone": "",           # Сюда можно добавить логику сбора телефона
        "message": text
    }

    # Отправляем POST-запрос в Google Apps Script
    async with aiohttp.ClientSession() as session:
        async with session.post(GAS_URL, json=payload) as resp:
            result = await resp.json()
            print(f"Ответ GAS: {result}")

    await event.message.answer("Заявка принята! ✅")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
