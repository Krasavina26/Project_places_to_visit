# geo_filter.py
import pandas as pd
from config import config

def apply_geo_filter(df: pd.DataFrame, bounds: dict = None) -> pd.DataFrame:
    """Фильтрация по прямоугольной области"""
    if bounds is None:
        bounds = config.MOSCOW_BOUNDS
    
    mask = (
        (df['latitude'] >= bounds['lat_min']) &
        (df['latitude'] <= bounds['lat_max']) &
        (df['longitude'] >= bounds['lon_min']) &
        (df['longitude'] <= bounds['lon_max'])
    )
    filtered = df[mask].copy()
    print(f"Геофильтрация: осталось {len(filtered)} локаций")
    return filtered
