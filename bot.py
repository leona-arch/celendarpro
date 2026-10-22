import asyncio
import os
import sqlite3
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

# --- РАБОТА С БАЗОЙ ДАННЫХ SQLITE ---
DB_FILE = "bookings.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guest TEXT NOT NULL,
            dates TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

def add_booking_to_db(guest, dates):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('INSERT INTO bookings (guest, dates) VALUES (?, ?)', (guest, dates))
    conn.commit()
    conn.close()

def get_all_bookings():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT id, guest, dates FROM bookings')
    rows = cursor.fetchall()
    conn.close()
    return rows

def delete_booking_by_id(booking_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM bookings WHERE id = ?', (booking_id,))
    conn.commit()
    conn.close()

# Инициализируем БД при старте
init_db()

class BookingForm(StatesGroup):
    waiting_for_guest = State()
    waiting_for_dates = State()

class CancelForm(StatesGroup):
    waiting_for_number = State()

@app.get("/")
def index():
    return {"status": "Ahatsa Bot is running!"}

main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📅 Шахматка"), KeyboardButton(text="➕ Новая бронь")],
        [KeyboardButton(text="📋 Ближайшие заезды"), KeyboardButton(text="❌ Отменить бронь")],
        [KeyboardButton(text="⚙️ Настройки iCal")]
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
    bookings = get_all_bookings()
    if not bookings:
        await message.answer("📅 **Шахматка**\n\nВсе даты пока свободны!", parse_mode="Markdown")
        return
    
    text = "📅 **Актуальные бронирования «Ахьаца»:**\n\n"
    for i, b in enumerate(bookings, 1):
        text += f"{i}. 👤 **{b[1]}**: {b[2]}\n"
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
    
    add_booking_to_db(guest_name, booking_dates)
    await state.clear()
    
    await message.answer(
        f"✅ **Бронь успешно сохранена в базу!**\n\n"
        f"👤 Гость: **{guest_name}**\n"
        f"🗓 Даты: **{booking_dates}**",
        parse_mode="Markdown",
        reply_markup=main_keyboard
    )

@dp.message(F.text == "📋 Ближайшие заезды")
async def show_list(message: types.Message):
    bookings = get_all_bookings()
    if not bookings:
        await message.answer("📋 Ближайших заездов нет.")
    else:
        text = "📋 **Список ближайших заездов:**\n\n"
        for i, b in enumerate(bookings, 1):
            text += f"{i}. {b[1]} — {b[2]}\n"
        await message.answer(text)

@dp.message(F.text == "❌ Отменить бронь")
async def cancel_booking_start(message: types.Message, state: FSMContext):
    bookings = get_all_bookings()
    if not bookings:
        await message.answer("❌ У вас пока нет активных броней для отмены.")
        return
    
    text = "❓ **Укажите номер брони, которую нужно отменить:**\n\n"
    for i, b in enumerate(bookings, 1):
        text += f"**{i}** — {b[1]} ({b[2]})\n"
    
    text += "\n*Отправьте цифру в ответное сообщение:*"
    await state.set_state(CancelForm.waiting_for_number)
    await message.answer(text, parse_mode="Markdown")

@dp.message(CancelForm.waiting_for_number)
async def process_cancel_number(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("⚠️ Пожалуйста, введите только номер (цифрой), например `1`.")
        return

    num = int(message.text) - 1
    bookings = get_all_bookings()

    if 0 <= num < len(bookings):
        target_booking = bookings[num]
        delete_booking_by_id(target_booking[0]) # Удаляем из базы по ID
        await state.clear()
        await message.answer(
            f"🗑 **Бронь отменена и удалена из базы!**\n\n"
            f"Удалено: **{target_booking[1]}** ({target_booking[2]})",
            parse_mode="Markdown",
            reply_markup=main_keyboard
        )
    else:
        await message.answer("⚠️ Брони с таким номером не существует. Попробуйте еще раз:")

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