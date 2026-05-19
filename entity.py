import re
import json
import pandas as pd
from typing import List, Dict, Set, Tuple, Optional
from dataclasses import dataclass, field
from enum import Enum

try:
    import pymorphy3
    MORPH = pymorphy3.MorphAnalyzer()
    HAS_MORPH = True
except ImportError:
    print("Предупреждение: pymorphy3 не установлен. Установите: pip install pymorphy3")
    HAS_MORPH = False


class EntityType(Enum):
    """Типы сущностей, извлекаемых из запроса"""
    PRICE_RANGE = "price_range"           # Ценовой диапазон
    PARKING = "parking"                   # Парковка
    WIFI = "wifi"                         # Wi-Fi/интернет
    RESERVATIONS = "reservations"         # Бронирование
    FOR_CHILDREN = "for_children"         # Для детей
    PAYMENT = "payment"                   # Способы оплаты
    AMENITIES = "amenities"               # Удобства
    ACCESSIBILITY = "accessibility"       # Доступность
    PETS = "pets"                         # Животные
    DINING_OPTIONS = "dining_options"     # Опции питания
    CROWD_TYPE = "crowd_type"             # Тип компании
    SERVICES = "services"                 # Дополнительные услуги
    OUTDOOR = "outdoor"                   # На открытом воздухе


@dataclass
class EntityRule:
    """Правило для извлечения сущности"""
    keywords: Set[str]                    # Ключевые слова в нормальной форме (леммы)
    entity_type: EntityType               # Тип сущности
    target_attribute: str                 # Целевой атрибут в about
    expected_value: Optional[str] = None  # Ожидаемое значение (если конкретное)
    weight: float = 1.0                   # Вес правила


