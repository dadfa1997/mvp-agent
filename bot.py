import os
import json
import logging
import threading
import re
from datetime import datetime
from dotenv import load_dotenv
import telebot
from telebot import types
from flask import Flask
from src.agent import NutritionAgent

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Загрузка переменных окружения
load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("❌ Ошибка: Не найден TELEGRAM_BOT_TOKEN в файле .env")

# Инициализация бота
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML", threaded=True)

# Память пользователей
user_agents = {}
user_states = {}  # Состояние пользователя (ожидание ввода)
user_data = {}    # Временные данные для пошагового ввода

# Файлы для хранения данных
PLANS_FILE = "user_plans.json"
CALENDARS_FILE = "user_calendars.json"
STATS_FILE = "user_stats.json"

# Дни недели
WEEK_DAYS = {
    "monday": "Понедельник",
    "tuesday": "Вторник",
    "wednesday": "Среда",
    "thursday": "Четверг",
    "friday": "Пятница",
    "saturday": "Суббота",
    "sunday": "Воскресенье"
}

# Уровни активности
ACTIVITY_LEVELS = {
    "low": "Низкая (сидячий образ жизни)",
    "moderate": "Средняя (тренировки 1-3 раза в неделю)",
    "high": "Высокая (тренировки 4-5 раз в неделю)",
    "very_high": "Очень высокая (тренировки 6-7 раз в неделю)"
}

# Цели
GOALS = {
    "lose": "Похудеть",
    "gain": "Набрать массу",
    "maintain": "Поддержать форму"
}

# --- ФУНКЦИИ РАБОТЫ С ДАННЫМИ ---

def load_json(filename):
    if os.path.exists(filename):
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_json(filename, data):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_plans():
    return load_json(PLANS_FILE)

def save_plans(plans):
    save_json(PLANS_FILE, plans)

def load_calendars():
    return load_json(CALENDARS_FILE)

def save_calendars(calendars):
    save_json(CALENDARS_FILE, calendars)

def load_stats():
    return load_json(STATS_FILE)

def save_stats(stats):
    save_json(STATS_FILE, stats)

def get_agent(user_id: int) -> NutritionAgent:
    if user_id not in user_agents:
        user_agents[user_id] = NutritionAgent()
    return user_agents[user_id]

def get_user_calendar(user_id: str) -> dict:
    calendars = load_calendars()
    if user_id not in calendars:
        calendars[user_id] = {day: [] for day in WEEK_DAYS.keys()}
        save_calendars(calendars)
    return calendars[user_id]

def get_user_stats(user_id: str) -> dict:
    stats = load_stats()
    if user_id not in stats:
        stats[user_id] = {
            "total_workouts": 0,
            "completed_workouts": 0,
            "streak_days": 0,
            "last_workout_date": None
        }
        save_stats(stats)
    return stats[user_id]

def update_stats(user_id: str, action: str):
    stats = load_stats()
    if user_id not in stats:
        stats[user_id] = {
            "total_workouts": 0,
            "completed_workouts": 0,
            "streak_days": 0,
            "last_workout_date": None
        }
    
    if action == "add":
        stats[user_id]["total_workouts"] += 1
    elif action == "complete":
        stats[user_id]["completed_workouts"] += 1
        stats[user_id]["last_workout_date"] = datetime.now().strftime("%d.%m.%Y")
    
    save_stats(stats)
    return stats[user_id]

# --- ФУНКЦИИ ФОРМАТИРОВАНИЯ ---

