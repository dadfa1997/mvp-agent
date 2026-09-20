import os
import logging
import threading
import re
from datetime import datetime
from dotenv import load_dotenv
import telebot
from telebot import types
from flask import Flask
from apscheduler.schedulers.background import BackgroundScheduler
from src.agent import NutritionAgent
import database as db

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
user_states = {}
user_data = {}

# Словари
WEEK_DAYS = {
    "monday": "Понедельник",
    "tuesday": "Вторник",
    "wednesday": "Среда",
    "thursday": "Четверг",
    "friday": "Пятница",
    "saturday": "Суббота",
    "sunday": "Воскресенье"
}

ACTIVITY_LEVELS = {
    "low": "Низкая (сидячий образ жизни)",
    "moderate": "Средняя (тренировки 1-3 раза в неделю)",
    "high": "Высокая (тренировки 4-5 раз в неделю)",
    "very_high": "Очень высокая (тренировки 6-7 раз в неделю)"
}

GOALS = {
    "lose": "Похудеть",
    "gain": "Набрать массу",
    "maintain": "Поддержать форму"
}

ACTIVITY_RU = {
    "low": "Низкая",
    "moderate": "Средняя",
    "high": "Высокая",
    "very_high": "Очень высокая"
}

# --- Вспомогательные функции ---

def get_agent(user_id: int) -> NutritionAgent:
    if user_id not in user_agents:
        user_agents[user_id] = NutritionAgent()
    return user_agents[user_id]


def format_response(text: str) -> str:
    """Безопасно форматирует ответ для Telegram HTML."""
    # Заменяем <br> на переносы строк
    text = re.sub(r'<br\s*/?>', '\n', text)
    
    # Экранируем HTML-символы
    text = text.replace('&', '&amp;')
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')
    
    # Заголовки
    text = text.replace('### ', '<b> ')
    text = text.replace('## ', '<b>📋 ')
    text = text.replace('# ', '<b>📌 ')
    
    # Жирный и курсив через регулярки
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'\*(.+?)\*', r'<i>\1</i>', text)
    
    # Списки
    lines = text.split('\n')
    formatted_lines = []
    for line in lines:
        if line.strip().startswith('- ') or line.strip().startswith('• '):
            formatted_lines.append('  • ' + line.strip()[2:])
        else:
            formatted_lines.append(line)
    
    text = '\n'.join(formatted_lines)
    
    # Эмодзи для ключевых слов
    emoji_map = {
        'калори': '🔥', 'белки': '🥩', 'жиры': '🥑', 'углеводы': '🍞',
        'тренировк': '💪', 'рацион': '️', 'завтрак': '', 'обед': '☀️',
        'полдник': '🍪', 'ужин': '🌙', 'цель': '🎯', 'вес': '⚖️',
        'рост': '📏', 'возраст': '🎂', 'активность': '🏃',
        'похуден': '📉', 'набор': '📈', 'поддержан': '️',
        'понедельник': '📅', 'вторник': '', 'среда': '📅',
        'четверг': '📅', 'пятница': '📅', 'суббота': '📅', 'воскресенье': '📅'
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


def format_calendar(user_id: int) -> str:
    """Форматирует календарь тренировок."""
    calendar = db.get_calendar(user_id)
    stats = db.get_stats(user_id)
    
    text = "<b>📅 Твой недельный календарь тренировок</b>\n\n"
    
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
    
    total = stats['total_workouts']
    completed = stats['completed_workouts']
    progress = round(completed / max(total, 1) * 100)
    
    text += f"<b>📊 Твоя статистика:</b>\n"
    text += f"  • Всего тренировок: {total}\n"
    text += f"  • Выполнено: {completed}\n"
    text += f"  • Прогресс: {progress}%\n"
    text += f"  • Последняя: {stats['last_workout_date'] or 'Ещё не было'}\n\n"
    text += "<i>Используй кнопки ниже для управления</i>"
    
    return text


def send_long_message(chat_id: int, text: str, reply_markup=None):
    """Разбивает длинные сообщения на части."""
    formatted_text = format_response(text)
    max_length = 4000
    
    chunks = []
    for i in range(0, len(formatted_text), max_length):
        chunks.append(formatted_text[i:i + max_length])
    
    for idx, chunk in enumerate(chunks):
        try:
            bot.send_message(chat_id, chunk, parse_mode="HTML", reply_markup=reply_markup if idx == len(chunks) - 1 else None)
        except Exception as e:
            logging.error(f"Ошибка отправки (HTML): {e}")
            try:
                clean_text = re.sub(r'<[^>]+>', '', chunk)
                bot.send_message(chat_id, clean_text, parse_mode=None, reply_markup=reply_markup if idx == len(chunks) - 1 else None)
            except Exception as e2:
                logging.error(f"Ошибка отправки (текст): {e2}")
                bot.send_message(chat_id, "❌ Произошла ошибка при отправке ответа.", parse_mode=None)


# --- Клавиатуры ---

def get_main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton("📊 Рассчитать КБЖУ"),
        types.KeyboardButton("💪 Программа тренировок")
    )
    markup.add(
        types.KeyboardButton("📅 Календарь тренировок"),
        types.KeyboardButton(" Мои планы")
    )
    markup.add(
        types.KeyboardButton("📈 Статистика"),
        types.KeyboardButton("🔔 Напоминания")
    )
    markup.add(types.KeyboardButton("❓ Помощь"))
    return markup


