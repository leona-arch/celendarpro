import asyncio
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from fastapi import FastAPI
import uvicorn

BOT_TOKEN = os.getenv("BOT_TOKEN", "ВАШ_ТОКЕН_БОТА")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
app = FastAPI()

# Простая база данных в памяти бота
bookings_db = []

class BookingForm(StatesGroup):
    waiting_for_guest = State()
    waiting_for_dates = State()

@app.get("/")
def index():
    return {"status": "Ahatsa Bot is running!"}

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
    if not bookings_db:
        await message.answer("📅 **Шахматка на Октябрь 2026**\n\nВсе даты пока свободны!", parse_mode="Markdown")
        return
    
    text = "📅 **Актуальные бронирования «Ахьаца»:**\n\n"
    for b in bookings_db:
        text += f"👤 **{b['guest']}**: {b['dates']}\n"
    await message.answer(text, parse_mode="Markdown")

@dp.message(F.text == "➕ Новая бронь")
async def add_booking_start(message: types.Message, state: FSMContext):
    await state.set_state(BookingForm.waiting_for_guest)
    await message.answer("📝 Введите имя или фамилию гостя:")

@dp.message(BookingForm.waiting_for_guest)
async def process_guest(message: types.Message, state: FSMContext):
    await state.update_data(guest=message.text)
    await state.set_state(BookingForm.waiting_for_dates)
    await message.answer("🗓 Введите даты заезда и выезда (например: `25.10 - 28.10`):", parse_mode="Markdown")

@dp.message(BookingForm.waiting_for_dates)
async def process_dates(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    guest_name = user_data['guest']
    booking_dates = message.text
    
    bookings_db.append({"guest": guest_name, "dates": booking_dates})
    await state.clear()
    
    await message.answer(
        f"✅ **Бронь успешно добавлена!**\n\n"
        f"👤 Гость: **{guest_name}**\n"
        f"🗓 Даты: **{booking_dates}**",
        parse_mode="Markdown"
    )

@dp.message(F.text == "📋 Ближайшие заезды")
async def show_list(message: types.Message):
    if not bookings_db:
        await message.answer("📋 Ближайших заездов нет.")
    else:
        text = "📋 **Список ближайших заездов:**\n\n"
        for i, b in enumerate(bookings_db, 1):
            text += f"{i}. {b['guest']} — {b['dates']}\n"
        await message.answer(text)

@dp.message(F.text == "⚙️ Настройки iCal")
async def settings_ical(message: types.Message):
    await message.answer(
        "⚙️ **Настройка синхронизации iCal**\n\n"
        "Сюда можно подключить ссылки на синхронизацию календарей Суточно.ру, Островок и Яндекс.Путешествия.",
        parse_mode="Markdown"
    )

async def run_bot():
    await dp.start_polling(bot)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(run_bot())

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)