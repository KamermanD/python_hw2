
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List
from config import WATER_PER_KG, WATER_PER_ACTIVITY, WATER_HOT_WEATHER


@dataclass
class DayRecord:
    date: str
    logged_water: float = 0
    logged_calories: float = 0
    burned_calories: float = 0
    water_goal: float = 0
    calorie_goal: float = 0
    temperature: float = 0
    food_log: List[Dict] = field(default_factory=list)
    workout_log: List[Dict] = field(default_factory=list)


@dataclass
class UserProfile:
    user_id: int
    weight: float
    height: float
    age: int
    activity_minutes: int
    city: str
    daily_stats: Dict[str, DayRecord] = field(default_factory=dict)

    def _today_key(self) -> str:
        return datetime.now().date().isoformat()

    async def today(self) -> DayRecord:
        

        key = self._today_key()

        if key not in self.daily_stats:
            record = DayRecord(date=key)
            self.daily_stats[key] = record

            from utils import fetch_city_temperature
            from config import WEATHER_API_KEY

            temp = await fetch_city_temperature(self.city, WEATHER_API_KEY)
            temp = temp if temp is not None else 20

            self.recalculate_targets(temp)

        return self.daily_stats[key]

    def water_target(self, temperature: float) -> float:
        base = self.weight * WATER_PER_KG
        activity_bonus = (self.activity_minutes // 30) * WATER_PER_ACTIVITY
        heat_bonus = WATER_HOT_WEATHER if temperature >= 26 else 0
        return base + activity_bonus + heat_bonus

    def calorie_target(self) -> float:
        base = 10 * self.weight + 6.25 * self.height - 5 * self.age
        activity_bonus = self.activity_minutes * 4.2
        return base + activity_bonus

    def recalculate_targets(self, temperature: float) -> None:
        record = self.daily_stats[self._today_key()]
        record.water_goal =  self.water_target(temperature)
        record.calorie_goal = self.calorie_target()
        record.temperature = temperature
