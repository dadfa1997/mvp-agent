import sqlite3
import json
import os
from datetime import datetime
from cryptography.fernet import Fernet
from dotenv import load_dotenv

load_dotenv()

ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")
if not ENCRYPTION_KEY:
    ENCRYPTION_KEY = Fernet.generate_key().decode()
    with open(".env", "a", encoding="utf-8") as f:
        f.write(f"\nENCRYPTION_KEY={ENCRYPTION_KEY}\n")

fernet = Fernet(ENCRYPTION_KEY.encode())
DB_NAME = "fitness_bot.db"

def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    # Таблица пользователей с полями профиля
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            gender TEXT,
            age INTEGER,
            weight REAL,
            height REAL,
            activity_level TEXT,
            goal TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            encrypted_content TEXT,
            goal TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS calendars (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            day_of_week TEXT,
            encrypted_training TEXT,
            completed INTEGER DEFAULT 0,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS stats (
            user_id INTEGER PRIMARY KEY,
            total_workouts INTEGER DEFAULT 0,
            completed_workouts INTEGER DEFAULT 0,
            streak_days INTEGER DEFAULT 0,
            last_workout_date TEXT,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            enabled INTEGER DEFAULT 1,
            reminder_time TEXT DEFAULT '08:00',
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)
    
    conn.commit()
    conn.close()

def encrypt_data(data: dict) -> str:
    return fernet.encrypt(json.dumps(data, ensure_ascii=False).encode()).decode()

def decrypt_data(encrypted_str: str) -> dict:
    if not encrypted_str: return {}
    return json.loads(fernet.decrypt(encrypted_str.encode()).decode())

# --- Пользователи и Профиль ---

def add_user(user_id: int, username: str, first_name: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR IGNORE INTO users (user_id, username, first_name)
        VALUES (?, ?, ?)
    """, (user_id, username, first_name))
    conn.commit()
    conn.close()

def save_user_profile(user_id: int, profile: dict):
    """Сохраняет или обновляет профиль пользователя."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE users 
        SET gender = ?, age = ?, weight = ?, height = ?, activity_level = ?, goal = ?
        WHERE user_id = ?
    """, (
        profile.get("gender"), profile.get("age"), profile.get("weight"),
        profile.get("height"), profile.get("activity_level"), profile.get("goal"),
        user_id
    ))
    conn.commit()
    conn.close()

def get_user_profile(user_id: int) -> dict:
    """Возвращает профиль, если он заполнен."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT gender, age, weight, height, activity_level, goal FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row and row["age"] is not None: # Проверяем, что данные действительно введены
        return dict(row)
    return None

# --- Планы, Календарь, Статистика, Напоминания (без изменений из предыдущего кода) ---
# (Оставь функции save_plan, get_plan, delete_plan, add_training, get_calendar, 
# delete_training, toggle_training_complete, get_todays_trainings, get_stats, 
# update_stats, get_reminder, toggle_reminder из предыдущей версии database.py)

def save_plan(user_id: int, content: str, goal: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM plans WHERE user_id = ?", (user_id,))
    cursor.execute("INSERT INTO plans (user_id, encrypted_content, goal) VALUES (?, ?, ?)", 
                   (user_id, encrypt_data({"content": content}), goal))
    conn.commit()
    conn.close()

def get_plan(user_id: int) -> dict:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM plans WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {"id": row["id"], "user_id": row["user_id"], "content": decrypt_data(row["encrypted_content"]).get("content", ""), "goal": row["goal"], "created_at": row["created_at"]}
    return None

def delete_plan(user_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM plans WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def add_training(user_id: int, day_of_week: str, training_name: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO calendars (user_id, day_of_week, encrypted_training) VALUES (?, ?, ?)", 
                   (user_id, day_of_week, encrypt_data({"name": training_name})))
    conn.commit()
    conn.close()

def get_calendar(user_id: int) -> dict:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM calendars WHERE user_id = ?", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    calendar = {"monday": [], "tuesday": [], "wednesday": [], "thursday": [], "friday": [], "saturday": [], "sunday": []}
    for row in rows:
        calendar[row["day_of_week"]].append({
            "id": row["id"], "name": decrypt_data(row["encrypted_training"]).get("name", ""),
            "completed": bool(row["completed"]), "added_at": row["added_at"]
        })
    return calendar

def delete_training(training_id: int, user_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM calendars WHERE id = ? AND user_id = ?", (training_id, user_id))
    conn.commit()
    conn.close()

def toggle_training_complete(training_id: int, user_id: int) -> bool:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT completed FROM calendars WHERE id = ? AND user_id = ?", (training_id, user_id))
    row = cursor.fetchone()
    if row:
        new_status = 0 if row["completed"] else 1
        cursor.execute("UPDATE calendars SET completed = ? WHERE id = ? AND user_id = ?", (new_status, training_id, user_id))
        conn.commit()
        conn.close()
        return bool(new_status)
    conn.close()
    return False

def get_todays_trainings(user_id: int, day_of_week: str) -> list:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM calendars WHERE user_id = ? AND day_of_week = ? AND completed = 0", (user_id, day_of_week))
    rows = cursor.fetchall()
    conn.close()
    return [{"id": row["id"], "name": decrypt_data(row["encrypted_training"]).get("name", "")} for row in rows]

def get_stats(user_id: int) -> dict:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM stats WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row: return dict(row)
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO stats (user_id) VALUES (?)", (user_id,))
    conn.commit()
    conn.close()
    return {"user_id": user_id, "total_workouts": 0, "completed_workouts": 0, "streak_days": 0, "last_workout_date": None}

def update_stats(user_id: int, action: str):
    stats = get_stats(user_id)
    conn = get_db()
    cursor = conn.cursor()
    if action == "add": stats["total_workouts"] += 1
    elif action == "complete": 
        stats["completed_workouts"] += 1
        stats["last_workout_date"] = datetime.now().strftime("%d.%m.%Y")
    elif action == "delete": stats["total_workouts"] = max(0, stats["total_workouts"] - 1)
    cursor.execute("UPDATE stats SET total_workouts = ?, completed_workouts = ?, last_workout_date = ? WHERE user_id = ?", 
                   (stats["total_workouts"], stats["completed_workouts"], stats["last_workout_date"], user_id))
    conn.commit()
    conn.close()

def get_reminder(user_id: int) -> dict:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM reminders WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row: return dict(row)
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO reminders (user_id) VALUES (?)", (user_id,))
    conn.commit()
    conn.close()
    return {"user_id": user_id, "enabled": 1, "reminder_time": "08:00"}

def toggle_reminder(user_id: int):
    reminder = get_reminder(user_id)
    new_status = 0 if reminder["enabled"] else 1
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE reminders SET enabled = ? WHERE user_id = ?", (new_status, user_id))
    conn.commit()
    conn.close()
    return bool(new_status)

init_db()