import os
import asyncio
import aiohttp
from maxapi import Bot, Dispatcher
from maxapi.types import MessageCreated, MessageCallback, CommandStart
from maxapi.types.attachments.buttons import CallbackButton
from maxapi.utils.inline_keyboard import InlineKeyboardBuilder

GAS_URL = os.environ["GAS_URL"]
TOKEN = os.environ["MAX_BOT_TOKEN"].strip()

bot = Bot(token=TOKEN)
dp = Dispatcher()

states = {}
processed_ids = set()


def units_keyboard():
    """Inline-клавиатура выбора подразделения."""
    builder = InlineKeyboardBuilder()
    builder.row(
        CallbackButton(text="АХО", payload="unit:АХО"),
        CallbackButton(text="СГИ", payload="unit:СГИ"),
    )
    builder.row(
        CallbackButton(text="ДП", payload="unit:ДП"),
        CallbackButton(text="ОИТ", payload="unit:ОИТ"),
    )
    return builder.as_markup()


def main_menu_keyboard():
    """Клавиатура главного меню."""
    builder = InlineKeyboardBuilder()
    builder.row(CallbackButton(text="📝 Создать заявку", payload="start_form"))
    return builder.as_markup()


@dp.message_created(CommandStart())
async def cmd_start(event: MessageCreated):
    uid = event.message.sender.user_id
    states.pop(uid, None)
    await event.message.answer(
        "Главное меню:",
        attachments=[main_menu_keyboard()],
    )


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

    print(f"UID={uid} STEP={st['step']} TEXT={text!r}")

    # Ввод ФИО
    if st["step"] == "fio":
        st["data"]["fio"] = text
        st["step"] = "target"
        await event.message.answer(
            "Куда направить заявку?",
            attachments=[units_keyboard()],
        )
        return

    # Ввод текста обращения
    if st["step"] == "text":
        st["data"]["message"] = text
        payload = {
            "user_id": str(uid),
            "department": st["data"].get("department", ""),
            "fio": st["data"].get("fio", ""),
            "target": st["data"].get("target", ""),
            "message": st["data"].get("message", ""),
        }

        try:
    async with aiohttp.ClientSession() as session:
        # 1. Отправляем POST, но НЕ следуем за редиректом автоматически
        async with session.post(
            GAS_URL, 
            json=payload, 
            headers={"X-Secret": os.environ["GAS_SECRET"]},
            allow_redirects=False
        ) as resp:
            print(f"Статус GAS (POST): {resp.status}")
            
            # 2. Если пришёл редирект (302, 303, 307) — идём по нему вручную через GET
            if resp.status in (301, 302, 303, 307, 308):
                location = resp.headers.get("Location")
                print(f"Редирект на: {location}")
                if location:
                    # 3. Выполняем GET по адресу редиректа, чтобы получить ответ от doPost
                    async with session.get(location) as final_resp:
                        print(f"Статус GAS (GET): {final_resp.status}")
                        print(f"Ответ GAS: {(await final_resp.text())[:300]}")
            else:
                # Если редиректа нет — читаем ответ сразу
                print(f"Ответ GAS: {(await resp.text())[:300]}")
except Exception as e:
    print(f"Ошибка отправки в GAS: {e}")

        states.pop(uid, None)
        await event.message.answer("✅ Ваша заявка принята.")
        return

    # Всё остальное вне диалога
    await event.message.answer(
        "Нажмите «📝 Создать заявку», чтобы оставить обращение.",
        attachments=[main_menu_keyboard()],
    )


@dp.message_callback()
async def on_callback(event: MessageCallback):
    print("=== CALLBACK ПОЛУЧЕН ===", event.model_dump())
    payload = (event.callback.payload or "") if hasattr(event, "callback") else ""

    # Достаём user_id из разных возможных мест
    uid = None
    for attr in ("user", "sender", "from_user"):
        obj = getattr(event, attr, None)
        if obj and hasattr(obj, "user_id"):
            uid = obj.user_id
            break
    if uid is None and hasattr(event, "message"):
        msg_sender = getattr(event.message, "sender", None)
        if msg_sender and hasattr(msg_sender, "user_id"):
            uid = msg_sender.user_id

    if uid is None:
        print("CALLBACK без user_id:", event.model_dump())
        return

    st = states.setdefault(uid, {"step": None, "data": {}})

    # Первый шаг: «Создать заявку»
    if payload == "start_form":
        st["step"] = "department"
        st["data"] = {}
        await event.message.answer(
            "Ваше подразделение?",
            attachments=[units_keyboard()],
        )
        await _safe_answer(event)
        return

    # Выбор подразделения или направления
    if payload.startswith("unit:"):
        unit = payload.split(":", 1)[1]

        if st["step"] == "department":
            st["data"]["department"] = unit
            st["step"] = "fio"
            await event.message.answer("Введите Ваше ФИО:")
            await _safe_answer(event)
            return

        if st["step"] == "target":
            st["data"]["target"] = unit
            st["step"] = "text"
            await event.message.answer("Введите текст обращения:")
            await _safe_answer(event)
            return

    await _safe_answer(event)


async def _safe_answer(event):
    """Гасим callback, если метод есть."""
    try:
        await event.answer()
    except Exception as e:
        print(f"event.answer ошибка: {e}")


async def main():
    print("Токен найден, длина:", len(TOKEN))
    print("GAS_URL длина:", len(GAS_URL))
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
