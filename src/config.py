from dotenv import load_dotenv
import logging
import os


load_dotenv()


BOT_TOKEN = os.getenv("BOT_TOKEN")
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")


CONSUMER_KEY = os.getenv("CONSUMER_KEY")
CONSUMER_SECRET = os.getenv("CONSUMER_SECRET")

def create_logger(name: str, level: str) -> logging.Logger:
    log = logging.getLogger(name)
    log.setLevel(level)

    if not log.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s | %(levelname)s | %(message)s"
            )
        )
        log.addHandler(handler)

    return log

logger = create_logger("fitness_bot", LOG_LEVEL)

REQUIRED_ENV_VARS = {
    "BOT_TOKEN": BOT_TOKEN,
    "WEATHER_API_KEY": WEATHER_API_KEY,
    "CONSUMER_KEY": CONSUMER_KEY,
    "CONSUMER_SECRET": CONSUMER_SECRET,
}

missing = [name for name, value in REQUIRED_ENV_VARS.items() if not value]

if missing:
    logger.error("Missing environment variables: %s", ", ".join(missing))
    raise RuntimeError("Environment configuration error")



WATER_PER_KG = 35
WATER_PER_ACTIVITY = 400
WATER_PER_WORKOUT = 250
WATER_HOT_WEATHER = 350 


WORKOUT_CALORIES = {
    "run": 12,
    "walk": 4,
    "swim": 9,
    "bike": 6,
    "yoga": 3,
    "power": 7
}
