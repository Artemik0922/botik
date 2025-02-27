import logging
import requests
import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# Замените на свои данные:
TELEGRAM_BOT_TOKEN = "8139319815:AAFqw9w92oFB518qy7eSIUsodMB5qcMUnAw"  # Замените на токен вашего бота
OWM_API_KEY = "993af5a46d9d36aed09f26f724b6b81d"
THINGSPEAK_CHANNEL_ID = "2858391"
THINGSPEAK_READ_API_KEY = "JKED7I2X1EMVCVOO"
WEBSITE_URL = "https://example.com"  # Замените на URL вашего сайта

# Словарь подписок: ключ — chat_id, значение — {"city": <город>}
subscriptions = {}

def get_current_weather(city: str) -> dict:
    url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={OWM_API_KEY}&units=metric&lang=ru"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Ошибка получения текущей погоды для {city}: {e}")
        return {}

def get_forecast(city: str) -> list:
    url = f"https://api.openweathermap.org/data/2.5/forecast?q={city}&appid={OWM_API_KEY}&units=metric&lang=ru"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        today = datetime.datetime.now().date()
        forecast_items = [item for item in data.get("list", []) if datetime.datetime.fromtimestamp(item["dt"]).date() == today]
        return forecast_items
    except Exception as e:
        logger.error(f"Ошибка получения прогноза для {city}: {e}")
        return []

def get_sensor_data() -> dict:
    url = f"https://api.thingspeak.com/channels/{THINGSPEAK_CHANNEL_ID}/feeds.json?api_key={THINGSPEAK_READ_API_KEY}&results=1"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        feeds = data.get("feeds", [])
        if feeds:
            return feeds[-1]
        else:
            return {}
    except Exception as e:
        logger.error(f"Ошибка получения данных с датчика: {e}")
        return {}

def format_sensor_data(sensor: dict) -> str:
    try:
        sensor_temp = float(sensor.get("field1", "0"))
        sensor_hum = float(sensor.get("field2", "0"))
        update_time = sensor.get("created_at", "N/A")
        return f"Данные с датчика:\nТемпература: {sensor_temp:.1f}°C\nВлажность: {sensor_hum:.1f}%\nОбновлено: {update_time}"
    except Exception as e:
        logger.error(f"Ошибка форматирования данных с датчика: {e}")
        return "Данные с датчика недоступны."

def format_weather_data(weather: dict) -> str:
    try:
        city_name = weather.get("name", "N/A")
        temp = weather.get("main", {}).get("temp", None)
        description = weather.get("weather", [{}])[0].get("description", "N/A")
        humidity = weather.get("main", {}).get("humidity", "N/A")
        wind = weather.get("wind", {}).get("speed", "N/A")
        pressure = weather.get("main", {}).get("pressure", "N/A")
        if temp is not None:
            return (f"Погода в {city_name}:\n"
                    f"Температура: {temp:.1f}°C\n"
                    f"Описание: {description}\n"
                    f"Влажность: {humidity}%\n"
                    f"Ветер: {wind} м/с\n"
                    f"Давление: {pressure} hPa")
        else:
            return "Погода недоступна."
    except Exception as e:
        logger.error(f"Ошибка форматирования данных погоды: {e}")
        return "Погода недоступна."

def analyze_and_recommend(weather: dict, forecast: list, sensor: dict) -> str:
    recs = []
    current_temp = weather.get("main", {}).get("temp", None)
    if current_temp is not None:
        if current_temp < 10:
            recs.append("На улице прохладно. Одевайтесь теплее!")
        elif current_temp > 25:
            recs.append("Жарко! Не забудьте пить воду и защитите себя от солнца.")
    if forecast:
        rain = any("rain" in item["weather"][0]["description"].lower() for item in forecast)
        if rain:
            recs.append("Ожидается дождь. Возьмите зонт!")
        max_wind = max((item["wind"]["speed"] for item in forecast), default=0)
        if max_wind > 10:
            recs.append("Может быть сильный ветер. Будьте осторожны!")
    if not recs:
        recs.append("Погода стабильная. Наслаждайтесь днем!")
    return "\n".join(recs)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    welcome = (
        "Привет!\n\n"
        "Я бот, который присылает вам отчёты с данными с датчика и погодой, а также прогноз и рекомендации.\n\n"
        "Команды:\n"
        "/subscribe <город> – подписаться (если город не указан, используется Moscow)\n"
        "/unsubscribe – отписаться\n"
        "/setcity <город> – изменить город\n"
        "/hourly – получить почасовой отчёт\n"
        "/daily – получить дневной отчёт\n"
        "/weather – получить текущую погоду\n\n"
        f"Наш сайт: {WEBSITE_URL}"
    )
    await update.message.reply_text(welcome)

