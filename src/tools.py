import json

def calculate_macros(gender: str, age: int, weight: float, height: float, activity_level: str) -> dict:
    """
    Рассчитывает суточную норму калорий и макронутриентов по формуле Миффлина-Сан Жеора.
    """
    # Валидация входных данных
    if weight <= 0 or height <= 0 or age <= 0:
        return {"status": "error", "message": "Вес, рост и возраст должны быть положительными числами."}
    
    if gender not in ["male", "female", "мужской", "женский"]:
        return {"status": "error", "message": "Пол должен быть указан как male/male или female/женский."}

    activity_multipliers = {
        "низкий": 1.2, "sedentary": 1.2,
        "средний": 1.55, "moderate": 1.55,
        "высокий": 1.725, "high": 1.725,
        "очень высокий": 1.9, "very_high": 1.9
    }

    if activity_level.lower() not in activity_multipliers:
        return {"status": "error", "message": f"Неизвестный уровень активности: {activity_level}. Допустимые: низкий, средний, высокий, очень высокий."}

    multiplier = activity_multipliers[activity_level.lower()]

    # Расчёт базового обмена веществ (BMR)
    is_male = gender.lower() in ["male", "мужской"]
    if is_male:
        bmr = 10 * weight + 6.25 * height - 5 * age + 5
    else:
        bmr = 10 * weight + 6.25 * height - 5 * age - 161

    # Общая суточная калорийность (TDEE)
    calories = round(bmr * multiplier)

    # Расчёт макронутриентов
    protein_g = round(weight * 2)
    protein_cal = protein_g * 4
    
    fat_g = round(weight * 1)
    fat_cal = fat_g * 9
    
    carbs_cal = max(0, calories - protein_cal - fat_cal)
    carbs_g = round(carbs_cal / 4)

    return {
        "status": "success",
        "calories": calories,
        "protein_g": protein_g,
        "fat_g": fat_g,
        "carbs_g": carbs_g,
        "bmr": round(bmr)
    }


