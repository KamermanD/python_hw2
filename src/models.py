
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List
from config import WATER_PER_KG, WATER_PER_ACTIVITY, WATER_HOT_WEATHER


@dataclass
class DayRecord:
    date_iso: str
    water_consumed_ml: float = 0
    calories_eaten: float = 0
    calories_burned: float = 0
    water_target_ml: float = 0
    calorie_target: float = 0
    temperature_celsius: float = 0
    meals: List[Dict] = field(default_factory=list)
    workouts: List[Dict] = field(default_factory=list)


@dataclass
class UserProfile:
    user_id: int
    weight: float
    height: float
    age: int
    activity_minutes: int
    city: str
    days: Dict[str, DayRecord] = field(default_factory=dict)

    def _today_key(self) -> str:
        return datetime.now().date().isoformat()

    async def today(self) -> DayRecord:
        

        key = self._today_key()

        if key not in self.days:
            record = DayRecord(date_iso=key)
            self.days[key] = record

            from utils import fetch_city_temperature
            from config import WEATHER_API_KEY

            temp = await fetch_city_temperature(self.city, WEATHER_API_KEY)
            temp = temp if temp is not None else 20

            self.recalculate_targets(temp)

        return self.days[key]

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
        record = self.days[self._today_key()]
        record.water_target_ml = self.water_target(temperature)
        record.calorie_target = self.calorie_target()
        record.temperature_celsius = temperature
