import asyncio
import os
import sqlite3
import aiohttp
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, WebAppInfo, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from fastapi import FastAPI
from fastapi.responses import FileResponse
import uvicorn

BOT_TOKEN = os.getenv("BOT_TOKEN", "ВАШ_ТОКЕН_БОТА")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
app = FastAPI()

DB_FILE = "bookings.db"

COTTAGES = [
    "Стандарт №1", "Стандарт №2", "Стандарт №3", "Стандарт №4", "Стандарт №5",
    "Стандарт №6", "Стандарт №7", "Стандарт №8", "Стандарт №9", "Стандарт №10"
]

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cottage TEXT NOT NULL,
            guest TEXT NOT NULL,
            dates TEXT NOT NULL,
            has_extra_bed INTEGER DEFAULT 0
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ical_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_name TEXT NOT NULL,
            url TEXT NOT NULL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS base_rates (
            cottage TEXT PRIMARY KEY,
            price_per_night INTEGER NOT NULL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS channel_rates (
            channel_name TEXT PRIMARY KEY,
            markup_percent INTEGER NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

def init_default_rates():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    for cottage in COTTAGES:
        cursor.execute('INSERT OR IGNORE INTO base_rates (cottage, price_per_night) VALUES (?, ?)', (cottage, 3500))
    channels = [("Суточно.ру", 15), ("Островок", 15), ("Яндекс.Путешествия", 10)]
    for ch, markup in channels:
        cursor.execute('INSERT OR IGNORE INTO channel_rates (channel_name, markup_percent) VALUES (?, ?)', (ch, markup))
    conn.commit()
    conn.close()

def get_all_bookings():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT id, cottage, guest, dates, has_extra_bed FROM bookings')
    rows = cursor.fetchall()
    conn.close()
    return rows

def add_booking_to_db(cottage, guest, dates, has_extra_bed=0):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('INSERT INTO bookings (cottage, guest, dates, has_extra_bed) VALUES (?, ?, ?, ?)', (cottage, guest, dates, has_extra_bed))
    conn.commit()
    conn.close()

def delete_booking_by_id(booking_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM bookings WHERE id = ?', (booking_id,))
    conn.commit()
    conn.close()

def get_base_rates():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT cottage, price_per_night FROM base_rates')
    rows = cursor.fetchall()
    conn.close()
    return rows

def update_base_rate(cottage, price):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('UPDATE base_rates SET price_per_night = ? WHERE cottage = ?', (price, cottage))
    conn.commit()
    conn.close()

def get_channel_rates():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT channel_name, markup_percent FROM channel_rates')
    rows = cursor.fetchall()
    conn.close()
    return rows

def update_channel_markup(channel, markup):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('UPDATE channel_rates SET markup_percent = ? WHERE channel_name = ?', (markup, channel))
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
init_default_rates()

# --- МАРШРУТЫ WEB APP ---
@app.get("/")
def index():
    return FileResponse("index.html")

@app.get("/api/bookings")
def api_bookings():
    bookings = get_all_bookings()
    return [{"id": b[0], "cottage": b[1], "guest": b[2], "dates": b[3], "has_extra_bed": b[4]} for b in bookings]

# --- FSM СОСТОЯНИЯ ---
class BookingForm(StatesGroup):
    waiting_for_cottage = State()
    waiting_for_guest = State()
    waiting_for_dates = State()
    waiting_for_extra_bed = State()

class CancelForm(StatesGroup):
    waiting_for_number = State()

class IcalForm(StatesGroup):
    waiting_for_name = State()
    waiting_for_url = State()

class PriceForm(StatesGroup):
    waiting_for_cottage = State()
    waiting_for_price = State()

class ChannelForm(StatesGroup):
    waiting_for_channel = State()
    waiting_for_markup = State()

# --- КЛАВИАТУРЫ ---
main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📅 Шахматка", web_app=WebAppInfo(url="https://celendarpro.onrender.com")), KeyboardButton(text="➕ Новая бронь")],
        [KeyboardButton(text="📋 Ближайшие заезды"), KeyboardButton(text="❌ Отменить бронь")],
        [KeyboardButton(text="💰 Цены и Тарифы"), KeyboardButton(text="⚙️ Настройки iCal")],
        [KeyboardButton(text="🔄 Синхронизировать")]
    ],
    resize_keyboard=True
)

rates_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="💵 Базовые цены"), KeyboardButton(text="🌐 Тарифы каналов")],
        [KeyboardButton(text="✏️ Изменить базовую цену"), KeyboardButton(text="✏️ Изменить наценку канала")],
        [KeyboardButton(text="⬅️ Главное меню")]
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

