import torch
import torch.nn as nn
import pandas as pd
from transformers import AutoTokenizer, AutoModel
from sklearn.preprocessing import LabelEncoder
from typing import Tuple, List, Optional
from config import config


class IntentClassifier(nn.Module):
    """Классификатор интенций на основе LaBSE"""
    
    def __init__(self, n_classes: int, model_name: str = "sentence-transformers/LaBSE"):
        super(IntentClassifier, self).__init__()
        self.bert = AutoModel.from_pretrained(model_name)
        self.dropout = nn.Dropout(p=0.4)
        self.classifier = nn.Linear(self.bert.config.hidden_size, n_classes)

    def forward(self, input_ids, attention_mask):
        outputs = self.bert(input_ids=input_ids, attention_mask=attention_mask)
        pooled_output = outputs.last_hidden_state[:, 0, :]  # [CLS] token
        pooled_output = self.dropout(pooled_output)
        logits = self.classifier(pooled_output)
        return logits


class IntentModule:
    """Основной класс модуля Intent"""
    
    def __init__(self):
        self.model = None
        self.tokenizer = None
        self.le = None
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.intent_config = self._get_intent_config()

    def _get_intent_config(self) -> dict:
        """Конфигурация рекомендаций для каждой интенции"""
        return {
            'food_search': {
                'tags': [
                    ('Еда', 2.5), ('Ресторан', 2.5), ('Кафе', 2.0), ('На вынос', 1.0),
                    ('Доставка', 1.0), ('Быстрая еда', 1.5), ('Обед', 1.5), ('Ужин', 1.5),
                    ('Завтрак', 1.0), ('Бранч', 1.0), ('Вегетарианское меню', 1.0),
                    ('Веганское меню', 1.0), ('Халяль еда', 0.8)
                ],
                'file_types': ['cafes_restaurants.json', 'anticafe_karaoke.json'],
                'rating_bonus_weight': 0.3,
                'min_reviews_for_bonus': 10
            },
            'cafe_dessert': {
                'tags': [
                    ('Кафе', 2.5), ('Десерты', 2.5), ('Отличные десерты', 3.0),
                    ('Кофе', 2.5), ('Отличный кофе', 3.0), ('Чай', 1.0), ('На вынос', 1.0),
                    ('Летняя веранда', 1.5)
                ],
                'file_types': ['cafes_restaurants.json', 'anticafe_karaoke.json'],
                'rating_bonus_weight': 0.25,
                'min_reviews_for_bonus': 10
            },
            'romantic_date': {
                'tags': [
                    ('Романтическая атмосфера', 3.0), ('Уютная атмосфера', 2.5),
                    ('Вино', 2.5), ('Коктейли', 2.0), ('Отличные коктейли', 2.5),
                    ('Отличные десерты', 2.0), ('Отдельный кабинет', 2.5), ('Камин', 2.5),
                    ('Живая музыка', 2.0), ('Тихая атмосфера', 2.0)
                ],
                'file_types': ['cafes_restaurants.json', 'clubs.json', 'theatres.json'],
                'rating_bonus_weight': 0.3,
                'min_reviews_for_bonus': 8
            },
            'first_date': {
                'tags': [
                    ('Романтическая атмосфера', 2.5), ('Уютная атмосфера', 2.5),
                    ('Тихая атмосфера', 2.5), ('Вино', 2.0), ('Коктейли', 2.0),
                    ('Живая музыка', 1.5), ('Бронирование', 1.5)
                ],
                'file_types': ['cafes_restaurants.json', 'parks.json', 'theatres.json'],
                'rating_bonus_weight': 0.25,
                'min_reviews_for_bonus': 8
            },
            'with_family': {
                'tags': [
                    ('Подходит для детей', 3.0), ('Детское меню', 2.5), ('Детская площадка', 2.5),
                    ('Семейная скидка', 2.0), ('Детские стульчики', 2.0), ('Пеленальный столик', 2.0),
                    ('Детские развлечения', 2.5), ('Контактный зоопарк', 2.0),
                    ('Парк', 2.0), ('Столы для пикника', 1.5)
                ],
                'file_types': [
                    'parks.json', 'gardens_zoos.json', 'amusement_parks_trampoline_centers.json',
                    'rope_parks_climbing_walls.json', 'cafes_restaurants.json'
                ],
                'rating_bonus_weight': 0.2,
                'min_reviews_for_bonus': 10
            },
            'with_friends': {
                'tags': [
                    ('Группы', 2.0), ('Живая музыка', 2.5), ('Барные игры', 3.0),
                    ('Спорт', 2.0), ('Викторины', 2.5), ('Караоке', 3.0), ('Танцы', 2.5),
                    ('Пиво', 2.5), ('Счастливые часы', 2.0), ('Коктейли', 2.0)
                ],
                'file_types': [
                    'clubs.json', 'billiards_bowling.json', 'quests_computer_clubs.json',
                    'anticafe_karaoke.json', 'cafes_restaurants.json'
                ],
                'rating_bonus_weight': 0.2,
                'min_reviews_for_bonus': 8
            },
            'outdoor_walk': {
                'tags': [
                    ('Пешие прогулки', 3.0), ('Парк', 2.5), ('Столы для пикника', 2.0),
                    ('Велосипедные дорожки', 2.5), ('Детская площадка', 1.5), ('Собаки разрешены', 1.5),
                    ('Пикники', 2.0)
                ],
                'file_types': ['parks.json', 'gardens_zoos.json', 'skate_parks.json'],
                'rating_bonus_weight': 0.15,
                'min_reviews_for_bonus': 5
            },
            'view_scenic': {
                'tags': [
                    ('Места на крыше', 3.0), ('Историческая атмосфера', 2.5), ('Экскурсии', 3.0),
                    ('Пешие прогулки', 1.5), ('Пикники', 1.5)
                ],
                'file_types': ['parks.json', 'planetariums_sights.json', 'museums_galleries.json', 'cafes_restaurants.json'],
                'rating_bonus_weight': 0.2,
                'min_reviews_for_bonus': 5
            },
            'active_sport': {
                'tags': [
                    ('Баскетбольная площадка', 2.5), ('Теннисный корт', 2.5),
                    ('Волейбольная площадка', 2.5), ('Скейт-парк', 2.5), ('Спорт', 2.5),
                    ('Бассейн', 2.5), ('Велосипедные дорожки', 2.0)
                ],
                'file_types': [
                    'golf_tennis.json', 'baths_saunas.json', 'skate_parks.json',
                    'rope_parks_climbing_walls.json', 'karting_airsoft.json'
                ],
                'rating_bonus_weight': 0.2,
                'min_reviews_for_bonus': 5
            },
            'gaming': {
                'tags': [
                    ('Аркадные игры', 3.0), ('Барные игры', 3.0), ('Спорт', 1.5), ('Караоке', 1.5)
                ],
                'file_types': [
                    'quests_computer_clubs.json', 'billiards_bowling.json', 'cafes_restaurants.json'
                ],
                'rating_bonus_weight': 0.2,
                'min_reviews_for_bonus': 5
            },
            'party_nightclub': {
                'tags': [
                    ('Танцы', 3.0), ('Живая музыка', 2.5), ('Караоке', 2.5), ('Коктейли', 2.5),
                    ('Пиво', 2.0), ('Счастливые часы', 2.0), ('Бар на месте', 2.5), ('Алкоголь', 2.5)
                ],
                'file_types': ['clubs.json', 'anticafe_karaoke.json', 'cafes_restaurants.json'],
                'rating_bonus_weight': 0.2,
                'min_reviews_for_bonus': 8
            },
            'evening_night': {
                'tags': [
                    ('Ужин', 2.5), ('Алкоголь', 2.5), ('Коктейли', 2.5), ('Живая музыка', 2.5),
                    ('Танцы', 2.5), ('Ночная еда', 3.0)
                ],
                'file_types': ['clubs.json', 'cafes_restaurants.json', 'cinemas_movie_theaters.json'],
                'rating_bonus_weight': 0.2,
                'min_reviews_for_bonus': 8
            },
            'quiet_cozy': {
                'tags': [
                    ('Тихая атмосфера', 3.0), ('Уютная атмосфера', 3.0), ('Wi-Fi', 2.5),
                    ('Можно работать с ноутбуком', 3.0), ('Кофе', 2.0), ('Камин', 2.5),
                    ('Чай', 1.5)
                ],
                'file_types': [
                    'cafes_restaurants.json', 'anticafe_karaoke.json', 'photo_studios_workshops.json'
                ],
                'rating_bonus_weight': 0.2,
                'min_reviews_for_bonus': 5
            },
            'relax_wellness': {
                'tags': [
                    ('Сауна', 3.0), ('Уход за кожей', 3.0), ('Тихая атмосфера', 2.5), ('Членство', 2.0)
                ],
                'file_types': ['baths_saunas.json'],
                'rating_bonus_weight': 0.25,
                'min_reviews_for_bonus': 5
            },
            'budget_leisure': {
                'tags': [
                    ('Бесплатный паркинг', 2.5), ('Бесплатная парковка', 2.5), ('Скидки для детей', 2.0),
                    ('Быстрая еда', 2.0), ('Счастливые часы', 2.0)
                ],
                'file_types': [
                    'parks.json', 'cafes_restaurants.json', 'amusement_parks_trampoline_centers.json'
                ],
                'rating_bonus_weight': 0.15,
                'min_reviews_for_bonus': 5
            },
            'luxury_premium': {
                'tags': [
                    ('Премиум атмосфера', 3.0), ('Винная карта', 3.0), ('Отдельный кабинет', 3.0),
                    ('Парковка с водителем', 2.5), ('Бронирование', 2.0)
                ],
                'file_types': ['cafes_restaurants.json', 'clubs.json', 'theatres.json'],
                'rating_bonus_weight': 0.3,
                'min_reviews_for_bonus': 10
            },
            'cultural': {
                'tags': [
                    ('Экскурсии', 3.0), ('Историческая атмосфера', 2.5), ('Группы', 1.5),
                    ('Камера хранения', 1.5), ('Магазин подарков', 1.5)
                ],
                'file_types': [
                    'museums_galleries.json', 'theatres.json', 'planetariums_sights.json',
                    'cinemas_movie_theaters.json'
                ],
                'rating_bonus_weight': 0.2,
                'min_reviews_for_bonus': 5
            },
            'general_recommendation': {
                'tags': [],
                'file_types': None,
                'rating_bonus_weight': 0.3,
                'min_reviews_for_bonus': 10
            }
        }

    def load_model(self, model_path: str = "recommendation_system/models/best_intent_model.pt", 
                   label_encoder_path: str = None):
        """Загрузка обученной модели и LabelEncoder"""
        # Загружаем токенизатор
        self.tokenizer = AutoTokenizer.from_pretrained("sentence-transformers/LaBSE")
        
        # Загружаем LabelEncoder (нужен файл с датасетом интенций или сохранённый le)
        if label_encoder_path:
            import pickle
            with open(label_encoder_path, 'rb') as f:
                self.le = pickle.load(f)
        else:
            # Временный fallback — создаём LE из известных ключей
            intents = list(self.intent_config.keys())
            self.le = LabelEncoder()
            self.le.fit(intents + ['general_recommendation'])
        
        n_classes = len(self.le.classes_)
        
        # Создаём и загружаем модель
        self.model = IntentClassifier(n_classes=n_classes)
        self.model.load_state_dict(torch.load(model_path, map_location=self.device))
        self.model.to(self.device)
        self.model.eval()
        
        print(f"✅ Intent модель загружена на {self.device}")

    def predict_intent(self, query: str, max_len: int = 128) -> Tuple[str, float]:
        """Предсказание интенции + уверенность"""
        if self.model is None:
            self.load_model()
        
        encoding = self.tokenizer(
            query,
            add_special_tokens=True,
            max_length=max_len,
            padding='max_length',
            truncation=True,
            return_attention_mask=True,
            return_tensors='pt'
        )
        
        input_ids = encoding['input_ids'].to(self.device)
        attention_mask = encoding['attention_mask'].to(self.device)

        with torch.no_grad():
            outputs = self.model(input_ids, attention_mask)
            probabilities = torch.softmax(outputs, dim=1)
            pred_class_id = torch.argmax(probabilities, dim=1).item()
            confidence = torch.max(probabilities).item()

        intent_name = self.le.inverse_transform([pred_class_id])[0]
        
        # Применяем порог уверенности
        if confidence < config.INTENT_THRESHOLD:
            intent_name = 'general_recommendation'
            print(f"⚠️ Низкая уверенность интенции ({confidence:.1%}) → general_recommendation")
        
        return intent_name, confidence

    def get_recommendations(self, 
                           query: str, 
                           df_places: pd.DataFrame,
                           top_k: int = 50) -> Tuple[str, float, pd.DataFrame]:
        """
        Полная рекомендация по интенции
        """
        intent, confidence = self.predict_intent(query)
        
        cfg = self.intent_config.get(intent, self.intent_config['general_recommendation'])
        
        # Фильтрация по типу файла
        rec_df = df_places.copy()
        if cfg['file_types'] is not None:
            rec_df = rec_df[rec_df['original_file'].isin(cfg['file_types'])]
        
        # Подсчёт скора
        scores = []
        for _, row in rec_df.iterrows():
            features = self._parse_features(row.get('features_text', ''))
            tag_score = sum(weight for tag, weight in cfg['tags'] if tag in features)
            
            # Бонус за высокий рейтинг
            rating = row.get('review_rating', 0.0)
            review_cnt = row.get('review_count', 0)
            bonus = 0.0
            if review_cnt >= cfg['min_reviews_for_bonus'] and rating >= 4.0:
                bonus = (rating - 3.5) * cfg['rating_bonus_weight']
            
            scores.append(tag_score + bonus)
        
        rec_df = rec_df.copy()
        rec_df['intent_score'] = scores
        rec_df = rec_df.sort_values('intent_score', ascending=False).head(top_k)
        
        return intent, confidence, rec_df

    def _parse_features(self, features_text: str) -> List[str]:
        """Парсинг строки 'Особенности: ...'"""
        if not isinstance(features_text, str) or 'информация отсутствует' in features_text:
            return []
        text = features_text.replace('Особенности: ', '').strip()
        return [tag.strip() for tag in text.split(', ') if tag.strip()]


# Для удобного импорта
intent_module = IntentModule()
