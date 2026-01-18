from datetime import datetime, timedelta
from aiogram.types import Message, BufferedInputFile
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command, CommandObject
import asyncio
from aiogram.fsm.state import State, StatesGroup
from utils import fetch_city_temperature, build_daily_charts, lookup_food_fatsecret
from config import BOT_TOKEN, WATER_PER_WORKOUT, WEATHER_API_KEY, WORKOUT_CALORIES, logger
from aiogram import Bot, Dispatcher, Router, BaseMiddleware
from models import UserProfile


class UserProfileFSM(StatesGroup): 
    input_weight = State()
    input_height = State()
    input_age = State()
    select_activity_level = State()
    input_city_name = State()


class HydrationFSM(StatesGroup): 
    input_water_amount = State()

class NutritionFSM(StatesGroup):
    input_food_weight = State()
    input_food_title = State()

class StatisticsFSM(StatesGroup):
    select_time_range = State()


class TrainingFSM(StatesGroup):  
    choose_training_type = State()
    enter_training_time = State()
    confirm_training = State()


users: dict[int, UserProfile] = {}
router = Router()


class UserProfileGuardMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: Message, data: dict):
        uid = event.from_user.id

        allowed_commands = {"/start", "/help", "/profile"}
        message_text = event.text or ""
        current_state = data.get("raw_state")

        is_allowed_command = any(
            message_text.startswith(cmd) for cmd in allowed_commands
        )

        is_in_profile_fsm = current_state and current_state.startswith("UserProfileFSM")

        if is_allowed_command or is_in_profile_fsm:
            return await handler(event, data)

        if uid not in users:
            await event.answer(
                "Сначала нужно заполнить профиль. Используйте команду /profile."
            )
            return

        return await handler(event, data)


class ActivityLoggerMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: Message, data: dict):
        logger.info("Пользователь %s написал: %s", event.from_user.id, event.text)
        return await handler(event, data)
    
class ActivityLoggerMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: Message, data: dict):
        user = event.from_user
        text = event.text

        logger.info(
            "Сообщение от пользователя %s: %s",
            user.id,
            text
        )

        result = await handler(event, data)
        return result


router.message.middleware(ActivityLoggerMiddleware())
router.message.middleware(UserProfileGuardMiddleware())


@router.message(Command("start"))
async def start_bot_handler(message: Message):
    intro = "Привет! Я помогу тебе следить за водой, питанием и тренировками.\n\n"
    commands = [
        "/profile — заполнить профиль",
        "/food <еда> — добавить приём пищи",
        "/water <мл> — учесть выпитую воду",
        "/workout <тип> <мин> — записать тренировку",
        "/progress — посмотреть текущий прогресс",
        "/charts — графики за день",
        "/history — история активности",
    ]

    response_text = intro + "Доступные команды:\n" + "\n".join(commands)

    await message.answer(response_text)


@router.message(UserProfileFSM.input_height)
async def handle_height_input(message: Message, state: FSMContext):
    text_value = message.text

    try:
        parsed_height = float(text_value)
    except ValueError:
        await message.answer("Неверный формат. Введите число повторно:")
        return

    await state.update_data(height=parsed_height)
    await state.set_state(UserProfileFSM.input_age)
    await message.answer("Пожалуйста, введите ваш возраст:")


@router.message(Command("profile"))
async def start_profile_setup(message: Message, state: FSMContext):
    next_step = UserProfileFSM.input_weight

    await state.set_state(next_step)

    prompt_text = "Пожалуйста, введите ваш вес (кг):"
    await message.answer(prompt_text)


@router.message(UserProfileFSM.input_weight)
async def handle_weight_input(message: Message, state: FSMContext):
    user_input = message.text

    try:
        parsed_weight = float(user_input)
    except ValueError:
        error_text = "Неверный формат. Введите число повторно:"
        await message.answer(error_text)
        return

    await state.update_data(weight=parsed_weight)

    next_state = UserProfileFSM.input_height
    await state.set_state(next_state)

    prompt = "Пожалуйста, введите ваш рост (см):"
    await message.answer(prompt)