def create_fitness_plan(
    gender: str,
    age: int,
    weight: float,
    height: float,
    activity_level: str,
    goal: str,
    target_weight_change: float
) -> dict:
    """
    Создаёт комплексную программу тренировок и рацион питания с учётом цели пользователя.
    """
    # Валидация входных данных
    if weight <= 0 or height <= 0 or age <= 0:
        return {"status": "error", "message": "Вес, рост и возраст должны быть положительными числами."}
    
    if gender not in ["male", "female", "мужской", "женский"]:
        return {"status": "error", "message": "Пол должен быть указан как male/male или female/женский."}

    activity_multipliers = {
        "низкий": 1.2, "sedentary": 1.2,
        "средний": 1.55, "moderate": 1.55,
        "высокий": 1.725, "high": 1.725,
        "очень высокий": 1.9, "very_high": 1.9
    }

    if activity_level.lower() not in activity_multipliers:
        return {"status": "error", "message": f"Неизвестный уровень активности: {activity_level}."}

    if goal not in ["lose_weight", "gain_weight", "maintain", "похудеть", "набрать", "поддержать"]:
        return {"status": "error", "message": f"Неизвестная цель: {goal}. Допустимые: lose_weight/похудеть, gain_weight/набрать, maintain/поддержать."}

    if target_weight_change < 0:
        return {"status": "error", "message": "Изменение веса не может быть отрицательным."}

    multiplier = activity_multipliers[activity_level.lower()]

    # Расчёт BMR
    is_male = gender.lower() in ["male", "мужской"]
    if is_male:
        bmr = 10 * weight + 6.25 * height - 5 * age + 5
    else:
        bmr = 10 * weight + 6.25 * height - 5 * age - 161

    # Базовая калорийность
    base_calories = round(bmr * multiplier)

    # Корректировка под цель
    goal_normalized = goal.lower()
    if goal_normalized in ["lose_weight", "похудеть"]:
        target_calories = round(base_calories * 0.80)  # Дефицит 20%
        protein_multiplier = 2.2  # Больше белка для сохранения мышц
        goal_description = "Похудение"
    elif goal_normalized in ["gain_weight", "набрать"]:
        target_calories = round(base_calories * 1.15)  # Профицит 15%
        protein_multiplier = 2.0
        goal_description = "Набор массы"
    else:  # maintain
        target_calories = base_calories
        protein_multiplier = 2.0
        goal_description = "Поддержание формы"

    # Расчёт БЖУ под цель
    protein_g = round(weight * protein_multiplier)
    protein_cal = protein_g * 4
    
    fat_g = round(weight * 1.0)
    fat_cal = fat_g * 9
    
    carbs_cal = max(0, target_calories - protein_cal - fat_cal)
    carbs_g = round(carbs_cal / 4)

    # Генерация программы тренировок (3 дня в неделю)
    if is_male:
        training_plan = {
            "days_per_week": 3,
            "schedule": [
                {
                    "day": "Понедельник",
                    "focus": "Грудь и трицепс",
                    "exercises": [
                        "Жим штанги лёжа: 4 подхода по 8-10 повторений",
                        "Жим гантелей на наклонной скамье: 3 подхода по 10-12 повторений",
                        "Разводка гантелей: 3 подхода по 12-15 повторений",
                        "Французский жим: 3 подхода по 10-12 повторений",
                        "Разгибания на блоке: 3 подхода по 12-15 повторений"
                    ]
                },
                {
                    "day": "Среда",
                    "focus": "Спина и бицепс",
                    "exercises": [
                        "Подтягивания: 4 подхода по максимуму",
                        "Тяга штанги в наклоне: 4 подхода по 8-10 повторений",
                        "Тяга гантели одной рукой: 3 подхода по 10-12 повторений",
                        "Подъём штанги на бицепс: 3 подхода по 10-12 повторений",
                        "Молотковые сгибания: 3 подхода по 12-15 повторений"
                    ]
                },
                {
                    "day": "Пятница",
                    "focus": "Ноги и плечи",
                    "exercises": [
                        "Приседания со штангой: 4 подхода по 8-10 повторений",
                        "Жим ногами: 3 подхода по 10-12 повторений",
                        "Выпады с гантелями: 3 подхода по 12 повторений на каждую ногу",
                        "Жим гантелей сидя: 4 подхода по 10-12 повторений",
                        "Подъёмы гантелей через стороны: 3 подхода по 12-15 повторений"
                    ]
                }
            ],
            "cardio": "2-3 раза в неделю по 20-30 минут (бег, велосипед, эллипс)" if goal_normalized in ["lose_weight", "похудеть"] else "1-2 раза в неделю по 15-20 минут для поддержания здоровья"
        }
    else:
        training_plan = {
            "days_per_week": 3,
            "schedule": [
                {
                    "day": "Понедельник",
                    "focus": "Ноги и ягодицы",
                    "exercises": [
                        "Приседания со штангой: 4 подхода по 10-12 повторений",
                        "Становая тяга на прямых ногах: 3 подхода по 12-15 повторений",
                        "Выпады с гантелями: 3 подхода по 15 повторений на каждую ногу",
                        "Ягодичный мостик: 3 подхода по 15-20 повторений",
                        "Разведения ног в тренажёре: 3 подхода по 15-20 повторений"
                    ]
                },
                {
                    "day": "Среда",
                    "focus": "Верх тела и пресс",
                    "exercises": [
                        "Жим гантелей лёжа: 3 подхода по 12-15 повторений",
                        "Тяга верхнего блока: 3 подхода по 12-15 повторений",
                        "Тяга гантели в наклоне: 3 подхода по 12-15 повторений",
                        "Жим гантелей сидя: 3 подхода по 12-15 повторений",
                        "Планка: 3 подхода по 45-60 секунд",
                        "Скручивания: 3 подхода по 20 повторений"
                    ]
                },
                {
                    "day": "Пятница",
                    "focus": "Фулбоди и кардио",
                    "exercises": [
                        "Приседания с гантелями: 3 подхода по 15 повторений",
                        "Отжимания: 3 подхода по максимуму",
                        "Выпады назад: 3 подхода по 15 повторений на каждую ногу",
                        "Тяга гантелей к подбородку: 3 подхода по 12-15 повторений",
                        "Кардио: 20-30 минут (бег, велосипед, танцы)"
                    ]
                }
            ],
            "cardio": "2-3 раза в неделю по 20-30 минут (бег, велосипед, танцы, плавание)" if goal_normalized in ["lose_weight", "похудеть"] else "1-2 раза в неделю по 15-20 минут для поддержания здоровья"
        }

    # Генерация примерного рациона
    if goal_normalized in ["lose_weight", "похудеть"]:
        meal_plan = {
            "breakfast": {
                "description": "Овсянка на воде с ягодами и 1 варёным яйцом",
                "calories": round(target_calories * 0.25)
            },
            "lunch": {
                "description": "Куриная грудка (150г) + гречка (100г) + салат из свежих овощей",
                "calories": round(target_calories * 0.35)
            },
            "snack": {
                "description": "Творог 5% (150г) + яблоко",
                "calories": round(target_calories * 0.15)
            },
            "dinner": {
                "description": "Рыба запечённая (150г) + овощи на пару (200г)",
                "calories": round(target_calories * 0.25)
            }
        }
    else:
        meal_plan = {
            "breakfast": {
                "description": "Овсянка на молоке с бананом и орехами + 2 варёных яйца",
                "calories": round(target_calories * 0.25)
            },
            "lunch": {
                "description": "Говядина/курица (200г) + рис/макароны (150г) + салат",
                "calories": round(target_calories * 0.35)
            },
            "snack": {
                "description": "Протеиновый коктейль или творог с мёдом",
                "calories": round(target_calories * 0.15)
            },
            "dinner": {
                "description": "Лосось/курица (200г) + картофель запечённый (150г) + овощи",
                "calories": round(target_calories * 0.25)
            }
        }

    # Расчёт времени достижения цели
    if goal_normalized in ["lose_weight", "похудеть"] and target_weight_change > 0:
        weeks_to_goal = round(target_weight_change / 0.5)  # 0.5 кг в неделю — безопасная скорость
        timeline = f"Примерно {weeks_to_goal} недель (при безопасной потере 0.5 кг в неделю)"
    elif goal_normalized in ["gain_weight", "набрать"] and target_weight_change > 0:
        weeks_to_goal = round(target_weight_change / 0.3)  # 0.3 кг в неделю
        timeline = f"Примерно {weeks_to_goal} недель (при безопасном наборе 0.3 кг в неделю)"
    else:
        timeline = "Поддержание текущей формы"

    return {
        "status": "success",
        "goal": goal_description,
        "target_weight_change_kg": target_weight_change,
        "timeline": timeline,
        "daily_nutrition": {
            "calories": target_calories,
            "protein_g": protein_g,
            "fat_g": fat_g,
            "carbs_g": carbs_g
        },
        "meal_plan": meal_plan,
        "training_plan": training_plan
    }


