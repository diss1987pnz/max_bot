from maxapi.types.attachments.buttons import Button, CallbackButton, MessageButton
import inspect

print("Button fields:", Button.model_fields)
print("CallbackButton fields:", CallbackButton.model_fields)
print("MessageButton fields:", MessageButton.model_fields)
raise SystemExit
import os
import asyncio
import aiohttp
from maxapi import Bot, Dispatcher
from maxapi.types import MessageCreated, MessageCallback, CommandStart
from maxapi.types.attachments.buttons import Button, CallbackButton

GAS_URL = os.environ["GAS_URL"]
TOKEN = os.environ["MAX_BOT_TOKEN"].strip()

bot = Bot(token=TOKEN)
dp = Dispatcher()

# Состояния храним в словаре: user_id -> {"step": ..., "data": {...}}
states = {}
processed_ids = set()


def units_keyboard():
    """Клавиатура выбора подразделения (inline, с payload)."""
    return [
        [CallbackButton(text="АХО", payload="unit:АХО"),
         CallbackButton(text="СГИ", payload="unit:СГИ")],
        [CallbackButton(text="ДП",  payload="unit:ДП"),
         CallbackButton(text="ОИТ", payload="unit:ОИТ")],
    ]


@dp.message_created(CommandStart())
async def cmd_start(event: MessageCreated):
    uid = event.message.sender.user_id
    states.pop(uid, None)
    keyboard = [
        [Button(text="📝 Создать заявку")],
    ]
    await event.message.answer("Главное меню:", keyboard=keyboard)


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

    uid = sender.user_id
    text = (event.message.body.text or "").strip()
    st = states.setdefault(uid, {"step": None, "data": {}})

    # Шаг 1: нажали «Создать заявку»
    if text == "📝 Создать заявку":
        st["step"] = "department"
        await event.message.answer(
            "Ваше подразделение?",
            keyboard=units_keyboard(),
        )
        return

    # Шаг 3: ввод ФИО
    if st["step"] == "fio":
        st["data"]["fio"] = text
        st["step"] = "target"
        await event.message.answer(
            "Куда направить заявку?",
            keyboard=units_keyboard(),
        )
        return

    # Шаг 5: ввод текста обращения
    if st["step"] == "text":
        st["data"]["message"] = text
        payload = {
            "user_id": str(uid),
            "department": st["data"].get("department", ""),
            "fio": st["data"].get("fio", ""),
            "target": st["data"].get("target", ""),
            "message": st["data"].get("message", ""),
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(GAS_URL, json=payload) as resp:
                print(f"Статус GAS: {resp.status}")
                print(f"Ответ GAS: {(await resp.text())[:300]}")

        states.pop(uid, None)
        await event.message.answer("✅ Ваша заявка принята.")
        return

    # Вне диалога
    await event.message.answer(
        "Нажмите «📝 Создать заявку», чтобы оставить обращение."
    )


@dp.message_callback()
async def on_callback(event: MessageCallback):
    payload = event.callback.payload or ""
    uid = event.message.sender.user_id if hasattr(event, "message") else None
    # ID пользователя из callback — уточните, где он лежит в вашей версии:
    # возможно event.callback.user.user_id или event.user.user_id
    # Ниже — универсальная попытка:
    if uid is None:
        for attr in ("user", "sender"):
            obj = getattr(event, attr, None)
            if obj and hasattr(obj, "user_id"):
                uid = obj.user_id
                break

    st = states.setdefault(uid, {"step": None, "data": {}})

    if payload.startswith("unit:"):
        unit = payload.split(":", 1)[1]

        if st["step"] == "department":
            st["data"]["department"] = unit
            st["step"] = "fio"
            await event.message.answer("Введите Ваше ФИО:")
            await event.answer()
            return

        if st["step"] == "target":
            st["data"]["target"] = unit
            st["step"] = "text"
            await event.message.answer("Введите текст обращения:")
            await event.answer()
            return

    await event.answer()


async def main():
    print("Токен найден, длина:", len(TOKEN))
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
