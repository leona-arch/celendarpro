import asyncio
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

# Замените "ВАШ_ТОКЕН_БОТА" на реальный токен от @BotFather
BOT_TOKEN = os.getenv("BOT_TOKEN", "ВАШ_ТОКЕН_БОТА")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

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
        "25 Вс: 🟢 Свободно\n\n"
        "*(Интерактивный режим)*",
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

async def main():
    print("Бот успешно запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
