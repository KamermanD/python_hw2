import io
from typing import Optional, Dict

import aiohttp
import matplotlib.pyplot as plt
from fatsecret import Fatsecret

from models import DayRecord
from config import logger, CONSUMER_KEY, CONSUMER_SECRET


async def fetch_city_temperature(city: str, api_key: str) -> Optional[float]:
    url = "http://api.openweathermap.org/data/2.5/weather"
    params = {
        "q": city,
        "appid": api_key,
        "units": "metric"
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params) as response:
            if response.status != 200:
                logger.error("Weather API error: %s", response.status)
                return None

            payload = await response.json()
            return payload.get("main", {}).get("temp")


async def lookup_food_openfacts(name: str) -> Optional[Dict]:
    url = "https://world.openfoodfacts.org/cgi/search.pl"
    params = {
        "search_terms": name,
        "search_simple": 1,
        "action": "process",
        "fields": "product_name,nutriments",
        "json": 1,
        "page_size": 1
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                if response.status != 200:
                    return None

                data = await response.json()
                products = data.get("products")

                if not products:
                    return None

                product = products[0]
                kcal = product.get("nutriments", {}).get("energy-kcal_100g")

                if not isinstance(kcal, (int, float)) or kcal <= 0:
                    return None

                return {
                    "name": product.get("product_name", name).strip() or name,
                    "calories": float(kcal)
                }
    except Exception as exc:
        logger.error("OpenFoodFacts error: %s", exc)
        return None


async def lookup_food_fatsecret(name: str) -> Optional[Dict]:
    try:
        client = Fatsecret(CONSUMER_KEY, CONSUMER_SECRET)
        search = client.foods_search(name)

        if not search:
            return None

        food_id = search[0]["food_id"]
        details = client.food_get_v2(food_id)

        servings = details.get("servings", {}).get("serving")
        if not servings:
            return None

        serving = servings[0] if isinstance(servings, list) else servings

        amount = float(serving.get("metric_serving_amount", 100))
        factor = 100 / amount if amount else 1

        return {
            "name": details.get("food_name", name),
            "calories": round(float(serving.get("calories", 0)) * factor),
            "protein": round(float(serving.get("protein", 0)) * factor, 1),
            "fat": round(float(serving.get("fat", 0)) * factor, 1),
            "carbs": round(float(serving.get("carbohydrate", 0)) * factor, 1),
        }

    except Exception as exc:
        logger.error("FatSecret error: %s", exc)
        return {"error": str(exc), "name": name}


async def build_daily_charts(day: DayRecord) -> io.BytesIO:
    fig, axes = plt.subplots(2, 1, figsize=(9, 10))

    water_actual = day.logged_water
    water_target = day.water_goal

    calorie_net = day.logged_calories - day.water_goal
    calorie_target = day.calorie_goal

    axes[0].bar(["actual", "target"], [water_actual, water_target])
    axes[0].set_title("Daily water balance (ml)")

    axes[1].bar(["net", "target"], [calorie_net, calorie_target])
    axes[1].set_title("Daily calorie balance (kcal)")

    for ax in axes:
        ax.grid(axis="y", alpha=0.4)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

    buffer = io.BytesIO()
    plt.tight_layout()
    plt.savefig(buffer, format="png", dpi=250)
    buffer.seek(0)
    plt.close()

    return buffer