def format_response(text: str) -> str:
    """
    Улучшает форматирование ответа для Telegram.
    Преобразует таблицы в красивые блоки.
    """
    # Экранируем HTML
    # === ВАЖНО: Сначала заменяем <br> на реальные переносы строк ===
    text = text.replace('<br>', '\n')
    text = text.replace('<br/>', '\n')
    text = text.replace('<br />', '\n')
    
    # Экранируем HTML
    text = text.replace('&', '&amp;')
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')
    
    # Жирный и курсив
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'\*(.+?)\*', r'<i>\1</i>', text)
    
    # === ОБРАБОТКА ТАБЛИЦ ===
    lines = text.split('\n')
    formatted_lines = []
    in_table = False
    table_headers = []
    table_rows = []
    
    for line in lines:
        # Проверяем, это таблица?
        if '|' in line and line.strip().startswith('|'):
            in_table = True
            # Убираем лишние | и пробелы
            cells = [cell.strip() for cell in line.split('|') if cell.strip()]
            
            # Пропускаем разделительную строку (---|---|---)
            if all(c.replace('-', '').replace(':', '').strip() == '' for c in cells):
                continue
            
            if not table_headers:
                table_headers = cells
            else:
                table_rows.append(cells)
        else:
            # Если вышли из таблицы, форматируем её
            if in_table and table_headers:
                # Форматируем таблицу как красивый блок
                formatted_table = format_table_as_block(table_headers, table_rows)
                formatted_lines.extend(formatted_table)
                table_headers = []
                table_rows = []
                in_table = False
            
            # Обрабатываем списки
            if line.strip().startswith('- ') or line.strip().startswith('• '):
                formatted_lines.append('  • ' + line.strip()[2:])
            else:
                formatted_lines.append(line)
    
    # Если таблица была в конце текста
    if in_table and table_headers:
        formatted_table = format_table_as_block(table_headers, table_rows)
        formatted_lines.extend(formatted_table)
    
    text = '\n'.join(formatted_lines)
    
    # === ДОБАВЛЕНИЕ ЭМОДЗИ ===
    emoji_map = {
        'калори': '🔥', 'белки': '🥩', 'жиры': '', 'углеводы': '🍞',
        'тренировк': '💪', 'рацион': '🍽️', 'завтрак': '🌅', 'обед': '☀️',
        'полдник': '🍪', 'ужин': '🌙', 'цель': '', 'вес': '⚖️',
        'рост': '', 'возраст': '🎂', 'активность': '🏃',
        'похуден': '📉', 'набор': '📈', 'поддержан': '⚖️',
        'понедельник': '📅', 'вторник': '📅', 'среда': '',
        'четверг': '', 'пятница': '📅', 'суббота': '📅', 'воскресенье': '📅'
    }
    
    lines = text.split('\n')
    for i, line in enumerate(lines):
        for key, emoji in emoji_map.items():
            if key in line.lower():
                if not any(e in line for e in emoji_map.values()):
                    lines[i] = f'{emoji} {line}'
                break
    
    text = '\n'.join(lines)
    
    return text


def format_table_as_block(headers: list, rows: list) -> list:
    """
    Преобразует таблицу в красивый блок с эмодзи.
    """
    if not headers or not rows:
        return []
    
    result = []
    result.append("<b>" + "─" * 40 + "</b>")
    
    # Заголовки
    header_text = " | ".join(headers)
    result.append(f"<b>{header_text}</b>")
    result.append("<b>" + "─" * 40 + "</b>")
    
    # Строки
    for row in rows:
        # Добавляем эмодзи в зависимости от содержимого
        row_emoji = ""
        if any("калори" in cell.lower() for cell in row):
            row_emoji = "🔥"
        elif any("белк" in cell.lower() for cell in row):
            row_emoji = "🥩"
        elif any("жир" in cell.lower() for cell in row):
            row_emoji = "🥑"
        elif any("углевод" in cell.lower() for cell in row):
            row_emoji = "🍞"
        
        row_text = " | ".join(row)
        result.append(f"{row_emoji} {row_text}")
    
    result.append("<b>" + "─" * 40 + "</b>")
    
    return result

