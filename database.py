import sqlite3
import json
import os
from datetime import datetime
from cryptography.fernet import Fernet
from dotenv import load_dotenv

load_dotenv()

# Ключ шифрования (берём из .env или генерируем)
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")
if not ENCRYPTION_KEY:
    # Генерируем новый ключ и сохраняем в .env
    ENCRYPTION_KEY = Fernet.generate_key().decode()
    with open(".env", "a", encoding="utf-8") as f:
        f.write(f"\nENCRYPTION_KEY={ENCRYPTION_KEY}\n")
    print(f"🔐 Сгенерирован новый ключ шифрования: {ENCRYPTION_KEY}")

fernet = Fernet(ENCRYPTION_KEY.encode())

DB_NAME = "fitness_bot.db"

def get_db():
    """Получить соединение с БД."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Инициализация таблиц."""
    conn = get_db()
    cursor = conn.cursor()
    
    # Таблица пользователей
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Таблица планов тренировок (зашифрованная)
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
    
    # Таблица календаря тренировок (зашифрованная)
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
    
    # Таблица статистики
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
    
    # Таблица напоминаний
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
    print("✅ База данных инициализирована")

# --- ФУНКЦИИ ШИФРОВАНИЯ ---

def encrypt_data(data: dict) -> str:
    """Шифрует словарь в строку."""
    json_str = json.dumps(data, ensure_ascii=False)
    return fernet.encrypt(json_str.encode()).decode()

def decrypt_data(encrypted_str: str) -> dict:
    """Расшифровывает строку в словарь."""
    if not encrypted_str:
        return {}
    json_str = fernet.decrypt(encrypted_str.encode()).decode()
    return json.loads(json_str)

# --- ФУНКЦИИ РАБОТЫ С ПОЛЬЗОВАТЕЛЯМИ ---

def add_user(user_id: int, username: str, first_name: str):
    """Добавить или обновить пользователя."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO users (user_id, username, first_name)
        VALUES (?, ?, ?)
    """, (user_id, username, first_name))
    conn.commit()
    conn.close()

def get_user(user_id: int) -> dict:
    """Получить пользователя."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

# --- ФУНКЦИИ РАБОТЫ С ПЛАНАМИ ---

def save_plan(user_id: int, content: str, goal: str):
    """Сохранить план (зашифрованный)."""
    conn = get_db()
    cursor = conn.cursor()
    # Удаляем старый план пользователя
    cursor.execute("DELETE FROM plans WHERE user_id = ?", (user_id,))
    # Шифруем контент
    encrypted = encrypt_data({"content": content})
    cursor.execute("""
        INSERT INTO plans (user_id, encrypted_content, goal)
        VALUES (?, ?, ?)
    """, (user_id, encrypted, goal))
    conn.commit()
    conn.close()

def get_plan(user_id: int) -> dict:
    """Получить план пользователя (расшифрованный)."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM plans WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {
            "id": row["id"],
            "user_id": row["user_id"],
            "content": decrypt_data(row["encrypted_content"]).get("content", ""),
            "goal": row["goal"],
            "created_at": row["created_at"]
        }
    return None

def delete_plan(user_id: int):
    """Удалить план пользователя."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM plans WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

# --- ФУНКЦИИ РАБОТЫ С КАЛЕНДАРЁМ ---

def add_training(user_id: int, day_of_week: str, training_name: str):
    """Добавить тренировку (зашифрованную)."""
    conn = get_db()
    cursor = conn.cursor()
    encrypted = encrypt_data({"name": training_name})
    cursor.execute("""
        INSERT INTO calendars (user_id, day_of_week, encrypted_training)
        VALUES (?, ?, ?)
    """, (user_id, day_of_week, encrypted))
    conn.commit()
    conn.close()

def get_calendar(user_id: int) -> dict:
    """Получить календарь пользователя (расшифрованный)."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM calendars WHERE user_id = ?", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    
    calendar = {
        "monday": [], "tuesday": [], "wednesday": [], "thursday": [],
        "friday": [], "saturday": [], "sunday": []
    }
    
    for row in rows:
        day = row["day_of_week"]
        training = decrypt_data(row["encrypted_training"])
        calendar[day].append({
            "id": row["id"],
            "name": training.get("name", ""),
            "completed": bool(row["completed"]),
            "added_at": row["added_at"]
        })
    
    return calendar