extra_bed_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Да, с допместом"), KeyboardButton(text="Нет, без допместа")]
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

@dp.message(F.text == "⬅️ Главное меню")
async def back_to_main(message: types.Message):
    await message.answer("Вы вернулись в главное меню:", reply_markup=main_keyboard)

@dp.message(F.text == "💰 Цены и Тарифы")
async def show_rates_menu(message: types.Message):
    await message.answer("💰 **Управление ценами и тарифами продаж:**", reply_markup=rates_keyboard)

@dp.message(F.text == "💵 Базовые цены")
async def show_base_rates(message: types.Message):
    rates = get_base_rates()
    text = "💵 **Текущие базовые цены за ночь:**\n\n"
    for cottage, price in rates:
        text += f"• **{cottage}**: `{price} руб.`\n"
    await message.answer(text, parse_mode="Markdown")

@dp.message(F.text == "🌐 Тарифы каналов")
async def show_channel_rates(message: types.Message):
    base_price = dict(get_base_rates()).get("Стандарт №1", 3500)
    channels = get_channel_rates()
    text = f"🌐 **Тарифы каналов продаж (наценка к базовой цене ~{base_price} руб.):**\n\n"
    for ch, markup in channels:
        final_price = int(base_price * (1 + markup / 100))
        text += f"• **{ch}**: `+{markup}%` ➔ ~`{final_price} руб/ночь`\n"
    await message.answer(text, parse_mode="Markdown")

@dp.message(F.text == "✏️ Изменить базовую цену")
async def edit_base_price_start(message: types.Message, state: FSMContext):
    await state.set_state(PriceForm.waiting_for_cottage)
    await message.answer("🏡 Выберите номер коттеджа:", reply_markup=cottages_keyboard)

@dp.message(PriceForm.waiting_for_cottage)
async def process_price_cottage(message: types.Message, state: FSMContext):
    if message.text not in COTTAGES:
        await message.answer("⚠️ Выберите коттедж из списка.")
        return
    await state.update_data(cottage=message.text)
    await state.set_state(PriceForm.waiting_for_price)
    await message.answer("💵 Введите новую базовую цену в рублях за ночь (например `4000`):")

@dp.message(PriceForm.waiting_for_price)
async def process_price_value(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("⚠️ Введите число, например `4000`.")
        return
    data = await state.get_data()
    cottage = data['cottage']
    price = int(message.text)
    update_base_rate(cottage, price)
    await state.clear()
    await message.answer(f"✅ Базовая цена для **{cottage}** изменена на `{price} руб.`!", parse_mode="Markdown", reply_markup=rates_keyboard)

@dp.message(F.text == "✏️ Изменить наценку канала")
async def edit_channel_start(message: types.Message, state: FSMContext):
    channels = get_channel_rates()
    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=ch[0])] for ch in channels] + [[KeyboardButton(text="⬅️ Главное меню")]],
        resize_keyboard=True
    )
    await state.set_state(ChannelForm.waiting_for_channel)
    await message.answer("🌐 Выберите канал продаж:", reply_markup=kb)

@dp.message(ChannelForm.waiting_for_channel)
async def process_channel_select(message: types.Message, state: FSMContext):
    await state.update_data(channel=message.text)
    await state.set_state(ChannelForm.waiting_for_markup)
    await message.answer("📈 Введите размер наценки в % (например `15`):")

