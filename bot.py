import asyncio
import sqlite3
from datetime import datetime, date

from aiogram import Bot, Dispatcher, executor, types

# 🔑 ВСТАВЬ СЮДА СВОЙ ТОКЕН
bot = Bot("import os

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")

bot = Bot(BOT_TOKEN)")
dp = Dispatcher(bot)

# --- БАЗА ДАННЫХ ---
db = sqlite3.connect("worktime.db")
cur = db.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS events (
    user_id INTEGER,
    day TEXT,
    type TEXT,
    time TEXT
)
""")
db.commit()

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
def now_hhmm():
    return datetime.now().strftime("%H:%M")

def now_ts():
    return int(datetime.now().timestamp())

def fmt_mmss(sec):
    m = sec // 60
    s = sec % 60
    return f"{m:02d}:{s:02d}"

# --- СОСТОЯНИЕ ПЕРЕРЫВА ---
break_state = {}

async def break_timer(user_id: int):
    while user_id in break_state:
        state = break_state[user_id]
        elapsed = now_ts() - state["start"]
        text = (
            f"⏳ Вы на перерыве уже: {fmt_mmss(elapsed)}\n\n"
            "Нажмите 🟢 Пришёл, когда вернётесь."
        )
        try:
            await bot.edit_message_text(
                text,
                chat_id=state["chat"],
                message_id=state["msg"]
            )
        except:
            pass
        await asyncio.sleep(5)

# --- КОМАНДЫ ---
@dp.message_handler(commands=["start"])
async def start(msg: types.Message):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🟢 Пришёл", "🔴 Вышел")
    kb.add("📋 Отчёт")
    await msg.answer("Отметь действие:", reply_markup=kb)

@dp.message_handler(lambda m: m.text == "🟢 Пришёл")
async def arrived(msg: types.Message):
    user_id = msg.from_user.id

    if user_id in break_state:
        break_state.pop(user_id)

    cur.execute(
        "INSERT INTO events VALUES (?,?,?,?)",
        (user_id, str(date.today()), "IN", now_hhmm())
    )
    db.commit()

    await msg.answer(f"✅ Приход зафиксирован: {now_hhmm()}")

@dp.message_handler(lambda m: m.text == "🔴 Вышел")
async def left(msg: types.Message):
    user_id = msg.from_user.id

    cur.execute(
        "INSERT INTO events VALUES (?,?,?,?)",
        (user_id, str(date.today()), "OUT", now_hhmm())
    )
    db.commit()

    sent = await msg.answer(
        "⏳ Вы на перерыве уже: 00:00\n\n"
        "Нажмите 🟢 Пришёл, когда вернётесь."
    )

    break_state[user_id] = {
        "start": now_ts(),
        "chat": sent.chat.id,
        "msg": sent.message_id
    }

    asyncio.create_task(break_timer(user_id))

@dp.message_handler(lambda m: m.text == "📋 Отчёт")
async def report(msg: types.Message):
    user_id = msg.from_user.id

    cur.execute(
        "SELECT type, time FROM events WHERE user_id=? AND day=? ORDER BY time",
        (user_id, str(date.today()))
    )
    rows = cur.fetchall()

    pairs = []
    current_in = None

    for t, tm in rows:
        if t == "IN":
            current_in = tm
        elif t == "OUT" and current_in:
            pairs.append(f"{current_in}–{tm}")
            current_in = None

    if not pairs:
        await msg.answer("Сегодня выходов ещё не было.")
        return

    await msg.answer("Выходы\n" + "\n".join(pairs))

# --- ЗАПУСК ---
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
