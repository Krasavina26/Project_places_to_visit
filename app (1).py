from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import List, Optional, Dict
from datetime import datetime
import re

app = FastAPI(title="Чат-бот для поиска мест", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

session_state: Dict[str, Dict] = {}

class ChatRequest(BaseModel):
    message: str
    user_id: Optional[str] = "default_user"

class ChatResponse(BaseModel):
    reply: str
    timestamp: str
    suggestions: Optional[List[str]] = None

def get_mock_celebration_recommendations(user_id: str) -> str:
    """Реальные бары Москвы для празднования"""
    
    mock_results = [
        {'place_id': '1', 'name': 'Chainaya.tea & cocktails', 'address': 'ул. Большая Никитская, 12', 'rating': 4.9, 'description': 'Уютный бар с авторскими коктейлями и чайной картой'},
        {'place_id': '2', 'name': 'Noise Moscow', 'address': 'ул. Большая Дмитровка, 32', 'rating': 4.8, 'description': 'Популярный коктейль-бар с живой музыкой по выходным'},
        {'place_id': '3', 'name': 'Soho Rooms', 'address': 'ул. Новый Арбат, 21', 'rating': 4.7, 'description': 'Легендарный ночной клуб с несколькими залами и лаунж-зоной'},
        {'place_id': '4', 'name': 'Территория', 'address': 'Цветной б-р, 2', 'rating': 4.8, 'description': 'Бар-ресторан с танцполом и караоке'},
        {'place_id': '5', 'name': 'Strelka Bar', 'address': 'Берсеневская наб., 14', 'rating': 4.9, 'description': 'Культовый бар на крыше с видом на Кремль'},
        {'place_id': '6', 'name': 'Propaganda', 'address': 'Большой Златоустинский пер., 1', 'rating': 4.6, 'description': 'Легендарный клуб для альтернативной тусовки'},
        {'place_id': '7', 'name': 'Belka Bar', 'address': 'ул. Тверская, 18/1', 'rating': 4.7, 'description': 'Бар на крыше отеля Ritz-Carlton'},
        {'place_id': '8', 'name': 'Mendeleev Bar', 'address': 'ул. Тверская, 18 к1', 'rating': 4.8, 'description': 'Стильный бар с коктейлями и видом на Тверскую'},
        {'place_id': '9', 'name': 'Soho Bar', 'address': 'Кутузовский пр-т, 2/1', 'rating': 4.6, 'description': 'Популярный бар для вечеринок и дней рождений'},
        {'place_id': '10', 'name': 'Wine & Crab', 'address': 'Никольская ул., 19', 'rating': 4.8, 'description': 'Ресторан-бар с винной картой и устрицами'},
        {'place_id': '11', 'name': 'True Cost Bar', 'address': 'Мясницкая ул., 44', 'rating': 4.7, 'description': 'Необычный бар с уникальными коктейлями'},
        {'place_id': '12', 'name': 'Синица', 'address': 'ул. Петровка, 23', 'rating': 4.6, 'description': 'Уютный бар с авторскими настойками'},
        {'place_id': '13', 'name': 'Cloud Bar', 'address': 'Кутузовский пр-т, 12', 'rating': 4.5, 'description': 'Лаунж-бар на 62 этаже Москва-Сити'},
        {'place_id': '14', 'name': 'Loft bar Love Story', 'address': 'Проспект Мира, 119', 'rating': 4.6, 'description': 'Караоке-бар для компаний'},
        {'place_id': '15', 'name': 'Rowan Bar', 'address': 'ул. Кузнецкий Мост, 7', 'rating': 4.7, 'description': 'Аккуратный бар с классическими коктейлями'},
        {'place_id': '16', 'name': 'Mishka Bar', 'address': 'Чистопрудный б-р, 23', 'rating': 4.6, 'description': 'Бар в стиле русский рэп'},
        {'place_id': '17', 'name': 'Bar Mishka', 'address': 'ул. Рождественка, 6/9', 'rating': 4.5, 'description': 'Популярный бар для молодежи'},
        {'place_id': '18', 'name': 'Raven Bar', 'address': 'Волхонка, 18с1', 'rating': 4.6, 'description': 'Бар с мрачной атмосферой и коктейлями'},
        {'place_id': '19', 'name': 'Блок', 'address': 'Тверской б-р, 2', 'rating': 4.5, 'description': 'Бар-ресторан с диджей-сетом'},
        {'place_id': '20', 'name': 'Times Bar', 'address': 'ул. Мясницкая, 15', 'rating': 4.7, 'description': 'Бар в стиле английских пабов'}
    ]
    
    existing_blacklist = session_state.get(user_id, {}).get('blacklist', [])
    
    session_state[user_id] = {
        'full_results': mock_results,
        'current_offset': 0,
        'blacklist': existing_blacklist
    }
    
    return format_recommendations(user_id)

def escape_html(text: str) -> str:
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;').replace("'", '&#39;')

def format_recommendations(user_id: str) -> str:
    state = session_state.get(user_id)
    if not state:
        return "Ошибка: нет активного поиска."
    
    full_results = state['full_results']
    blacklist = state.get('blacklist', [])
    offset = state.get('current_offset', 0)
    
    filtered_results = [p for p in full_results if str(p.get('place_id')) not in blacklist]
    
    if offset >= len(filtered_results):
        return "Вы посмотрели все подходящие места. Напишите \"новый поиск\", чтобы начать заново."
    
    batch = filtered_results[offset:offset + 5]
    state['current_offset'] = offset + len(batch)
    
    if not batch:
        return "Вы посмотрели все подходящие места. Напишите \"новый поиск\", чтобы начать заново."
    
    response = '<div class="recommendations-list">'
    for i, place in enumerate(batch, 1):
        name = escape_html(place.get('name', 'Место'))
        address = escape_html(place.get('address', 'Адрес не указан'))
        rating = place.get('rating', 'Нет оценки')
        description = place.get('description', '')
        place_id = str(place.get('place_id'))
        
        response += f'''
        <div class="place-card" data-place-id="{place_id}">
            <div class="place-info">
                <div class="place-name">{i}. {name}</div>
                <div class="place-address">📍 {address}</div>
                <div class="place-rating">⭐ Рейтинг: {rating}</div>
                <div class="place-desc">📝 {escape_html(description)}</div>
            </div>
            <div class="place-buttons">
                <button class="blacklist-btn" data-place-id="{place_id}" data-place-name="{name}">❌ Не нравится</button>
            </div>
        </div>
        '''
    response += '</div>'
    
    remaining = len(filtered_results) - state['current_offset']
    response += '<div class="control-buttons">'
    if remaining > 0:
        response += '<button class="more-btn" id="moreBtn">Ещё</button>'
    response += '<button class="new-search-btn" id="newSearchBtn">Новый поиск</button>'
    response += '</div>'
    
    return response

def handle_load_more(user_id: str) -> str:
    state = session_state.get(user_id)
    if not state:
        return "У вас нет активного поиска. Напишите, что хотите найти."
    
    full_results = state['full_results']
    blacklist = state.get('blacklist', [])
    offset = state.get('current_offset', 0)
    
    filtered_results = [p for p in full_results if str(p.get('place_id')) not in blacklist]
    
    if offset >= len(filtered_results):
        return "Вы посмотрели все доступные места. Напишите \"новый поиск\", чтобы начать заново."
    
    batch = filtered_results[offset:offset + 5]
    state['current_offset'] = offset + len(batch)
    
    if not batch:
        return "Вы посмотрели все доступные места. Напишите \"новый поиск\", чтобы начать заново."
    
    # Форматируем новые рекомендации с кнопками
    response = '<div class="recommendations-list">'
    for i, place in enumerate(batch, 1):
        name = escape_html(place.get('name', 'Место'))
        address = escape_html(place.get('address', 'Адрес не указан'))
        rating = place.get('rating', 'Нет оценки')
        description = place.get('description', '')
        place_id = str(place.get('place_id'))
        
        response += f'''
        <div class="place-card" data-place-id="{place_id}">
            <div class="place-info">
                <div class="place-name">{i}. {name}</div>
                <div class="place-address">📍 {address}</div>
                <div class="place-rating">⭐ Рейтинг: {rating}</div>
                <div class="place-desc">📝 {escape_html(description)}</div>
            </div>
            <div class="place-buttons">
                <button class="blacklist-btn" data-place-id="{place_id}" data-place-name="{name}">❌ Не нравится</button>
            </div>
        </div>
        '''
    response += '</div>'
    
    # Добавляем кнопки для новой порции
    remaining = len(filtered_results) - state['current_offset']
    response += '<div class="control-buttons">'
    if remaining > 0:
        response += '<button class="more-btn" id="moreBtn">Ещё</button>'
    response += '<button class="new-search-btn" id="newSearchBtn">Новый поиск</button>'
    response += '</div>'
    
    return response

def handle_blacklist(user_id: str, place_id: str) -> str:
    state = session_state.get(user_id)
    if not state:
        return "Нет активного поиска. Начните новый запрос."
    
    if 'blacklist' not in state:
        state['blacklist'] = []
    
    if place_id not in state['blacklist']:
        state['blacklist'].append(place_id)
    
    return format_recommendations(user_id)

def get_bot_response(message: str, area: Optional[Dict] = None, point: Optional[Dict] = None, user_id: str = "default_user") -> str:
    msg_lower = message.lower().strip()
    
    if any(word in msg_lower for word in ['привет', 'здравствуй', 'hello']):
        return "Привет!\n\nЯ ищу места только в Москве.\n\nЧто я могу:\n- Найти кафе, рестораны, парки, музеи\n- Учитываю ваши предпочтения\n- Работаю с областью на карте"
    
    if any(word in msg_lower for word in ['спасибо', 'благодарю']):
        return "Пожалуйста! Рад помочь. Что ещё вас интересует в Москве?"
    
    if msg_lower == "ещё" or msg_lower == "еще":
        state = session_state.get(user_id)
        if state and state.get('full_results') and state.get('current_offset', 0) < len(state['full_results']):
            return handle_load_more(user_id)
        else:
            return "У вас нет активного поиска. Напишите, что хотите найти, и выделите область на карте."
    
    if msg_lower in ["новый поиск", "найти другое", "сброс", "другое место"]:
        session_state.pop(user_id, None)
        return "Начинаем новый поиск!\n\n- Выделите область на карте\n- Напишите, что хотите найти"
    
    if any(word in msg_lower for word in ['весело', 'праздновать', 'диплом', 'выпуск', 'коктейли', 'друзьями', 'отпраздновать', 'коктейль', 'тусить', 'бар', 'выпить', 'танцы']):
        return get_mock_celebration_recommendations(user_id)
    
    if any(word in msg_lower for word in ['найди', 'ищу', 'где найти', 'поищи', 'покажи']):
        return "Отлично! Я могу найти для вас места.\n\nЧто нужно сделать:\n1. Выделите область на карте (прямоугольник)\n2. Или кликните на карту для выбора точки\n3. Напишите, что хотите найти (кафе, парк, музей и т.д.)"
    
    return "Я вас понял!\n\nНапишите, что хотите найти: кафе, ресторан, парк, музей, театр или что-то другое.\n\nНе забудьте выделить область на карте для точного поиска."

HTML_CONTENT = '''
<!DOCTYPE html>
<html>
<head>
    <title>Чат-бот - Поиск мест в Москве</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet.draw/1.0.4/leaflet.draw.css"/>
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet.draw/1.0.4/leaflet.draw.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }
        .app-container {
            width: 100%;
            max-width: 1400px;
            display: flex;
            gap: 20px;
            flex-wrap: wrap;
        }
        .map-container {
            flex: 2;
            min-width: 500px;
            background: #16213e;
            border-radius: 20px;
            overflow: hidden;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
        }
        .chat-container {
            flex: 1;
            min-width: 400px;
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            overflow: hidden;
            display: flex;
            flex-direction: column;
            height: 700px;
        }
        .chat-header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            text-align: center;
        }
        .chat-header h1 { font-size: 1.3rem; margin-bottom: 5px; }
        .chat-header p { font-size: 0.7rem; opacity: 0.9; }
        .chat-messages {
            flex: 1;
            overflow-y: auto;
            padding: 20px;
            background: #f5f5f5;
        }
        .message { margin-bottom: 15px; display: flex; flex-direction: column; }
        .message.user { align-items: flex-end; }
        .message.bot { align-items: flex-start; }
        .message-content {
            max-width: 90%;
            padding: 10px 16px;
            border-radius: 18px;
            font-size: 14px;
            line-height: 1.4;
            white-space: pre-wrap;
            word-wrap: break-word;
        }
        .message.user .message-content {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border-bottom-right-radius: 4px;
        }
        .message.bot .message-content {
            background: white;
            color: #333;
            border-bottom-left-radius: 4px;
            box-shadow: 0 1px 2px rgba(0,0,0,0.1);
        }
        .message-time {
            font-size: 10px;
            color: #999;
            margin-top: 4px;
            margin-left: 12px;
            margin-right: 12px;
        }
        .recommendations-list {
            display: flex;
            flex-direction: column;
            gap: 12px;
        }
        .place-card {
            background: #f9f9f9;
            border-radius: 12px;
            padding: 12px;
            border: 1px solid #e0e0e0;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 10px;
        }
        .place-info { flex: 1; }
        .place-name { font-weight: bold; font-size: 15px; margin-bottom: 5px; }
        .place-address { font-size: 12px; color: #666; }
        .place-rating { font-size: 12px; color: #f5a623; }
        .place-desc { font-size: 11px; color: #888; margin-top: 3px; }
        .place-buttons { display: flex; gap: 8px; }
        .blacklist-btn {
            background: #ff4757;
            color: white;
            border: none;
            border-radius: 20px;
            padding: 6px 12px;
            font-size: 11px;
            cursor: pointer;
        }
        .blacklist-btn:hover {
            background: #ff6b81;
        }
        .control-buttons {
            display: flex;
            gap: 10px;
            margin-top: 15px;
            justify-content: center;
        }
        .more-btn, .new-search-btn {
            padding: 8px 16px;
            border: none;
            border-radius: 25px;
            cursor: pointer;
            font-weight: bold;
            font-size: 13px;
        }
        .more-btn { background: #667eea; color: white; }
        .more-btn:hover { background: #764ba2; }
        .new-search-btn { background: #f5f5f5; border: 1px solid #ddd; color: #333; }
        .new-search-btn:hover { background: #e0e0e0; }
        .chat-input-container {
            padding: 16px 20px;
            background: white;
            border-top: 1px solid #e0e0e0;
            display: flex;
            gap: 10px;
        }
        .chat-input {
            flex: 1;
            padding: 12px 16px;
            border: 1px solid #e0e0e0;
            border-radius: 25px;
            outline: none;
            font-size: 14px;
        }
        .chat-input:focus { border-color: #667eea; }
        .send-btn {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 25px;
            cursor: pointer;
            font-weight: bold;
        }
        .send-btn:hover { opacity: 0.9; }
        .typing {
            display: none;
            padding: 10px 20px;
            background: white;
            border-radius: 18px;
            width: fit-content;
            margin: 10px 20px;
        }
        .typing span {
            display: inline-block;
            width: 8px;
            height: 8px;
            background: #999;
            border-radius: 50%;
            margin: 0 2px;
            animation: typing 1.4s infinite;
        }
        .typing span:nth-child(2) { animation-delay: 0.2s; }
        .typing span:nth-child(3) { animation-delay: 0.4s; }
        @keyframes typing {
            0%, 60%, 100% { transform: translateY(0); }
            30% { transform: translateY(-10px); }
        }
        .map-controls {
            padding: 10px;
            background: #f9f9f9;
            border-bottom: 1px solid #e0e0e0;
            text-align: center;
            display: flex;
            justify-content: center;
            gap: 10px;
            flex-wrap: wrap;
        }
        .map-controls button {
            background: #667eea;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 20px;
            cursor: pointer;
        }
        .map-controls button:hover { background: #764ba2; }
        .info-text {
            padding: 10px;
            text-align: center;
            color: #666;
            font-size: 12px;
            background: #f9f9f9;
            border-top: 1px solid #e0e0e0;
        }
        .moscow-badge {
            background: #ff4757;
            color: white;
            padding: 5px 10px;
            border-radius: 20px;
            font-size: 12px;
        }
        .metro-marker {
            background: none;
            border: none;
            cursor: pointer;
        }
    </style>
</head>
<body>
<div class="app-container">
    <div class="map-container">
        <div class="map-controls">
            <span class="moscow-badge">Москва</span>
            <button onclick="resetMap()">Центр Москвы</button>
            <button onclick="clearArea()">Очистить область</button>
            <button onclick="searchInArea()">Искать в выделенной области</button>
        </div>
        <div id="map" style="height: 550px; width: 100%;"></div>
        <div class="info-text">
            Используйте инструменты в правом верхнем углу карты:<br>
            <strong>Прямоугольник</strong> — для выделения области | <strong>Редактировать/Удалить</strong> — кликните на фигуру<br>
            На карте отмечены станции метро Москвы
        </div>
    </div>
    
    <div class="chat-container">
        <div class="chat-header">
            <h1>Место под настроение</h1>
            <p>Поиск только в Москве | Выдели область на карте</p>
        </div>
        <div class="chat-messages" id="messages">
            <div class="message bot">
                <div class="message-content">Привет! Я помогу найти место под настроение в Москве!<br><br>Что ты можешь делать:<br>• Нарисовать область на карте<br>• Кликнуть на карту — выберу точку<br>• На карте отмечены станции метро<br>• Написать, что хочешь найти<br><br>Попробуй написать: "Хочу отпраздновать с друзьями, нужен бар с коктейлями"</div>
            </div>
        </div>
        <div class="typing" id="typing"><span></span><span></span><span></span></div>
        <div class="chat-input-container">
            <input type="text" class="chat-input" id="chatInput" placeholder="Напиши сообщение..." onkeypress="if(event.key===13) sendMessage()">
            <button class="send-btn" onclick="sendMessage()">→</button>
        </div>
    </div>
</div>

<script>
    let map;
    let drawnItems;
    let selectedCoords = null;
    let selectedArea = null;
    let currentUserId = 'user_' + Date.now();
    
    const MOSCOW_CENTER = [55.751244, 37.618423];
    
    const metroStations = [
    { name: 'Новокосино', line: 'Калининская', lat: 55.745113, lng: 37.864052, color: '#FCD116' },
    { name: 'Новогиреево', line: 'Калининская', lat: 55.752237, lng: 37.814587, color: '#FCD116' },
    { name: 'Перово', line: 'Калининская', lat: 55.75098, lng: 37.78422, color: '#FCD116' },
    { name: 'Шоссе Энтузиастов', line: 'Калининская', lat: 55.75809, lng: 37.751703, color: '#FCD116' },
    { name: 'Авиамоторная', line: 'Калининская', lat: 55.751933, lng: 37.717444, color: '#FCD116' },
    { name: 'Площадь Ильича', line: 'Калининская', lat: 55.747115, lng: 37.680726, color: '#FCD116' },
    { name: 'Марксистская', line: 'Калининская', lat: 55.740746, lng: 37.65604, color: '#FCD116' },
    { name: 'Третьяковская', line: 'Калининская', lat: 55.741125, lng: 37.626142, color: '#FCD116' },
    { name: 'Ховрино', line: 'Замоскворецкая', lat: 55.8777, lng: 37.4877, color: '#3A7E3A' },
    { name: 'Беломорская', line: 'Замоскворецкая', lat: 55.8651, lng: 37.4764, color: '#3A7E3A' },
    { name: 'Речной вокзал', line: 'Замоскворецкая', lat: 55.854152, lng: 37.476728, color: '#3A7E3A' },
    { name: 'Водный стадион', line: 'Замоскворецкая', lat: 55.838978, lng: 37.487515, color: '#3A7E3A' },
    { name: 'Войковская', line: 'Замоскворецкая', lat: 55.818923, lng: 37.497791, color: '#3A7E3A' },
    { name: 'Сокол', line: 'Замоскворецкая', lat: 55.805564, lng: 37.515245, color: '#3A7E3A' },
    { name: 'Аэропорт', line: 'Замоскворецкая', lat: 55.800441, lng: 37.530477, color: '#3A7E3A' },
    { name: 'Динамо', line: 'Замоскворецкая', lat: 55.789704, lng: 37.558212, color: '#3A7E3A' },
    { name: 'Белорусская', line: 'Замоскворецкая', lat: 55.777439, lng: 37.582107, color: '#3A7E3A' },
    { name: 'Маяковская', line: 'Замоскворецкая', lat: 55.769808, lng: 37.596192, color: '#3A7E3A' },
    { name: 'Тверская', line: 'Замоскворецкая', lat: 55.765343, lng: 37.603918, color: '#3A7E3A' },
    { name: 'Театральная', line: 'Замоскворецкая', lat: 55.758808, lng: 37.61768, color: '#3A7E3A' },
    { name: 'Новокузнецкая', line: 'Замоскворецкая', lat: 55.742391, lng: 37.62928, color: '#3A7E3A' },
    { name: 'Павелецкая', line: 'Замоскворецкая', lat: 55.729741, lng: 37.638693, color: '#3A7E3A' },
    { name: 'Автозаводская', line: 'Замоскворецкая', lat: 55.706634, lng: 37.657008, color: '#3A7E3A' },
    { name: 'Технопарк', line: 'Замоскворецкая', lat: 55.695, lng: 37.664167, color: '#3A7E3A' },
    { name: 'Коломенская', line: 'Замоскворецкая', lat: 55.677423, lng: 37.663719, color: '#3A7E3A' },
    { name: 'Каширская', line: 'Замоскворецкая', lat: 55.655745, lng: 37.649683, color: '#3A7E3A' },
    { name: 'Кантемировская', line: 'Замоскворецкая', lat: 55.636107, lng: 37.656218, color: '#3A7E3A' },
    { name: 'Царицыно', line: 'Замоскворецкая', lat: 55.620982, lng: 37.669612, color: '#3A7E3A' },
    { name: 'Орехово', line: 'Замоскворецкая', lat: 55.61269, lng: 37.695214, color: '#3A7E3A' },
    { name: 'Домодедовская', line: 'Замоскворецкая', lat: 55.610131, lng: 37.717111, color: '#3A7E3A' },
    { name: 'Красногвардейская', line: 'Замоскворецкая', lat: 55.614075, lng: 37.742697, color: '#3A7E3A' },
    { name: 'Алма-Атинская', line: 'Замоскворецкая', lat: 55.63349, lng: 37.765678, color: '#3A7E3A' },
    { name: 'Медведково', line: 'Калужско-Рижская', lat: 55.888103, lng: 37.661562, color: '#FCA01C' },
    { name: 'Бабушкинская', line: 'Калужско-Рижская', lat: 55.870641, lng: 37.664341, color: '#FCA01C' },
    { name: 'Свиблово', line: 'Калужско-Рижская', lat: 55.855558, lng: 37.653379, color: '#FCA01C' },
    { name: 'Ботанический сад', line: 'Калужско-Рижская', lat: 55.844597, lng: 37.637811, color: '#FCA01C' },
    { name: 'ВДНХ', line: 'Калужско-Рижская', lat: 55.819626, lng: 37.640751, color: '#FCA01C' },
    { name: 'Алексеевская', line: 'Калужско-Рижская', lat: 55.807794, lng: 37.638699, color: '#FCA01C' },
    { name: 'Рижская', line: 'Калужско-Рижская', lat: 55.792494, lng: 37.636114, color: '#FCA01C' },
    { name: 'Проспект Мира', line: 'Калужско-Рижская', lat: 55.781827, lng: 37.633199, color: '#FCA01C' },
    { name: 'Сухаревская', line: 'Калужско-Рижская', lat: 55.772315, lng: 37.63285, color: '#FCA01C' },
    { name: 'Тургеневская', line: 'Калужско-Рижская', lat: 55.765371, lng: 37.636732, color: '#FCA01C' },
    { name: 'Китай-город', line: 'Калужско-Рижская', lat: 55.756498, lng: 37.631326, color: '#FCA01C' },
    { name: 'Третьяковская', line: 'Калужско-Рижская', lat: 55.74073, lng: 37.625624, color: '#FCA01C' },
    { name: 'Октябрьская', line: 'Калужско-Рижская', lat: 55.731232, lng: 37.612851, color: '#FCA01C' },
    { name: 'Шаболовская', line: 'Калужско-Рижская', lat: 55.718828, lng: 37.607892, color: '#FCA01C' },
    { name: 'Ленинский проспект', line: 'Калужско-Рижская', lat: 55.70678, lng: 37.58499, color: '#FCA01C' },
    { name: 'Академическая', line: 'Калужско-Рижская', lat: 55.687147, lng: 37.5723, color: '#FCA01C' },
    { name: 'Профсоюзная', line: 'Калужско-Рижская', lat: 55.677671, lng: 37.562595, color: '#FCA01C' },
    { name: 'Новые Черемушки', line: 'Калужско-Рижская', lat: 55.670077, lng: 37.554493, color: '#FCA01C' },
    { name: 'Калужская', line: 'Калужско-Рижская', lat: 55.656682, lng: 37.540075, color: '#FCA01C' },
    { name: 'Беляево', line: 'Калужско-Рижская', lat: 55.642357, lng: 37.526115, color: '#FCA01C' },
    { name: 'Коньково', line: 'Калужско-Рижская', lat: 55.631857, lng: 37.519156, color: '#FCA01C' },
    { name: 'Теплый Стан', line: 'Калужско-Рижская', lat: 55.61873, lng: 37.505912, color: '#FCA01C' },
    { name: 'Ясенево', line: 'Калужско-Рижская', lat: 55.606182, lng: 37.5334, color: '#FCA01C' },
    { name: 'Новоясеневская', line: 'Калужско-Рижская', lat: 55.601947, lng: 37.553017, color: '#FCA01C' },
    { name: 'Бульвар Рокоссовского', line: 'Сокольническая', lat: 55.814916, lng: 37.732227, color: '#E31E24' },
    { name: 'Черкизовская', line: 'Сокольническая', lat: 55.802787, lng: 37.744863, color: '#E31E24' },
    { name: 'Преображенская площадь', line: 'Сокольническая', lat: 55.796322, lng: 37.713582, color: '#E31E24' },
    { name: 'Сокольники', line: 'Сокольническая', lat: 55.789282, lng: 37.679895, color: '#E31E24' },
    { name: 'Красносельская', line: 'Сокольническая', lat: 55.780014, lng: 37.666097, color: '#E31E24' },
    { name: 'Комсомольская', line: 'Сокольническая', lat: 55.774072, lng: 37.654565, color: '#E31E24' },
    { name: 'Красные ворота', line: 'Сокольническая', lat: 55.768307, lng: 37.6478, color: '#E31E24' },
    { name: 'Чистые пруды', line: 'Сокольническая', lat: 55.76499, lng: 37.638293, color: '#E31E24' },
    { name: 'Лубянка', line: 'Сокольническая', lat: 55.759889, lng: 37.625336, color: '#E31E24' },
    { name: 'Охотный ряд', line: 'Сокольническая', lat: 55.757228, lng: 37.615078, color: '#E31E24' },
    { name: 'Библиотека им.Ленина', line: 'Сокольническая', lat: 55.752123, lng: 37.610388, color: '#E31E24' },
    { name: 'Кропоткинская', line: 'Сокольническая', lat: 55.745297, lng: 37.604217, color: '#E31E24' },
    { name: 'Парк культуры', line: 'Сокольническая', lat: 55.736163, lng: 37.595027, color: '#E31E24' },
    { name: 'Фрунзенская', line: 'Сокольническая', lat: 55.727462, lng: 37.58022, color: '#E31E24' },
    { name: 'Спортивная', line: 'Сокольническая', lat: 55.722388, lng: 37.562041, color: '#E31E24' },
    { name: 'Воробьевы горы', line: 'Сокольническая', lat: 55.709169, lng: 37.557293, color: '#E31E24' },
    { name: 'Университет', line: 'Сокольническая', lat: 55.69329, lng: 37.534511, color: '#E31E24' },
    { name: 'Проспект Вернадского', line: 'Сокольническая', lat: 55.676549, lng: 37.504584, color: '#E31E24' },
    { name: 'Юго-Западная', line: 'Сокольническая', lat: 55.663146, lng: 37.482852, color: '#E31E24' },
    { name: 'Тропарево', line: 'Сокольническая', lat: 55.6459, lng: 37.4725, color: '#E31E24' },
    { name: 'Румянцево', line: 'Сокольническая', lat: 55.633, lng: 37.4419, color: '#E31E24' },
    { name: 'Саларьево', line: 'Сокольническая', lat: 55.6227, lng: 37.424, color: '#E31E24' },
    { name: 'Филатов луг', line: 'Сокольническая', lat: 55.5997, lng: 37.4075, color: '#E31E24' },
    { name: 'Прокшино', line: 'Сокольническая', lat: 55.5813, lng: 37.4425, color: '#E31E24' },
    { name: 'Ольховая', line: 'Сокольническая', lat: 55.5692, lng: 37.4589, color: '#E31E24' },
    { name: 'Новомосковская (Коммунарка)', line: 'Сокольническая', lat: 55.559765, lng: 37.468716, color: '#E31E24' },
    { name: 'Потапово', line: 'Сокольническая', lat: 55.552538, lng: 37.490978, color: '#E31E24' },
    { name: 'Щелковская', line: 'Арбатско-Покровская', lat: 55.809962, lng: 37.798261, color: '#2958A0' },
    { name: 'Первомайская', line: 'Арбатско-Покровская', lat: 55.794376, lng: 37.799364, color: '#2958A0' },
    { name: 'Измайловская', line: 'Арбатско-Покровская', lat: 55.787713, lng: 37.779896, color: '#2958A0' },
    { name: 'Партизанская', line: 'Арбатско-Покровская', lat: 55.788401, lng: 37.74882, color: '#2958A0' },
    { name: 'Семеновская', line: 'Арбатско-Покровская', lat: 55.783096, lng: 37.719289, color: '#2958A0' },
    { name: 'Электрозаводская', line: 'Арбатско-Покровская', lat: 55.782057, lng: 37.7053, color: '#2958A0' },
    { name: 'Бауманская', line: 'Арбатско-Покровская', lat: 55.772405, lng: 37.67904, color: '#2958A0' },
    { name: 'Курская', line: 'Арбатско-Покровская', lat: 55.758564, lng: 37.659039, color: '#2958A0' },
    { name: 'Площадь Революции', line: 'Арбатско-Покровская', lat: 55.756741, lng: 37.62236, color: '#2958A0' },
    { name: 'Арбатская', line: 'Арбатско-Покровская', lat: 55.752312, lng: 37.60349, color: '#2958A0' },
    { name: 'Смоленская', line: 'Арбатско-Покровская', lat: 55.747713, lng: 37.583802, color: '#2958A0' },
    { name: 'Киевская', line: 'Арбатско-Покровская', lat: 55.743117, lng: 37.564132, color: '#2958A0' },
    { name: 'Парк Победы', line: 'Арбатско-Покровская', lat: 55.735679, lng: 37.516865, color: '#2958A0' },
    { name: 'Славянский бульвар', line: 'Арбатско-Покровская', lat: 55.729542, lng: 37.470973, color: '#2958A0' },
    { name: 'Кунцевская', line: 'Арбатско-Покровская', lat: 55.730673, lng: 37.446522, color: '#2958A0' },
    { name: 'Молодежная', line: 'Арбатско-Покровская', lat: 55.741375, lng: 37.415627, color: '#2958A0' },
    { name: 'Крылатское', line: 'Арбатско-Покровская', lat: 55.756842, lng: 37.408139, color: '#2958A0' },
    { name: 'Строгино', line: 'Арбатско-Покровская', lat: 55.803831, lng: 37.402405, color: '#2958A0' },
    { name: 'Мякинино', line: 'Арбатско-Покровская', lat: 55.823342, lng: 37.385214, color: '#2958A0' },
    { name: 'Волоколамская', line: 'Арбатско-Покровская', lat: 55.835154, lng: 37.382453, color: '#2958A0' },
    { name: 'Митино', line: 'Арбатско-Покровская', lat: 55.846098, lng: 37.36122, color: '#2958A0' },
    { name: 'Пятницкое шоссе', line: 'Арбатско-Покровская', lat: 55.853634, lng: 37.353108, color: '#2958A0' },
    { name: 'Кунцевская', line: 'Филевская', lat: 55.730815, lng: 37.446754, color: '#00BFFF' },
    { name: 'Пионерская', line: 'Филевская', lat: 55.736027, lng: 37.466728, color: '#00BFFF' },
    { name: 'Филевский парк', line: 'Филевская', lat: 55.739665, lng: 37.483902, color: '#00BFFF' },
    { name: 'Багратионовская', line: 'Филевская', lat: 55.743544, lng: 37.497042, color: '#00BFFF' },
    { name: 'Фили', line: 'Филевская', lat: 55.746763, lng: 37.514035, color: '#00BFFF' },
    { name: 'Кутузовская', line: 'Филевская', lat: 55.740544, lng: 37.5341, color: '#00BFFF' },
    { name: 'Студенческая', line: 'Филевская', lat: 55.738761, lng: 37.54842, color: '#00BFFF' },
    { name: 'Киевская', line: 'Филевская', lat: 55.743168, lng: 37.565425, color: '#00BFFF' },
    { name: 'Смоленская', line: 'Филевская', lat: 55.749083, lng: 37.582173, color: '#00BFFF' },
    { name: 'Арбатская', line: 'Филевская', lat: 55.752122, lng: 37.601553, color: '#00BFFF' },
    { name: 'Александровский сад', line: 'Филевская', lat: 55.752255, lng: 37.608775, color: '#00BFFF' },
    { name: 'Деловой центр (Выставочная)', line: 'Филевская', lat: 55.750243, lng: 37.542641, color: '#00BFFF' },
    { name: 'Москва-Сити', line: 'Филевская', lat: 55.748056, lng: 37.532778, color: '#00BFFF' },
    { name: 'Алтуфьево', line: 'Серпуховско-Тимирязевская', lat: 55.899034, lng: 37.586473, color: '#8C8C8C' },
    { name: 'Бибирево', line: 'Серпуховско-Тимирязевская', lat: 55.883868, lng: 37.603011, color: '#8C8C8C' },
    { name: 'Отрадное', line: 'Серпуховско-Тимирязевская', lat: 55.864273, lng: 37.605066, color: '#8C8C8C' },
    { name: 'Владыкино', line: 'Серпуховско-Тимирязевская', lat: 55.848236, lng: 37.590451, color: '#8C8C8C' },
    { name: 'Петровско-Разумовская', line: 'Серпуховско-Тимирязевская', lat: 55.836565, lng: 37.575512, color: '#8C8C8C' },
    { name: 'Тимирязевская', line: 'Серпуховско-Тимирязевская', lat: 55.81866, lng: 37.574498, color: '#8C8C8C' },
    { name: 'Дмитровская', line: 'Серпуховско-Тимирязевская', lat: 55.808056, lng: 37.581734, color: '#8C8C8C' },
    { name: 'Савёловская', line: 'Серпуховско-Тимирязевская', lat: 55.794054, lng: 37.587163, color: '#8C8C8C' },
    { name: 'Менделеевская', line: 'Серпуховско-Тимирязевская', lat: 55.781999, lng: 37.599141, color: '#8C8C8C' },
    { name: 'Цветной бульвар', line: 'Серпуховско-Тимирязевская', lat: 55.771653, lng: 37.620466, color: '#8C8C8C' },
    { name: 'Чеховская', line: 'Серпуховско-Тимирязевская', lat: 55.765747, lng: 37.608493, color: '#8C8C8C' },
    { name: 'Боровицкая', line: 'Серпуховско-Тимирязевская', lat: 55.750399, lng: 37.60934, color: '#8C8C8C' },
    { name: 'Полянка', line: 'Серпуховско-Тимирязевская', lat: 55.736795, lng: 37.618594, color: '#8C8C8C' },
    { name: 'Серпуховская', line: 'Серпуховско-Тимирязевская', lat: 55.726548, lng: 37.624792, color: '#8C8C8C' },
    { name: 'Тульская', line: 'Серпуховско-Тимирязевская', lat: 55.70961, lng: 37.622569, color: '#8C8C8C' },
    { name: 'Нагатинская', line: 'Серпуховско-Тимирязевская', lat: 55.682099, lng: 37.620917, color: '#8C8C8C' },
    { name: 'Нагорная', line: 'Серпуховско-Тимирязевская', lat: 55.672962, lng: 37.610397, color: '#8C8C8C' },
    { name: 'Нахимовский проспект', line: 'Серпуховско-Тимирязевская', lat: 55.662379, lng: 37.605274, color: '#8C8C8C' },
    { name: 'Севастопольская', line: 'Серпуховско-Тимирязевская', lat: 55.651451, lng: 37.59809, color: '#8C8C8C' },
    { name: 'Чертановская', line: 'Серпуховско-Тимирязевская', lat: 55.640538, lng: 37.606065, color: '#8C8C8C' },
    { name: 'Южная', line: 'Серпуховско-Тимирязевская', lat: 55.622436, lng: 37.609047, color: '#8C8C8C' },
    { name: 'Пражская', line: 'Серпуховско-Тимирязевская', lat: 55.610962, lng: 37.602386, color: '#8C8C8C' },
    { name: 'Улица Академика Янгеля', line: 'Серпуховско-Тимирязевская', lat: 55.596753, lng: 37.601498, color: '#8C8C8C' },
    { name: 'Аннино', line: 'Серпуховско-Тимирязевская', lat: 55.583477, lng: 37.596999, color: '#8C8C8C' },
    { name: 'Бульвар Дмитрия Донского', line: 'Серпуховско-Тимирязевская', lat: 55.568201, lng: 37.576856, color: '#8C8C8C' },
    { name: 'Планерная', line: 'Таганско-Краснопресненская', lat: 55.859676, lng: 37.436808, color: '#8C4799' },
    { name: 'Сходненская', line: 'Таганско-Краснопресненская', lat: 55.84926, lng: 37.44076, color: '#8C4799' },
    { name: 'Тушинская', line: 'Таганско-Краснопресненская', lat: 55.825479, lng: 37.437024, color: '#8C4799' },
    { name: 'Спартак', line: 'Таганско-Краснопресненская', lat: 55.8182, lng: 37.4352, color: '#8C4799' },
    { name: 'Щукинская', line: 'Таганско-Краснопресненская', lat: 55.8094, lng: 37.463241, color: '#8C4799' },
    { name: 'Октябрьское поле', line: 'Таганско-Краснопресненская', lat: 55.793581, lng: 37.493317, color: '#8C4799' },
    { name: 'Полежаевская', line: 'Таганско-Краснопресненская', lat: 55.777201, lng: 37.517895, color: '#8C4799' },
    { name: 'Беговая', line: 'Таганско-Краснопресненская', lat: 55.773505, lng: 37.545518, color: '#8C4799' },
    { name: 'Улица 1905 года', line: 'Таганско-Краснопресненская', lat: 55.763944, lng: 37.562271, color: '#8C4799' },
    { name: 'Баррикадная', line: 'Таганско-Краснопресненская', lat: 55.760793, lng: 37.581242, color: '#8C4799' },
    { name: 'Пушкинская', line: 'Таганско-Краснопресненская', lat: 55.765607, lng: 37.604356, color: '#8C4799' },
    { name: 'Кузнецкий мост', line: 'Таганско-Краснопресненская', lat: 55.761498, lng: 37.624423, color: '#8C4799' },
    { name: 'Китай-город', line: 'Таганско-Краснопресненская', lat: 55.75436, lng: 37.633877, color: '#8C4799' },
    { name: 'Таганская', line: 'Таганско-Краснопресненская', lat: 55.739502, lng: 37.653605, color: '#8C4799' },
    { name: 'Пролетарская', line: 'Таганско-Краснопресненская', lat: 55.731546, lng: 37.666917, color: '#8C4799' },
    { name: 'Волгоградский проспект', line: 'Таганско-Краснопресненская', lat: 55.725546, lng: 37.685197, color: '#8C4799' },
    { name: 'Текстильщики', line: 'Таганско-Краснопресненская', lat: 55.709211, lng: 37.732117, color: '#8C4799' },
    { name: 'Кузьминки', line: 'Таганско-Краснопресненская', lat: 55.705493, lng: 37.763295, color: '#8C4799' },
    { name: 'Рязанский проспект', line: 'Таганско-Краснопресненская', lat: 55.716139, lng: 37.792694, color: '#8C4799' },
    { name: 'Выхино', line: 'Таганско-Краснопресненская', lat: 55.715983, lng: 37.816788, color: '#8C4799' },
    { name: 'Лермонтовский проспект', line: 'Таганско-Краснопресненская', lat: 55.702036, lng: 37.851044, color: '#8C4799' },
    { name: 'Жулебино', line: 'Таганско-Краснопресненская', lat: 55.684722, lng: 37.855833, color: '#8C4799' },
    { name: 'Котельники', line: 'Таганско-Краснопресненская', lat: 55.6743, lng: 37.8582, color: '#8C4799' },
    { name: 'Новослободская', line: 'Кольцевая', lat: 55.779606, lng: 37.601252, color: '#A43E2B' },
    { name: 'Проспект Мира', line: 'Кольцевая', lat: 55.779584, lng: 37.633646, color: '#A43E2B' },
    { name: 'Комсомольская', line: 'Кольцевая', lat: 55.775672, lng: 37.654772, color: '#A43E2B' },
    { name: 'Курская', line: 'Кольцевая', lat: 55.758631, lng: 37.661059, color: '#A43E2B' },
    { name: 'Таганская', line: 'Кольцевая', lat: 55.742396, lng: 37.653334, color: '#A43E2B' },
    { name: 'Павелецкая', line: 'Кольцевая', lat: 55.731414, lng: 37.636294, color: '#A43E2B' },
    { name: 'Добрынинская', line: 'Кольцевая', lat: 55.728994, lng: 37.622533, color: '#A43E2B' },
    { name: 'Октябрьская', line: 'Кольцевая', lat: 55.729264, lng: 37.611049, color: '#A43E2B' },
    { name: 'Парк культуры', line: 'Кольцевая', lat: 55.735221, lng: 37.593095, color: '#A43E2B' },
    { name: 'Киевская', line: 'Кольцевая', lat: 55.74361, lng: 37.56735, color: '#A43E2B' },
    { name: 'Краснопресненская', line: 'Кольцевая', lat: 55.760378, lng: 37.577114, color: '#A43E2B' },
    { name: 'Белорусская', line: 'Кольцевая', lat: 55.775179, lng: 37.582303, color: '#A43E2B' },
    { name: 'Физтех', line: 'Люблинско-Дмитровская', lat: 55.921389, lng: 37.546389, color: '#A1C935' },
    { name: 'Лианозово', line: 'Люблинско-Дмитровская', lat: 55.931111, lng: 37.543611, color: '#A1C935' },
    { name: 'Яхромская', line: 'Люблинско-Дмитровская', lat: 55.8775, lng: 37.545833, color: '#A1C935' },
    { name: 'Селигерская', line: 'Люблинско-Дмитровская', lat: 55.86483, lng: 37.55005, color: '#A1C935' },
    { name: 'Верхние Лихоборы', line: 'Люблинско-Дмитровская', lat: 55.85566, lng: 37.56282, color: '#A1C935' },
    { name: 'Окружная', line: 'Люблинско-Дмитровская', lat: 55.848889, lng: 37.571111, color: '#A1C935' },
    { name: 'Петровско-Разумовская', line: 'Люблинско-Дмитровская', lat: 55.836667, lng: 37.575556, color: '#A1C935' },
    { name: 'Фонвизинская', line: 'Люблинско-Дмитровская', lat: 55.822778, lng: 37.588056, color: '#A1C935' },
    { name: 'Бутырская ', line: 'Люблинско-Дмитровская', lat: 55.813333, lng: 37.602778, color: '#A1C935' },
    { name: 'Марьина Роща', line: 'Люблинско-Дмитровская', lat: 55.793723, lng: 37.61618, color: '#A1C935' },
    { name: 'Достоевская', line: 'Люблинско-Дмитровская', lat: 55.781667, lng: 37.613889, color: '#A1C935' },
    { name: 'Трубная', line: 'Люблинско-Дмитровская', lat: 55.76771, lng: 37.621926, color: '#A1C935' },
    { name: 'Сретенский бульвар', line: 'Люблинско-Дмитровская', lat: 55.766106, lng: 37.635688, color: '#A1C935' },
    { name: 'Чкаловская', line: 'Люблинско-Дмитровская', lat: 55.755951, lng: 37.659293, color: '#A1C935' },
    { name: 'Римская', line: 'Люблинско-Дмитровская', lat: 55.747027, lng: 37.679996, color: '#A1C935' },
    { name: 'Крестьянская застава', line: 'Люблинско-Дмитровская', lat: 55.732278, lng: 37.665325, color: '#A1C935' },
    { name: 'Дубровка', line: 'Люблинско-Дмитровская', lat: 55.71807, lng: 37.676259, color: '#A1C935' },
    { name: 'Кожуховская', line: 'Люблинско-Дмитровская', lat: 55.706156, lng: 37.68544, color: '#A1C935' },
    { name: 'Печатники', line: 'Люблинско-Дмитровская', lat: 55.692921, lng: 37.728338, color: '#A1C935' },
    { name: 'Волжская', line: 'Люблинско-Дмитровская', lat: 55.690446, lng: 37.754314, color: '#A1C935' },
    { name: 'Люблино', line: 'Люблинско-Дмитровская', lat: 55.676596, lng: 37.761639, color: '#A1C935' },
    { name: 'Братиславская', line: 'Люблинско-Дмитровская', lat: 55.658817, lng: 37.748415, color: '#A1C935' },
    { name: 'Марьино', line: 'Люблинско-Дмитровская', lat: 55.649158, lng: 37.743844, color: '#A1C935' },
    { name: 'Борисово', line: 'Люблинско-Дмитровская', lat: 55.6325, lng: 37.743333, color: '#A1C935' },
    { name: 'Шипиловская', line: 'Люблинско-Дмитровская', lat: 55.621667, lng: 37.743611, color: '#A1C935' },
    { name: 'Зябликово', line: 'Люблинско-Дмитровская', lat: 55.611944, lng: 37.745278, color: '#A1C935' },
    { name: 'Каширская', line: 'Каховская', lat: 55.654327, lng: 37.647705, color: '#808080' },
    { name: 'Варшавская', line: 'Каховская', lat: 55.653294, lng: 37.619522, color: '#808080' },
    { name: 'Каховская', line: 'Каховская', lat: 55.652923, lng: 37.596573, color: '#808080' },
    { name: 'Бунинская аллея', line: 'Бутовская', lat: 55.537977, lng: 37.515899, color: '#808080' },
    { name: 'Улица Горчакова', line: 'Бутовская', lat: 55.542281, lng: 37.532063, color: '#808080' },
    { name: 'Бульвар Адмирала Ушакова', line: 'Бутовская', lat: 55.545207, lng: 37.542329, color: '#808080' },
    { name: 'Улица Скобелевская', line: 'Бутовская', lat: 55.548103, lng: 37.552721, color: '#808080' },
    { name: 'Улица Старокачаловская', line: 'Бутовская', lat: 55.569194, lng: 37.576074, color: '#808080' },
    { name: 'Лесопарковая', line: 'Бутовская', lat: 55.581656, lng: 37.577816, color: '#808080' },
    { name: 'Битцевский Парк', line: 'Бутовская', lat: 55.600066, lng: 37.556058, color: '#808080' },
    { name: 'Деловой центр', line: 'Солнцевская', lat: 55.7491, lng: 37.5395, color: '#FCD116' },
    { name: 'Пыхтино', line: 'Солнцевская', lat: 55.625, lng: 37.298056, color: '#FCD116' },
    { name: 'Парк Победы', line: 'Солнцевская', lat: 55.736478, lng: 37.514401, color: '#FCD116' },
    { name: 'Минская', line: 'Солнцевская', lat: 55.7232, lng: 37.5038, color: '#FCD116' },
    { name: 'Ломоносовский проспект', line: 'Солнцевская', lat: 55.7055, lng: 37.5225, color: '#FCD116' },
    { name: 'Раменки', line: 'Солнцевская', lat: 55.6961, lng: 37.505, color: '#FCD116' },
    { name: 'Мичуринский проспект', line: 'Солнцевская', lat: 55.6888, lng: 37.485, color: '#FCD116' },
    { name: 'Озёрная', line: 'Солнцевская', lat: 55.6698, lng: 37.4495, color: '#FCD116' },
    { name: 'Говорово', line: 'Солнцевская', lat: 55.6588, lng: 37.4174, color: '#FCD116' },
    { name: 'Солнцево', line: 'Солнцевская', lat: 55.649, lng: 37.3911, color: '#FCD116' },
    { name: 'Боровское шоссе', line: 'Солнцевская', lat: 55.647, lng: 37.3701, color: '#FCD116' },
    { name: 'Новопеределкино', line: 'Солнцевская', lat: 55.6385, lng: 37.3544, color: '#FCD116' },
    { name: 'Рассказовка', line: 'Солнцевская', lat: 55.6324, lng: 37.3328, color: '#FCD116' },
    { name: 'Аэропорт Внуково', line: 'Солнцевская', lat: 55.606667, lng: 37.288333, color: '#FCD116' },
    { name: 'Окружная', line: 'МЦК', lat: 55.848889, lng: 37.571111, color: '#808080' },
    { name: 'Владыкино', line: 'МЦК', lat: 55.847222, lng: 37.591944, color: '#808080' },
    { name: 'Ботанический сад', line: 'МЦК', lat: 55.845556, lng: 37.640278, color: '#808080' },
    { name: 'Ростокино', line: 'МЦК', lat: 55.839444, lng: 37.667778, color: '#808080' },
    { name: 'Белокаменная', line: 'МЦК', lat: 55.83, lng: 37.700556, color: '#808080' },
    { name: 'Бульвар Рокоссовского', line: 'МЦК', lat: 55.817222, lng: 37.736944, color: '#808080' },
    { name: 'Локомотив', line: 'МЦК', lat: 55.803219, lng: 37.745742, color: '#808080' },
    { name: 'Измайлово', line: 'МЦК', lat: 55.788611, lng: 37.742778, color: '#808080' },
    { name: 'Соколиная Гора', line: 'МЦК', lat: 55.77, lng: 37.745278, color: '#808080' },
    { name: 'Шоссе Энтузиастов', line: 'МЦК', lat: 55.758633, lng: 37.748477, color: '#808080' },
    { name: 'Андроновка', line: 'МЦК', lat: 55.741111, lng: 37.734444, color: '#808080' },
    { name: 'Нижегородская', line: 'МЦК', lat: 55.732222, lng: 37.72825, color: '#808080' },
    { name: 'Новохохловская', line: 'МЦК', lat: 55.723889, lng: 37.716111, color: '#808080' },
    { name: 'Угрешская', line: 'МЦК', lat: 55.718333, lng: 37.697778, color: '#808080' },
    { name: 'Дубровка', line: 'МЦК', lat: 55.71268, lng: 37.677775, color: '#808080' },
    { name: 'Автозаводская', line: 'МЦК', lat: 55.70631, lng: 37.66314, color: '#808080' },
    { name: 'ЗИЛ', line: 'МЦК', lat: 55.698333, lng: 37.648333, color: '#808080' },
    { name: 'Верхние Котлы', line: 'МЦК', lat: 55.69, lng: 37.618889, color: '#808080' },
    { name: 'Крымская', line: 'МЦК', lat: 55.690038, lng: 37.605, color: '#808080' },
    { name: 'Площадь Гагарина', line: 'МЦК', lat: 55.706944, lng: 37.585833, color: '#808080' },
    { name: 'Лужники', line: 'МЦК', lat: 55.720278, lng: 37.563056, color: '#808080' },
    { name: 'Кутузовская', line: 'МЦК', lat: 55.740833, lng: 37.533333, color: '#808080' },
    { name: 'Деловой центр', line: 'МЦК', lat: 55.747222, lng: 37.532222, color: '#808080' },
    { name: 'Шелепиха', line: 'МЦК', lat: 55.7575, lng: 37.525556, color: '#808080' },
    { name: 'Хорошево', line: 'МЦК', lat: 55.777222, lng: 37.507222, color: '#808080' },
    { name: 'Зорге', line: 'МЦК', lat: 55.787778, lng: 37.504444, color: '#808080' },
    { name: 'Панфиловская', line: 'МЦК', lat: 55.799167, lng: 37.498889, color: '#808080' },
    { name: 'Стрешнево', line: 'МЦК', lat: 55.813611, lng: 37.486944, color: '#808080' },
    { name: 'Балтийская', line: 'МЦК', lat: 55.825833, lng: 37.496111, color: '#808080' },
    { name: 'Коптево', line: 'МЦК', lat: 55.839637, lng: 37.520037, color: '#808080' },
    { name: 'Лихоборы', line: 'МЦК', lat: 55.847222, lng: 37.551389, color: '#808080' },
    { name: 'Мичуринский проспект', line: 'Большая кольцевая линия', lat: 55.688333, lng: 37.485, color: '#808080' },
    { name: 'Проспект Вернадского', line: 'Большая кольцевая линия', lat: 55.677778, lng: 37.505, color: '#808080' },
    { name: 'Новаторская', line: 'Большая кольцевая линия', lat: 55.670833, lng: 37.52, color: '#808080' },
    { name: 'Воронцовская', line: 'Большая кольцевая линия', lat: 55.658333, lng: 37.540833, color: '#808080' },
    { name: 'Зюзино', line: 'Большая кольцевая линия', lat: 55.655158, lng: 37.575786, color: '#808080' },
    { name: 'Каховская', line: 'Большая кольцевая линия', lat: 55.653056, lng: 37.598333, color: '#808080' },
    { name: 'Варшавская', line: 'Большая кольцевая линия', lat: 55.653333, lng: 37.619444, color: '#808080' },
    { name: 'Каширская', line: 'Большая кольцевая линия', lat: 55.655, lng: 37.648611, color: '#808080' },
    { name: 'Кленовый бульвар', line: 'Большая кольцевая линия', lat: 55.674444, lng: 37.680833, color: '#808080' },
    { name: 'Нагатинский Затон', line: 'Большая кольцевая линия', lat: 55.684444, lng: 37.703611, color: '#808080' },
    { name: 'Печатники', line: 'Большая кольцевая линия', lat: 55.694722, lng: 37.7275, color: '#808080' },
    { name: 'Текстильщики', line: 'Большая кольцевая линия', lat: 55.708333, lng: 37.728333, color: '#808080' },
    { name: 'Нижегородская', line: 'Большая кольцевая линия', lat: 55.7325, lng: 37.728611, color: '#808080' },
    { name: 'Авиамоторная', line: 'Большая кольцевая линия', lat: 55.753056, lng: 37.718611, color: '#808080' },
    { name: 'Лефортово', line: 'Большая кольцевая линия', lat: 55.764444, lng: 37.702778, color: '#808080' },
    { name: 'Электрозаводская', line: 'Большая кольцевая линия', lat: 55.782057, lng: 37.7053, color: '#808080' },
    { name: 'Сокольники', line: 'Большая кольцевая линия', lat: 55.791111, lng: 37.678889, color: '#808080' },
    { name: 'Рижская', line: 'Большая кольцевая линия', lat: 55.792222, lng: 37.633889, color: '#808080' },
    { name: 'Марьина Роща', line: 'Большая кольцевая линия', lat: 55.798333, lng: 37.617222, color: '#808080' },
    { name: 'Савёловская', line: 'Большая кольцевая линия', lat: 55.794054, lng: 37.587163, color: '#808080' },
    { name: 'Петровский парк', line: 'Большая кольцевая линия', lat: 55.79233, lng: 37.55952, color: '#808080' },
    { name: 'ЦСКА', line: 'Большая кольцевая линия', lat: 55.78643, lng: 37.53502, color: '#808080' },
    { name: 'Хорошевская', line: 'Большая кольцевая линия', lat: 55.77643, lng: 37.51981, color: '#808080' },
    { name: 'Шелепиха', line: 'Большая кольцевая линия', lat: 55.75723, lng: 37.52571, color: '#808080' },
    { name: 'Деловой центр', line: 'Большая кольцевая линия', lat: 55.7491, lng: 37.5395, color: '#808080' },
    { name: 'Народное Ополчение', line: 'Большая кольцевая линия', lat: 55.77592, lng: 37.485073, color: '#808080' },
    { name: 'Мнёвники', line: 'Большая кольцевая линия', lat: 55.761153, lng: 37.47139, color: '#808080' },
    { name: 'Терехово', line: 'Большая кольцевая линия', lat: 55.748108, lng: 37.459738, color: '#808080' },
    { name: 'Кунцевская', line: 'Большая кольцевая линия', lat: 55.730278, lng: 37.445833, color: '#808080' },
    { name: 'Давыдково', line: 'Большая кольцевая линия', lat: 55.715278, lng: 37.451667, color: '#808080' },
    { name: 'Аминьевская', line: 'Большая кольцевая линия', lat: 55.697222, lng: 37.464167, color: '#808080' },
    { name: 'Косино', line: 'Некрасовская', lat: 55.7026, lng: 37.8511, color: '#E8682E' },
    { name: 'Улица Дмитриевского', line: 'Некрасовская', lat: 55.7093, lng: 37.8792, color: '#E8682E' },
    { name: 'Лухмановская', line: 'Некрасовская', lat: 55.7078, lng: 37.9004, color: '#E8682E' },
    { name: 'Некрасовка', line: 'Некрасовская', lat: 55.7029, lng: 37.9264, color: '#E8682E' },
    { name: 'Юго-Восточная', line: 'Некрасовская', lat: 55.71, lng: 37.82, color: '#E8682E' },
    { name: 'Окская', line: 'Некрасовская', lat: 55.72, lng: 37.77, color: '#E8682E' },
    { name: 'Стахановская', line: 'Некрасовская', lat: 55.73, lng: 37.76, color: '#E8682E' },
    { name: 'Нижегородская', line: 'Некрасовская', lat: 55.73, lng: 37.73, color: '#E8682E' },
    { name: 'Лефортово', line: 'Некрасовская', lat: 55.764444, lng: 37.702778, color: '#E8682E' },
    { name: 'Электрозаводская', line: 'Некрасовская', lat: 55.782057, lng: 37.7053, color: '#E8682E' },
    { name: 'Авиамоторная', line: 'Некрасовская', lat: 55.751933, lng: 37.717444, color: '#E8682E' },
    { name: 'Лобня', line: 'МЦД-1', lat: 56.0048, lng: 37.29057, color: '#808080' },
    { name: 'Шереметьевская', line: 'МЦД-1', lat: 55.983882, lng: 37.498752, color: '#808080' },
    { name: 'Хлебниково', line: 'МЦД-1', lat: 55.970682, lng: 37.504638, color: '#808080' },
    { name: 'Водники', line: 'МЦД-1', lat: 55.953419, lng: 37.511143, color: '#808080' },
    { name: 'Долгопрудная', line: 'МЦД-1', lat: 55.938656, lng: 37.520542, color: '#808080' },
    { name: 'Новодачная', line: 'МЦД-1', lat: 55.924459, lng: 37.527877, color: '#808080' },
    { name: 'Марк', line: 'МЦД-1', lat: 55.904458, lng: 37.538242, color: '#808080' },
    { name: 'Лианозово', line: 'МЦД-1', lat: 55.897316, lng: 37.553261, color: '#808080' },
    { name: 'Бескудниково', line: 'МЦД-1', lat: 55.882713, lng: 37.567768, color: '#808080' },
    { name: 'Дегунино', line: 'МЦД-1', lat: 55.86586, lng: 37.573235, color: '#808080' },
    { name: 'Окружная', line: 'МЦД-1', lat: 55.848889, lng: 37.571111, color: '#808080' },
    { name: 'Тимирязевская', line: 'МЦД-1', lat: 55.81866, lng: 37.574498, color: '#808080' },
    { name: 'Савёловская', line: 'МЦД-1', lat: 55.793936, lng: 37.587038, color: '#808080' },
    { name: 'Белорусская', line: 'МЦД-1', lat: 55.775179, lng: 37.582303, color: '#808080' },
    { name: 'Беговая', line: 'МЦД-1', lat: 55.773505, lng: 37.545518, color: '#808080' },
    { name: 'Тестовская', line: 'МЦД-1', lat: 55.754292, lng: 37.531551, color: '#808080' },
    { name: 'Фили', line: 'МЦД-1', lat: 55.744263, lng: 37.514526, color: '#808080' },
    { name: 'Славянский бульвар', line: 'МЦД-1', lat: 55.729722, lng: 37.470556, color: '#808080' },
    { name: 'Кунцевская', line: 'МЦД-1', lat: 55.730554, lng: 37.445591, color: '#808080' },
    { name: 'Рабочий Посёлок', line: 'МЦД-1', lat: 55.726957, lng: 37.415577, color: '#808080' },
    { name: 'Сетунь', line: 'МЦД-1', lat: 55.723713, lng: 37.397259, color: '#808080' },
    { name: 'Немчиновка', line: 'МЦД-1', lat: 55.715668, lng: 37.374611, color: '#808080' },
    { name: 'Сколково', line: 'МЦД-1', lat: 55.666801, lng: 37.424618, color: '#808080' },
    { name: 'Баковка', line: 'МЦД-1', lat: 55.682816, lng: 37.315205, color: '#808080' },
    { name: 'Одинцово', line: 'МЦД-1', lat: 55.67798, lng: 37.27773, color: '#808080' },
    { name: 'Нахабино', line: 'МЦД-2', lat: 55.841522, lng: 37.185204, color: '#808080' },
    { name: 'Аникеевка', line: 'МЦД-2', lat: 55.832099, lng: 37.219829, color: '#808080' },
    { name: 'Опалиха', line: 'МЦД-2', lat: 55.82333, lng: 37.246843, color: '#808080' },
    { name: 'Красногорская', line: 'МЦД-2', lat: 55.814571, lng: 37.303337, color: '#808080' },
    { name: 'Павшино', line: 'МЦД-2', lat: 55.815231, lng: 37.341461, color: '#808080' },
    { name: 'Пенягино', line: 'МЦД-2', lat: 55.822539, lng: 37.361049, color: '#808080' },
    { name: 'Волоколамская', line: 'МЦД-2', lat: 55.835154, lng: 37.382453, color: '#808080' },
    { name: 'Трикотажная', line: 'МЦД-2', lat: 55.833137, lng: 37.398967, color: '#808080' },
    { name: 'Тушинская', line: 'МЦД-2', lat: 55.825479, lng: 37.437024, color: '#808080' },
    { name: 'Покровское-Стрешнево', line: 'МЦД-2', lat: 55.814247, lng: 37.47678, color: '#808080' },
    { name: 'Стрешнево', line: 'МЦД-2', lat: 55.813611, lng: 37.486944, color: '#808080' },
    { name: 'Красный Балтиец', line: 'МЦД-2', lat: 55.815514, lng: 37.526367, color: '#808080' },
    { name: 'Гражданская', line: 'МЦД-2', lat: 55.805527, lng: 37.55315, color: '#808080' },
    { name: 'Дмитровская', line: 'МЦД-2', lat: 55.808056, lng: 37.581734, color: '#808080' },
    { name: 'Рижская', line: 'МЦД-2', lat: 55.792494, lng: 37.636114, color: '#808080' },
    { name: 'Площадь трёх вокзалов', line: 'МЦД-2', lat: 55.776087, lng: 37.651861, color: '#808080' },
    { name: 'Курская', line: 'МЦД-2', lat: 55.757622, lng: 37.660767, color: '#808080' },
    { name: 'Москва Товарная', line: 'МЦД-2', lat: 55.745358, lng: 37.688839, color: '#808080' },
    { name: 'Калитники', line: 'МЦД-2', lat: 55.733981, lng: 37.702203, color: '#808080' },
    { name: 'Новохохловская', line: 'МЦД-2', lat: 55.718523, lng: 37.719236, color: '#808080' },
    { name: 'Текстильщики', line: 'МЦД-2', lat: 55.708934, lng: 37.731283, color: '#808080' },
    { name: 'Люблино', line: 'МЦД-2', lat: 55.676596, lng: 37.761639, color: '#808080' },
    { name: 'Депо', line: 'МЦД-2', lat: 55.674257, lng: 37.728446, color: '#808080' },
    { name: 'Перерва', line: 'МЦД-2', lat: 55.660809, lng: 37.716278, color: '#808080' },
    { name: 'Курьяново', line: 'МЦД-2', lat: 55.649722, lng: 37.701667, color: '#808080' },
    { name: 'Москворечье', line: 'МЦД-2', lat: 55.641239, lng: 37.689789, color: '#808080' },
    { name: 'Царицыно', line: 'МЦД-2', lat: 55.618309, lng: 37.668846, color: '#808080' },
    { name: 'Покровское', line: 'МЦД-2', lat: 55.814247, lng: 37.47678, color: '#808080' },
    { name: 'Красный строитель', line: 'МЦД-2', lat: 55.589455, lng: 37.615093, color: '#808080' },
    { name: 'Битца', line: 'МЦД-2', lat: 55.571186, lng: 37.611443, color: '#808080' },
    { name: 'Бутово', line: 'МЦД-2', lat: 55.548279, lng: 37.555668, color: '#808080' },
    { name: 'Щербинка', line: 'МЦД-2', lat: 55.509724, lng: 37.562008, color: '#808080' },
    { name: 'Остафьево', line: 'МЦД-2', lat: 55.50337, lng: 37.520055, color: '#808080' },
    { name: 'Силикатная', line: 'МЦД-2', lat: 55.470278, lng: 37.555278, color: '#808080' },
    { name: 'Подольск', line: 'МЦД-2', lat: 55.431667, lng: 37.565, color: '#808080' },
    { name: 'Марьина Роща', line: 'МЦД-2', lat: 55.800833, lng: 37.618889, color: '#808080' },
    { name: 'Крюково', line: 'МЦД-3', lat: 55.979722, lng: 37.173611, color: '#808080' },
    { name: 'Малино', line: 'МЦД-3', lat: 55.969167, lng: 37.211667, color: '#808080' },
    { name: 'Фирсановская', line: 'МЦД-3', lat: 55.960278, lng: 37.251111, color: '#808080' },
    { name: 'Сходня', line: 'МЦД-3', lat: 55.949722, lng: 37.298611, color: '#808080' },
    { name: 'Подрезково', line: 'МЦД-3', lat: 55.941667, lng: 37.334722, color: '#808080' },
    { name: 'Новоподрезково', line: 'МЦД-3', lat: 55.936389, lng: 37.351667, color: '#808080' },
    { name: 'Молжаниново', line: 'МЦД-3', lat: 55.924167, lng: 37.380833, color: '#808080' },
    { name: 'Химки', line: 'МЦД-3', lat: 55.894444, lng: 37.450833, color: '#808080' },
    { name: 'Левобережная', line: 'МЦД-3', lat: 55.886944, lng: 37.468611, color: '#808080' },
    { name: 'Ховрино', line: 'МЦД-3', lat: 55.879444, lng: 37.486667, color: '#808080' },
    { name: 'Грачёвская', line: 'МЦД-3', lat: 55.869444, lng: 37.509167, color: '#808080' },
    { name: 'Моссельмаш', line: 'МЦД-3', lat: 55.862222, lng: 37.526389, color: '#808080' },
    { name: 'Лихоборы', line: 'МЦД-3', lat: 55.85, lng: 37.5525, color: '#808080' },
    { name: 'Петровско-Разумовская', line: 'МЦД-3', lat: 55.839722, lng: 37.568333, color: '#808080' },
    { name: 'Останкино', line: 'МЦД-3', lat: 55.817222, lng: 37.603611, color: '#808080' },
    { name: 'Рижская', line: 'МЦД-3', lat: 55.796944, lng: 37.639167, color: '#808080' },
    { name: 'Митьково', line: 'МЦД-3', lat: 55.786389, lng: 37.6675, color: '#808080' },
    { name: 'Электрозаводская', line: 'МЦД-3', lat: 55.781111, lng: 37.705278, color: '#808080' },
    { name: 'Сортировочная', line: 'МЦД-3', lat: 55.763611, lng: 37.720833, color: '#808080' },
    { name: 'Авиамоторная', line: 'МЦД-3', lat: 55.750278, lng: 37.721944, color: '#808080' },
    { name: 'Андроновка', line: 'МЦД-3', lat: 55.744444, lng: 37.741111, color: '#808080' },
    { name: 'Перово', line: 'МЦД-3', lat: 55.735556, lng: 37.765, color: '#808080' },
    { name: 'Плющево', line: 'МЦД-3', lat: 55.730556, lng: 37.774167, color: '#808080' },
    { name: 'Вешняки', line: 'МЦД-3', lat: 55.721944, lng: 37.799167, color: '#808080' },
    { name: 'Выхино', line: 'МЦД-3', lat: 55.716575, lng: 37.815911, color: '#808080' },
    { name: 'Косино', line: 'МЦД-3', lat: 55.714167, lng: 37.8475, color: '#808080' },
    { name: 'Ухтомская', line: 'МЦД-3', lat: 55.698611, lng: 37.864167, color: '#808080' },
    { name: 'Люберцы I', line: 'МЦД-3', lat: 55.681667, lng: 37.896944, color: '#808080' },
    { name: 'Панки', line: 'МЦД-3', lat: 55.668889, lng: 37.9225, color: '#808080' },
    { name: 'Томилино', line: 'МЦД-3', lat: 55.655, lng: 37.954722, color: '#808080' },
    { name: 'Красково', line: 'МЦД-3', lat: 55.649722, lng: 37.9825, color: '#808080' },
    { name: 'Малаховка', line: 'МЦД-3', lat: 55.645, lng: 38.008333, color: '#808080' },
    { name: 'Удельная', line: 'МЦД-3', lat: 55.634444, lng: 38.043889, color: '#808080' },
    { name: 'Быково', line: 'МЦД-3', lat: 55.626667, lng: 38.070556, color: '#808080' },
    { name: 'Ильинская', line: 'МЦД-3', lat: 55.616389, lng: 38.100278, color: '#808080' },
    { name: 'Отдых', line: 'МЦД-3', lat: 55.601111, lng: 38.136944, color: '#808080' },
    { name: 'Кратово', line: 'МЦД-3', lat: 55.591667, lng: 38.16, color: '#808080' },
    { name: 'Есенинская', line: 'МЦД-3', lat: 55.581944, lng: 38.184167, color: '#808080' },
    { name: 'Фабричная', line: 'МЦД-3', lat: 55.572778, lng: 1.873333, color: '#808080' },
    { name: 'Раменское', line: 'МЦД-3', lat: 55.565278, lng: 55.565278, color: '#808080' },
    { name: 'Ипподром', line: 'МЦД-3', lat: 55.560278, lng: 38.238889, color: '#808080' },
    { name: 'Железнодорожная', line: 'МЦД-4', lat: 55.7525, lng: 38.008889, color: '#808080' },
    { name: 'Ольгино', line: 'МЦД-4', lat: 55.751667, lng: 37.978611, color: '#808080' },
    { name: 'Кучино', line: 'МЦД-4', lat: 55.752222, lng: 37.954722, color: '#808080' },
    { name: 'Салтыковская', line: 'МЦД-4', lat: 55.757778, lng: 37.923056, color: '#808080' },
    { name: 'Никольское', line: 'МЦД-4', lat: 55.759722, lng: 37.897778, color: '#808080' },
    { name: 'Реутов', line: 'МЦД-4', lat: 55.751389, lng: 37.855833, color: '#808080' },
    { name: 'Новогиреево', line: 'МЦД-4', lat: 55.744444, lng: 37.818333, color: '#808080' },
    { name: 'Кусково', line: 'МЦД-4', lat: 55.739722, lng: 37.795278, color: '#808080' },
    { name: 'Чухлинка', line: 'МЦД-4', lat: 55.733889, lng: 55.733889, color: '#808080' },
    { name: 'Нижегородская', line: 'МЦД-4', lat: 55.733333, lng: 37.729444, color: '#808080' },
    { name: 'Серп и Молот', line: 'МЦД-4', lat: 55.748056, lng: 37.681944, color: '#808080' },
    { name: 'Курская', line: 'МЦД-4', lat: 55.740833, lng: 37.660556, color: '#808080' },
    { name: 'Площадь трёх вокзалов', line: 'МЦД-4', lat: 55.776667, lng: 37.651111, color: '#808080' },
    { name: 'Рижская', line: 'МЦД-4', lat: 55.793889, lng: 37.638611, color: '#808080' },
    { name: 'Марьина Роща', line: 'МЦД-4', lat: 55.800833, lng: 37.618889, color: '#808080' },
    { name: 'Савёловская', line: 'МЦД-4', lat: 55.794444, lng: 37.590278, color: '#808080' },
    { name: 'Белорусская', line: 'МЦД-4', lat: 55.776389, lng: 37.580278, color: '#808080' },
    { name: 'Ермакова Роща', line: 'МЦД-4', lat: 55.765556, lng: 37.535278, color: '#808080' },
    { name: 'Тестовская', line: 'МЦД-4', lat: 55.750833, lng: 37.530278, color: '#808080' },
    { name: 'Кутузовская', line: 'МЦД-4', lat: 55.741944, lng: 37.533056, color: '#808080' },
    { name: 'Поклонная', line: 'МЦД-4', lat: 55.728333, lng: 37.511667, color: '#808080' },
    { name: 'Минская', line: 'МЦД-4', lat: 55.723333, lng: 37.533056, color: '#808080' },
    { name: 'Матвеевское', line: 'МЦД-4', lat: 55.704722, lng: 37.482222, color: '#808080' },
    { name: 'Аминьевская', line: 'МЦД-4', lat: 55.699444, lng: 37.468056, color: '#808080' },
    { name: 'Очаково I', line: 'МЦД-4', lat: 55.683611, lng: 37.451389, color: '#808080' },
    { name: 'Мещерская', line: 'МЦД-4', lat: 55.666667, lng: 37.424444, color: '#808080' },
    { name: 'Солнечная', line: 'МЦД-4', lat: 55.656944, lng: 37.383611, color: '#808080' },
    { name: 'Новопеределкино', line: 'МЦД-4', lat: 55.639167, lng: 37.381111, color: '#808080' },
    { name: 'Переделкино', line: 'МЦД-4', lat: 55.656111, lng: 37.353889, color: '#808080' },
    { name: 'Мичуринец', line: 'МЦД-4', lat: 55.646111, lng: 37.315, color: '#808080' },
    { name: 'Внуково', line: 'МЦД-4', lat: 55.648889, lng: 37.269722, color: '#808080' },
    { name: 'Лесной Городок', line: 'МЦД-4', lat: 55.630278, lng: 37.219167, color: '#808080' },
    { name: 'Толстопальцево', line: 'МЦД-4', lat: 55.607778, lng: 37.186389, color: '#808080' },
    { name: 'Кокошкино', line: 'МЦД-4', lat: 55.599722, lng: 37.171389, color: '#808080' },
    { name: 'Санино', line: 'МЦД-4', lat: 55.583889, lng: 37.138333, color: '#808080' },
    { name: 'Крёкшино', line: 'МЦД-4', lat: 55.577778, lng: 37.109722, color: '#808080' },
    { name: 'Победа', line: 'МЦД-4', lat: 55.566111, lng: 37.093056, color: '#808080' },
    { name: 'Апрелевка', line: 'МЦД-4', lat: 55.550278, lng: 37.0675, color: '#808080' },
    { name: 'ЗИЛ', line: 'Троицкая', lat: 55.697915, lng: 37.647565, color: '#808080' },
    { name: 'Крымская', line: 'Троицкая', lat: 55.689971, lng: 37.605612, color: '#808080' },
    { name: 'Академическая', line: 'Троицкая', lat: 55.68808, lng: 37.57501, color: '#808080' },
    { name: 'Вавиловская', line: 'Троицкая', lat: 55.686688, lng: 37.543706, color: '#808080' },
    { name: 'Новаторская', line: 'Троицкая', lat: 55.670833, lng: 37.52, color: '#808080' },
    { name: 'Университет дружбы народов', line: 'Троицкая', lat: 55.64824, lng: 37.507556, color: '#808080' },
    { name: 'Генерала Тюленева', line: 'Троицкая', lat: 55.626248, lng: 37.486032, color: '#808080' },
    { name: 'Тютчевская', line: 'Троицкая', lat: 55.618801, lng: 37.481415, color: '#808080' },
    { name: 'Корниловская', line: 'Троицкая', lat: 55.599411, lng: 37.479586, color: '#808080' },
    { name: 'Коммунарка', line: 'Троицкая', lat: 55.57354, lng: 37.468116, color: '#808080' },
    { name: 'Новомосковская', line: 'Троицкая', lat: 55.560094, lng: 37.469807, color: '#808080' }
];
    
    function initMap() {
        map = L.map('map').setView(MOSCOW_CENTER, 12);
        
        L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a>',
            subdomains: 'abcd',
            maxZoom: 19
        }).addTo(map);
        
        addMetroStations();
        
        map.setMaxBounds([
            [55.3, 37.1],
            [56.0, 38.1]
        ]);
        
        drawnItems = new L.FeatureGroup();
        map.addLayer(drawnItems);
        
        var drawControl = new L.Control.Draw({
            edit: { featureGroup: drawnItems, edit: true, remove: true },
            draw: {
                polygon: false,
                polyline: false,
                circle: false,
                circlemarker: false,
                marker: false,
                rectangle: {
                    shapeOptions: {
                        color: '#ff4757',
                        weight: 3,
                        fillColor: '#ff4757',
                        fillOpacity: 0.3
                    }
                }
            }
        });
        map.addControl(drawControl);
        
        map.on('draw:created', function(e) {
            drawnItems.clearLayers();
            var layer = e.layer;
            drawnItems.addLayer(layer);
            selectedArea = layer;
            var bounds = layer.getBounds();
            selectedCoords = {
                north: bounds.getNorth(),
                south: bounds.getSouth(),
                east: bounds.getEast(),
                west: bounds.getWest()
            };
        });
        
        map.on('click', function(e) {
            var lat = e.latlng.lat;
            var lng = e.latlng.lng;
            drawnItems.clearLayers();
            selectedArea = null;
            selectedCoords = { lat: lat, lng: lng };
        });
    }
    
    function addMetroStations() {
        metroStations.forEach(station => {
            const metroIcon = L.divIcon({
                className: 'metro-marker',
                html: `<div style="background: white; border-radius: 50%; width: 24px; height: 24px; display: flex; align-items: center; justify-content: center; box-shadow: 0 2px 5px rgba(0,0,0,0.2); border: 2px solid ${station.color}; font-size: 12px; font-weight: bold; color: ${station.color};">M</div>`,
                iconSize: [24, 24],
                popupAnchor: [0, -12]
            });
            
            const marker = L.marker([station.lat, station.lng], { icon: metroIcon }).addTo(map);
            marker.bindPopup(`
                <div style="font-family: Arial; padding: 5px;">
                    <strong style="color: ${station.color};">🚇 ${station.name}</strong><br>
                    <span style="font-size: 11px; color: #666;">${station.line} линия</span>
                </div>
            `);
        });
        console.log('Станции метро добавлены на карту, всего:', metroStations.length);
    }
    
    function resetMap() {
        map.setView(MOSCOW_CENTER, 12);
        addMessage('Карта перемещена в центр Москвы', 'bot');
    }
    
    function clearArea() {
        drawnItems.clearLayers();
        selectedArea = null;
        selectedCoords = null;
        addMessage('Выделенная область очищена', 'bot');
    }
    
    function searchInArea() {
        if (selectedArea) {
            addMessage('Поиск мест в выделенной области...', 'bot');
            addMessage('Напишите, что хотите найти (кафе, ресторан, парк и т.д.)', 'bot');
        } else if (selectedCoords && selectedCoords.lat) {
            addMessage('Поиск мест рядом с выбранной точкой...', 'bot');
            addMessage('Напишите, что хотите найти (кафе, ресторан, парк и т.д.)', 'bot');
        } else {
            addMessage('Сначала нарисуйте область на карте или кликните на карту, чтобы выбрать точку!', 'bot');
        }
    }
    
    async function sendMessage() {
        var input = document.getElementById('chatInput');
        var message = input.value.trim();
        if (!message) return;
        addMessage(message, 'user');
        input.value = '';
        showTyping(true);
        
        var context = "";
        if (selectedArea) {
            var bounds = selectedArea.getBounds();
            context = ' (поиск в области: север ' + bounds.getNorth().toFixed(4) + ', юг ' + bounds.getSouth().toFixed(4) + ', восток ' + bounds.getEast().toFixed(4) + ', запад ' + bounds.getWest().toFixed(4) + ')';
        } else if (selectedCoords) {
            context = ' (поиск рядом с точкой: ' + selectedCoords.lat + ', ' + selectedCoords.lng + ')';
        }
        
        try {
            var response = await fetch('/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: message + context, user_id: currentUserId })
            });
            if (!response.ok) throw new Error('HTTP error');
            var data = await response.json();
            showTyping(false);
            addMessage(data.reply, 'bot', true);
            attachButtonHandlers();
        } catch (error) {
            showTyping(false);
            addMessage('Извините, произошла ошибка. Попробуйте позже.', 'bot');
        }
    }
    
    function addMessage(text, sender, isHtml) {
        var messagesDiv = document.getElementById('messages');
        var msgDiv = document.createElement('div');
        msgDiv.className = 'message ' + sender;
        var now = new Date();
        var time = now.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
        
        var contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        
        if (isHtml && sender === 'bot') {
            contentDiv.innerHTML = text;
            setTimeout(function() {
                attachButtonHandlers();
            }, 100);
        } else if (isHtml && sender === 'user') {
            contentDiv.innerHTML = text;
        } else {
            var safeText = text.replace(/[&<>]/g, function(m) {
                if (m === '&') return '&amp;';
                if (m === '<') return '&lt;';
                if (m === '>') return '&gt;';
                return m;
            }).replace(/\\n/g, '<br>');
            contentDiv.innerHTML = safeText;
        }
        
        var timeDiv = document.createElement('div');
        timeDiv.className = 'message-time';
        timeDiv.textContent = time;
        
        msgDiv.appendChild(contentDiv);
        msgDiv.appendChild(timeDiv);
        messagesDiv.appendChild(msgDiv);
        messagesDiv.scrollTop = messagesDiv.scrollHeight;
    }
    
    function showTyping(show) {
        document.getElementById('typing').style.display = show ? 'block' : 'none';
    }
    
    function attachButtonHandlers() {
        var btns = document.querySelectorAll('.blacklist-btn');
        for (var i = 0; i < btns.length; i++) {
            btns[i].removeEventListener('click', handleBlacklist);
            btns[i].addEventListener('click', handleBlacklist);
        }
        var moreBtns = document.querySelectorAll('.more-btn');
        for (var i = 0; i < moreBtns.length; i++) {
            moreBtns[i].removeEventListener('click', handleMore);
            moreBtns[i].addEventListener('click', handleMore);
        }
        var newBtns = document.querySelectorAll('.new-search-btn');
        for (var i = 0; i < newBtns.length; i++) {
            newBtns[i].removeEventListener('click', handleNewSearch);
            newBtns[i].addEventListener('click', handleNewSearch);
        }
    }
    
    async function handleBlacklist(event) {
        var btn = event.currentTarget;
        var placeCard = btn.closest('.place-card');
        var placeId = btn.dataset.placeId;
        var placeName = btn.dataset.placeName;
        
        addMessage('Место "' + placeName + '" удалено из списка', 'user');
        
        showTyping(true);
        try {
            var response = await fetch('/blacklist', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_id: currentUserId, place_id: placeId })
            });
            var data = await response.json();
            showTyping(false);
            
            if (placeCard) {
                placeCard.remove();
            }
            
            var remainingCards = document.querySelectorAll('.place-card');
            if (remainingCards.length === 0) {
                var recommendationsDiv = document.querySelector('.recommendations-list');
                if (recommendationsDiv) {
                    recommendationsDiv.innerHTML = '<div class="message bot"><div class="message-content">Вы отфильтровали все места. Нажмите "Новый поиск", чтобы начать заново.</div></div>';
                }
                var controlButtons = document.querySelector('.control-buttons');
                if (controlButtons) {
                    var newBtn = controlButtons.querySelector('.new-search-btn');
                    if (newBtn) {
                        var moreBtn = controlButtons.querySelector('.more-btn');
                        if (moreBtn) moreBtn.remove();
                    }
                }
            }
            
        } catch (error) {
            showTyping(false);
            addMessage('Ошибка при удалении места', 'bot');
        }
    }
    
    async function handleMore() {
        addMessage('Ещё', 'user');
        showTyping(true);
        try {
            var response = await fetch('/more', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_id: currentUserId })
            });
            var data = await response.json();
            showTyping(false);
            
            if (data.reply && data.reply !== 'undefined') {
                addMessage(data.reply, 'bot', true);
            } else {
                addMessage('Нет больше рекомендаций', 'bot');
            }
            
            attachButtonHandlers();
        } catch (error) {
            console.error('Ошибка:', error);
            showTyping(false);
            addMessage('Ошибка при загрузке следующих мест', 'bot');
        }
    }
    
    async function handleNewSearch() {
        addMessage('Новый поиск', 'user');
        showTyping(true);
        try {
            var response = await fetch('/new_search', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_id: currentUserId })
            });
            var data = await response.json();
            showTyping(false);
            addMessage(data.reply, 'bot');
            
            if (drawnItems) {
                drawnItems.clearLayers();
                selectedArea = null;
                selectedCoords = null;
            }
        } catch (error) {
            showTyping(false);
            addMessage('Ошибка при сбросе поиска', 'bot');
        }
    }
    
    window.onload = function() {
        initMap();
    };
</script>
</body>
</html>
'''

@app.get("/", response_class=HTMLResponse)
async def root():
    return HTMLResponse(content=HTML_CONTENT)

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    print(f"Получено сообщение: {request.message}")
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Сообщение не может быть пустым")
    
    area = None
    point = None
    
    if "поиск в области" in request.message:
        try:
            north_match = re.search(r'север ([\d\.]+)', request.message)
            if north_match:
                area = {
                    'north': float(north_match.group(1)),
                    'south': float(re.search(r'юг ([\d\.]+)', request.message).group(1)),
                    'east': float(re.search(r'восток ([\d\.]+)', request.message).group(1)),
                    'west': float(re.search(r'запад ([\d\.]+)', request.message).group(1))
                }
        except Exception as e:
            print(f"Ошибка парсинга области: {e}")
    elif "поиск рядом с точкой" in request.message:
        try:
            coords = re.findall(r'([\d\.]+)', request.message)
            if len(coords) >= 2:
                point = {'lat': float(coords[0]), 'lon': float(coords[1])}
        except Exception as e:
            print(f"Ошибка парсинга точки: {e}")
    
    clean_message = request.message.split('(поиск')[0].strip()
    reply_text = get_bot_response(clean_message, area, point, request.user_id)
    
    return ChatResponse(
        reply=reply_text,
        timestamp=datetime.now().isoformat(),
        suggestions=["Кафе поблизости", "Парки", "Рестораны", "Музеи", "Театры"]
    )

@app.post("/more")
async def load_more(request: ChatRequest):
    reply_text = handle_load_more(request.user_id)
    return {"reply": reply_text, "timestamp": datetime.now().isoformat()}

@app.post("/new_search")
async def new_search(request: ChatRequest):
    session_state.pop(request.user_id, None)
    return {"reply": "Начинаем новый поиск!\n\n- Выделите область на карте\n- Напишите, что хотите найти", "timestamp": datetime.now().isoformat()}

@app.post("/blacklist")
async def blacklist(request: Dict):
    user_id = request.get('user_id', 'default_user')
    place_id = request.get('place_id')
    reply_text = handle_blacklist(user_id, place_id)
    return {"reply": reply_text, "timestamp": datetime.now().isoformat()}

@app.get("/health")
async def health():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7860)