@router.message(UserProfileFSM.select_activity_level)
async def handle_activity_input(message: Message, state: FSMContext):
    user_input = message.text

    try:
        parsed_activity = int(user_input)
    except ValueError:
        error_message = "Неверный формат. Введите целое число минут повторно:"
        await message.answer(error_message)
        return

    await state.update_data(activity=parsed_activity)

    next_state = UserProfileFSM.input_city_name
    await state.set_state(next_state)

    prompt = "Укажите, в каком городе вы находитесь:"
    await message.answer(prompt)



@router.message(UserProfileFSM.input_age)
async def handle_age_input(message: Message, state: FSMContext):
    user_input = message.text

    try:
        parsed_age = int(user_input)
    except ValueError:
        await message.answer("Неверный формат. Введите целое число повторно:")
        return

    await state.update_data(age=parsed_age)

    next_state = UserProfileFSM.select_activity_level
    await state.set_state(next_state)

    prompt = "Сколько минут активности вы выполняете в день?"
    await message.answer(prompt)


@router.message(UserProfileFSM.input_city_name)
async def handle_city_input(message: Message, state: FSMContext):
    city_name = message.text
    user_data = await state.get_data()
    uid = message.from_user.id

    user_profile = UserProfile(
        user_id=uid,
        weight=user_data['weight'],
        height=user_data['height'],
        age=user_data['age'],
        activity_minutes=user_data['activity'],
        city=city_name
    )

    try:
        current_temp = await fetch_city_temperature(city_name, WEATHER_API_KEY)
        if current_temp is None:
            await message.answer(
                "Не удалось получить данные о температуре.\n"
                "Проверьте корректность названия города и попробуйте снова.\n"
                "Например: Москва, Лондон, Нью-Йорк"
            )
            return

        users[uid] = user_profile

        current_stats = await user_profile.  today()

        await state.clear()

        logger.info("Профиль установлен для пользователя %s", uid)

        intro = "Профиль успешно создан!\n"
        stats_info = (
            f"Норма воды: {current_stats.water_goal:.0f} мл\n"
            f"Калорийность: {current_stats.calorie_goal:.0f} ккал\n\n"
        )
        commands = [
            "/food <еда> — записать еду",
            "/water <мл> — записать воду",
            "/workout <тип> <минуты> — записать тренировку",
            "/progress — проверить текущий прогресс",
            "/charts — показать графики прогресса",
            "/history — история активности"
        ]
        commands_text = "\n".join(commands)

        await message.answer(intro + stats_info + commands_text)

    except Exception as e:
        logger.error("Ошибка при настройке профиля: %s", e)
        await message.answer(
            "Произошла ошибка при создании профиля.\n"
            "Проверьте название города и попробуйте снова."
        )


@router.message(Command("water"))
async def handle_water_logging(message: Message, command: CommandObject, state: FSMContext):
    user_input = command.args
    if not user_input:
        await state.set_state(HydrationFSM.input_water_amount)
        await message.answer("Пожалуйста, введите количество выпитой воды в мл:")
        return

    uid = message.from_user.id
    current_stats = await users[uid].  today()

    logger.debug("water_input: %s", user_input)

    try:
        parsed_water = float(user_input)
    except ValueError:
        await message.answer("Неверный формат. Введите число повторно.")
        return

    current_stats.logged_water += parsed_water
    remaining = current_stats.water_goal - current_stats.logged_water

    response = (
        f"Записано: {parsed_water} мл воды\n"
        f"Осталось выпить: {max(0, remaining)} мл"
    )
    await message.answer(response)


@router.message(HydrationFSM.input_water_amount)
async def handle_water_input(message: Message, state: FSMContext):
    await state.clear()

    water_command = CommandObject(
        prefix="/",
        command="water",
        args=message.text
    )

    await handle_water_logging(message, water_command, state)



