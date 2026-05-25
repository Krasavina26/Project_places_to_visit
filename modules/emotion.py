from transformers import AutoTokenizer, AutoModelForSequenceClassification
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import torch
from typing import Dict, Optional, Tuple, List, Union
import re
import pymorphy3
import pandas as pd
import numpy as np


class EmotionDetector:
    def __init__(self, emotion_threshold: float = 0.3, semantic_weight: float = 0.6):
        """
        Инициализация детектора эмоций
        
        Args:
            emotion_threshold: порог уверенности для определения эмоции (0-1)
            semantic_weight: вес семантического поиска при комбинировании с about_dict (0-1)
        """
        print(" Инициализация EmotionDetector...")
        
        self.emotion_threshold = emotion_threshold
        self.semantic_weight = semantic_weight
        self.tokenizer = AutoTokenizer.from_pretrained("fyaronskiy/ruRoberta-large-ru-go-emotions")
        self.model = AutoModelForSequenceClassification.from_pretrained("fyaronskiy/ruRoberta-large-ru-go-emotions")
        self.model.eval()
        
        self.semantic_model = SentenceTransformer('intfloat/multilingual-e5-small')
        
        self.labels = [
            'admiration', 'amusement', 'anger', 'annoyance', 'approval', 'caring',
            'confusion', 'curiosity', 'desire', 'disappointment', 'disapproval',
            'disgust', 'embarrassment', 'excitement', 'fear', 'gratitude', 'grief',
            'joy', 'love', 'nervousness', 'optimism', 'pride', 'realization',
            'relief', 'remorse', 'sadness', 'surprise', 'neutral'
        ]
        
        self.morph = pymorphy3.MorphAnalyzer()
        self.lemmatizer_available = True
        
        self.default_coping_for_emotion = {
            'admiration': 'quiet', 'amusement': 'have_fun', 'approval': 'socialize',
            'caring': 'family', 'curiosity': 'explore', 'desire': 'romantic',
            'excitement': 'active', 'gratitude': 'quiet', 'joy': 'celebrate',
            'love': 'romantic', 'optimism': 'celebrate', 'pride': 'celebrate',
            'realization': 'quiet', 'relief': 'calm_down', 'anger': 'discharge',
            'annoyance': 'discharge', 'confusion': 'calm_down', 'disappointment': 'distract',
            'disapproval': 'calm_down', 'disgust': 'calm_down', 'embarrassment': 'calm_down',
            'fear': 'calm_down', 'grief': 'calm_down', 'nervousness': 'calm_down',
            'remorse': 'calm_down', 'sadness': 'distract', 'surprise': 'explore', 'neutral': 'any'
        }
        
        # ЗАГРУЗКА МАППИНГОВ
        self.about_dict_mapping = self._load_about_dict_mapping()
        self.tag_keywords = self._load_tag_keywords()
        self.coping_strategies = self._load_coping_strategies()
        self.desired_profiles = self._load_desired_profiles()
        
        # Кэш для семантических эмбеддингов тегов мест
        self._place_embeddings_cache = {}
        
        print(f" EmotionDetector готов (порог эмоций: {self.emotion_threshold}, вес семантики: {self.semantic_weight})\n")
    
    # МЕТОДЫ _load_* 
    def _load_about_dict_mapping(self) -> Dict:
        """Прямое отображение значений из about_dict в характеристики"""
        return {
            "Atmosphere": {
                "Quiet": {"activity_level": ["low"], "noise_level": ["quiet"], "atmosphere_type": ["relaxing", "cozy"], "crowdedness": ["empty"]},
                "Cozy": {"activity_level": ["low"], "noise_level": ["quiet"], "atmosphere_type": ["cozy", "romantic"], "crowdedness": ["empty", "moderate"]},
                "Casual": {"activity_level": ["medium"], "noise_level": ["moderate"], "atmosphere_type": ["cozy", "professional"], "crowdedness": ["moderate"]},
                "Romantic": {"activity_level": ["low"], "noise_level": ["quiet"], "atmosphere_type": ["romantic", "cozy"], "lighting": ["dim"], "crowdedness": ["empty", "moderate"]},
                "Lively": {"activity_level": ["high"], "noise_level": ["loud"], "atmosphere_type": ["lively"], "crowdedness": ["crowded"]},
                "Trendy": {"activity_level": ["medium"], "noise_level": ["moderate"], "atmosphere_type": ["lively", "professional"], "crowdedness": ["crowded"]},
                "Upscale": {"activity_level": ["low"], "noise_level": ["quiet"], "atmosphere_type": ["romantic", "professional"], "crowdedness": ["empty", "moderate"]},
                "Historic": {"activity_level": ["low"], "noise_level": ["quiet"], "atmosphere_type": ["cozy", "professional"], "crowdedness": ["moderate"]},
                "Trending": {"activity_level": ["high"], "noise_level": ["loud"], "atmosphere_type": ["lively"], "crowdedness": ["crowded"]}
            },
            "Highlights": {
                "Fireplace": {"atmosphere_type": ["romantic", "cozy"], "lighting": ["dim"]},
                "Live music": {"noise_level": ["loud"], "atmosphere_type": ["lively"], "crowdedness": ["crowded"]},
                "Live performances": {"atmosphere_type": ["lively"], "crowdedness": ["crowded"]},
                "Karaoke": {"noise_level": ["loud"], "atmosphere_type": ["lively"], "crowdedness": ["crowded"]},
                "Bar games": {"activity_level": ["high"], "atmosphere_type": ["lively"], "crowdedness": ["crowded"]},
                "Sports": {"activity_level": ["high"], "noise_level": ["loud"], "crowdedness": ["crowded"]},
                "Great coffee": {"atmosphere_type": ["cozy", "professional"]},
                "Great tea selection": {"atmosphere_type": ["cozy"]},
                "Great dessert": {"atmosphere_type": ["cozy"]},
                "Great cocktails": {"atmosphere_type": ["lively", "romantic"]},
                "Great wine list": {"atmosphere_type": ["romantic", "cozy"]},
                "Great beer selection": {"atmosphere_type": ["lively", "casual"], "crowdedness": ["moderate", "crowded"]},
                "Rooftop seating": {"lighting": ["natural"], "atmosphere_type": ["romantic", "cozy"]}
            },
            "Crowd": {
                "Groups": {"crowdedness": ["crowded"], "activity_level": ["medium"]},
                "Family-friendly": {"atmosphere_type": ["family"], "crowdedness": ["moderate"]},
                "College students": {"crowdedness": ["crowded"], "activity_level": ["high"], "noise_level": ["loud"]},
                "Tourists": {"crowdedness": ["crowded"]}
            },
            "Popular for": {
                "Solo dining": {"crowdedness": ["empty"]},
                "Good for working on laptop": {"activity_level": ["low"], "noise_level": ["quiet"], "atmosphere_type": ["professional"]},
                "Breakfast": {"atmosphere_type": ["casual", "cozy"]},
                "Lunch": {"atmosphere_type": ["casual", "professional"]},
                "Dinner": {"atmosphere_type": ["cozy", "romantic"]}
            },
            "Offerings": {
                "Sauna": {"activity_level": ["low"], "noise_level": ["quiet"], "atmosphere_type": ["relaxing"], "crowdedness": ["empty", "moderate"]},
                "Skincare treatments": {"activity_level": ["low"], "noise_level": ["quiet"], "atmosphere_type": ["relaxing"], "crowdedness": ["empty"]},
                "Dancing": {"activity_level": ["high"], "noise_level": ["loud"], "atmosphere_type": ["lively"], "crowdedness": ["crowded"]},
                "Arcade games": {"activity_level": ["medium"], "noise_level": ["loud"], "atmosphere_type": ["lively"], "crowdedness": ["crowded"]}
            }
        }
    
    def _load_tag_keywords(self) -> Dict:
        """Ключевые слова для классификации русских тегов"""
        return {
            "activity_level": {
                "low": ["тихое", "спокойное", "уютное", "расслабленное", "медленное"],
                "medium": ["умеренное", "обычное", "нешумное"],
                "high": ["активное", "энергичное", "шумное", "весёлое", "танцевальное"]
            },
            "noise_level": {
                "quiet": ["тихо", "спокойно", "бесшумно", "уединённо"],
                "moderate": ["умеренно", "разговоры", "фоновая музыка"],
                "loud": ["громко", "шумно", "живая музыка", "танцы"]
            },
            "atmosphere_type": {
                "romantic": ["романтично", "свечи", "уютно", "вдвоём"],
                "cozy": ["уютно", "лампово", "душевно", "тепло"],
                "lively": ["весело", "энергично", "живо", "шумно"],
                "relaxing": ["расслабляюще", "спокойно", "тихо", "релакс"],
                "family": ["семейно", "детям", "по-домашнему"],
                "professional": ["деловая", "рабочая", "строго"]
            },
            "lighting": {
                "dim": ["приглушённый свет", "свечи", "полумрак"],
                "natural": ["естественный свет", "окна", "светло"],
                "bright": ["ярко", "хорошее освещение"]
            },
            "crowdedness": {
                "empty": ["мало людей", "пусто", "свободно", "уединённо"],
                "moderate": ["несколько человек", "умеренно", "есть места"],
                "crowded": ["много людей", "людно", "аншлаг", "толпа"]
            }
        }
    
    def _load_coping_strategies(self) -> Dict:
        """Словарь копинг-стратегий"""
        return {
            'romantic': {'description': 'Романтическое свидание', 
                        'keywords': ['романтик', 'свидани', 'вдвоём', 'любим', 'пара', 'свечи'],
                        'semantic_templates': ['хочу романтический вечер', 'ищу место для свидания']},
            'celebrate': {'description': 'Празднование, вечеринка',
                        'keywords': ['праздник', 'отметить', 'день рождения', 'вечеринк', 'юбилей'],
                        'semantic_templates': ['хочу отметить праздник', 'ищу место для дня рождения']},
            'have_fun': {'description': 'Веселье, развлечения',
                        'keywords': ['веселиться', 'повеселиться', 'развлечься', 'тусить', 'зажечь'],
                        'semantic_templates': ['хочу повеселиться', 'нужно развлечься']},
            'active': {'description': 'Активный отдых, движение',
                      'keywords': ['активный', 'подвигаться', 'спорт', 'бег', 'тренировка'],
                      'semantic_templates': ['хочу активного отдыха', 'нужно подвигаться']},
            'explore': {'description': 'Узнать новое, исследовать',
                       'keywords': ['новое', 'узнать', 'интересн', 'посмотреть', 'экскурсия', 'музей'],
                       'semantic_templates': ['хочу узнать что-то новое', 'интересное место']},
            'socialize': {'description': 'Встреча с друзьями, общение',
                         'keywords': ['друзья', 'компания', 'встретиться', 'поговорить', 'посидеть'],
                         'semantic_templates': ['хочу встретиться с друзьями', 'куда сходить с компанией']},
            'family': {'description': 'Семейное время, с детьми',
                      'keywords': ['семья', 'детьми', 'ребёнком', 'дети', 'семейный'],
                      'semantic_templates': ['хочу сходить с семьёй', 'куда пойти с детьми']},
            'discharge': {'description': 'Выплеснуть энергию, выпустить пар',
                         'keywords': ['выпустить пар', 'выплеснуть', 'разрядиться', 'злость', 'гнев'],
                         'semantic_templates': ['хочу выплеснуть гнев', 'нужно выпустить пар']},
            'calm_down': {'description': 'Успокоиться, расслабиться',
                         'keywords': ['успокоиться', 'расслабиться', 'отдохнуть', 'восстановить силы', 'тишина'],
                         'semantic_templates': ['хочу отдохнуть', 'нужно расслабиться', 'хочется покоя']},
            'distract': {'description': 'Отвлечься, переключить внимание',
                        'keywords': ['забыться', 'оторваться', 'отвлечься', 'переключиться', 'кино'],
                        'semantic_templates': ['хочу отвлечься от проблем', 'нужно забыться']},
            'quiet': {'description': 'Тишина и покой',
                     'keywords': ['тишина', 'побыть один', 'уединение', 'без людей', 'спокойное место'],
                     'semantic_templates': ['хочу побыть один', 'нужно уединение', 'хочется тишины']},
            'safety': {'description': 'Безопасное, спокойное место',
                      'keywords': ['безопасно', 'спокойно', 'надёжно', 'тихо'],
                      'semantic_templates': ['хочу безопасное место', 'нужно спокойное место']},
            'support': {'description': 'Поддержка, понимание',
                       'keywords': ['поддержка', 'помощь', 'выслушать', 'пожалеть', 'излить душу'],
                       'semantic_templates': ['нужна поддержка', 'хочу пожаловаться']},
            'any': {'description': 'Любое времяпрепровождение', 'keywords': [], 'semantic_templates': []}
        }
    
    def _load_desired_profiles(self) -> Dict:
        """Желаемые профили мест для каждой эмоции и стратегии"""
        profiles = {}
        
        base_profiles = {
            'romantic': {"activity_level": ["low"], "noise_level": ["quiet"], 
                        "atmosphere_type": ["romantic", "cozy"], "lighting": ["dim"], 
                        "crowdedness": ["empty", "moderate"], "priority": {"atmosphere_type": 2.0}},
            'celebrate': {"activity_level": ["high"], "noise_level": ["loud"], 
                         "atmosphere_type": ["lively"], "crowdedness": ["crowded"],
                         "priority": {"activity_level": 1.5}},
            'quiet': {"activity_level": ["low"], "noise_level": ["quiet"], 
                     "atmosphere_type": ["cozy", "relaxing"], "crowdedness": ["empty"],
                     "priority": {"noise_level": 2.0}},
            'active': {"activity_level": ["high"], "noise_level": ["moderate"], 
                      "atmosphere_type": ["lively"], "crowdedness": ["moderate", "crowded"],
                      "priority": {"activity_level": 2.0}},
            'calm_down': {"activity_level": ["low"], "noise_level": ["quiet"], 
                         "atmosphere_type": ["cozy", "relaxing"], "crowdedness": ["empty"],
                         "priority": {"noise_level": 2.0, "atmosphere_type": 1.5}},
            'discharge': {"activity_level": ["high"], "noise_level": ["loud"], 
                         "atmosphere_type": ["lively"], "crowdedness": ["crowded", "moderate"],
                         "priority": {"activity_level": 2.0}},
            'explore': {"activity_level": ["medium"], "noise_level": ["moderate"], 
                       "atmosphere_type": ["professional", "lively"], "crowdedness": ["moderate"],
                       "priority": {"atmosphere_type": 1.5}},
            'socialize': {"activity_level": ["medium"], "noise_level": ["moderate"], 
                         "atmosphere_type": ["cozy", "lively"], "crowdedness": ["moderate"],
                         "priority": {}},
            'family': {"activity_level": ["low"], "noise_level": ["quiet"], 
                      "atmosphere_type": ["family", "cozy"], "crowdedness": ["moderate"],
                      "priority": {"atmosphere_type": 2.0}},
            'any': {"activity_level": ["medium"], "noise_level": ["moderate"], 
                   "atmosphere_type": ["cozy"], "crowdedness": ["moderate"],
                   "priority": {}}
        }
        
        emotions = ['admiration', 'amusement', 'approval', 'caring', 'curiosity', 'desire',
                   'excitement', 'gratitude', 'joy', 'love', 'optimism', 'pride', 'realization',
                   'relief', 'anger', 'annoyance', 'confusion', 'disappointment', 'disapproval',
                   'disgust', 'embarrassment', 'fear', 'grief', 'nervousness', 'remorse', 
                   'sadness', 'surprise', 'neutral']
        
        for emotion in emotions:
            for strategy, profile in base_profiles.items():
                profiles[(emotion, strategy)] = profile.copy()
        
        return profiles
    
    # ЛЕММАТИЗАЦИЯ
    def _lemmatize_word(self, word: str) -> str:
        try:
            return self.morph.parse(word.lower().strip())[0].normal_form
        except:
            return word.lower().strip()
    
    def _lemmatize_text(self, text: str) -> List[str]:
        words = re.findall(r'\b\w+\b', text.lower())
        return [self._lemmatize_word(w) for w in words if len(w) > 2]
    
    # ПОИСК СТРАТЕГИИ
    def _detect_coping_by_keywords(self, text: str) -> Tuple[Optional[str], float]:
        text_lemmas = set(self._lemmatize_text(text))
        scores = {}
        
        for strategy, data in self.coping_strategies.items():
            if not data['keywords']:
                continue
            match_count = 0
            for keyword in data['keywords']:
                keyword_lemma = self._lemmatize_word(keyword)
                if keyword_lemma in text_lemmas:
                    match_count += 1
            if match_count > 0:
                max_possible = min(len(data['keywords']), 5)
                confidence = min(match_count / max_possible, 1.0)
                scores[strategy] = confidence
        
        if scores:
            best = max(scores.items(), key=lambda x: x[1])
            return best[0], best[1]
        return None, 0.0
    
    def _detect_coping_by_semantic(self, text: str, threshold: float = 0.55) -> Tuple[Optional[str], float]:
        templates_dict = {
            strategy: data.get('semantic_templates', [])
            for strategy, data in self.coping_strategies.items()
            if data.get('semantic_templates')
        }
        if not templates_dict:
            return None, 0.0
        
        all_templates = []
        template_labels = []
        for strategy, templates in templates_dict.items():
            for template in templates:
                all_templates.append(template)
                template_labels.append(strategy)
        
        query_embedding = self.semantic_model.encode([text])
        template_embeddings = self.semantic_model.encode(all_templates)
        similarities = cosine_similarity(query_embedding, template_embeddings)[0]
        
        scores = {}
        for i, strategy in enumerate(template_labels):
            if similarities[i] >= threshold:
                scores[strategy] = max(scores.get(strategy, 0), similarities[i])
        
        if scores:
            best = max(scores.items(), key=lambda x: x[1])
            return best[0], best[1]
        return None, 0.0
    
    def _detect_coping_strategy(self, text: str, emotion: str) -> Tuple[str, float, str]:
        strategy, confidence = self._detect_coping_by_keywords(text)
        if strategy and confidence >= 0.3:
            return strategy, confidence, 'keywords'
        
        strategy, confidence = self._detect_coping_by_semantic(text, threshold=0.55)
        if strategy and confidence >= 0.55:
            return strategy, confidence, 'semantic'
        
        default_strategy = self.default_coping_for_emotion.get(emotion, 'any')
        return default_strategy, 0.3, 'default'
    
    # ИЗВЛЕЧЕНИЕ ХАРАКТЕРИСТИК МЕСТА
    def extract_from_about_dict(self, about_dict) -> Dict:
        """Извлекает характеристики из about_dict"""
        features = {"activity_level": [], "noise_level": [], "atmosphere_type": [], "lighting": [], "crowdedness": []}
        
        if isinstance(about_dict, str):
            try:
                import ast
                about_dict = ast.literal_eval(about_dict)
            except:
                return features
        
        if not about_dict or not isinstance(about_dict, dict):
            return features
        
        for field, values in about_dict.items():
            if field in self.about_dict_mapping and isinstance(values, list):
                for value in values:
                    if value in self.about_dict_mapping[field]:
                        mapping = self.about_dict_mapping[field][value]
                        for cat, vals in mapping.items():
                            if cat in features:
                                features[cat].extend(vals if isinstance(vals, list) else [vals])
        
        for cat in features:
            if features[cat]:
                features[cat] = list(set(features[cat]))
        return features
    
    def extract_from_atmosphere_tags(self, tags_str: str) -> Dict:
        """Извлекает характеристики из атмосферных тегов"""
        features = {"activity_level": [], "noise_level": [], "atmosphere_type": [], "lighting": [], "crowdedness": []}
        
        if not tags_str or not isinstance(tags_str, str) or not tags_str.strip():
            return features
        
        tags = [t.strip().lower() for t in tags_str.split(', ') if t.strip()]
        
        for tag in tags:
            for category, levels in self.tag_keywords.items():
                for level, keywords in levels.items():
                    for keyword in keywords:
                        if keyword in tag:
                            features[category].append(level)
                            break
        
        for cat in features:
            if features[cat]:
                features[cat] = list(set(features[cat]))
        return features
    
    def extract_place_features_combined(self, place_row) -> Tuple[Dict, float]:
        """Объединяет характеристики из about_dict и all_tags_concat"""
        features = {"activity_level": [], "noise_level": [], "atmosphere_type": [], 
                    "lighting": [], "crowdedness": []}
        confidence = 0.0
        
        about_features = {}
        if 'about_dict' in place_row.index:
            about_features = self.extract_from_about_dict(place_row['about_dict'])
            for cat in features:
                features[cat].extend(about_features.get(cat, []))
        
        tags_column = 'all_tags_concat'
        has_semantic_data = False
        
        if tags_column in place_row.index:
            tags_value = place_row[tags_column]
            
            if not pd.isna(tags_value) and tags_value is not None:
                if isinstance(tags_value, str):
                    tags_str = tags_value.strip()
                    has_semantic_data = bool(tags_str)
                elif isinstance(tags_value, (list, dict)):
                    has_semantic_data = bool(tags_value)
            
            if has_semantic_data:
                if isinstance(tags_value, str):
                    tags_features = self.extract_from_atmosphere_tags(tags_value)
                else:
                    tags_features = self.extract_from_atmosphere_tags(str(tags_value))
                
                for cat in features:
                    existing = set(features[cat])
                    new_tags = set(tags_features.get(cat, []))
                    features[cat].extend(list(new_tags - existing))
        
        for cat in features:
            if features[cat]:
                features[cat] = list(set(features[cat]))
        
        has_about = any(len(about_features.get(cat, [])) > 0 for cat in features)
        
        if has_about and has_semantic_data:
            confidence = 1.0
        elif has_about:
            confidence = 0.7
        elif has_semantic_data:
            confidence = 0.5
        else:
            confidence = 0.0
        
        return features, confidence
    
    # СЕМАНТИЧЕСКИЙ ПОИСК
    def semantic_search_score(self, query: str, tags_str: str) -> float:
        """Вычисляет семантическую близость между запросом и тегами места"""
        if not tags_str or not isinstance(tags_str, str) or not tags_str.strip():
            return 0.0
        
        cache_key = tags_str
        if cache_key not in self._place_embeddings_cache:
            self._place_embeddings_cache[cache_key] = self.semantic_model.encode([tags_str])
        
        query_embedding = self.semantic_model.encode([query])
        tags_embedding = self._place_embeddings_cache[cache_key]
        
        similarity = cosine_similarity(query_embedding, tags_embedding)[0][0]
        return float(similarity)
    
    # РАСЧЁТ СКОРОВ
    def calculate_final_score(
        self, 
        place_row, 
        desired_profile: Dict, 
        query: str,
        rating_col: str = 'review_rating',
        reviews_count_col: str = 'review_count'
    ) -> Dict:
        """Рассчитывает итоговый скор для места"""
        place_features, features_confidence = self.extract_place_features_combined(place_row)
        match_score = self.calculate_match_score(place_features, desired_profile)
        
        tags_value = place_row.get('all_tags_concat', '')
        has_tags = False
        tags_str = ""
        
        if not pd.isna(tags_value) and tags_value is not None:
            if isinstance(tags_value, str):
                tags_str = tags_value.strip()
                has_tags = bool(tags_str)
            elif isinstance(tags_value, (list, dict)):
                has_tags = bool(tags_value)
                tags_str = str(tags_value) if tags_value else ""
        
        semantic_score = 0.0
        
        if has_tags:
            semantic_score = self.semantic_search_score(query, tags_str)
            combined_match_score = (match_score * (1 - self.semantic_weight) + 
                                semantic_score * self.semantic_weight)
        else:
            combined_match_score = match_score
        
        rating_score = self.calculate_rating_score(place_row, rating_col, reviews_count_col)
        final_score = combined_match_score * 0.7 + rating_score * 0.3
        
        return {
            'match_score': match_score,
            'semantic_score': semantic_score,
            'combined_match_score': combined_match_score,
            'rating_score': rating_score,
            'final_score': final_score,
            'features_confidence': features_confidence,
            'has_semantic_data': has_tags
        }
    
    def calculate_rating_score(
        self, 
        place_row, 
        rating_col: str = 'review_rating', 
        reviews_count_col: str = 'review_count',
        global_avg_rating: float = 4.0,
        prior_weight: int = 10
    ) -> float:
        """Рассчитывает скор рейтинга с учётом количества отзывов (Bayesian average)"""
        rating = place_row.get(rating_col, 0)
        reviews_count = place_row.get(reviews_count_col, 0)
        
        if pd.isna(rating) or rating is None or rating == 0:
            return 0.0
        if pd.isna(reviews_count) or reviews_count is None:
            reviews_count = 0
        
        bayesian_rating = (reviews_count * rating + prior_weight * global_avg_rating) / (reviews_count + prior_weight)
        rating_score = bayesian_rating / 5.0
        
        return min(max(rating_score, 0.0), 1.0)
    
    def calculate_match_score(self, place_features: Dict, desired_profile: Dict) -> float:
        """Рассчитывает степень соответствия места желаемому профилю"""
        base_weights = {"activity_level": 1.0, "noise_level": 1.5, "atmosphere_type": 2.0, "lighting": 0.8, "crowdedness": 1.0}
        weights = base_weights.copy()
        
        if "priority" in desired_profile:
            for key, weight in desired_profile["priority"].items():
                if key in weights:
                    weights[key] = weight
        
        total_score = 0
        total_weight = 0
        
        for category in weights:
            if category in desired_profile:
                target_values = desired_profile[category]
                actual_values = place_features.get(category, [])
                
                if actual_values:
                    matches = set(target_values) & set(actual_values)
                    if matches:
                        score_ratio = len(matches) / len(target_values)
                        total_score += weights[category] * score_ratio
                total_weight += weights[category]
        
        return total_score / total_weight if total_weight > 0 else 0.0
    
    # ОСНОВНОЙ МЕТОД PREDICT
    def predict(self, text: str, emotion_threshold: Optional[float] = None) -> Union[Dict, None]:
        """Предсказание эмоции и стратегии"""
        threshold = emotion_threshold if emotion_threshold is not None else self.emotion_threshold
        
        inputs = self.tokenizer(text, truncation=True, max_length=128, return_tensors='pt')
        
        with torch.no_grad():
            logits = self.model(**inputs).logits
        probas = torch.sigmoid(logits).squeeze().tolist()
        
        emotion_scores = dict(zip(self.labels, probas))
        top_emotion = max(emotion_scores.items(), key=lambda x: x[1])
        
        if top_emotion[1] < threshold:
            return None
        
        coping, coping_confidence, coping_method = self._detect_coping_strategy(text, top_emotion[0])
        
        key = (top_emotion[0], coping)
        desired_profile = self.desired_profiles.get(key, self.desired_profiles.get((top_emotion[0], 'any'), {
            "activity_level": ["medium"], "noise_level": ["moderate"], 
            "atmosphere_type": ["cozy"], "crowdedness": ["moderate"], "priority": {}
        }))
        
        profile_description = self._get_profile_description(desired_profile)
        
        return {
            "emotion": top_emotion[0],
            "emotion_confidence": top_emotion[1],
            "emotion_scores": {k: v for k, v in sorted(emotion_scores.items(), key=lambda x: x[1], reverse=True)[:5]},
            "coping": coping,
            "coping_confidence": coping_confidence,
            "coping_method": coping_method,
            "coping_description": self.coping_strategies.get(coping, {}).get('description', 'Любое времяпрепровождение'),
            "desired_profile": desired_profile,
            "profile_description": profile_description,
            "threshold_used": threshold
        }
    
    def _get_profile_description(self, profile: Dict) -> str:
        """Формирует описание желаемого места"""
        desc_parts = []
        
        if profile.get("activity_level"):
            activity = profile["activity_level"][0]
            if activity == "low":
                desc_parts.append("спокойное")
            elif activity == "medium":
                desc_parts.append("умеренно активное")
            else:
                desc_parts.append("активное")
        
        if profile.get("noise_level"):
            noise = profile["noise_level"][0]
            if noise == "quiet":
                desc_parts.append("тихое")
            elif noise == "moderate":
                desc_parts.append("с умеренным шумом")
            else:
                desc_parts.append("шумное")
        
        if profile.get("atmosphere_type"):
            atmos = profile["atmosphere_type"]
            if "romantic" in atmos:
                desc_parts.append("романтичное")
            elif "lively" in atmos:
                desc_parts.append("с живой атмосферой")
            elif "cozy" in atmos:
                desc_parts.append("уютное")
            elif "relaxing" in atmos:
                desc_parts.append("рассабляющее")
        
        if profile.get("crowdedness"):
            crowded = profile["crowdedness"][0]
            if crowded == "empty":
                desc_parts.append("малолюдное")
            elif crowded == "crowded":
                desc_parts.append("популярное")
        
        if desc_parts:
            return f"идеальное место: {', '.join(desc_parts)}"
        return "комфортное место"
    
    # ОСНОВНОЙ МЕТОД РЕКОМЕНДАЦИЙ
    def get_emotion_based_recommendations(
        self, 
        query: str, 
        places_df: pd.DataFrame, 
        top_k: int = None,
        min_match_score: float = 0.0
    ) -> pd.DataFrame:
        """
        Возвращает ВСЕ подходящие места, ранжированные по рейтингу с учётом количества отзывов
        
        Args:
            query: текст запроса пользователя
            places_df: DataFrame с колонками 'about_dict', 'all_tags_concat', 
                      'review_rating', 'review_count'
            top_k: если указан, возвращает только top_k мест, иначе ВСЕ подходящие
            min_match_score: минимальный скор соответствия (0-1)
        
        Returns:
            DataFrame со всеми подходящими местами, отсортированный по финальному скору
        """
        emotion_result = self.predict(query)
        
        if not emotion_result:
            print(f" Эмоция не распознана (ниже порога {self.emotion_threshold})")
            result_df = places_df.copy()
            result_df['final_score'] = result_df.apply(
                lambda row: self.calculate_rating_score(row), axis=1
            )
            result_df['match_score'] = 0.0
            result_df['semantic_score'] = 0.0
            result_df['combined_match_score'] = 0.0
            result_df['rating_score'] = result_df['final_score']
            result_df['features_confidence'] = 0.0
            result_df['has_semantic_data'] = False
            result_df = result_df.sort_values('final_score', ascending=False)
            
            if top_k:
                return result_df.head(top_k)
            return result_df
        
        desired_profile = emotion_result["desired_profile"]
        
        print(f"\n Распознана эмоция: {emotion_result['emotion']} "
              f"(уверенность: {emotion_result['emotion_confidence']:.2f})")
        print(f" Стратегия: {emotion_result['coping_description']}")
        print(f" {emotion_result['profile_description']}")
        
        print(f" Оценка {len(places_df)} мест...")
        
        # Рассчитываем скоры для ВСЕХ мест
        scores = []
        for idx, row in places_df.iterrows():
            score_data = self.calculate_final_score(row, desired_profile, query)
            scores.append(score_data)
        
        # Добавляем скоры в DataFrame
        result_df = places_df.copy()
        for key in scores[0].keys():
            result_df[key] = [s[key] for s in scores]
        
        # Фильтруем по минимальному скору
        result_df = result_df[result_df['final_score'] >= min_match_score]
        
        # Сортируем по финальному скору (уже учитывает рейтинг с весом отзывов)
        result_df = result_df.sort_values('final_score', ascending=False)
        
        print(f"\n📊 Результаты:")
        print(f"   - Всего мест: {len(places_df)}")
        print(f"   - Прошло фильтр (score >= {min_match_score}): {len(result_df)}")
        print(f"   - Средний финальный скор: {result_df['final_score'].mean():.3f}")
        print(f"   - Мест с семантическими данными: {result_df['has_semantic_data'].sum()}")
        
        # Возвращаем ВСЕ результаты (или top_k если указан)
        if top_k:
            return result_df.head(top_k)
        return result_df

