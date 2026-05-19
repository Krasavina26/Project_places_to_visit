# recommendation_system/__init__.py
"""
Рекомендательная система для поиска мест в Москве
"""

from .pipeline import RecommendationPipeline
from .modules.recommender import PlaceRecommender
from .modules.preprocessor import QueryPreprocessor

__all__ = ['RecommendationPipeline', 'PlaceRecommender', 'QueryPreprocessor']