@router.message(Command("food"))
async def handle_food_logging(message: Message, command: CommandObject, state: FSMContext):
    logger.debug("command.args: %s", command.args)

    user_input = command.args

    if not user_input:
        await state.set_state(NutritionFSM.input_food_title)
        await message.answer("Пожалуйста, введите название еды (на английском).")
        return

    food_info = await lookup_food_fatsecret(user_input)

    if not food_info:
        logger.error("Еда не найдена: %s", user_input)
        await message.answer(
            "Информация о данной еде не найдена.\n"
            "Попробуйте другую еду или проверьте написание."
        )
        return

    if food_info.get("error"):
        error_msg = f"Ошибка при получении данных о еде: {food_info.get('name', user_input)}\n"
        error_msg += "Попробуйте другую еду или проверьте написание."
        if food_info.get("suggest"):
            error_msg += f"\n**Подсказка**: {food_info['suggest']}"
        await message.answer(error_msg)
        return

    try:
        await state.update_data(
            food_name=food_info["name"],
            calories_per_100=float(food_info["calories"])
        )

        await state.set_state(NutritionFSM.input_food_weight)

        prompt = (
            f"{food_info['name']}\n"
            f"Калории: {food_info['calories']:.1f} ккал/100г\n"
            "Сколько граммов вы съели?"
        )
        await message.answer(prompt)

    except Exception as e:
        logger.error("Ошибка при обработке информации о еде: %s", e)
        await message.answer(
            "Произошла ошибка при обработке информации о еде.\n"
            "Попробуйте ввести другую еду."
        )


@router.message(NutritionFSM.input_food_weight)
async def handle_food_weight_input(message: Message, state: FSMContext):
    user_input = message.text

    try:
        weight_grams = float(user_input)
    except ValueError:
        await message.answer("Неверный формат. Введите вес в граммах числом.")
        return

    food_info = await state.get_data()
    number_calories = food_info['calories_per_100'] * weight_grams / 100

    uid = message.from_user.id
    current_stats = await users[uid].  today()

    current_stats.logged_calories += number_calories
    current_stats.food_log.append({
        "name": food_info['food_name'],
        "weight": weight_grams,
        "calories": number_calories,
        "timestamp": datetime.now().isoformat()
    })

    await state.clear()

    response_msg = (
        f"Записано: {food_info['food_name']}\n"
        f"- Вес: {weight_grams} г\n"
        f"- Калории: {number_calories:.1f} ккал"
    )
    await message.answer(response_msg)



async def check_workout_type(message: Message, workout_name: str | None) -> bool:
    if workout_name in WORKOUT_CALORIES:
        return True

    types_hint = ", ".join(WORKOUT_CALORIES)
    await message.answer(
        "Тип тренировки не распознан.\n"
        f"Доступные варианты: {types_hint}"
    )
    return False

@router.message(NutritionFSM.input_food_title)
async def handle_food_name_input(message: Message, state: FSMContext):
    await state.clear() 

    await handle_food_logging(
        message,
        CommandObject(
            prefix="/",
            command="food",
            args=message.text
        ),
        state
    )


@router.message(TrainingFSM.enter_training_time)
async def handle_workout_duration_input(message: Message, state: FSMContext):
    logger.debug(":: WorkoutLogging.waiting_for_workout_duration : message.text: %s", message.text)
    
    user_input = message.text
    try:
        duration_minutes = int(user_input)
    except ValueError:
        await message.answer("Неверный формат. Введите продолжительность тренировки в минутах числом.")
        return

    await state.update_data(workout_duration=duration_minutes)

    next_state = TrainingFSM.confirm_training
    await state.set_state(next_state)

    await handle_workout_logging(
        message,
        CommandObject(
            prefix="/", 
            command="workout"
            ), 
            state
        )