def format_calendar(user_id: str) -> str:
    calendar = get_user_calendar(user_id)
    stats = get_user_stats(user_id)
    
    text = "<b> Твой недельный календарь тренировок</b>\n\n"
    
    for day_key, day_name in WEEK_DAYS.items():
        trainings = calendar.get(day_key, [])
        text += f"<b>📌 {day_name}:</b>\n"
        
        if trainings:
            for i, training in enumerate(trainings, 1):
                status = "✅" if training.get("completed", False) else "⬜"
                text += f"  {status} {i}. {training['name']}\n"
        else:
            text += "  <i>Нет запланированных тренировок</i>\n"
        
        text += "\n"
    
    text += f"<b>📊 Твоя статистика:</b>\n"
    text += f"  • Всего тренировок: {stats['total_workouts']}\n"
    text += f"  • Выполнено: {stats['completed_workouts']}\n"
    text += f"  • Прогресс: {round(stats['completed_workouts'] / max(stats['total_workouts'], 1) * 100)}%\n\n"
    text += "<i>Используй кнопки ниже для управления</i>"
    
    return text

def send_long_message(chat_id: int, text: str):
    formatted_text = format_response(text)
    max_length = 4000
    
    for i in range(0, len(formatted_text), max_length):
        chunk = formatted_text[i:i + max_length]
        try:
            bot.send_message(chat_id, chunk, parse_mode="HTML")
        except Exception as e:
            logging.error(f"Ошибка отправки сообщения (HTML): {e}")
            try:
                clean_text = re.sub(r'<[^>]+>', '', chunk)
                bot.send_message(chat_id, clean_text, parse_mode=None)
            except Exception as e2:
                logging.error(f"Ошибка отправки сообщения (текст): {e2}")
                bot.send_message(chat_id, " Произошла ошибка при отправке ответа.", parse_mode=None)

# --- КЛАВИАТУРЫ ---

def get_main_menu():
    """Главное меню."""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton(" Рассчитать КБЖУ"),
        types.KeyboardButton("💪 Программа тренировок")
    )
    markup.add(
        types.KeyboardButton(" Календарь тренировок"),
        types.KeyboardButton("📋 Мои планы")
    )
    markup.add(
        types.KeyboardButton("📈 Статистика"),
        types.KeyboardButton("❓ Помощь")
    )
    return markup

def get_calendar_menu():
    """Меню календаря."""
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("➕ Добавить", callback_data="cal_add"),
        types.InlineKeyboardButton(" Удалить", callback_data="cal_delete")
    )
    markup.add(
        types.InlineKeyboardButton("✅ Отметить выполненной", callback_data="cal_complete"),
        types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")
    )
    return markup

def get_days_menu(action_prefix: str):
    """Меню выбора дня недели."""
    markup = types.InlineKeyboardMarkup(row_width=2)
    for day_key, day_name in WEEK_DAYS.items():
        markup.add(types.InlineKeyboardButton(f"📅 {day_name}", callback_data=f"{action_prefix}_{day_key}"))
    markup.add(types.InlineKeyboardButton("🔙 Отмена", callback_data="cancel"))
    return markup

def get_goals_menu():
    """Меню выбора цели."""
    markup = types.InlineKeyboardMarkup(row_width=1)
    for goal_key, goal_name in GOALS.items():
        markup.add(types.InlineKeyboardButton(f"🎯 {goal_name}", callback_data=f"goal_{goal_key}"))
    markup.add(types.InlineKeyboardButton("🔙 Отмена", callback_data="cancel"))
    return markup

def get_activity_menu():
    """Меню выбора уровня активности."""
    markup = types.InlineKeyboardMarkup(row_width=1)
    for act_key, act_name in ACTIVITY_LEVELS.items():
        markup.add(types.InlineKeyboardButton(f" {act_name}", callback_data=f"act_{act_key}"))
    markup.add(types.InlineKeyboardButton("🔙 Отмена", callback_data="cancel"))
    return markup

# --- ОБРАБОТЧИКИ КОМАНД ---