async def subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    city = " ".join(context.args) if context.args else "Moscow"
    subscriptions[chat_id] = {"city": city}
    await update.message.reply_text(
        f"Вы подписаны на отчёты. Город: {city}.\nНаш сайт: {WEBSITE_URL}"
    )

async def unsubscribe(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    if chat_id in subscriptions:
        del subscriptions[chat_id]
        await update.message.reply_text("Вы успешно отписались от отчётов.")
    else:
        await update.message.reply_text("Вы не были подписаны.")

async def setcity(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    if not context.args:
        await update.message.reply_text("Пожалуйста, укажите город. Пример: /setcity Moscow")
        return
    city = " ".join(context.args)
    subscriptions[chat_id] = {"city": city}
    await update.message.reply_text(f"Город обновлён на {city}.")

async def hourly_report_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    city = subscriptions.get(chat_id, {}).get("city", "Moscow")
    weather_data = get_current_weather(city)
    sensor_data = get_sensor_data()
    weather_text = format_weather_data(weather_data)
    sensor_text = format_sensor_data(sensor_data)
    message = f"Почасовой отчёт:\n\n{sensor_text}\n\n{weather_text}\n\nНаш сайт: {WEBSITE_URL}"
    await update.message.reply_text(message)

async def daily_report_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    city = subscriptions.get(chat_id, {}).get("city", "Moscow")
    weather_data = get_current_weather(city)
    forecast_data = get_forecast(city)
    sensor_data = get_sensor_data()
    weather_text = format_weather_data(weather_data)
    sensor_text = format_sensor_data(sensor_data)
    recommendations = analyze_and_recommend(weather_data, forecast_data, sensor_data)
    message = (
        f"Дневной отчёт:\n\n"
        f"{sensor_text}\n\n{weather_text}\n\n"
        f"Прогноз и рекомендации:\n{recommendations}\n\nНаш сайт: {WEBSITE_URL}"
    )
    await update.message.reply_text(message)

async def weather_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    city = subscriptions.get(chat_id, {}).get("city", "Moscow")
    message = format_weather_data(get_current_weather(city))
    await update.message.reply_text(message)

async def hourly_report_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    for chat_id, data in subscriptions.items():
        city = data.get("city", "Moscow")
        weather_data = get_current_weather(city)
        sensor_data = get_sensor_data()
        weather_text = format_weather_data(weather_data)
        sensor_text = format_sensor_data(sensor_data)
        message = f"Почасовой отчёт:\n\n{sensor_text}\n\n{weather_text}\n\nНаш сайт: {WEBSITE_URL}"
        try:
            await context.bot.send_message(chat_id=chat_id, text=message)
        except Exception as e:
            logger.error(f"Ошибка отправки почасового отчёта пользователю {chat_id}: {e}")

async def daily_report_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    for chat_id, data in subscriptions.items():
        city = data.get("city", "Moscow")
        weather_data = get_current_weather(city)
        forecast_data = get_forecast(city)
        sensor_data = get_sensor_data()
        weather_text = format_weather_data(weather_data)
        sensor_text = format_sensor_data(sensor_data)
        recommendations = analyze_and_recommend(weather_data, forecast_data, sensor_data)
        message = (
            f"Дневной отчёт:\n\n{sensor_text}\n\n{weather_text}\n\n"
            f"Прогноз и рекомендации:\n{recommendations}\n\nНаш сайт: {WEBSITE_URL}"
        )
        try:
            await context.bot.send_message(chat_id=chat_id, text=message)
        except Exception as e:
            logger.error(f"Ошибка отправки дневного отчёта пользователю {chat_id}: {e}")

async def weather_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    city = subscriptions.get(chat_id, {}).get("city", "Moscow")
    message = format_weather_data(get_current_weather(city))
    await update.message.reply_text(message)

def main() -> None:
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("subscribe", subscribe))
    application.add_handler(CommandHandler("unsubscribe", unsubscribe))
    application.add_handler(CommandHandler("setcity", setcity))
    application.add_handler(CommandHandler("hourly", hourly_report_command))
    application.add_handler(CommandHandler("daily", daily_report_command))
    application.add_handler(CommandHandler("weather", weather_command))
    
    # Почасовой отчёт каждый час
    application.job_queue.run_repeating(hourly_report_job, interval=3600, first=10)
    # Дневной отчёт каждый день в 08:00
    target_time = datetime.time(hour=8, minute=0, second=0)
    application.job_queue.run_daily(daily_report_job, target_time)
    
    application.run_polling()

if __name__ == '__main__':
    main()