def delete_training(training_id: int, user_id: int):
    """Удалить тренировку."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM calendars WHERE id = ? AND user_id = ?", (training_id, user_id))
    conn.commit()
    conn.close()

def toggle_training_complete(training_id: int, user_id: int) -> bool:
    """Переключить статус выполнения тренировки."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT completed FROM calendars WHERE id = ? AND user_id = ?", (training_id, user_id))
    row = cursor.fetchone()
    if row:
        new_status = 0 if row["completed"] else 1
        cursor.execute("UPDATE calendars SET completed = ? WHERE id = ? AND user_id = ?", 
                      (new_status, training_id, user_id))
        conn.commit()
        conn.close()
        return bool(new_status)
    conn.close()
    return False

def get_todays_trainings(user_id: int, day_of_week: str) -> list:
    """Получить тренировки на конкретный день."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM calendars 
        WHERE user_id = ? AND day_of_week = ? AND completed = 0
    """, (user_id, day_of_week))
    rows = cursor.fetchall()
    conn.close()
    
    trainings = []
    for row in rows:
        training = decrypt_data(row["encrypted_training"])
        trainings.append({
            "id": row["id"],
            "name": training.get("name", "")
        })
    return trainings

# --- ФУНКЦИИ РАБОТЫ СО СТАТИСТИКОЙ ---

def get_stats(user_id: int) -> dict:
    """Получить статистику пользователя."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM stats WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return dict(row)
    
    # Создаём новую запись
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO stats (user_id, total_workouts, completed_workouts, streak_days, last_workout_date)
        VALUES (?, 0, 0, 0, NULL)
    """, (user_id,))
    conn.commit()
    conn.close()
    
    return {
        "user_id": user_id,
        "total_workouts": 0,
        "completed_workouts": 0,
        "streak_days": 0,
        "last_workout_date": None
    }

def update_stats(user_id: int, action: str):
    """Обновить статистику."""
    stats = get_stats(user_id)
    conn = get_db()
    cursor = conn.cursor()
    
    if action == "add":
        stats["total_workouts"] += 1
    elif action == "complete":
        stats["completed_workouts"] += 1
        stats["last_workout_date"] = datetime.now().strftime("%d.%m.%Y")
    elif action == "delete":
        stats["total_workouts"] = max(0, stats["total_workouts"] - 1)
    
    cursor.execute("""
        UPDATE stats 
        SET total_workouts = ?, completed_workouts = ?, last_workout_date = ?
        WHERE user_id = ?
    """, (stats["total_workouts"], stats["completed_workouts"], stats["last_workout_date"], user_id))
    conn.commit()
    conn.close()

# --- ФУНКЦИИ РАБОТЫ С НАПОМИНАНИЯМИ ---

def get_reminder(user_id: int) -> dict:
    """Получить настройки напоминаний."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM reminders WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return dict(row)
    
    # Создаём по умолчанию
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO reminders (user_id, enabled, reminder_time)
        VALUES (?, 1, '08:00')
    """, (user_id,))
    conn.commit()
    conn.close()
    
    return {"user_id": user_id, "enabled": 1, "reminder_time": "08:00"}

def toggle_reminder(user_id: int):
    """Включить/выключить напоминания."""
    reminder = get_reminder(user_id)
    new_status = 0 if reminder["enabled"] else 1
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE reminders SET enabled = ? WHERE user_id = ?", (new_status, user_id))
    conn.commit()
    conn.close()
    return bool(new_status)

# Инициализация БД при импорте
init_db()