# data_loader.py
import pandas as pd

def load_dataset(path: str = "recommendation_system/data/dataset_about.csv") -> pd.DataFrame:
    """Загрузка датасета"""
    df = pd.read_csv(path, encoding='utf-8-sig')
    
    # Приведение типов
    for col in ['latitude', 'longitude', 'review_rating', 'review_count']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    
    print(f"Загружено {len(df)} заведений")
    return df