def get_calendar_menu():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("➕ Добавить", callback_data="cal_add"),
        types.InlineKeyboardButton("🗑 Удалить", callback_data="cal_delete")
    )
    markup.add(
        types.InlineKeyboardButton("✅ Отметить выполненной", callback_data="cal_complete"),
        types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")
    )
    return markup


def get_days_menu(action_prefix: str):
    markup = types.InlineKeyboardMarkup(row_width=2)
    for day_key, day_name in WEEK_DAYS.items():
        markup.add(types.InlineKeyboardButton(f"📅 {day_name}", callback_data=f"{action_prefix}_{day_key}"))
    markup.add(types.InlineKeyboardButton("🔙 Отмена", callback_data="cancel"))
    return markup


def get_goals_menu():
    markup = types.InlineKeyboardMarkup(row_width=1)
    for goal_key, goal_name in GOALS.items():
        markup.add(types.InlineKeyboardButton(f"🎯 {goal_name}", callback_data=f"goal_{goal_key}"))
    markup.add(types.InlineKeyboardButton("🔙 Отмена", callback_data="cancel"))
    return markup


def get_activity_menu():
    markup = types.InlineKeyboardMarkup(row_width=1)
    for act_key, act_name in ACTIVITY_LEVELS.items():
        markup.add(types.InlineKeyboardButton(f"🏃 {act_name}", callback_data=f"act_{act_key}"))
    markup.add(types.InlineKeyboardButton("🔙 Отмена", callback_data="cancel"))
    return markup


def get_gender_menu():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("👨 Мужской", callback_data="gender_male"),
        types.InlineKeyboardButton(" Женский", callback_data="gender_female")
    )
    return markup


# --- Напоминания ---

def send_daily_reminders():
    """Отправляет напоминания о тренировках."""
    logging.info("⏰ Проверка напоминаний...")
    
    conn = db.get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM reminders WHERE enabled = 1")
    users = cursor.fetchall()
    conn.close()
    
    today = datetime.now().strftime("%A").lower()
    day_ru = WEEK_DAYS.get(today, "сегодня")
    
    for user_row in users:
        user_id = user_row["user_id"]
        trainings = db.get_todays_trainings(user_id, today)
        
        if trainings:
            training_list = "\n".join([f"  • {t['name']}" for t in trainings])
            reminder_text = (
                f"<b>🔔 Доброе утро! Сегодня у тебя тренировка!</b>\n\n"
                f"<b>📅 {day_ru}:</b>\n{training_list}\n\n"
                f"💪 Не забудь разминку и хорошее настроение!\n\n"
                f"<i>Напиши /complete, чтобы отметить выполнение</i>"
            )
            try:
                bot.send_message(user_id, reminder_text, parse_mode="HTML")
                logging.info(f"✅ Напоминание отправлено пользователю {user_id}")
            except Exception as e:
                logging.error(f"❌ Ошибка отправки напоминания пользователю {user_id}: {e}")


