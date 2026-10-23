import asyncio
import os
import sqlite3
import aiohttp
from datetime import datetime, timedelta
from icalendar import Calendar
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

DB_FILE = "bookings.db"

# Список категорий и коттеджей "Ахьаца"
COTTAGES = [
    "Стандарт №1", "Стандарт №2", "Стандарт №3", "Стандарт №4", "Стандарт №5",
    "Стандарт №6", "Стандарт №7", "Стандарт №8", "Стандарт №9", "Стандарт №10",
    "Стандарт с допместом"
]

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cottage TEXT NOT NULL,
            guest TEXT NOT NULL,
            dates TEXT NOT NULL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ical_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_name TEXT NOT NULL,
            url TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

def add_booking_to_db(cottage, guest, dates):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('INSERT INTO bookings (cottage, guest, dates) VALUES (?, ?, ?)', (cottage, guest, dates))
    conn.commit()
    conn.close()

def get_all_bookings():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT id, cottage, guest, dates FROM bookings')
    rows = cursor.fetchall()
    conn.close()
    return rows

def delete_booking_by_id(booking_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM bookings WHERE id = ?', (booking_id,))
    conn.commit()
    conn.close()

def add_ical_to_db(source_name, url):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('INSERT INTO ical_links (source_name, url) VALUES (?, ?)', (source_name, url))
    conn.commit()
    conn.close()

def get_all_icals():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT id, source_name, url FROM ical_links')
    rows = cursor.fetchall()
    conn.close()
    return rows

init_db()

# --- FSM Состояния ---
class BookingForm(StatesGroup):
    waiting_for_cottage = State()
    waiting_for_guest = State()
    waiting_for_dates = State()

class CancelForm(StatesGroup):
    waiting_for_number = State()

class IcalForm(StatesGroup):
    waiting_for_name = State()
    waiting_for_url = State()

@app.get("/")
def index():
    return {"status": "Ahatsa Bot is running!"}

# --- Клавиатуры ---
main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📅 Шахматка"), KeyboardButton(text="➕ Новая бронь")],
        [KeyboardButton(text="📋 Ближайшие заезды"), KeyboardButton(text="❌ Отменить бронь")],
        [KeyboardButton(text="⚙️ Настройки iCal"), KeyboardButton(text="🔄 Синхронизировать")]
    ],
    resize_keyboard=True
)

ical_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🔗 Добавить iCal ссылку"), KeyboardButton(text="📜 Список моих ссылок")],
        [KeyboardButton(text="⬅️ Главное меню")]
    ],
    resize_keyboard=True
)

cottages_keyboard = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text=c)] for c in COTTAGES] + [[KeyboardButton(text="⬅️ Главное меню")]],
    resize_keyboard=True
)

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "👋 Добро пожаловать в менеджер бронирований «Ахьаца»!\n\n"
        "Выберите нужное действие на панели ниже:",
        reply_markup=main_keyboard
    )

@dp.message(F.text == "⬅️ Главное меню")
async def back_to_main(message: types.Message):
    await message.answer("Вы вернулись в главное меню:", reply_markup=main_keyboard)

# --- Наглядная Шахматка по Коттеджам ---
@dp.message(F.text == "📅 Шахматка")
async def show_calendar(message: types.Message):
    bookings = get_all_bookings()
    
    text = "📅 **Шахматка бронирований «Ахьаца»**\n"
    text += "────────────────────\n\n"
    
    for cottage in COTTAGES:
        cottage_bookings = [b for b in bookings if b[1] == cottage]
        text += f"🏡 **{cottage}**:\n"
        if not cottage_bookings:
            text += "  └ 🟢 Свободен\n\n"
        else:
            for b in cottage_bookings:
                text += f"  └ 🔴 **{b[2]}**: {b[3]}\n"
            text += "\n"
            
    await message.answer(text, parse_mode="Markdown")

# --- Добавление брони с выбором коттеджа ---
@dp.message(F.text == "➕ Новая бронь")
async def add_booking_start(message: types.Message, state: FSMContext):
    await state.set_state(BookingForm.waiting_for_cottage)
    await message.answer("🏡 Выберите категории/номер коттеджа:", reply_markup=cottages_keyboard)

@dp.message(BookingForm.waiting_for_cottage)
async def process_cottage(message: types.Message, state: FSMContext):
    if message.text not in COTTAGES:
        await message.answer("⚠️ Пожалуйста, выберите коттедж из списка ниже.")
        return
    await state.update_data(cottage=message.text)
    await state.set_state(BookingForm.waiting_for_guest)
    await message.answer("📝 Введите имя или фамилию гостя:", reply_markup=types.ReplyKeyboardRemove())

@dp.message(BookingForm.waiting_for_guest)
async def process_guest(message: types.Message, state: FSMContext):
    await state.update_data(guest=message.text)
    await state.set_state(BookingForm.waiting_for_dates)
    await message.answer("🗓 Введите даты заезда и выезда (например: `23.10 - 28.10`):", parse_mode="Markdown")