@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    get_agent(user_id)
    
    welcome_text = (
        "<b>👋 Привет! Я твой персональный ИИ-ассистент по фитнесу и питанию.</b>\n\n"
        "<b>🛠 Что я умею:</b>\n"
        "• Рассчитывать суточную норму КБЖУ\n"
        "• Составлять программы тренировок и рационы\n"
        "• Вести твой личный календарь тренировок\n"
        "• Сохранять планы для быстрого доступа\n"
        "• Отслеживать твой прогресс\n\n"
        "<b>💡 Как начать?</b>\n"
        "Выбери действие из меню ниже или напиши свой запрос:\n\n"
        "<i>Пример: «Я мужчина, 29 лет, вес 120 кг, рост 186 см, низкая активность. Хочу похудеть на 30 кг.»</i>"
    )
    bot.send_message(message.chat.id, welcome_text, reply_markup=get_main_menu())

@bot.message_handler(commands=['reset'])
def reset_memory(message):
    user_id = message.from_user.id
    if user_id in user_agents:
        del user_agents[user_id]
    if user_id in user_states:
        del user_states[user_id]
    if user_id in user_data:
        del user_data[user_id]
    bot.send_message(message.chat.id, "🔄 <b>Память очищена.</b>\nНачнем диалог с чистого листа!", reply_markup=get_main_menu())

@bot.message_handler(commands=['help'])
def send_help(message):
    help_text = (
        "<b>📚 Доступные команды:</b>\n\n"
        "/start - Начать работу\n"
        "/reset - Очистить историю диалога\n"
        "/help - Показать это сообщение\n\n"
        "<b>💡 Или используй кнопки меню:</b>\n"
        "• 📊 Рассчитать КБЖУ\n"
        "• 💪 Программа тренировок\n"
        "• 📅 Календарь тренировок\n"
        "• 📋 Мои планы\n"
        "• 📈 Статистика"
    )
    bot.send_message(message.chat.id, help_text, reply_markup=get_main_menu())

# --- ОБРАБОТЧИКИ ТЕКСТОВЫХ КНОПОК ---

@bot.message_handler(func=lambda message: message.text == " Рассчитать КБЖУ")
def start_calc_macros(message):
    user_id = message.from_user.id
    user_states[user_id] = {"step": "gender", "action": "calc_macros"}
    user_data[user_id] = {}
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("👨 Мужской", callback_data="gender_male"),
        types.InlineKeyboardButton("👩 Женский", callback_data="gender_female")
    )
    
    bot.send_message(
        message.chat.id,
        "<b>📊 Расчет КБЖУ</b>\n\n"
        "Давай пройдем по шагам. Сначала выбери пол:",
        reply_markup=markup
    )

@bot.message_handler(func=lambda message: message.text == "💪 Программа тренировок")
def start_fitness_plan(message):
    user_id = message.from_user.id
    user_states[user_id] = {"step": "gender", "action": "fitness_plan"}
    user_data[user_id] = {}
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton(" Мужской", callback_data="gender_male"),
        types.InlineKeyboardButton("👩 Женский", callback_data="gender_female")
    )
    
    bot.send_message(
        message.chat.id,
        "<b>💪 Программа тренировок и рацион</b>\n\n"
        "Давай пройдем по шагам. Сначала выбери пол:",
        reply_markup=markup
    )

@bot.message_handler(func=lambda message: message.text == "📅 Календарь тренировок")
def show_calendar(message):
    user_id = str(message.from_user.id)
    calendar_text = format_calendar(user_id)
    bot.send_message(message.chat.id, calendar_text, reply_markup=get_calendar_menu())

@bot.message_handler(func=lambda message: message.text == "📋 Мои планы")
def show_my_plan(message):
    user_id = str(message.from_user.id)
    plans = load_plans()
    
    if user_id in plans:
        plan = plans[user_id]
        plan_text = (
            f"<b>📋 Твой сохраненный план</b>\n"
            f"<b>Дата создания:</b> {plan['created_at']}\n"
            f"<b>Цель:</b> {plan['goal']}\n\n"
            f"{plan['content']}"
        )
        send_long_message(message.chat.id, plan_text)
    else:
        bot.send_message(
            message.chat.id,
            "ℹ️ У тебя пока нет сохраненных планов.\n\n"
            "Используй кнопку « Программа тренировок», чтобы создать план!",
            reply_markup=get_main_menu()
        )

