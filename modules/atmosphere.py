# modules/atmosphere.py
from transformers import AutoTokenizer, AutoModelForTokenClassification
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import torch
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional, Union
import re
from tqdm import tqdm


class AtmosphereDetector:
    def __init__(
        self, 
        model_path: str,
        semantic_weight: float = 0.7,
        rating_weight: float = 0.3,
        min_tag_similarity: float = 0.5,
        use_gpu: bool = True
    ):
        """
        Инициализация детектора атмосферы
        
        Args:
            model_path: путь к обученной модели NER для извлечения тегов атмосферы
            semantic_weight: вес семантического поиска (0-1)
            rating_weight: вес рейтинга (0-1), сумма = 1
            min_tag_similarity: минимальное косинусное сходство для совпадения тегов
            use_gpu: использовать ли GPU
        """
        print(" Инициализация AtmosphereDetector...")
        
        self.semantic_weight = semantic_weight
        self.rating_weight = rating_weight
        self.min_tag_similarity = min_tag_similarity
        
        # Определяем устройство
        self.device = torch.device("cuda" if use_gpu and torch.cuda.is_available() else "cpu")
        print(f"   Устройство: {self.device}")
        
        # ==================== 1. ЗАГРУЗКА МОДЕЛИ ДЛЯ ИЗВЛЕЧЕНИЯ ТЕГОВ ====================
        print(f"   Загрузка модели из {model_path}...")
        
        # Загружаем модель и токенизатор
        self.tokenizer = AutoTokenizer.from_pretrained(model_path)
        self.model = AutoModelForTokenClassification.from_pretrained(model_path)
        self.model.to(self.device)
        self.model.eval()
        
        # Метки для NER
        self.id_to_label = {0: 'O', 1: 'B-AMBIENCE', 2: 'I-AMBIENCE'}
        
        # ==================== 2. ЗАГРУЗКА МОДЕЛИ ДЛЯ СЕМАНТИЧЕСКОГО ПОИСКА ====================
        print("   Загрузка модели для семантического поиска...")
        self.semantic_model = SentenceTransformer('intfloat/multilingual-e5-small')
        if use_gpu and torch.cuda.is_available():
            self.semantic_model = self.semantic_model.to(self.device)
        
        # Кэш для эмбеддингов тегов мест
        self._place_embeddings_cache = {}
        
        print(f" AtmosphereDetector готов (семантический вес: {self.semantic_weight}, "
              f"минимальное сходство: {self.min_tag_similarity})\n")
    
    # ==================== ИЗВЛЕЧЕНИЕ ТЕГОВ ИЗ ТЕКСТА (С OFFSET MAPPING) ====================
    def extract_tags_from_text(self, text: str) -> List[str]:
        """
        Извлекает теги атмосферы из текста с помощью обученной модели NER.
        Использует offset_mapping для точного восстановления исходных слов.
        
        Args:
            text: входной текст пользователя
            
        Returns:
            список извлечённых тегов (уникальных)
        """
        if not text or not isinstance(text, str):
            return []
        
        text = text.strip()
        if not text:
            return []
        
        # Токенизация с offset mapping
        inputs = self.tokenizer(
            text,
            return_tensors="pt",
            truncation=True,
            max_length=512,
            return_offsets_mapping=True
        )
        
        offsets = inputs['offset_mapping'][0]
        inputs.pop('offset_mapping')
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        
        with torch.no_grad():
            outputs = self.model(**inputs)
            predictions = torch.argmax(outputs.logits, dim=2)[0]
        
        tokens = self.tokenizer.convert_ids_to_tokens(inputs['input_ids'][0])
        
        # Восстанавливаем слова и их метки
        words_with_labels = []
        current_word = ""
        current_label = None
        last_end = 0
        
        for token, pred, (start, end) in zip(tokens, predictions, offsets):
            # Пропускаем специальные токены и пустые
            if start == end or token in ['[CLS]', '[SEP]', '[PAD]']:
                continue
            
            pred_label = self.id_to_label[pred.item()]
            fragment = text[start:end]
            
            # Если есть разрыв - новое слово
            if start > last_end and current_word:
                if current_label in ['B-AMBIENCE', 'I-AMBIENCE']:
                    words_with_labels.append((current_word, current_label))
                current_word = ""
                current_label = None
            
            current_word += fragment
            
            # B-AMBIENCE имеет приоритет над I-AMBIENCE
            if pred_label == 'B-AMBIENCE':
                current_label = 'B-AMBIENCE'
            elif pred_label == 'I-AMBIENCE' and current_label != 'B-AMBIENCE':
                current_label = 'I-AMBIENCE'
            
            last_end = end
        
        # Добавляем последнее слово
        if current_word and current_label in ['B-AMBIENCE', 'I-AMBIENCE']:
            words_with_labels.append((current_word, current_label))
        
        # Формируем фразы (B-AMBIENCE + следующие I-AMBIENCE)
        phrases = []
        current_phrase = []
        
        for word, label in words_with_labels:
            if label == 'B-AMBIENCE':
                if current_phrase:
                    phrases.append(' '.join(current_phrase))
                current_phrase = [word]
            elif label == 'I-AMBIENCE' and current_phrase:
                current_phrase.append(word)
            else:
                if current_phrase:
                    phrases.append(' '.join(current_phrase))
                    current_phrase = []
        
        if current_phrase:
            phrases.append(' '.join(current_phrase))
        
        # Удаляем дубликаты (сохраняя порядок)
        phrases = list(dict.fromkeys(phrases))
        
        # Фильтруем слишком короткие теги (меньше 3 символов)
        phrases = [p for p in phrases if len(p) >= 3]
        
        return phrases
    
    # ==================== СЕМАНТИЧЕСКИЙ ПОИСК ====================
    def _get_embedding(self, text: str) -> np.ndarray:
        """Получает эмбеддинг для текста с кэшированием"""
        if text in self._place_embeddings_cache:
            return self._place_embeddings_cache[text]
        
        embedding = self.semantic_model.encode([text])[0]
        self._place_embeddings_cache[text] = embedding
        return embedding
    
    def calculate_tag_similarity(self, query_tags: List[str], place_tags_str: str) -> float:
        """
        Вычисляет семантическую близость между тегами запроса и тегами места
        
        Args:
            query_tags: список тегов из запроса пользователя
            place_tags_str: строка с тегами места (из датасета)
            
        Returns:
            максимальная косинусная близость (0-1)
        """
        if not query_tags or not place_tags_str or pd.isna(place_tags_str):
            return 0.0
        
        # Проверяем тип
        if not isinstance(place_tags_str, str):
            place_tags_str = str(place_tags_str)
        
        place_tags_str = place_tags_str.strip()
        if not place_tags_str or place_tags_str in ['[]', '']:
            return 0.0
        
        # Получаем эмбеддинг для строки тегов места
        place_embedding = self._get_embedding(place_tags_str)
        
        best_similarity = 0.0
        
        for query_tag in query_tags:
            if not query_tag.strip():
                continue
            query_embedding = self._get_embedding(query_tag)
            similarity = cosine_similarity([query_embedding], [place_embedding])[0][0]
            best_similarity = max(best_similarity, similarity)
        
        return float(best_similarity)
    
    def semantic_search_score(self, query_tags: List[str], place_tags_str: str) -> float:
        """
        Вычисляет итоговый семантический скор для места
        
        Args:
            query_tags: теги из запроса
            place_tags_str: теги места из датасета
            
        Returns:
            семантический скор (0-1)
        """
        similarity = self.calculate_tag_similarity(query_tags, place_tags_str)
        
        # Если сходство выше порога, используем его, иначе 0
        if similarity >= self.min_tag_similarity:
            return similarity
        return 0.0
    
    # ==================== РАСЧЁТ РЕЙТИНГОВОГО СКОРА ====================
    def calculate_rating_score(
        self, 
        place_row: pd.Series,
        rating_col: str = 'review_rating',
        reviews_count_col: str = 'review_count',
        global_avg_rating: float = 4.0,
        prior_weight: int = 10
    ) -> float:
        """
        Рассчитывает скор рейтинга с учётом количества отзывов (Bayesian average)
        
        Args:
            place_row: строка с данными места
            rating_col: название колонки с рейтингом
            reviews_count_col: название колонки с количеством отзывов
            global_avg_rating: средний рейтинг по всем местам
            prior_weight: вес априорного среднего
            
        Returns:
            скор рейтинга (0-1)
        """
        rating = place_row.get(rating_col, 0)
        reviews_count = place_row.get(reviews_count_col, 0)
        
        if pd.isna(rating) or rating is None or rating == 0:
            return 0.0
        if pd.isna(reviews_count) or reviews_count is None:
            reviews_count = 0
        
        # Bayesian average
        bayesian_rating = (reviews_count * rating + prior_weight * global_avg_rating) / (reviews_count + prior_weight)
        rating_score = bayesian_rating / 5.0
        
        return min(max(rating_score, 0.0), 1.0)
    
    # ==================== ИТОГОВЫЙ СКОР ====================
    def calculate_final_score(
        self,
        place_row: pd.Series,
        query_tags: List[str],
        rating_col: str = 'review_rating',
        reviews_count_col: str = 'review_count'
    ) -> Dict:
        """
        Рассчитывает итоговый скор для места
        
        Args:
            place_row: строка с данными места
            query_tags: теги из запроса пользователя
            rating_col: название колонки с рейтингом
            reviews_count_col: название колонки с количеством отзывов
            
        Returns:
            словарь со скорами
        """
        # Получаем теги места
        tags_col = 'atmosphere_tags'  # колонка с тегами в датасете
        place_tags = place_row.get(tags_col, '')
        
        # Семантический скор
        semantic_score = self.semantic_search_score(query_tags, place_tags)
        
        # Рейтинговый скор
        rating_score = self.calculate_rating_score(place_row, rating_col, reviews_count_col)
        
        # Итоговый скор
        final_score = (semantic_score * self.semantic_weight + 
                      rating_score * self.rating_weight)
        
        return {
            'semantic_score': semantic_score,
            'rating_score': rating_score,
            'final_score': final_score,
            'has_tags': bool(place_tags and not pd.isna(place_tags) and place_tags not in ['[]', ''])
        }
    
    # ==================== ПРОГНОЗ ДЛЯ ОДНОГО ЗАПРОСА ====================
    def predict(self, text: str) -> Dict:
        """
        Прогноз атмосферных тегов для одного текста
        
        Args:
            text: входной текст
            
        Returns:
            словарь с извлечёнными тегами
        """
        query_tags = self.extract_tags_from_text(text)
        
        return {
            'text': text,
            'tags': query_tags,
            'has_tags': len(query_tags) > 0,
            'num_tags': len(query_tags)
        }
    
    # ==================== ОСНОВНОЙ МЕТОД РЕКОМЕНДАЦИЙ ====================
    def get_atmosphere_recommendations(
        self,
        query: str,
        places_df: pd.DataFrame,
        top_k: int = None,
        min_semantic_score: float = 0.0,
        min_final_score: float = 0.0,
        rating_col: str = 'review_rating',
        reviews_count_col: str = 'review_count',
        verbose: bool = True
    ) -> pd.DataFrame:
        """
        Возвращает рекомендации мест на основе атмосферы
        
        Args:
            query: текст запроса пользователя
            places_df: DataFrame с колонками 'atmosphere_tags', 'review_rating', 'review_count'
            top_k: если указан, возвращает только top_k мест
            min_semantic_score: минимальный семантический скор для фильтрации
            min_final_score: минимальный итоговый скор для фильтрации
            rating_col: название колонки с рейтингом
            reviews_count_col: название колонки с количеством отзывов
            verbose: печатать ли подробности
            
        Returns:
            DataFrame с отсортированными рекомендациями
        """
        if verbose:
            print(f"\n🔍 Анализ запроса: \"{query}\"")
        
        # 1. Извлекаем теги из запроса
        query_tags = self.extract_tags_from_text(query)
        
        if not query_tags:
            if verbose:
                print(f" Не удалось извлечь теги атмосферы из запроса")
                print(f"   Возвращаем места, отсортированные по рейтингу...")
            
            # Возвращаем ВСЕ места, отсортированные по рейтингу
            result_df = places_df.copy()
            result_df['rating_score'] = result_df.apply(
                lambda row: self.calculate_rating_score(row, rating_col, reviews_count_col), axis=1
            )
            result_df['semantic_score'] = 0.0
            result_df['final_score'] = result_df['rating_score']
            result_df['has_tags'] = False
            result_df['query_tags'] = ''
            
            result_df = result_df.sort_values('final_score', ascending=False)
            
            if top_k:
                return result_df.head(top_k)
            return result_df
        
        if verbose:
            print(f" Извлечённые теги: {query_tags}")
        
        # 2. Оцениваем все места
        if verbose:
            print(f" Оценка {len(places_df)} мест...")
        
        scores = []
        for idx, row in places_df.iterrows():
            score_data = self.calculate_final_score(row, query_tags, rating_col, reviews_count_col)
            scores.append(score_data)
        
        # 3. Добавляем скоры в DataFrame
        result_df = places_df.copy()
        for key in scores[0].keys():
            result_df[key] = [s[key] for s in scores]
        result_df['query_tags'] = ', '.join(query_tags)
        
        # 4. Фильтруем
        result_df = result_df[result_df['semantic_score'] >= min_semantic_score]
        result_df = result_df[result_df['final_score'] >= min_final_score]
        
        # 5. Сортируем по итоговому скору
        result_df = result_df.sort_values('final_score', ascending=False)
        
        if verbose:
            print(f"\n Результаты:")
            print(f"   - Всего мест: {len(places_df)}")
            print(f"   - Извлечено тегов из запроса: {len(query_tags)}")
            print(f"   - Прошло фильтр (semantic >= {min_semantic_score}): {len(result_df)}")
            print(f"   - Средний финальный скор: {result_df['final_score'].mean():.3f}")
            print(f"   - Мест с тегами: {result_df['has_tags'].sum()}")
        
        if top_k:
            return result_df.head(top_k)
        return result_df