@dp.message(BookingForm.waiting_for_dates)
async def process_dates(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    cottage = user_data['cottage']
    guest_name = user_data['guest']
    booking_dates = message.text
    
    add_booking_to_db(cottage, guest_name, booking_dates)
    await state.clear()
    
    await message.answer(
        f"✅ **Бронь успешно сохранена!**\n\n"
        f"🏡 Коттедж: **{cottage}**\n"
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
        text = "📋 **Список всех заездов:**\n\n"
        for i, b in enumerate(bookings, 1):
            text += f"{i}. **{b[1]}** | {b[2]} — {b[3]}\n"
        await message.answer(text, parse_mode="Markdown")

@dp.message(F.text == "❌ Отменить бронь")
async def cancel_booking_start(message: types.Message, state: FSMContext):
    bookings = get_all_bookings()
    if not bookings:
        await message.answer("❌ У вас пока нет активных броней для отмены.")
        return
    
    text = "❓ **Укажите номер брони для отмены:**\n\n"
    for i, b in enumerate(bookings, 1):
        text += f"**{i}** — {b[1]} | {b[2]} ({b[3]})\n"
    
    text += "\n*Отправьте цифру в ответ:* "
    await state.set_state(CancelForm.waiting_for_number)
    await message.answer(text, parse_mode="Markdown")

@dp.message(CancelForm.waiting_for_number)
async def process_cancel_number(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("⚠️ Введите только номер (цифрой), например `1`.")
        return

    num = int(message.text) - 1
    bookings = get_all_bookings()

    if 0 <= num < len(bookings):
        target_booking = bookings[num]
        delete_booking_by_id(target_booking[0])
        await state.clear()
        await message.answer(
            f"🗑 **Бронь отменена!**\n\n"
            f"Удалено: **{target_booking[1]}** — {target_booking[2]} ({target_booking[3]})",
            parse_mode="Markdown",
            reply_markup=main_keyboard
        )
    else:
        await message.answer("⚠️ Брони с таким номером не существует. Попробуйте ещё раз:")

# --- Настройки и Синхронизация iCal ---
@dp.message(F.text == "⚙️ Настройки iCal")
async def settings_ical(message: types.Message):
    await message.answer("⚙️ **Управление iCal ссылками:**", reply_markup=ical_keyboard)

@dp.message(F.text == "📜 Список моих ссылок")
async def list_icals(message: types.Message):
    icals = get_all_icals()
    if not icals:
        await message.answer("⚙️ У вас пока нет сохранённых iCal-ссылок.")
    else:
        text = "📜 **Ваши iCal каналы:**\n\n"
        for i, ic in enumerate(icals, 1):
            text += f"{i}. **{ic[1]}**:\n`{ic[2]}`\n\n"
        await message.answer(text, parse_mode="Markdown")

@dp.message(F.text == "🔗 Добавить iCal ссылку")
async def add_ical_start(message: types.Message, state: FSMContext):
    await state.set_state(IcalForm.waiting_for_name)
    await message.answer("📌 Введите название (например: `Суточно.ру`):", parse_mode="Markdown")

@dp.message(IcalForm.waiting_for_name)
async def process_ical_name(message: types.Message, state: FSMContext):
    await state.update_data(source_name=message.text)
    await state.set_state(IcalForm.waiting_for_url)
    await message.answer("🔗 Отправьте iCal ссылку (начинается с `http://` или `https://`):", parse_mode="Markdown")

@dp.message(IcalForm.waiting_for_url)
async def process_ical_url(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    source_name = user_data['source_name']
    url = message.text
    
    add_ical_to_db(source_name, url)
    await state.clear()
    
    await message.answer(
        f"✅ **iCal-ссылка сохранена!**\n\n"
        f"📌 Площадка: **{source_name}**\n"
        f"🔗 Ссылка: `{url}`",
        parse_mode="Markdown",
        reply_markup=ical_keyboard
    )

@dp.message(F.text == "🔄 Синхронизировать")
async def sync_calendars(message: types.Message):
    icals = get_all_icals()
    if not icals:
        await message.answer("⚠️ У вас не добавлены iCal ссылки. Зайдите в «⚙️ Настройки iCal».")
        return

    msg = await message.answer("🔄 Загружаю данные с площадок...")
    imported_count = 0

    async with aiohttp.ClientSession() as session:
        for ic in icals:
            source_name = ic[1]
            url = ic[2]
            try:
                async with session.get(url, timeout=10) as resp:
                    if resp.status == 200:
                        content = await resp.text()
                        cal = Calendar.from_ical(content)
                        for component in cal.walk('vevent'):
                            summary = str(component.get('summary', f'Бронь ({source_name})'))
                            dtstart = component.get('dtstart')
                            dtend = component.get('dtend')
                            
                            if dtstart and dtend:
                                start_date = dtstart.dt.strftime('%d.%m') if hasattr(dtstart.dt, 'strftime') else str(dtstart.dt)
                                end_date = dtend.dt.strftime('%d.%m') if hasattr(dtend.dt, 'strftime') else str(dtend.dt)
                                dates_str = f"{start_date} - {end_date}"
                                
                                # По умолчанию привязываем внешние брони к Стандарту №1 (или первому свободному)
                                add_booking_to_db("Стандарт №1", summary, dates_str)
                                imported_count += 1
            except Exception as e:
                print(f"Ошибка синхронизации: {e}")

    await message.edit_text(f"✅ **Синхронизация завершена!**\n\nОбновлено броней: **{imported_count}**", parse_mode="Markdown")

async def run_bot():
    await dp.start_polling(bot)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(run_bot())

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)