@bot.message_handler(func=lambda message: message.text == "📈 Статистика")
def show_stats(message):
    user_id = str(message.from_user.id)
    stats = get_user_stats(user_id)
    
    stats_text = (
        f"<b> Твоя статистика</b>\n\n"
        f"️ <b>Всего тренировок:</b> {stats['total_workouts']}\n"
        f"✅ <b>Выполнено:</b> {stats['completed_workouts']}\n"
        f"📊 <b>Прогресс:</b> {round(stats['completed_workouts'] / max(stats['total_workouts'], 1) * 100)}%\n"
        f"📅 <b>Последняя тренировка:</b> {stats['last_workout_date'] or 'Еще не было'}\n\n"
        f"<i>Продолжай в том же духе! 💪</i>"
    )
    bot.send_message(message.chat.id, stats_text, reply_markup=get_main_menu())

# --- ОБРАБОТКА INLINE-КНОПОК ---

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    user_id_str = str(user_id)
    
    # Возврат в главное меню
    if call.data == "back_to_main":
        bot.send_message(call.message.chat.id, "🔙 Возврат в главное меню", reply_markup=get_main_menu())
        bot.answer_callback_query(call.id)
        return
    
    # Отмена действия
    if call.data == "cancel":
        if user_id in user_states:
            del user_states[user_id]
        if user_id in user_data:
            del user_data[user_id]
        bot.send_message(call.message.chat.id, "❌ Действие отменено", reply_markup=get_main_menu())
        bot.answer_callback_query(call.id)
        return
    
    # Выбор пола
    if call.data.startswith("gender_"):
        gender = "male" if call.data == "gender_male" else "female"
        
        # Инициализируем user_data, если еще нет
        if user_id not in user_data:
            user_data[user_id] = {}
        
        user_data[user_id]["gender"] = gender
        
        # ВАЖНО: Обновляем шаг!
        if user_id in user_states:
            user_states[user_id]["step"] = "age"
        
        bot.send_message(
            call.message.chat.id,
            f"✅ Пол: <b>{'Мужской' if gender == 'male' else 'Женский'}</b>\n\n"
            "Теперь напиши свой возраст (например, 25):"
        )
        bot.answer_callback_query(call.id)
        return
    
    # Выбор уровня активности
    if call.data.startswith("act_"):
        activity = call.data.replace("act_", "")
        user_data[user_id]["activity_level"] = activity
        
        if user_states[user_id]["action"] == "calc_macros":
            # Для КБЖУ собираем данные и отправляем агенту
            data = user_data[user_id]
            query = f"Рассчитай КБЖУ для {'мужчины' if data['gender'] == 'male' else 'женщины'}, {data['age']} лет, вес {data['weight']} кг, рост {data['height']} см, {ACTIVITY_LEVELS[activity].split(' ')[0].lower()} активность."
            
            del user_states[user_id]
            del user_data[user_id]
            
            bot.send_message(call.message.chat.id, "⏳ Рассчитываю...", reply_markup=get_main_menu())
            agent = get_agent(user_id)
            response = agent.process_input(query)
            send_long_message(call.message.chat.id, response)
        else:
            # Для программы тренировок спрашиваем цель
            bot.send_message(
                call.message.chat.id,
                f"✅ Активность: <b>{ACTIVITY_LEVELS[activity]}</b>\n\n"
                "Теперь выбери цель:",
                reply_markup=get_goals_menu()
            )
        
        bot.answer_callback_query(call.id)
        return
    
    # Выбор цели
    if call.data.startswith("goal_"):
        goal = call.data.replace("goal_", "")
        user_data[user_id]["goal"] = goal
        
        # ВАЖНО: Обновляем шаг!
        if user_id in user_states:
            user_states[user_id]["step"] = "goal_weight"
        
        bot.send_message(
            call.message.chat.id,
            f"✅ Цель: <b>{GOALS[goal]}</b>\n\n"
            "Напиши, на сколько кг хочешь изменить вес (например, 10):\n"
            "<i>Если цель «Поддержать форму», напиши 0</i>"
        )
        bot.answer_callback_query(call.id)
    return
    
    # Календарь - добавить тренировку
    if call.data == "cal_add":
        bot.send_message(
            call.message.chat.id,
            "<b>➕ Добавление тренировки</b>\n\n"
            "Выбери день недели:",
            reply_markup=get_days_menu("add")
        )
        bot.answer_callback_query(call.id)
        return
    
    # Календарь - удалить тренировку
    if call.data == "cal_delete":
        bot.send_message(
            call.message.chat.id,
            "<b>🗑 Удаление тренировки</b>\n\n"
            "Выбери день недели:",
            reply_markup=get_days_menu("del")
        )
        bot.answer_callback_query(call.id)
        return
    
    # Календарь - отметить выполненной
    if call.data == "cal_complete":
        bot.send_message(
            call.message.chat.id,
            "<b>✅ Отметка тренировки</b>\n\n"
            "Выбери день недели:",
            reply_markup=get_days_menu("comp")
        )
        bot.answer_callback_query(call.id)
        return
    
    # Добавление тренировки - выбор дня
    if call.data.startswith("add_"):
        day_key = call.data.replace("add_", "")
        user_states[user_id] = {"action": "add_training", "day": day_key}
        bot.send_message(
            call.message.chat.id,
            f"<b>➕ Добавление тренировки на {WEEK_DAYS[day_key]}</b>\n\n"
            "Напиши название тренировки:\n"
            "<i>Например: Жим лежа 4x10, Приседания 5x5, Бег 30 минут</i>"
        )
        bot.answer_callback_query(call.id)
        return
    
    # Удаление тренировки - выбор дня
    if call.data.startswith("del_"):
        day_key = call.data.replace("del_", "")
        calendar = get_user_calendar(user_id_str)
        trainings = calendar.get(day_key, [])
        
        if not trainings:
            bot.send_message(call.message.chat.id, "ℹ️ В этот день нет тренировок.")
            bot.answer_callback_query(call.id)
            return
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        for i, training in enumerate(trainings):
            markup.add(types.InlineKeyboardButton(
                f"❌ {i+1}. {training['name']}",
                callback_data=f"del_confirm_{day_key}_{i}"
            ))
        markup.add(types.InlineKeyboardButton("🔙 Отмена", callback_data="cancel"))
        
        bot.send_message(
            call.message.chat.id,
            f"<b>🗑 Удаление тренировки на {WEEK_DAYS[day_key]}</b>\n\n"
            "Выбери тренировку для удаления:",
            reply_markup=markup
        )
        bot.answer_callback_query(call.id)
        return
    
    # Подтверждение удаления
    if call.data.startswith("del_confirm_"):
        parts = call.data.split("_")
        day_key = parts[2]
        training_index = int(parts[3])
        
        calendars = load_calendars()
        if user_id_str in calendars and day_key in calendars[user_id_str]:
            training_name = calendars[user_id_str][day_key][training_index]['name']
            del calendars[user_id_str][day_key][training_index]
            save_calendars(calendars)
            update_stats(user_id_str, "delete")
            
            bot.send_message(
                call.message.chat.id,
                f"✅ Тренировка <b>«{training_name}»</b> удалена!",
                reply_markup=get_main_menu()
            )
        bot.answer_callback_query(call.id)
        return
    
    # Отметка тренировки - выбор дня
    if call.data.startswith("comp_"):
        day_key = call.data.replace("comp_", "")
        calendar = get_user_calendar(user_id_str)
        trainings = calendar.get(day_key, [])
        
        if not trainings:
            bot.send_message(call.message.chat.id, "ℹ️ В этот день нет тренировок.")
            bot.answer_callback_query(call.id)
            return
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        for i, training in enumerate(trainings):
            status = "✅" if training.get("completed", False) else "⬜"
            markup.add(types.InlineKeyboardButton(
                f"{status} {i+1}. {training['name']}",
                callback_data=f"comp_confirm_{day_key}_{i}"
            ))
        markup.add(types.InlineKeyboardButton("🔙 Отмена", callback_data="cancel"))
        
        bot.send_message(
            call.message.chat.id,
            f"<b>✅ Отметка тренировки на {WEEK_DAYS[day_key]}</b>\n\n"
            "Выбери тренировку:",
            reply_markup=markup
        )
        bot.answer_callback_query(call.id)
        return
    
    # Подтверждение отметки
    if call.data.startswith("comp_confirm_"):
        parts = call.data.split("_")
        day_key = parts[2]
        training_index = int(parts[3])
        
        calendars = load_calendars()
        if user_id_str in calendars and day_key in calendars[user_id_str]:
            training = calendars[user_id_str][day_key][training_index]
            training['completed'] = not training.get('completed', False)
            save_calendars(calendars)
            
            if training['completed']:
                update_stats(user_id_str, "complete")
            
            status = "выполнена ✅" if training['completed'] else "не выполнена "
            bot.send_message(
                call.message.chat.id,
                f"✅ Тренировка <b>«{training['name']}»</b> теперь {status}!",
                reply_markup=get_main_menu()
            )
        bot.answer_callback_query(call.id)
        return
    
    bot.answer_callback_query(call.id)