# ==================== ФУНКЦИЯ ДЛЯ КРАСИВОГО ВЫВОДА ====================
def print_atmosphere_recommendations(
    recommendations_df: pd.DataFrame, 
    top_n: int = None,
    show_tags: bool = True
):
    """
    Красиво выводит рекомендации мест на основе атмосферы
    
    Args:
        recommendations_df: результат работы get_atmosphere_recommendations
        top_n: сколько мест показать (если None - все)
        show_tags: показывать ли теги места
    """
    if top_n:
        recommendations_df = recommendations_df.head(top_n)
    
    if len(recommendations_df) == 0:
        print("\n Нет мест, соответствующих критериям")
        return
    
    print(f"\n{'='*100}")
    print(f" РЕКОМЕНДАЦИИ ПО АТМОСФЕРЕ (ранжированы по семантическому сходству и рейтингу):")
    print(f"{'='*100}")
    
    # Выводим теги запроса, если они есть
    if 'query_tags' in recommendations_df.columns and len(recommendations_df) > 0:
        query_tags = recommendations_df.iloc[0].get('query_tags', '')
        if query_tags:
            print(f" Теги запроса: {query_tags}")
            print(f"{'─'*100}")
    
    for display_idx, (idx, row) in enumerate(recommendations_df.iterrows(), 1):
        # Название
        title = row.get('title', 'Название не указано')
        if pd.isna(title):
            title = 'Название не указано'
        
        # Категория
        category = row.get('category', 'Категория не указана')
        if pd.isna(category):
            category = 'Категория не указана'
        
        # ID
        place_id = row.get('place_id', idx)
        if pd.isna(place_id):
            place_id = idx
        
        # Рейтинг
        rating = row.get('review_rating', 'Нет')
        if pd.isna(rating):
            rating = 'Нет'
        elif isinstance(rating, (int, float)):
            rating = f"{rating:.1f}"
        
        # Количество отзывов
        review_count = row.get('review_count', 0)
        if pd.isna(review_count):
            review_count = 0
        
        # Скоры
        final_score = row.get('final_score', 0)
        semantic_score = row.get('semantic_score', 0)
        rating_score = row.get('rating_score', 0)
        
        print(f"\n{'─'*100}")
        print(f" {display_idx}. {title}")
        print(f"    ID: {place_id} |  Категория: {category}")
        print(f"    Рейтинг: {rating} (всего оценок: {int(review_count)})")
        print(f"   {'─'*60}")
        print(f"    Итоговый скор: {final_score:.4f}")
        print(f"   ├─  Семантический скор (теги): {semantic_score:.4f}")
        print(f"   └─  Рейтинговый скор (Bayesian): {rating_score:.4f}")
        
        if show_tags:
            tags_value = row.get('atmosphere_tags', '')
            if pd.isna(tags_value) or tags_value is None:
                tags_str = ""
            else:
                tags_str = str(tags_value).strip()
            
            if tags_str and tags_str not in ['[]', '']:
                # Очищаем от лишних скобок
                tags_str = tags_str.strip('[]').strip()
                if len(tags_str) > 150:
                    tags_str = tags_str[:150] + "..."
                print(f"    Теги места: {tags_str}")
    
    print(f"\n{'='*100}")