# --- Обработчики команд ---

@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    username = message.from_user.username or ""
    first_name = message.from_user.first_name or ""
    
    db.add_user(user_id, username, first_name)
    get_agent(user_id)
    
    welcome_text = (
        f"<b> Привет, {first_name}! Я твой персональный ИИ-ассистент по фитнесу и питанию.</b>\n\n"
        "<b> Что я умею:</b>\n"
        "• Рассчитывать суточную норму КБЖУ\n"
        "• Составлять программы тренировок и рационы\n"
        "• Вести твой личный календарь тренировок\n"
        "• Сохранять планы для быстрого доступа\n"
        "• Отслеживать твой прогресс\n"
        "• Напоминать о тренировках\n\n"
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
    bot.send_message(message.chat.id, "🔄 <b>Память очищена.</b>\nНачнём диалог с чистого листа!", reply_markup=get_main_menu())


@bot.message_handler(commands=['help'])
def send_help(message):
    help_text = (
        "<b>📚 Доступные команды:</b>\n\n"
        "/start - Начать работу\n"
        "/reset - Очистить историю диалога\n"
        "/calendar - Показать календарь тренировок\n"
        "/addtraining - Добавить тренировку\n"
        "/deletetraining - Удалить тренировку\n"
        "/complete - Отметить тренировку выполненной\n"
        "/myplan - Показать сохранённый план\n"
        "/deleteplan - Удалить сохранённый план\n"
        "/stats - Показать статистику\n"
        "/reminders - Настройки напоминаний\n"
        "/help - Показать это сообщение"
    )
    bot.send_message(message.chat.id, help_text, reply_markup=get_main_menu())


@bot.message_handler(commands=['calendar'])
def show_calendar_cmd(message):
    user_id = message.from_user.id
    calendar_text = format_calendar(user_id)
    bot.send_message(message.chat.id, calendar_text, reply_markup=get_calendar_menu())


@bot.message_handler(commands=['myplan'])
def show_my_plan_cmd(message):
    user_id = message.from_user.id
    plan = db.get_plan(user_id)
    
    if plan:
        plan_text = (
            f"<b>📋 Твой сохранённый план</b>\n"
            f"<b>Дата создания:</b> {plan['created_at']}\n"
            f"<b>Цель:</b> {plan['goal']}\n\n"
            f"{plan['content']}"
        )
        send_long_message(message.chat.id, plan_text)
    else:
        bot.send_message(
            message.chat.id,
            "ℹ️ У тебя пока нет сохранённых планов.\n\n"
            "Используй кнопку «💪 Программа тренировок», чтобы создать план!",
            reply_markup=get_main_menu()
        )


@bot.message_handler(commands=['deleteplan'])
def delete_plan_cmd(message):
    user_id = message.from_user.id
    db.delete_plan(user_id)
    bot.send_message(message.chat.id, " <b>План удалён.</b>", reply_markup=get_main_menu())


@bot.message_handler(commands=['stats'])
def show_stats_cmd(message):
    user_id = message.from_user.id
    stats = db.get_stats(user_id)
    
    total = stats['total_workouts']
    completed = stats['completed_workouts']
    progress = round(completed / max(total, 1) * 100)
    
    stats_text = (
        f"<b>📊 Твоя статистика</b>\n\n"
        f"⚖️ <b>Всего тренировок:</b> {total}\n"
        f"✅ <b>Выполнено:</b> {completed}\n"
        f"📊 <b>Прогресс:</b> {progress}%\n"
        f"📅 <b>Последняя тренировка:</b> {stats['last_workout_date'] or 'Ещё не было'}\n\n"
        f"<i>Продолжай в том же духе! 💪</i>"
    )
    bot.send_message(message.chat.id, stats_text, reply_markup=get_main_menu())


@bot.message_handler(commands=['reminders'])
def toggle_reminders_cmd(message):
    user_id = message.from_user.id
    new_status = db.toggle_reminder(user_id)
    
    if new_status:
        bot.send_message(message.chat.id, "🔔 <b>Напоминания включены!</b>\nТеперь я буду напоминать о тренировках каждое утро.", reply_markup=get_main_menu())
    else:
        bot.send_message(message.chat.id, "🔕 <b>Напоминания выключены.</b>", reply_markup=get_main_menu())


# --- Обработчики текстовых кнопок главного меню ---

@bot.message_handler(func=lambda message: message.text == "📊 Рассчитать КБЖУ")
def start_calc_macros(message):
    user_id = message.from_user.id
    profile = db.get_user_profile(user_id)
    
    if profile:
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("✅ Да, использовать мои данные", callback_data="use_saved_calc"),
            types.InlineKeyboardButton("🔄 Нет, ввести новые данные", callback_data="enter_new_calc")
        )
        
        gender_ru = "Мужской" if profile["gender"] == "male" else "Женский"
        act_ru = ACTIVITY_RU.get(profile["activity_level"], profile["activity_level"])
        
        bot.send_message(
            message.chat.id,
            f"<b>📊 Расчёт КБЖУ</b>\n\n"
            f"У меня уже есть твои данные:\n"
            f"• {gender_ru}, {profile['age']} лет\n"
            f"• Вес: {profile['weight']} кг, Рост: {profile['height']} см\n"
            f"• Активность: {act_ru}\n\n"
            f"Использовать их для расчёта?",
            reply_markup=markup
        )
    else:
        user_states[user_id] = {"step": "gender", "action": "calc_macros"}
        user_data[user_id] = {}
        bot.send_message(
            message.chat.id,
            "<b> Расчёт КБЖУ</b>\n\nДавай пройдём по шагам. Сначала выбери пол:",
            reply_markup=get_gender_menu()
        )