class EntityExtractor:
    """
    Модуль извлечения сущностей из пользовательского запроса.
    Использует лемматизацию для корректного сопоставления слов.
    """

    def __init__(self):
        # Загружаем реальные признаки из about (для проверки)
        self.available_attributes = self._load_available_attributes()

        # Строим расширенные правила извлечения
        self.rules = self._build_extended_rules()

        # Обратное отображение: атрибут -> список типов сущностей
        self.attr_to_entities = self._build_reverse_mapping()

    def _load_available_attributes(self) -> Dict[str, List[str]]:
        """Загружает реальные атрибуты из столбца about."""
        return {
            "parking": [
                "Free parking lot", "Paid parking lot", "Paid street parking",
                "Free street parking", "Valet parking", "Parking", "Parking lot"
            ],
            "amenities": [
                "Wi-Fi", "Bar on site", "Restroom", "Gender-neutral restroom",
                "Restaurant", "Smoking area", "Dogs allowed", "Dogs allowed outside",
                "Live music", "Rooftop seating", "Fireplace", "Breakfast", "Brunch",
                "Lunch", "Dinner", "Dessert"
            ],

            "children": [
                "Good for kids", "Kids' menu", "High chairs", "Playground",
                "Diaper changing table", "Family-friendly"
            ],
            "payments": [
                "Credit cards", "Debit cards", "NFC mobile payments", "Checks", "Cash only"
            ],
            "price_level": ["Price range: $", "Price range: $$", "Price range: $$$"],
            "crowd": [
                "LGBTQ+ friendly", "Transgender safespace", "Tourists",
                "University students", "Family-friendly", "Groups"
            ],
            "services": [
                "Takeout", "Delivery", "Dine-in", "No-contact delivery",
                "Reservations required", "Reservations recommended"
            ],
            "accessibility": [
                "Wheelchair accessible entrance", "Wheelchair accessible restroom",
                "Wheelchair accessible parking lot", "Wheelchair accessible seating"
            ]
        }

    def _lemmatize(self, text: str) -> str:
        """
        Лемматизация текста с помощью pymorphy3.
        Преобразует слова в нормальную форму.
        """
        if not HAS_MORPH:
            # Fallback: просто приводим к нижнему регистру
            return text.lower()

        words = re.findall(r'[а-яёa-z]+', text.lower())
        lemmatized_words = []

        for word in words:
            parsed = MORPH.parse(word)[0]
            lemmatized_words.append(parsed.normal_form)

        return ' '.join(lemmatized_words)

    def _normalize_text(self, text: str) -> str:
        """Нормализация текста запроса с лемматизацией"""
        # Приводим к нижнему регистру
        text = text.lower()
        # Удаляем пунктуацию
        text = re.sub(r'[^\w\s]', ' ', text)
        # Удаляем лишние пробелы
        text = re.sub(r'\s+', ' ', text).strip()
        # Лемматизация
        text = self._lemmatize(text)
        return text

    def _extract_keywords(self, text: str) -> Set[str]:
        """
        Извлекает ключевые слова и биграммы из лемматизированного текста.
        """
        words = text.split()
        keywords = set(words)

        # Добавляем биграммы (важно для "бесплатная парковка" -> "бесплатный парковка")
        for i in range(len(words) - 1):
            bigram = f"{words[i]} {words[i+1]}"
            keywords.add(bigram)

        return keywords

    def _build_extended_rules(self) -> List[EntityRule]:
        """Строит расширенные правила для извлечения сущностей."""
        rules = []

        # ---------- 1. Ценовой диапазон (Price Range) ----------
        price_patterns = [
            # Недорого / бюджетно
            ({"недорогой", "бюджетный", "дешевый", "доступный", "экономный",
              "low cost", "budget", "cheap", "affordable", "недорого", "дешево"},
             EntityType.PRICE_RANGE, "price_level", "$", 1.2),
            # Средний ценовой сегмент
            ({"средний", "нормальный", "адекватный", "средний чек",
              "средняя цена", "moderate", "average"},
             EntityType.PRICE_RANGE, "price_level", "$$", 1.0),
            # Дорого / премиум
            ({"дорогой", "премиум", "expensive", "premium", "luxury",
              "элитный", "богатый", "vip"},
             EntityType.PRICE_RANGE, "price_level", "$$$", 1.1),
        ]

        for keywords, etype, attr, value, weight in price_patterns:
            rules.append(EntityRule(keywords, etype, attr, value, weight))

        # ---------- 2. Парковка (Parking) ----------
        parking_patterns = [
            ({"парковка", "паркинг", "оставить машину", "припарковать",
              "parking", "park", "car park", "парковочный место"},
             EntityType.PARKING, "parking", None, 1.5),
            ({"бесплатный парковка", "free parking"},
             EntityType.PARKING, "parking", "Free parking lot", 1.3),
            ({"валет", "valet"},
             EntityType.PARKING, "parking", "Valet parking", 1.2),
        ]

        for keywords, etype, attr, value, weight in parking_patterns:
            rules.append(EntityRule(keywords, etype, attr, value, weight))

        # ---------- 3. Wi-Fi / Интернет ----------
        wifi_patterns = [
            ({"вайфай", "wi-fi", "wifi", "интернет", "internet",
              "работать с ноутбук", "ноутбук", "коворкинг",
              "подключиться к интернет", "бесплатный интернет"},
             EntityType.WIFI, "amenities", "Wi-Fi", 1.4),
        ]

        for keywords, etype, attr, value, weight in wifi_patterns:
            rules.append(EntityRule(keywords, etype, attr, value, weight))

        # ---------- 4. Бронирование (Reservations) ----------
        reservation_patterns = [
            ({"бронирование", "бронь", "забронировать", "заранее заказать",
              "заказать стол", "reservation", "book a table", "reserve"},
             EntityType.RESERVATIONS, "services", "Reservations required", 1.0),
            ({"не нужно бронь", "можно без брони", "walk-in"},
             EntityType.RESERVATIONS, "services", None, 0.8),
        ]

        for keywords, etype, attr, value, weight in reservation_patterns:
            rules.append(EntityRule(keywords, etype, attr, value, weight))

        # ---------- 5. Для детей (For Children) ----------
        children_patterns = [
            ({"детский", "ребёнок", "ребенок", "дети", "family", "семья",
              "с детьми", "детская комната", "игровой", "high chair",
              "детское меню", "kids"},
             EntityType.FOR_CHILDREN, "children", None, 1.3),
            ({"детский меню", "kids menu", "детское меню"},
             EntityType.FOR_CHILDREN, "children", "Kids' menu", 1.2),
            ({"игровой площадка", "playground"},
             EntityType.FOR_CHILDREN, "children", "Playground", 1.3),
        ]

        for keywords, etype, attr, value, weight in children_patterns:
            rules.append(EntityRule(keywords, etype, attr, value, weight))

        # ---------- 6. Способы оплаты (Payment) ----------
        payment_patterns = [
            ({"карта", "безналичный", "credit card", "банковский карта",
              "pay by card", "оплата картой"},
             EntityType.PAYMENT, "payments", "Credit cards", 0.9),
            ({"наличный", "cash"},
             EntityType.PAYMENT, "payments", "Cash only", 1.0),
        ]

        for keywords, etype, attr, value, weight in payment_patterns:
            rules.append(EntityRule(keywords, etype, attr, value, weight))

        # ---------- 7. Удобства (Amenities) ----------
        amenities_patterns = [
            ({"туалет", "restroom", "уборная"},
             EntityType.AMENITIES, "amenities", "Restroom", 0.8),
            ({"бар", "bar", "выпивка", "алкоголь"},
             EntityType.AMENITIES, "amenities", "Bar on site", 1.0),
            ({"музыка", "live music", "живой музыка"},
             EntityType.AMENITIES, "amenities", "Live music", 1.5),
            ({"камин", "fireplace"},
             EntityType.AMENITIES, "amenities", "Fireplace", 1.3),
            ({"завтрак", "breakfast"},
             EntityType.AMENITIES, "amenities", "Breakfast", 1.1),
        ]

        for keywords, etype, attr, value, weight in amenities_patterns:
            rules.append(EntityRule(keywords, etype, attr, value, weight))

        # ---------- 8. Животные (Pets) ----------
        pets_patterns = [
            ({"собака", "животное", "pet", "dog", "pets allowed",
              "с питомцем", "с животными"},
             EntityType.PETS, "amenities", "Dogs allowed", 1.3),
        ]

        for keywords, etype, attr, value, weight in pets_patterns:
            rules.append(EntityRule(keywords, etype, attr, value, weight))

        # ---------- 9. На открытом воздухе (Outdoor) ----------
        outdoor_patterns = [
            ({"улица", "outdoor", "терраса", "веранда", "на открытом воздух",
              "летний веранда", "на улица"},
             EntityType.OUTDOOR, "atmosphere", "Outdoor seating", 1.4),
        ]

        for keywords, etype, attr, value, weight in outdoor_patterns:
            rules.append(EntityRule(keywords, etype, attr, value, weight))

        # ---------- 10. Тип компании (Crowd Type) ----------
        crowd_patterns = [
            ({"один", "alone", "solo"},
             EntityType.CROWD_TYPE, "crowd", "University students", 1.0),
            ({"компания", "friends", "друг", "с друзьями"},
             EntityType.CROWD_TYPE, "crowd", "Groups", 1.2),
        ]

        for keywords, etype, attr, value, weight in crowd_patterns:
            rules.append(EntityRule(keywords, etype, attr, value, weight))

        # ---------- 11. Услуги (Services) ----------
        services_patterns = [
            ({"доставка", "delivery", "с собой", "takeout"},
             EntityType.SERVICES, "services", "Delivery", 1.0),
            ({"на вынос", "takeout"},
             EntityType.SERVICES, "services", "Takeout", 1.0),
        ]

        for keywords, etype, attr, value, weight in services_patterns:
            rules.append(EntityRule(keywords, etype, attr, value, weight))

        return rules

    def _build_reverse_mapping(self) -> Dict[str, List[EntityType]]:
        """Строит обратное отображение: атрибут -> типы сущностей"""
        mapping = {}
        for rule in self.rules:
            key = f"{rule.target_attribute}_{rule.expected_value}" if rule.expected_value else rule.target_attribute
            if key not in mapping:
                mapping[key] = []
            mapping[key].append(rule.entity_type)
        return mapping

    def extract_entities(self, query: str) -> Dict[EntityType, List[Dict]]:
        """
        Извлекает сущности из пользовательского запроса.

        Args:
            query: Пользовательский запрос на русском языке

        Returns:
            Словарь: тип сущности -> список извлечённых значений с метаданными
        """
        normalized_query = self._normalize_text(query)
        query_keywords = self._extract_keywords(normalized_query)

        extracted = {}

        for rule in self.rules:
            # Проверяем пересечение ключевых слов
            matched_keywords = rule.keywords.intersection(query_keywords)

            if matched_keywords:
                entity_value = {
                    "attribute": rule.target_attribute,
                    "value": rule.expected_value,
                    "matched_keywords": list(matched_keywords),
                    "weight": rule.weight,
                    "query_fragment": self._get_query_fragment(query, matched_keywords)
                }

                if rule.entity_type not in extracted:
                    extracted[rule.entity_type] = []
                extracted[rule.entity_type].append(entity_value)

        # Дедупликация и сортировка по весу
        for etype in extracted:
            unique = {}
            for item in extracted[etype]:
                key = f"{item['attribute']}_{item['value']}"
                if key not in unique or item['weight'] > unique[key]['weight']:
                    unique[key] = item
            extracted[etype] = sorted(unique.values(), key=lambda x: x['weight'], reverse=True)

        return extracted

    def _get_query_fragment(self, query: str, matched_keywords: Set[str]) -> str:
        """Возвращает фрагмент запроса, где были найдены ключевые слова"""
        query_lower = query.lower()
        for kw in matched_keywords:
            if kw in query_lower:
                idx = query_lower.find(kw)
                return query[idx:idx + len(kw)]
        return ""

    def extract_entities_with_negation(self, query: str) -> Dict[EntityType, List[Dict]]:
        """
        Извлекает сущности + определяет отрицания (без детей, не для детей и т.д.)
        """
        entities = self.extract_entities(query)
        
        if not entities:
            return entities

        text_lower = query.lower()
        
        # Слова-отрицания
        negation_keywords = {'без', 'не', 'никаких', 'исключить', 'нет', 'против', 'только не'}
        
        has_negation = any(word in text_lower for word in negation_keywords)

        if has_negation:
            for etype_list in entities.values():
                for item in etype_list:
                    item['is_negation'] = True
            print("⚠️ Обнаружено отрицание в запросе — сущности помечены как исключения")

        return entities
    
entity_extractor = EntityExtractor()