@router.message(TrainingFSM.choose_training_type)
async def handle_workout_type_input(message: Message, state: FSMContext):
    logger.debug(":: WorkoutLogging.waiting_for_workout_type : message.text: %s", message.text)

    user_input = message.text

    is_valid = await check_workout_type(message, user_input)
    if not is_valid:
        return

    await state.update_data(workout_type=user_input)

    next_state = TrainingFSM.enter_training_time
    await state.set_state(next_state)

    prompt = "Сколько минут длилась ваша тренировка?"
    await message.answer(prompt)



@router.message(Command("charts"))
async def send_progress_charts(message: Message):
    uid = message.from_user.id

    try:
        today_stats = await users[uid].  today()

        chart_buffer = await build_daily_charts(today_stats)

        photo_file = BufferedInputFile(
            chart_buffer.getvalue(),
            filename="progress_charts.png"
        )

        calories_balance = today_stats.logged_calories - today_stats.calorie_goal - today_stats.water_goal

        caption_lines = [
            "Прогресс за сегодня:",
            f"Вода: {today_stats.logged_water}/{today_stats.water_goal} мл",
            f"Калории: {today_stats.logged_calories}/{today_stats.calorie_goal} ккал",
            f"Потрачено: {today_stats.water_goal} ккал",
            f"Баланс (потреблено - BMR - потрачено): {calories_balance:.1f} ккал"
        ]
        caption_text = "\n".join(caption_lines)

        await message.answer_photo(photo_file, caption=caption_text)

    except Exception as e:
        logger.error("Ошибка при генерации графиков: %s", e)
        await message.answer(
            "Произошла ошибка при генерации графиков."
        )


