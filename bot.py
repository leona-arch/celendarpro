import asyncio
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from fastapi import FastAPI
import uvicorn

# Токен бота
BOT_TOKEN = os.getenv("BOT_TOKEN", "ВАШ_ТОКЕН_БОТА")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# FastAPI для того, чтобы Render считал приложение веб-сервисом
app = FastAPI()

@app.get("/")
def index():
    return {"status": "Ahatsa Bot is running!"}

# Главные кнопки под клавиатурой
main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📅 Шахматка"), KeyboardButton(text="➕ Новая бронь")],
        [KeyboardButton(text="📋 Ближайшие заезды"), KeyboardButton(text="⚙️ Настройки iCal")]
    ],
    resize_keyboard=True
)

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "👋 Добро пожаловать в менеджер бронирований «Ахьаца»!\n\n"
        "Выберите нужное действие на панели ниже:",
        reply_markup=main_keyboard
    )

@dp.message(F.text == "📅 Шахматка")
async def show_calendar(message: types.Message):
    await message.answer(
        "🟢 **Октябрь 2026 — Коттедж Стандарт**\n\n"
        "22 Чт: 🟢 Свободно\n"
        "23 Пт: 🟢 Свободно\n"
        "24 Сб: 🟢 Свободно\n"
        "25 Вс: 🟢 Свободно",
        parse_mode="Markdown"
    )

@dp.message(F.text == "➕ Новая бронь")
async def add_booking(message: types.Message):
    await message.answer("📝 Введите даты заезда и выезда (например: `25.10 - 28.10`):", parse_mode="Markdown")

@dp.message(F.text == "📋 Ближайшие заезды")
async def show_list(message: types.Message):
    await message.answer("📋 Ближайших бронирований пока нет.")

@dp.message(F.text == "⚙️ Настройки iCal")
async def settings_ical(message: types.Message):
    await message.answer("⚙️ Здесь будут храниться ваши ссылки iCal.")

async def run_bot():
    await dp.start_polling(bot)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(run_bot())

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
