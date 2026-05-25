# config.py
from dataclasses import dataclass
from typing import Dict

@dataclass
class PipelineConfig:
    # Пороги уверенности
    INTENT_THRESHOLD: float = 0.65
    EMOTION_THRESHOLD: float = 0.40
    ENTITY_MIN_WEIGHT: float = 0.8
    AMBIENCE_THRESHOLD: float = 0.65

    # Границы Москвы 
    MOSCOW_BOUNDS: Dict = None

    TOP_K_CANDIDATES: int = 50
    FINAL_TOP_K: int = 5
    MIN_RATING: float = 3.5

    def __post_init__(self):
        if self.MOSCOW_BOUNDS is None:
            self.MOSCOW_BOUNDS = {
                "lat_min": 55.55, "lat_max": 55.95,
                "lon_min": 37.30, "lon_max": 37.90
            }

config = PipelineConfig()