# Описание инструментов для OpenAI Function Calling
TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "calculate_macros",
            "description": "Рассчитывает суточную норму калорий и макронутриентов (БЖУ) на основе параметров пользователя.",
            "parameters": {
                "type": "object",
                "properties": {
                    "gender": {"type": "string", "description": "Пол: 'male' или 'female'"},
                    "age": {"type": "integer", "description": "Возраст в годах"},
                    "weight": {"type": "number", "description": "Вес в килограммах"},
                    "height": {"type": "number", "description": "Рост в сантиметрах"},
                    "activity_level": {"type": "string", "description": "Уровень активности: 'низкий', 'средний', 'высокий', 'очень высокий'"}
                },
                "required": ["gender", "age", "weight", "height", "activity_level"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_fitness_plan",
            "description": "Создаёт комплексную программу тренировок и рацион питания с учётом цели пользователя (похудеть, набрать массу, поддержать форму).",
            "parameters": {
                "type": "object",
                "properties": {
                    "gender": {"type": "string", "description": "Пол: 'male' или 'female'"},
                    "age": {"type": "integer", "description": "Возраст в годах"},
                    "weight": {"type": "number", "description": "Текущий вес в килограммах"},
                    "height": {"type": "number", "description": "Рост в сантиметрах"},
                    "activity_level": {"type": "string", "description": "Уровень активности: 'низкий', 'средний', 'высокий', 'очень высокий'"},
                    "goal": {"type": "string", "description": "Цель: 'lose_weight' (похудеть), 'gain_weight' (набрать массу), 'maintain' (поддержать)"},
                    "target_weight_change": {"type": "number", "description": "Сколько килограммов нужно скинуть или набрать (положительное число)"}
                },
                "required": ["gender", "age", "weight", "height", "activity_level", "goal", "target_weight_change"]
            }
        }
    }
]