# --- ОБРАБОТКА ТЕКСТОВЫХ СООБЩЕНИЙ (пошаговый ввод) ---

@bot.message_handler(func=lambda message: message.from_user.id in user_states)
def handle_user_state(message):
    user_id = message.from_user.id
    user_id_str = str(user_id)
    state = user_states[user_id]
    data = user_data.get(user_id, {})
    
    # Добавление тренировки
    if state.get("action") == "add_training":
        day_key = state["day"]
        training_name = message.text.strip()
        
        if not training_name:
            bot.send_message(message.chat.id, "❌ Название тренировки не может быть пустым.")
            return
        
        calendars = load_calendars()
        if user_id_str not in calendars:
            calendars[user_id_str] = {day: [] for day in WEEK_DAYS.keys()}
        
        calendars[user_id_str][day_key].append({
            "name": training_name,
            "completed": False,
            "added_at": datetime.now().strftime("%d.%m.%Y %H:%M")
        })
        save_calendars(calendars)
        update_stats(user_id_str, "add")
        
        del user_states[user_id]
        
        bot.send_message(
            message.chat.id,
            f"✅ Тренировка <b>«{training_name}»</b> добавлена на {WEEK_DAYS[day_key]}!",
            reply_markup=get_main_menu()
        )
        return
    
    # Пошаговый ввод для КБЖУ и программы тренировок
    step = state.get("step")
    
    if step == "gender":
        # Этот шаг обрабатывается через inline-кнопки
        return
    
    elif step == "age":
        try:
            age = int(message.text.strip())
            if age < 10 or age > 100:
                bot.send_message(message.chat.id, "❌ Возраст должен быть от 10 до 100 лет. Попробуй еще раз:")
                return
            data["age"] = age
            user_data[user_id] = data
            bot.send_message(message.chat.id, f"✅ Возраст: <b>{age} лет</b>\n\nТеперь напиши свой вес в кг (например, 75):")
            user_states[user_id]["step"] = "weight"
        except ValueError:
            bot.send_message(message.chat.id, "❌ Пожалуйста, введи число (например, 25):")
        return
    
    elif step == "weight":
        try:
            weight = float(message.text.strip())
            if weight < 30 or weight > 300:
                bot.send_message(message.chat.id, "❌ Вес должен быть от 30 до 300 кг. Попробуй еще раз:")
                return
            data["weight"] = weight
            user_data[user_id] = data
            bot.send_message(message.chat.id, f"✅ Вес: <b>{weight} кг</b>\n\nТеперь напиши свой рост в см (например, 180):")
            user_states[user_id]["step"] = "height"
        except ValueError:
            bot.send_message(message.chat.id, "❌ Пожалуйста, введи число (например, 75):")
        return
    
    elif step == "height":
        try:
            height = float(message.text.strip())
            if height < 100 or height > 250:
                bot.send_message(message.chat.id, "❌ Рост должен быть от 100 до 250 см. Попробуй еще раз:")
                return
            data["height"] = height
            user_data[user_id] = data
            bot.send_message(
                message.chat.id,
                f"✅ Рост: <b>{height} см</b>\n\nТеперь выбери уровень активности:",
                reply_markup=get_activity_menu()
            )
            user_states[user_id]["step"] = "activity"
        except ValueError:
            bot.send_message(message.chat.id, "❌ Пожалуйста, введи число (например, 180):")
        return
    
    elif step == "goal_weight":
        try:
            target = float(message.text.strip())
            if target < 0 or target > 100:
                bot.send_message(message.chat.id, "❌ Значение должно быть от 0 до 100 кг. Попробуй еще раз:")
                return
            data["target_weight_change"] = target
            user_data[user_id] = data
            
            # Формируем запрос для агента
            gender_text = "мужчины" if data["gender"] == "male" else "женщины"
            goal_text = GOALS[data["goal"]]
            activity_text = ACTIVITY_LEVELS[data["activity_level"]].split(" ")[0].lower()
            
            query = f"Я {gender_text}, {data['age']} лет, вес {data['weight']} кг, рост {data['height']} см, {activity_text} активность. Хочу {goal_text.lower()} на {target} кг. Составь программу тренировок и рацион."
            
            del user_states[user_id]
            del user_data[user_id]
            
            bot.send_message(message.chat.id, " Составляю программу...", reply_markup=get_main_menu())
            agent = get_agent(user_id)
            response = agent.process_input(query)
            
            # Сохраняем план
            plans = load_plans()
            plans[user_id_str] = {
                "created_at": datetime.now().strftime("%d.%m.%Y %H:%M"),
                "goal": goal_text,
                "content": response
            }
            save_plans(plans)
            
            response += "\n\n💾 <i>План автоматически сохранен! Используй кнопку «📋 Мои планы», чтобы посмотреть его позже.</i>"
            send_long_message(message.chat.id, response)
        except ValueError:
            bot.send_message(message.chat.id, "❌ Пожалуйста, введи число (например, 10):")
        return