@bot.message_handler(func=lambda message: message.text == "💪 Программа тренировок")
def start_fitness_plan(message):
    user_id = message.from_user.id
    profile = db.get_user_profile(user_id)
    
    if profile:
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("✅ Да, использовать мои данные", callback_data="use_saved_plan"),
            types.InlineKeyboardButton("🔄 Нет, ввести новые данные", callback_data="enter_new_plan")
        )
        
        gender_ru = "Мужской" if profile["gender"] == "male" else "Женский"
        act_ru = ACTIVITY_RU.get(profile["activity_level"], profile["activity_level"])
        
        bot.send_message(
            message.chat.id,
            f"<b>💪 Программа тренировок и рацион</b>\n\n"
            f"У меня уже есть твои данные:\n"
            f"• {gender_ru}, {profile['age']} лет\n"
            f"• Вес: {profile['weight']} кг, Рост: {profile['height']} см\n"
            f"• Активность: {act_ru}\n\n"
            f"Использовать их для составления плана?",
            reply_markup=markup
        )
    else:
        user_states[user_id] = {"step": "gender", "action": "fitness_plan"}
        user_data[user_id] = {}
        bot.send_message(
            message.chat.id,
            "<b>💪 Программа тренировок и рацион</b>\n\nДавай пройдём по шагам. Сначала выбери пол:",
            reply_markup=get_gender_menu()
        )


@bot.message_handler(func=lambda message: message.text == "📅 Календарь тренировок")
def show_calendar_btn(message):
    user_id = message.from_user.id
    calendar_text = format_calendar(user_id)
    bot.send_message(message.chat.id, calendar_text, reply_markup=get_calendar_menu())


@bot.message_handler(func=lambda message: message.text == "📋 Мои планы")
def show_my_plan_btn(message):
    user_id = message.from_user.id
    plan = db.get_plan(user_id)
    
    if plan:
        plan_text = (
            f"<b>📋 Твой сохранённый план</b>\n"
            f"<b>Дата создания:</b> {plan['created_at']}\n"
            f"<b>Цель:</b> {plan['goal']}\n\n"
            f"{plan['content']}"
        )
        send_long_message(message.chat.id, plan_text)
    else:
        bot.send_message(
            message.chat.id,
            "ℹ️ У тебя пока нет сохранённых планов.\n\n"
            "Используй кнопку «💪 Программа тренировок», чтобы создать план!",
            reply_markup=get_main_menu()
        )


