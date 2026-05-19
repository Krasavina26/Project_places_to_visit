# modules/ambience.py
# Заготовка под будущий FAISS
import pandas as pd

class AmbienceModule:
    def __init__(self):
        self.index = None  # FAISS Index
        self.mapping = None

    def search(self, query: str, candidates: pd.DataFrame, top_k: int = 20):
        """Когда доделаешь atmosphere-tags — здесь будет поиск"""
        # TODO: извлечь теги → поиск в FAISS
        return list(candidates.index[:top_k])  # временная заглушка