# ==================== ФУНКЦИЯ ДЛЯ ТЕСТИРОВАНИЯ МОДЕЛИ ====================
def test_atmosphere_model(model_path: str, test_texts: List[str] = None):
    """
    Тестирует модель на примерах
    """
    detector = AtmosphereDetector(model_path=model_path)
    
    if test_texts is None:
        test_texts = [
            "уютная атмосфера",
            "тихая музыка",
            "шумное место",
            "романтичная обстановка",
            "В этом ресторане царит невероятно уютная и теплая атмосфера, как дома",
            "Очень шумное место, громкая музыка и постоянно кричат официанты",
            "Атмосфера здесь романтичная, приглушенный свет и тихая музыка"
        ]
    
    print("\n" + "="*70)
    print("ТЕСТИРОВАНИЕ МОДЕЛИ")
    print("="*70)
    
    for text in test_texts:
        result = detector.predict(text)
        print(f"\n Текст: {text}")
        print(f"    Найдено тегов: {result['num_tags']}")
        if result['tags']:
            for i, tag in enumerate(result['tags'], 1):
                print(f"      {i}. '{tag}'")


# ==================== ПРИМЕР ИСПОЛЬЗОВАНИЯ ====================
if __name__ == "__main__":
    # Пример загрузки датасета
    df = pd.read_csv('recommendation_system/data/places_with_all_tags.csv')
    
    # Инициализация детектора
    detector = AtmosphereDetector(
        model_path="C:/Users/krask/Downloads/recommendation_system/recommendation_system/models/atmosphere_model_best",
        semantic_weight=0.7,
        rating_weight=0.3,
        min_tag_similarity=0.5,
        use_gpu=True
    )
    
    # Тестирование на примерах
    test_atmosphere_model(
        model_path="C:/Users/krask/Downloads/recommendation_system/recommendation_system/models/atmosphere_model_best"
    )
    
    # Пример запроса
    query = "Ищу тихое и уютное кафе с приглушённым светом"
    
    # Получение рекомендаций
    recommendations = detector.get_atmosphere_recommendations(
        query=query,
        places_df=df,
        top_k=10,
        min_semantic_score=0.4,
        verbose=True
    )
    
    # Вывод результатов
    print_atmosphere_recommendations(recommendations, show_tags=True)
    
    print("\n Модуль готов к использованию!")