@bot.message_handler(func=lambda message: message.text == "📈 Статистика")
def show_stats_btn(message):
    user_id = message.from_user.id
    stats = db.get_stats(user_id)
    
    total = stats['total_workouts']
    completed = stats['completed_workouts']
    progress = round(completed / max(total, 1) * 100)
    
    stats_text = (
        f"<b>📊 Твоя статистика</b>\n\n"
        f"⚖️ <b>Всего тренировок:</b> {total}\n"
        f"✅ <b>Выполнено:</b> {completed}\n"
        f"📊 <b>Прогресс:</b> {progress}%\n"
        f"📅 <b>Последняя тренировка:</b> {stats['last_workout_date'] or 'Ещё не было'}"
    )
    bot.send_message(message.chat.id, stats_text, reply_markup=get_main_menu())


@bot.message_handler(func=lambda message: message.text == "🔔 Напоминания")
def toggle_reminders_btn(message):
    user_id = message.from_user.id
    new_status = db.toggle_reminder(user_id)
    
    if new_status:
        bot.send_message(message.chat.id, "🔔 <b>Напоминания включены!</b>", reply_markup=get_main_menu())
    else:
        bot.send_message(message.chat.id, "🔕 <b>Напоминания выключены.</b>", reply_markup=get_main_menu())