@dp.message(ChannelForm.waiting_for_markup)
async def process_channel_markup(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("⚠️ Введите процент числом, например `15`.")
        return
    data = await state.get_data()
    channel = data['channel']
    markup = int(message.text)
    update_channel_markup(channel, markup)
    await state.clear()
    await message.answer(f"✅ Наценка для канала **{channel}** установлена в `{markup}%`!", parse_mode="Markdown", reply_markup=rates_keyboard)

# --- ДОБАВЛЕНИЕ БРОНИ ---
@dp.message(F.text == "➕ Новая бронь")
async def add_booking_start(message: types.Message, state: FSMContext):
    await state.set_state(BookingForm.waiting_for_cottage)
    await message.answer("🏡 Выберите номер коттеджа:", reply_markup=cottages_keyboard)

@dp.message(BookingForm.waiting_for_cottage)
async def process_guest_cottage(message: types.Message, state: FSMContext):
    if message.text not in COTTAGES:
        await message.answer("⚠️ Выберите коттедж из списка.")
        return
    await state.update_data(cottage=message.text)
    await state.set_state(BookingForm.waiting_for_guest)
    await message.answer("📝 Введите имя или фамилию гостя:", reply_markup=ReplyKeyboardRemove())

@dp.message(BookingForm.waiting_for_guest)
async def process_guest(message: types.Message, state: FSMContext):
    await state.update_data(guest=message.text)
    await state.set_state(BookingForm.waiting_for_dates)
    await message.answer("🗓 Введите даты заезда и выезда (например: `24.10 - 30.10`):", parse_mode="Markdown")

@dp.message(BookingForm.waiting_for_dates)
async def process_dates(message: types.Message, state: FSMContext):
    await state.update_data(dates=message.text)
    await state.set_state(BookingForm.waiting_for_extra_bed)
    await message.answer("🛏 Требуется дополнительное место?", reply_markup=extra_bed_keyboard)

@dp.message(BookingForm.waiting_for_extra_bed)
async def process_extra_bed(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    cottage = user_data['cottage']
    guest_name = user_data['guest']
    booking_dates = user_data['dates']
    
    has_extra_bed = 1 if "Да" in message.text else 0
    extra_text = " (с допместом)" if has_extra_bed else ""

    add_booking_to_db(cottage, guest_name, booking_dates, has_extra_bed)
    await state.clear()
    
    await message.answer(
        f"✅ **Бронь успешно сохранена!**\n\n"
        f"🏡 Коттедж: **{cottage}**\n"
        f"👤 Гость: **{guest_name}**{extra_text}\n"
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
            extra = " 🛏 (допместо)" if b[4] else ""
            text += f"{i}. **{b[1]}** | {b[2]}{extra} — {b[3]}\n"
        await message.answer(text, parse_mode="Markdown")

@dp.message(F.text == "❌ Отменить бронь")
async def cancel_booking_start(message: types.Message, state: FSMContext):
    bookings = get_all_bookings()
    if not bookings:
        await message.answer("❌ У вас пока нет активных броней для отмены.")
        return
    text = "❓ **Укажите номер брони для отмены:**\n\n"
    for i, b in enumerate(bookings, 1):
        extra = " (+допместо)" if b[4] else ""
        text += f"**{i}** — {b[1]} | {b[2]}{extra} ({b[3]})\n"
    text += "\n*Отправьте цифру в ответ:*"
    await state.set_state(CancelForm.waiting_for_number)
    await message.answer(text, parse_mode="Markdown")

@dp.message(CancelForm.waiting_for_number)
async def process_cancel_number(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("⚠️ Введите номер цифрой.")
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
        await message.answer("⚠️ Брони с таким номером не существует.")

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
        await message.answer("⚠️ У вас не добавлены iCal ссылки.")
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
                        from icalendar import Calendar
                        cal = Calendar.from_ical(content)
                        for component in cal.walk('vevent'):
                            summary = str(component.get('summary', f'Бронь ({source_name})'))
                            dtstart = component.get('dtstart')
                            dtend = component.get('dtend')
                            if dtstart and dtend:
                                start_date = dtstart.dt.strftime('%d.%m') if hasattr(dtstart.dt, 'strftime') else str(dtstart.dt)
                                end_date = dtend.dt.strftime('%d.%m') if hasattr(dtend.dt, 'strftime') else str(dtend.dt)
                                dates_str = f"{start_date} - {end_date}"
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