def print_emotion_recommendations(recommendations_df: pd.DataFrame, top_n: int = None):
    """
    Красиво выводит рекомендации с названиями, категориями и всеми скорами
    """
    if top_n:
        recommendations_df = recommendations_df.head(top_n)
    
    print(f" РЕКОМЕНДАЦИИ (ранжированы по рейтингу с учётом числа отзывов):")
    
    for display_idx, (idx, row) in enumerate(recommendations_df.iterrows(), 1):
        title = row.get('title', 'Название не указано')
        if pd.isna(title):
            title = 'Название не указано'
        
        category = row.get('category', 'Категория не указана')
        if pd.isna(category):
            category = 'Категория не указана'
        
        place_id = row.get('place_id', idx)
        if pd.isna(place_id):
            place_id = idx
        
        rating = row.get('review_rating', 'Нет')
        if pd.isna(rating):
            rating = 'Нет'
        elif isinstance(rating, (int, float)):
            rating = f"{rating:.1f}"
        
        review_count = row.get('review_count', 0)
        if pd.isna(review_count):
            review_count = 0
        
        print(f"\n{'─'*100}")
        print(f" {display_idx}. {title}")
        print(f"    ID: {place_id} | 📂 Категория: {category}")
        print(f"    Рейтинг: {rating} (всего оценок: {int(review_count)})")
        print(f"   {'─'*80}")
        
        if 'final_score' in row:
            print(f"    Итоговый скор (рейтинг+соответствие): {row['final_score']:.4f}")
        if 'rating_score' in row:
            print(f"   ├─  Рейтинговый скор (Bayesian): {row['rating_score']:.4f}")
        if 'match_score' in row:
            print(f"   ├─  Match скор (about_dict): {row['match_score']:.4f}")
        if 'semantic_score' in row:
            print(f"   └─  Semantic скор (теги): {row['semantic_score']:.4f}")
        
        tags_value = row.get('all_tags_concat', '')
        if pd.isna(tags_value) or tags_value is None:
            tags_str = ""
        elif not isinstance(tags_value, str):
            tags_str = str(tags_value)
        else:
            tags_str = tags_value.strip()
        
        if tags_str:
            if len(tags_str) > 100:
                tags_str = tags_str[:100] + "..."
            print(f"    Теги из отзывов: {tags_str}")
    
    print(f"\n{'='*100}")