# --- Обработка inline-кнопок ---

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    
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
    
    # === Использование сохранённых данных ===
    if call.data in ["use_saved_calc", "use_saved_plan"]:
        profile = db.get_user_profile(user_id)
        action = "calc_macros" if call.data == "use_saved_calc" else "fitness_plan"
        
        bot.send_message(call.message.chat.id, "⏳ Обрабатываю твои данные...", reply_markup=get_main_menu())
        
        agent = get_agent(user_id)
        gender_text = "мужчины" if profile["gender"] == "male" else "женщины"
        act_text = ACTIVITY_RU.get(profile["activity_level"], "средняя").lower()
        
        if action == "calc_macros":
            query = f"Рассчитай КБЖУ для {gender_text}, {profile['age']} лет, вес {profile['weight']} кг, рост {profile['height']} см, {act_text} активность."
            response = agent.process_input(query)
            send_long_message(call.message.chat.id, response)
        else:
            # Для плана спрашиваем цель, так как она могла измениться
            user_states[user_id] = {"step": "goal", "action": "fitness_plan"}
            user_data[user_id] = dict(profile)
            
            bot.send_message(
                call.message.chat.id,
                "Отлично! Данные приняты. Теперь выбери текущую цель:",
                reply_markup=get_goals_menu()
            )
            bot.answer_callback_query(call.id)
            return
        
        bot.answer_callback_query(call.id)
        return
    
    # === Ввод новых данных ===
    if call.data in ["enter_new_calc", "enter_new_plan"]:
        action = "calc_macros" if call.data == "enter_new_calc" else "fitness_plan"
        user_states[user_id] = {"step": "gender", "action": action}
        user_data[user_id] = {}
        
        bot.send_message(
            call.message.chat.id,
            "Понял! Давай введём новые данные. Сначала выбери пол:",
            reply_markup=get_gender_menu()
        )
        bot.answer_callback_query(call.id)
        return
    
    # Выбор пола
    if call.data.startswith("gender_"):
        gender = "male" if call.data == "gender_male" else "female"
        
        if user_id not in user_data:
            user_data[user_id] = {}
        
        user_data[user_id]["gender"] = gender
        
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
            data = user_data[user_id]
            
            # Сохраняем профиль
            db.save_user_profile(user_id, data)
            
            query = f"Рассчитай КБЖУ для {'мужчины' if data['gender'] == 'male' else 'женщины'}, {data['age']} лет, вес {data['weight']} кг, рост {data['height']} см, {ACTIVITY_RU.get(activity, 'средняя').lower()} активность."
            
            del user_states[user_id]
            del user_data[user_id]
            
            bot.send_message(call.message.chat.id, "⏳ Рассчитываю...", reply_markup=get_main_menu())
            agent = get_agent(user_id)
            response = agent.process_input(query)
            send_long_message(call.message.chat.id, response)
        else:
            # Для программы тренировок спрашиваем цель
            if user_id in user_states:
                user_states[user_id]["step"] = "goal"
            
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
    
    # === Календарь ===
    if call.data == "cal_add":
        bot.send_message(
            call.message.chat.id,
            "<b>➕ Добавление тренировки</b>\n\n"
            "Выбери день недели:",
            reply_markup=get_days_menu("add")
        )
        bot.answer_callback_query(call.id)
        return
    
    if call.data == "cal_delete":
        bot.send_message(
            call.message.chat.id,
            "<b>🗑 Удаление тренировки</b>\n\n"
            "Выбери день недели:",
            reply_markup=get_days_menu("del")
        )
        bot.answer_callback_query(call.id)
        return
    
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
            "<i>Например: Жим лёжа 4x10, Приседания 5x5, Бег 30 минут</i>"
        )
        bot.answer_callback_query(call.id)
        return
    
    # Удаление тренировки - выбор дня
    if call.data.startswith("del_"):
        day_key = call.data.replace("del_", "")
        calendar = db.get_calendar(user_id)
        trainings = calendar.get(day_key, [])
        
        if not trainings:
            bot.send_message(call.message.chat.id, "ℹ️ В этот день нет тренировок.")
            bot.answer_callback_query(call.id)
            return
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        for i, training in enumerate(trainings):
            markup.add(types.InlineKeyboardButton(
                f"❌ {i+1}. {training['name']}",
                callback_data=f"del_confirm_{training['id']}"
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
        training_id = int(call.data.replace("del_confirm_", ""))
        db.delete_training(training_id, user_id)
        db.update_stats(user_id, "delete")
        
        bot.send_message(
            call.message.chat.id,
            "✅ Тренировка удалена!",
            reply_markup=get_main_menu()
        )
        bot.answer_callback_query(call.id)
        return
    
    # Отметка тренировки - выбор дня
    if call.data.startswith("comp_"):
        day_key = call.data.replace("comp_", "")
        calendar = db.get_calendar(user_id)
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
                callback_data=f"comp_confirm_{training['id']}"
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
        training_id = int(call.data.replace("comp_confirm_", ""))
        new_status = db.toggle_training_complete(training_id, user_id)
        
        if new_status:
            db.update_stats(user_id, "complete")
        
        status = "выполнена ✅" if new_status else "не выполнена "
        bot.send_message(
            call.message.chat.id,
            f"✅ Тренировка теперь {status}!",
            reply_markup=get_main_menu()
        )
        bot.answer_callback_query(call.id)
        return
    
    # === Добавить план в календарь ===
    if call.data == "add_plan_to_cal":
        db.add_training(user_id, "monday", "Тренировка А (из плана)")
        db.add_training(user_id, "wednesday", "Тренировка Б (из плана)")
        db.add_training(user_id, "friday", "Тренировка В (из плана)")
        db.update_stats(user_id, "add")
        db.update_stats(user_id, "add")
        db.update_stats(user_id, "add")
        
        bot.send_message(
            call.message.chat.id,
            "✅ <b>Готово!</b>\n\n"
            "Я добавил базовые тренировки на Понедельник, Среду и Пятницу.\n\n"
            "Ты можешь изменить их названия или удалить через:\n"
            "• /addtraining\n• /deletetraining\n• /calendar",
            reply_markup=get_main_menu()
        )
        bot.answer_callback_query(call.id)
        return
    
    bot.answer_callback_query(call.id)


# --- Обработка текстовых сообщений (пошаговый ввод) ---

@bot.message_handler(func=lambda message: message.from_user.id in user_states)
def handle_user_state(message):
    user_id = message.from_user.id
    state = user_states[user_id]
    data = user_data.get(user_id, {})
    
    # Добавление тренировки
    if state.get("action") == "add_training":
        day_key = state["day"]
        training_name = message.text.strip()
        
        if not training_name:
            bot.send_message(message.chat.id, "❌ Название тренировки не может быть пустым.")
            return
        
        db.add_training(user_id, day_key, training_name)
        db.update_stats(user_id, "add")
        
        del user_states[user_id]
        
        bot.send_message(
            message.chat.id,
            f"✅ Тренировка <b>«{training_name}»</b> добавлена на {WEEK_DAYS[day_key]}!",
            reply_markup=get_main_menu()
        )
        return
    
    # Пошаговый ввод
    step = state.get("step")
    
    if step == "age":
        try:
            age = int(message.text.strip())
            if age < 10 or age > 100:
                bot.send_message(message.chat.id, "❌ Возраст должен быть от 10 до 100 лет. Попробуй ещё раз:")
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
                bot.send_message(message.chat.id, "❌ Вес должен быть от 30 до 300 кг. Попробуй ещё раз:")
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
                bot.send_message(message.chat.id, "❌ Рост должен быть от 100 до 250 см. Попробуй ещё раз:")
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
                bot.send_message(message.chat.id, "❌ Значение должно быть от 0 до 100 кг. Попробуй ещё раз:")
                return
            data["target_weight_change"] = target
            user_data[user_id] = data
            
            # Сохраняем профиль
            db.save_user_profile(user_id, data)
            
            gender_text = "мужчины" if data["gender"] == "male" else "женщины"
            goal_text = GOALS[data["goal"]]
            activity_text = ACTIVITY_RU.get(data["activity_level"], "средняя").lower()
            
            query = f"Я {gender_text}, {data['age']} лет, вес {data['weight']} кг, рост {data['height']} см, {activity_text} активность. Хочу {goal_text.lower()} на {target} кг. Составь программу тренировок и рацион."
            
            del user_states[user_id]
            del user_data[user_id]
            
            bot.send_message(message.chat.id, "⏳ Составляю программу...", reply_markup=get_main_menu())
            agent = get_agent(user_id)
            response = agent.process_input(query)
            
            # Сохраняем план в БД
            db.save_plan(user_id, response, goal_text)
            
            # Создаём клавиатуру с кнопкой добавления в календарь
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("➕ Добавить базовый шаблон в календарь", callback_data="add_plan_to_cal"))
            
            response += "\n\n💾 <i>План автоматически сохранён! Используй кнопку «📋 Мои планы», чтобы посмотреть его позже.</i>"
            
            bot.send_message(message.chat.id, format_response(response), reply_markup=markup, parse_mode="HTML")
        except ValueError:
            bot.send_message(message.chat.id, "❌ Пожалуйста, введи число (например, 10):")
        return


# --- Обработка обычных сообщений ---

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    user_id = message.from_user.id
    agent = get_agent(user_id)
    
    bot.send_chat_action(message.chat.id, 'typing')
    
    try:
        response = agent.process_input(message.text)
        
        if "программа тренировок" in response.lower() or "рацион" in response.lower():
            db.save_plan(user_id, response, "Фитнес-план")
            
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("➕ Добавить базовый шаблон в календарь", callback_data="add_plan_to_cal"))
            
            response += "\n\n💾 <i>План автоматически сохранён! Используй кнопку «📋 Мои планы», чтобы посмотреть его позже.</i>"
            
            bot.send_message(message.chat.id, format_response(response), reply_markup=markup, parse_mode="HTML")
        else:
            send_long_message(message.chat.id, response)
        
    except Exception as e:
        logging.error(f"Критическая ошибка при обработке сообщения от {user_id}: {e}")
        bot.send_message(
            message.chat.id,
            "😕 Произошла внутренняя ошибка. Попробуйте переформулировать запрос или нажмите /reset.",
            reply_markup=get_main_menu()
        )


# --- Flask для поддержания активности на Render ---
app = Flask(__name__)

@app.route('/', methods=['GET'])
def health_check():
    return "Bot is running!", 200

def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))


# --- Планировщик напоминаний ---
def run_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(send_daily_reminders, 'cron', hour=8, minute=0)
    scheduler.start()
    logging.info("⏰ Планировщик напоминаний запущен")


# --- Запуск ---
if __name__ == "__main__":
    logging.info("🚀 Запуск бота...")
    
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    run_scheduler()
    
    bot.infinity_polling(timeout=60, long_polling_timeout=60)