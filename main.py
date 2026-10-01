import os
import asyncio
import aiohttp
from maxapi import Bot, Dispatcher
from maxapi.types import MessageCreated, MessageCallback, CommandStart
from maxapi.types.attachments.buttons import (
    Keyboard, Button,
    InlineKeyboard, CallbackButton,
)
from maxapi.context import MemoryContext, State, StatesGroup

GAS_URL = os.environ["GAS_URL"]
TOKEN = os.environ["MAX_BOT_TOKEN"].strip()

bot = Bot(token=TOKEN)
dp = Dispatcher()
processed_ids = set()


# ─── Состояния ───────────────────────────────────────────────
class Form(StatesGroup):
    department = State()   # выбор своего подразделения
    fio = State()          # ввод ФИО
    target = State()       # выбор, куда направить
    text = State()         # текст обращения


# ─── Клавиатура с 4 подразделениями ──────────────────────────
def units_keyboard() -> InlineKeyboard:
    return InlineKeyboard(buttons=[
        [CallbackButton(text="АХО", payload="unit:АХО"),
         CallbackButton(text="СГИ", payload="unit:СГИ")],
        [CallbackButton(text="ДП",  payload="unit:ДП"),
         CallbackButton(text="ОИТ", payload="unit:ОИТ")],
    ])


# ─── /start — меню ───────────────────────────────────────────
@dp.message_created(CommandStart())
async def cmd_start(event: MessageCreated, context: MemoryContext):
    await context.clear()
    keyboard = Keyboard(buttons=[
        [Button(text="📝 Создать заявку")],
    ])
    await event.message.answer("Главное меню:", keyboard=keyboard)


# ─── Единый обработчик текстов ───────────────────────────────
@dp.message_created()
async def handle_message(event: MessageCreated, context: MemoryContext):
    sender = event.message.sender
    if getattr(sender, "is_bot", False):
        return

    msg_id = getattr(event.message, "message_id", None)
    if msg_id and msg_id in processed_ids:
        return
    if msg_id:
        processed_ids.add(msg_id)

    text = (event.message.body.text or "").strip()
    state = await context.get_state()

    # Шаг 1: нажали «Создать заявку»
    if text == "📝 Создать заявку":
        await context.set_state(Form.department)
        await event.message.answer(
            "Ваше подразделение?",
            keyboard=units_keyboard(),
        )
        return

    # Шаг 3: ввод ФИО
    if state == Form.fio:
        await context.update_data(fio=text)
        await context.set_state(Form.target)
        await event.message.answer(
            "Куда направить заявку?",
            keyboard=units_keyboard(),
        )
        return

    # Шаг 5: ввод текста обращения
    if state == Form.text:
        data = await context.get_data()
        payload = {
            "user_id": str(sender.user_id),
            "department": data.get("department", ""),
            "fio": data.get("fio", ""),
            "target": data.get("target", ""),
            "message": text,
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(GAS_URL, json=payload) as resp:
                print(f"Статус GAS: {resp.status}")
                print(f"Ответ GAS: {(await resp.text())[:300]}")

        await context.clear()
        await event.message.answer("✅ Ваша заявка принята.")
        return

    # Всё остальное вне диалога — игнорируем или подсказываем
    await event.message.answer(
        "Нажмите «📝 Создать заявку», чтобы оставить обращение."
    )


# ─── Обработка нажатий на inline-кнопки ──────────────────────
@dp.message_callback()
async def on_callback(event: MessageCallback, context: MemoryContext):
    payload = event.callback.payload or ""
    state = await context.get_state()

    if payload.startswith("unit:"):
        unit = payload.split(":", 1)[1]

        # Шаг 2: выбрали своё подразделение
        if state == Form.department:
            await context.update_data(department=unit)
            await context.set_state(Form.fio)
            await event.message.answer("Введите Ваше ФИО:")
            await event.answer()
            return

        # Шаг 4: выбрали, куда направить
        if state == Form.target:
            await context.update_data(target=unit)
            await context.set_state(Form.text)
            await event.message.answer("Введите текст обращения:")
            await event.answer()
            return

    await event.answer()


async def main():
    print("Токен найден, длина:", len(TOKEN))
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
