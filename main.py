import os
import asyncio
import aiohttp
from maxapi import Bot, Dispatcher
from maxapi.types import MessageCreated, MessageCallback, CommandStart
from maxapi.types.attachments.buttons import CallbackButton
from maxapi.utils.inline_keyboard import InlineKeyboardBuilder

GAS_URL = os.environ["GAS_URL"]
GAS_SECRET = os.environ["GAS_SECRET"]
TOKEN = os.environ["MAX_BOT_TOKEN"].strip()

bot = Bot(token=TOKEN)
dp = Dispatcher()

states = {}
processed_ids = set()


def units_keyboard():
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


def target_keyboard():
    builder = InlineKeyboardBuilder()
    builder.row(
        CallbackButton(text="АХО", payload="target:АХО"),
        CallbackButton(text="Тимуровцы", payload="target:Тимуровцы"),
    )
    return builder.as_markup()


def photo_keyboard():
    builder = InlineKeyboardBuilder()
    builder.row(
        CallbackButton(text="📎 Прикрепить фото", payload="photo:attach"),
    )
    builder.row(
        CallbackButton(text="⏭ Пропустить и отправить заявку", payload="photo:skip"),
    )
    return builder.as_markup()


def main_menu_keyboard():
    builder = InlineKeyboardBuilder()
    builder.row(CallbackButton(text="📝 Создать заявку", payload="start_form"))
    return builder.as_markup()


def extract_photo_url(event):
    """Пытается извлечь URL фото/файла из сообщения MAX."""
    try:
        body = event.message.body
        attachments = getattr(body, "attachments", None)
        if attachments:
            for att in attachments:
                url = getattr(att, "url", None)
                if url:
                    return url
                payload = getattr(att, "payload", None)
                if payload:
                    url = getattr(payload, "url", None)
                    if url:
                        return url
                    photos = getattr(payload, "photos", None) or getattr(payload, "images", None)
                    if photos and isinstance(photos, list) and photos:
                        last = photos[-1]
                        url = getattr(last, "url", None)
                        if url:
                            return url
    except Exception as e:
        print(f"Ошибка извлечения фото: {e}")
    return None


async def submit_to_gas(uid, st, event):
    """Отправляет заявку в GAS и отвечает пользователю."""
    payload = {
        "user_id": str(uid),
        "department": st["data"].get("department", ""),
        "fio": st["data"].get("fio", ""),
        "target": st["data"].get("target", ""),
        "message": st["data"].get("message", ""),
        "photo_url": st["data"].get("photo_url", ""),
        "secret": GAS_SECRET,
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                GAS_URL,
                json=payload,
                allow_redirects=False,
            ) as resp:
                print(f"Статус GAS (POST): {resp.status}")
                if resp.status in (301, 302, 303, 307, 308):
                    location = resp.headers.get("Location")
                    print(f"Редирект на: {location}")
                    if location:
                        async with session.get(location) as final_resp:
                            print(f"Статус GAS (GET): {final_resp.status}")
                            print(f"Ответ GAS: {(await final_resp.text())[:300]}")
                else:
                    print(f"Ответ GAS: {(await resp.text())[:300]}")
    except Exception as e:
        print(f"Ошибка отправки в GAS: {e}")

    states.pop(uid, None)
    await event.message.answer("✅ Ваша заявка принята.")


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

    # Шаг «ФИО»
    if st["step"] == "fio":
        if not text:
            await event.message.answer("Пожалуйста, введите ФИО текстом.")
            return
        st["data"]["fio"] = text
        st["step"] = "target"
        await event.message.answer(
            "Куда направить заявку?",
            attachments=[target_keyboard()],
        )
        return

    # Шаг «Текст обращения»
    if st["step"] == "text":
        if not text:
            await event.message.answer("Пожалуйста, введите текст обращения.")
            return
        st["data"]["message"] = text
        st["step"] = "photo"
        await event.message.answer(
            "Прикрепите фото\\файлы при необходимости:",
            attachments=[photo_keyboard()],
        )
        return

    # Шаг «Фото» — ждём фото после нажатия «Прикрепить фото»
    if st["step"] == "photo_wait":
        photo_url = extract_photo_url(event)
        if not photo_url:
            try:
                print("DEBUG BODY:", event.message.body.model_dump())
            except Exception:
                print("DEBUG BODY:", event.message.body)
            await event.message.answer(
                "Не удалось распознать фото. Отправьте картинку ещё раз "
                "или нажмите «⏭ Пропустить и отправить заявку»."
            )
            return
        st["data"]["photo_url"] = photo_url
        await submit_to_gas(uid, st, event)
        return

    # Вне диалога
    await event.message.answer(
        "Нажмите «📝 Создать заявку», чтобы оставить обращение.",
        attachments=[main_menu_keyboard()],
    )


@dp.message_callback()
async def on_callback(event: MessageCallback):
    payload = (event.callback.payload or "") if hasattr(event, "callback") else ""

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

    # Старт формы
    if payload == "start_form":
        st["step"] = "department"
        st["data"] = {}
        await event.message.answer(
            "Ваше подразделение?",
            attachments=[units_keyboard()],
        )
        await _safe_answer(event)
        return

    # Выбор своего подразделения
    if payload.startswith("unit:"):
        unit = payload.split(":", 1)[1]
        if st["step"] == "department":
            st["data"]["department"] = unit
            st["step"] = "fio"
            await event.message.answer("Введите Ваше ФИО:")
            await _safe_answer(event)
            return

    # Выбор, куда направить
    if payload.startswith("target:"):
        target = payload.split(":", 1)[1]
        if st["step"] == "target":
            st["data"]["target"] = target
            st["step"] = "text"
            await event.message.answer("Введите текст обращения:")
            await _safe_answer(event)
            return

    # Фото: прикрепить
    if payload == "photo:attach" and st["step"] == "photo":
        st["step"] = "photo_wait"
        await event.message.answer("Отправьте фото или файл следующим сообщением.")
        await _safe_answer(event)
        return

    # Фото: пропустить и отправить
    if payload == "photo:skip" and st["step"] == "photo":
        st["data"]["photo_url"] = ""
        await submit_to_gas(uid, st, event)
        await _safe_answer(event)
        return

    await _safe_answer(event)


async def _safe_answer(event):
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
