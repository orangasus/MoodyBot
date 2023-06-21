import sqlite3 as sq
import datetime
from MoodRecord import MoodRecord


async def db_start():
    global db, cur
    db = sq.connect("moody_db.db")
    cur = db.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS mood_records(
        id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
        user_id INT NOT NULL,
        datetime TEXT NOT NULL,
        mood INT NOT NULL,
        description TEXT
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS users(
            user_id INT NOT NULL,
            creation_date TEXT NOT NULL,
            name TEXT NOT NULL,
            chat_id INT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            num_messages INT NOT NULL
        )""")
    db.commit()


async def create_profile(user_id, name, date, chat_id, start_time, end_time, num_messages):
    cur.execute("INSERT INTO users VALUES(?, ?, ?, ?, ?, ?, ?)",
                (user_id, date, name, chat_id, start_time, end_time, num_messages))
    db.commit()


async def delete_profile(user_id):
    cur.execute(f"DELETE FROM users WHERE user_id == {user_id}")
    cur.execute(f"DELETE FROM mood_records WHERE user_id == {user_id}")
    db.commit()


async def edit_profile(user_id, name, creation_date, start_time, end_time, num_messages):
    cur.execute(
        f"""UPDATE users SET name='{name}', creation_date='{creation_date}', 
        start_time='{start_time}', end_time='{end_time}', num_messages={num_messages} 
        WHERE user_id={user_id}""")
    db.commit()


async def user_exists(user_id):
    user = cur.execute(f"SELECT 1 FROM users WHERE user_id={user_id}").fetchone()
    if not user:
        return False
    return True

async def get_profile(user_id):
    profile = cur.execute(f"SELECT * FROM users WHERE user_id={user_id}").fetchone()
    return profile


async def get_chat_id(user_id):
    chat_id = cur.execute(f"SELECT chat_id FROM users WHERE user_id={user_id} LIMIT 1").fetchone()
    return chat_id


async def insert_record(record: MoodRecord):
    with db:
        cur.execute("INSERT INTO mood_records (user_id, datetime, mood, description) VALUES (?, ?, ?, ?)",
                    (record.user_id, record.datetime, record.mood, record.description))

async def get_week_records(user_id):
    today = datetime.datetime.now().date()
    start_of_week = today - datetime.timedelta(days=today.weekday())
    end_of_week = start_of_week + datetime.timedelta(days=6)
    rec = cur.execute("SELECT * FROM mood_records WHERE datetime >= ? AND datetime <= ?",
                (start_of_week.strftime('%Y-%m-%d %H:%M:%S'), end_of_week.strftime('%Y-%m-%d %H:%M:%S')))
    return rec

async def get_records(user_id):
    cur.execute(f"SELECT * FROM mood_records WHERE user_id={user_id}")
    rec = cur.fetchall()
    return rec
