# pipeline.py
import pandas as pd
from typing import Dict, Optional

from config import config
from data_loader import load_dataset
from geo_filter import apply_geo_filter

# Модули
from modules.intent import intent_module
from modules.emotion import EmotionDetector, print_emotion_recommendations
from modules.entity import entity_extractor
from modules.ambience import AmbienceModule
from utils import reciprocal_rank_fusion


class RecommendationPipeline:
    """Центральный класс интеллектуальной системы рекомендаций"""

    def __init__(self):
        print("🚀 Инициализация Recommendation Pipeline...")
        
        # 1. Загрузка данных
        self.df = load_dataset()
        
        # 2. Инициализация модулей
        self.emotion_detector = EmotionDetector(emotion_threshold=0.3, semantic_weight=0.6)
        self.ambience = AmbienceModule()
        
        # 3. Intent Module (самый важный)
        print("📌 Загрузка Intent модели...")
        intent_module.load_model()
        
        print("✅ Пайплайн успешно инициализирован!\n")

    def recommend(self, 
                  query: str, 
                  bounds: Optional[Dict] = None,
                  top_k: int = None,
                  use_emotion_in_rrf: bool = True) -> pd.DataFrame:
        
        if top_k is None:
            top_k = config.FINAL_TOP_K

        print(f"\n🔍 Обработка запроса: '{query}'")

        # 1. Геофильтрация
        df_filtered = apply_geo_filter(self.df, bounds)
        if len(df_filtered) == 0:
            return pd.DataFrame()

        # ====================== 1. INTENT ======================
        intent, intent_conf, intent_candidates = intent_module.get_recommendations(
            query=query, 
            df_places=df_filtered, 
            top_k=config.TOP_K_CANDIDATES
        )
        print(f"🎯 Intent Module     → {len(intent_candidates):3d} кандидатов")

        # ====================== 2. AMBIENCE ======================
        ambience_candidates_idx = self.ambience.search(query, df_filtered, top_k=config.TOP_K_CANDIDATES)
        ambience_candidates = df_filtered.loc[df_filtered.index.intersection(ambience_candidates_idx)]
        print(f"🌫️  Ambience Module   → {len(ambience_candidates):3d} кандидатов")

        # ====================== 3. EMOTION ======================
        emotion_candidates = pd.DataFrame()
        emotion_candidates_with_scores = None
        emotion_result = None
        
        if use_emotion_in_rrf:
            emotion_result = self.emotion_detector.predict(query)
            
            if emotion_result:
                print(f"😌 Emotion Module    → распознана эмоция: {emotion_result['emotion']} "
                      f"(уверенность: {emotion_result['emotion_confidence']:.2f})")
                print(f"   Стратегия: {emotion_result['coping_description']}")
                print(f"   Желаемый профиль: {emotion_result['profile_description']}")
                
                # Получаем кандидатов от эмоционального модуля (СО ВСЕМИ СКОРАМИ)
                emotion_candidates_with_scores = self.emotion_detector.get_emotion_based_recommendations(
                    query=query,
                    places_df=df_filtered,
                    top_k=config.TOP_K_CANDIDATES,
                    min_match_score=0.1
                )
                # Для RRF используем только индексы (без скорей)
                emotion_candidates = emotion_candidates_with_scores
                print(f"   → {len(emotion_candidates):3d} кандидатов")
            else:
                print(f"😌 Emotion Module    → не распознана (ниже порога {self.emotion_detector.emotion_threshold})")
        else:
            print(f"😌 Emotion Module    → отключён")

        # ====================== 4. RRF ======================
        candidate_dfs = [intent_candidates]
        
        if len(ambience_candidates) > 0:
            candidate_dfs.append(ambience_candidates)
        
        if len(emotion_candidates) > 0:
            candidate_dfs.append(emotion_candidates)
            print(f"🔄 RRF → объединяем {len(candidate_dfs)} модуля: Intent, Ambience, Emotion")
        else:
            print(f"🔄 RRF → объединяем {len(candidate_dfs)} модуля: Intent, Ambience")

        combined_scores = reciprocal_rank_fusion(candidate_dfs)
        result = df_filtered.join(combined_scores, how='inner')

        if 'rrf_score' not in result.columns:
            result['rrf_score'] = 1.0

        print(f"   → После RRF: {len(result)} заведений")
        
        # ====================== ВОССТАНАВЛИВАЕМ ЭМОЦИОНАЛЬНЫЕ СКОРЫ ======================
        if emotion_candidates_with_scores is not None and len(emotion_candidates_with_scores) > 0:
            # Берём только нужные колонки со скорами
            score_cols = ['final_score', 'match_score', 'semantic_score', 
                         'combined_match_score', 'rating_score', 'features_confidence', 
                         'has_semantic_data']
            existing_score_cols = [col for col in score_cols if col in emotion_candidates_with_scores.columns]
            
            if existing_score_cols:
                # Присоединяем эмоциональные скоры к result по индексу
                result = result.join(emotion_candidates_with_scores[existing_score_cols], how='left')
                print(f"   → Восстановлены эмоциональные скоры для {len(result)} заведений")

        # ====================== 5. ENTITY FILTER ======================
        entities = entity_extractor.extract_entities_with_negation(query)
        
        print(f"📋 Entity Extraction → {len(entities)} типов сущностей")
        for etype, items in entities.items():
            for item in items:
                negation = " [ИСКЛЮЧЕНИЕ]" if item.get('is_negation') else ""
                print(f"   • {etype.value}: {item.get('value')}{negation} (вес: {item.get('weight')})")

        if entities:
            before = len(result)
            result = self._apply_entity_filters(result, entities)
            print(f"   → После фильтра сущностей: {len(result)} (было {before})")

        # ====================== ФИНАЛЬНЫЙ ФИЛЬТР ======================
        if 'review_rating' in result.columns:
            result = result[result['review_rating'] >= config.MIN_RATING]
            print(f"⭐ После фильтра рейтинга: {len(result)} заведений")

        # Сортировка
        sort_columns = ['rrf_score']
        if 'review_rating' in result.columns:
            sort_columns.append('review_rating')
        if 'review_count' in result.columns:
            sort_columns.append('review_count')
        
        result = result.sort_values(
            by=sort_columns,
            ascending=[False, False, False] if len(sort_columns) == 3 else [False, False]
        )

        final_result = result.head(top_k).copy()

        # Формируем колонки для вывода
        display_cols = ['title', 'category', 'address', 'review_rating', 
                       'review_count', 'link', 'phone', 'rrf_score']
        
        # Добавляем эмоциональные скоры если они есть
        if emotion_result and 'final_score' in final_result.columns:
            display_cols.append('final_score')
        if emotion_result and 'match_score' in final_result.columns:
            display_cols.append('match_score')
        if emotion_result and 'semantic_score' in final_result.columns:
            display_cols.append('semantic_score')
        
        display_cols = [col for col in display_cols if col in final_result.columns]

        print(f"\n🎉 Финально выдано: {len(final_result)} рекомендаций\n")
        
        # Красиво выводим топ рекомендаций (используем функцию, а не метод класса)
        if emotion_result and len(final_result) > 0:
            print_emotion_recommendations(final_result, top_n=min(5, len(final_result)))
        
        return final_result[display_cols]

    def _apply_entity_filters(self, df: pd.DataFrame, entities: dict) -> pd.DataFrame:
        """Применяет фильтры по сущностям (включая отрицания)"""
        if not entities:
            return df
            
        result = df.copy()
        
        for etype, items in entities.items():
            for item in items:
                attr = item.get('attribute')
                value = item.get('value')
                is_negation = item.get('is_negation', False)
                
                if not attr or attr not in result.columns:
                    continue
                
                col = result[attr].astype(str)
                
                if is_negation:
                    if value:
                        result = result[~col.str.contains(str(value), case=False, na=False)]
                    print(f"   ❌ Исключение: {attr} = {value}")
                else:
                    if value:
                        result = result[col.str.contains(str(value), case=False, na=False)]
                    else:
                        result = result[col.str.contains('True|Yes|есть|да', case=False, na=False)]
                    print(f"   ✅ Требование: {attr} = {value}")
        
        return result