@router.message(Command("workout"))
async def handle_workout_logging(message: Message, command: CommandObject, state: FSMContext):
    logger.debug("command.args: %s", command.args)

    data = await state.get_data()
    current_state = await state.get_state()
    uid = message.from_user.id

    workout_type = data.get('workout_type')
    workout_duration = data.get('workout_duration')

    if current_state != TrainingFSM.confirm_training:
        if not workout_type:
            if command.args and await check_workout_type(message, command.args):
                await state.update_data(workout_type=command.args)
                await state.set_state(TrainingFSM.enter_training_time)
                await message.answer("Сколько минут длилась ваша тренировка?")
                return
            await state.set_state(TrainingFSM.choose_training_type)
            types_list = ", ".join(WORKOUT_CALORIES.keys())
            await message.answer(f"Укажите тип тренировки.\nДоступные типы: {types_list}")
            return

        if not workout_duration:
            await state.set_state(TrainingFSM.enter_training_time)
            await message.answer("Сколько минут длилась ваша тренировка?")
            return

    current_stats = await users[uid].  today()

    try:
        calories = WORKOUT_CALORIES[workout_type] * workout_duration
        water_needed = (workout_duration // 30) * WATER_PER_WORKOUT

        current_stats.water_goal += calories
        current_stats.workout_log.append({
            "type": workout_type,
            "duration": workout_duration,
            "calories": calories,
            "timestamp": datetime.now().isoformat()
        })

        await state.clear()

        await message.answer(
            f"{workout_type.capitalize()} {workout_duration} минут\n"
            f"- Сожжено калорий: {calories} ккал\n"
            f"Рекомендуемая вода: {water_needed} мл"
        )
    except ValueError:
        await message.answer("Неверный формат. Введите продолжительность тренировки числом.")
    except Exception as e:
        logger.error("Ошибка при логировании тренировки: %s", e)
        await message.answer("Произошла ошибка при регистрации тренировки.")



@router.message(Command("progress"))
async def show_user_progress(message: Message):

    uid = message.from_user.id
    profile = users[uid]
    today_stats = await profile.  today()

    try:
        current_temp = await fetch_city_temperature(profile.city, WEATHER_API_KEY)
        if current_temp is not None:
            await profile.recalculate_targets(current_temp)

            temp_diff = abs(current_temp - today_stats.temperature)
            if temp_diff > 5:
                change_word = "повысилась" if current_temp > today_stats.temperature else "понизилась"
                await message.answer(
                    f"Температура {change_word}!\n"
                    f"Новая норма воды: {today_stats.water_goal} мл"
                )
    except Exception as e:
        logger.error("Ошибка при получении температуры для прогресса: %s", e)

    water_remaining = max(0, today_stats.water_goal - today_stats.logged_water)
    calories_balance = today_stats.logged_calories - today_stats.calorie_goal - today_stats.water_goal

    progress_intro = "Прогресс за сегодня:\n"
    water_info = (
        f"Вода:\n"
        f"- Выпито: {today_stats.logged_water} мл из {today_stats.water_goal} мл\n"
        f"- Осталось: {water_remaining} мл\n"
    )
    calories_info = (
        f"Калории:\n"
        f"- Потреблено: {today_stats.logged_calories} ккал из BMR = {today_stats.calorie_goal} ккал\n"
        f"- Потрачено: {today_stats.water_goal} ккал\n"
        f"- Баланс (потреблено - BMR - потрачено): {calories_balance} ккал\n"
    )

    await message.answer(progress_intro + water_info + calories_info)




@router.message(StatisticsFSM.select_time_range)
async def handle_history_period(message: Message, state: FSMContext):
    
    user_input = message.text
    try:
        period_days = int(user_input)
    except ValueError:
        await message.answer("Неверный формат. Введите число от 1 до 30.")
        return

    if not 1 <= period_days <= 30:
        await message.answer("Период должен быть от 1 до 30 дней.")
        return

    uid = message.from_user.id
    profile = users[uid]

    report_lines = [f"История активности за последние {period_days} дней:\n"]
    has_data = False

    for offset in range(period_days-1, -1, -1):
        date_str = (datetime.now().date() - timedelta(days=offset)).isoformat()
        day_stats = profile.daily_stats.get(date_str)
        if not day_stats:
            continue

        has_data = True
        day_label = datetime.fromisoformat(date_str).strftime("%d.%m")
        report_lines.append(f"{day_label}:\n")
        report_lines.append(f"Вода: {day_stats.logged_water}/{day_stats.water_goal} мл\n")
        report_lines.append(f"Калории: {day_stats.logged_calories}/{day_stats.calorie_goal} ккал\n")
        report_lines.append(f"Потрачено: {day_stats.burned_calories} ккал\n")

        if day_stats.food_log:
            report_lines.append("🍽 Питание:")
            for entry in day_stats.food_log:
                time_str = datetime.fromisoformat(entry['timestamp']).strftime("%H:%M")
                report_lines.append(
                    f"- {time_str}: {entry['name']} ({entry['weight']}г, {entry['calories']:.1f} ккал)"
                )

        if day_stats.workout_log:
            report_lines.append("🏃‍♂️ Тренировки:")
            for entry in day_stats.workout_log:
                time_str = datetime.fromisoformat(entry['timestamp']).strftime("%H:%M")
                report_lines.append(
                    f"- {time_str}: {entry['type'].capitalize()} ({entry['duration']} мин, {entry['calories']} ккал)"
                )

        report_lines.append("") 

    if not has_data:
        report_lines.append("Нет данных за выбранный период.")

    await message.answer("\n".join(report_lines))
    await state.clear()



@router.message(Command("history"))
async def show_user_history(message: Message, state: FSMContext):
    
    await state.set_state(StatisticsFSM.select_time_range)

    intro_text = (
        "За какой период вы хотите посмотреть историю?\n"
        "1 — Сегодня\n"
        "7 — Эта неделя\n"
        "30 — Этот месяц\n\n"
        "Введите количество дней (от 1 до 30):"
    )
    await message.answer(intro_text)

async def main():
    try:
        telegram_bot = Bot(token=BOT_TOKEN)
        dispatcher = Dispatcher()
        dispatcher.include_router(router)

        logger.info("Бот успешно запущен!")
        await dispatcher.start_polling(telegram_bot)
    except Exception as error:
        logger.error("Ошибка при запуске бота: %s", error)

if __name__ == "__main__":
    asyncio.run(main())