# --- ОБРАБОТКА ОБЫЧНЫХ СООБЩЕНИЙ ---

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    user_id = message.from_user.id
    agent = get_agent(user_id)
    
    bot.send_chat_action(message.chat.id, 'typing')
    
    try:
        response = agent.process_input(message.text)
        
        if "программа тренировок" in response.lower() or "рацион" in response.lower():
            plans = load_plans()
            plans[str(user_id)] = {
                "created_at": datetime.now().strftime("%d.%m.%Y %H:%M"),
                "goal": "Фитнес-план",
                "content": response
            }
            save_plans(plans)
            response += "\n\n💾 <i>План автоматически сохранен! Используй кнопку «📋 Мои планы», чтобы посмотреть его позже.</i>"
        
        send_long_message(message.chat.id, response)
        
    except Exception as e:
        logging.error(f"Критическая ошибка при обработке сообщения от {user_id}: {e}")
        bot.send_message(message.chat.id, "😕 Произошла внутренняя ошибка. Попробуйте переформулировать запрос или нажмите /reset.", reply_markup=get_main_menu())

# --- Механизм защиты от "засыпания" ---
app = Flask(__name__)

@app.route('/', methods=['GET'])
def health_check():
    return "Bot is running!", 200

def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))

if __name__ == "__main__":
    logging.info("🚀 Запуск бота и веб-сервера для поддержания активности...")
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    bot.infinity_polling(timeout=60, long_polling_timeout=60)