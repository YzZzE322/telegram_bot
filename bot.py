"""
Telegram бот: Всё в одном
- Погода, курс валют, курс биткоина
- Вероятность событий
- Предсказания
- Репутация с кулдауном 10 минут
- Топ репутации с именами и статусами
- Игра КНБ с собеседником
- Специальные ответы для @thugdaplug на "пасрал"
"""

import random
import requests
import time
import re
import json
import os
from datetime import datetime

# ========== НАСТРОЙКИ ==========
TOKEN = "8760632799:AAGXBCPxu1rQXMc71OX2ZWoUshg34jrwqPA"
LAST_UPDATE_ID = 0

# Хранилище игр
GAMES = {}

# Файлы для хранения репутации
REPUTATION_FILE = "reputation.json"
REPUTATION_STATS_FILE = "reputation_stats.json"
USERS_CACHE_FILE = "users_cache.json"

PROCESSED_UPDATES = set()

# ===== ЗАЩИТА ОТ АБУЗА РЕПУТАЦИИ =====
REP_COOLDOWN = {}
REP_COOLDOWN_SECONDS = 600  # 10 минут

# Координаты Томска
TOMSK_LAT = 56.4977
TOMSK_LON = 84.9744

# Ключевые фразы
PROBABILITY_PHRASES = [
    'будет ли', 'вероятность', 'какой шанс', 'удастся ли',
    'получится ли', 'сможет ли', 'выйдет ли', 'повезет ли',
    'сбудется ли', 'произойдет ли', 'случится ли'
]

WEATHER_PHRASES = ['погода', 'какая погода', 'температура', 'на улице']
CURRENCY_PHRASES = ['курс', 'валюта', 'доллар', 'евро', 'юань', 'фунт']

# ===== ОСКОРБЛЕНИЯ =====
BAD_WORDS = [
    'пидар', 'пидарас', 'далбаеб', 'даун', 'дурак', 'дебил',
    'чмо', 'сука', 'гандон', 'гнида', 'уебок', 'уебище',
    'мразь', 'конч', 'конченый', 'еблан', 'ебланище',
    'лох', 'лошара', 'редиска', 'овцеёб', 'хуйло', 'петух'
]

# ===== ПОХВАЛА =====
GOOD_WORDS = [
    'спс', 'спасибо', 'пажалуйста', 'пожалуйста', 'не за что',
    'незачто', 'дякую', 'вибачте', 'сори', 'сорянчик',
    'спасибки', 'благодарю', 'мерси', 'сенкью', 'thanks'
]

# ===== ПРЕДСКАЗАНИЯ =====
BAD_PREDICTIONS = [
    "💀 Ты настолько бесполезен, что даже Вселенная забыла выдать тебе судьбу",
    "🔮 Единственное, что тебя ждёт в будущем — осознание, что всё могло быть хуже",
    "🪦 Твоя жизнь — как фильм ужасов",
    "💀 Ты — ошибка бета-версии",
]

GOOD_PREDICTIONS = [
    "✨ Сегодня тебе реально повезёт",
    "🌸 Звёзды говорят: есть надежда",
    "🌞 Сегодня будет хороший день",
    "🍀 Удача улыбнётся тебе",
]

ALL_PREDICTIONS = BAD_PREDICTIONS + GOOD_PREDICTIONS

# ===== ФУНКЦИИ РЕПУТАЦИИ И КЭША =====
def load_reputation():
    if os.path.exists(REPUTATION_FILE):
        with open(REPUTATION_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_reputation(reputation):
    with open(REPUTATION_FILE, "w", encoding="utf-8") as f:
        json.dump(reputation, f, ensure_ascii=False, indent=2)

REPUTATION = load_reputation()

def load_users_cache():
    if os.path.exists(USERS_CACHE_FILE):
        with open(USERS_CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_users_cache(cache):
    with open(USERS_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

USERS_CACHE = load_users_cache()

def update_user_cache(user_id, user_name, username=""):
    """Сохраняет имя пользователя в кэш"""
    user_id_str = str(user_id)
    if user_id_str not in USERS_CACHE or USERS_CACHE[user_id_str].get("name") != user_name:
        USERS_CACHE[user_id_str] = {
            "name": user_name,
            "username": username,
            "last_seen": datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        }
        save_users_cache(USERS_CACHE)

def get_user_name_from_api(user_id):
    """Получает имя пользователя через Telegram API"""
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/getChat"
        params = {"chat_id": user_id}
        response = requests.get(url, params=params, timeout=5)
        data = response.json()
        if data.get("ok") and data.get("result"):
            user = data["result"]
            first_name = user.get("first_name", "")
            last_name = user.get("last_name", "")
            username = user.get("username", "")
            if first_name:
                return f"{first_name} {last_name}".strip()
            elif username:
                return f"@{username}"
        return str(user_id)
    except Exception as e:
        print(f"Ошибка получения имени {user_id}: {e}")
        return str(user_id)

def get_user_name(user_id):
    """Возвращает имя пользователя: из кэша, через API или ID"""
    user_id_str = str(user_id)
    
    # Сначала проверяем кэш
    if user_id_str in USERS_CACHE:
        return USERS_CACHE[user_id_str].get("name", str(user_id))
    
    # Если нет в кэше, пробуем получить через API
    name = get_user_name_from_api(user_id)
    
    # Сохраняем в кэш для будущих запросов
    if name != str(user_id):
        update_user_cache(user_id, name, "")
    
    return name

def load_stats():
    if os.path.exists(REPUTATION_STATS_FILE):
        with open(REPUTATION_STATS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_stats(stats):
    with open(REPUTATION_STATS_FILE, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

REPUTATION_STATS = load_stats()

def update_reputation(user_id, change, reason=""):
    user_id_str = str(user_id)
    if user_id_str not in REPUTATION:
        REPUTATION[user_id_str] = 0
    old = REPUTATION[user_id_str]
    new = old + change
    REPUTATION[user_id_str] = new
    save_reputation(REPUTATION)
    
    if user_id_str not in REPUTATION_STATS:
        REPUTATION_STATS[user_id_str] = {"total_bad": 0, "total_good": 0, "last_change": None, "last_reason": "", "history": []}
    
    if change < 0:
        REPUTATION_STATS[user_id_str]["total_bad"] += 1
    else:
        REPUTATION_STATS[user_id_str]["total_good"] += 1
    
    REPUTATION_STATS[user_id_str]["last_change"] = change
    REPUTATION_STATS[user_id_str]["last_reason"] = reason
    REPUTATION_STATS[user_id_str]["history"].insert(0, {"time": datetime.now().strftime("%d.%m.%Y %H:%M:%S"), "change": change, "reason": reason, "new_value": new})
    REPUTATION_STATS[user_id_str]["history"] = REPUTATION_STATS[user_id_str]["history"][:10]
    save_stats(REPUTATION_STATS)
    return new

def get_reputation(user_id):
    return REPUTATION.get(str(user_id), 0)

def get_reputation_stats(user_id):
    return REPUTATION_STATS.get(str(user_id), {})

def get_reputation_emoji(score):
    if score >= 100: return "👑"
    elif score >= 50: return "⭐"
    elif score >= 25: return "🌟"
    elif score >= 10: return "👍"
    elif score <= -50: return "💀"
    elif score <= -25: return "👹"
    elif score <= -10: return "👎"
    elif score < 0: return "😈"
    return "😐"

def get_reputation_title(score):
    if score >= 100: return "Легенда 👑"
    elif score >= 50: return "Авторитет ⭐"
    elif score >= 25: return "Уважаемый 🌟"
    elif score >= 10: return "Хороший человек 👍"
    elif score >= 1: return "Норм 😊"
    elif score == 0: return "Нейтрал 😐"
    elif score >= -9: return "Подозрительный 👎"
    elif score >= -24: return "Плохой 👹"
    elif score >= -49: return "Отморозок 💀"
    else: return "Абсолютное зло 💀💀💀"

def is_bad_word(text):
    for word in text.lower().split():
        clean = re.sub(r'[^а-яa-z]', '', word)
        if clean in BAD_WORDS:
            return True, clean
    return False, None

def is_good_word(text):
    for word in text.lower().split():
        clean = re.sub(r'[^а-яa-z]', '', word)
        if clean in GOOD_WORDS:
            return True, clean
    return False, None

def check_rep_cooldown(giver_id, target_id):
    if giver_id not in REP_COOLDOWN:
        REP_COOLDOWN[giver_id] = {}
    
    last_time = REP_COOLDOWN[giver_id].get(target_id, 0)
    current_time = time.time()
    
    if last_time and (current_time - last_time) < REP_COOLDOWN_SECONDS:
        remaining = int(REP_COOLDOWN_SECONDS - (current_time - last_time))
        minutes = remaining // 60
        seconds = remaining % 60
        return False, f"⏰ Кулдаун {minutes} мин {seconds} сек. Подожди!"
    
    REP_COOLDOWN[giver_id][target_id] = current_time
    return True, "OK"

def get_reputation_top(limit=10):
    """Возвращает топ пользователей по репутации с именами и статусами"""
    if not REPUTATION:
        return [], []
    
    # Сортируем по убыванию репутации
    sorted_users = sorted(REPUTATION.items(), key=lambda x: x[1], reverse=True)
    
    top_positive = []
    top_negative = []
    
    for user_id_str, rep in sorted_users:
        user_id = int(user_id_str)
        name = get_user_name(user_id)
        status_emoji = get_reputation_emoji(rep)
        
        if rep > 0:
            top_positive.append((user_id, name, rep, status_emoji))
        elif rep < 0:
            top_negative.append((user_id, name, rep, status_emoji))
        
        if len(top_positive) >= limit and len(top_negative) >= limit:
            break
    
    return top_positive[:limit], top_negative[:limit]

def get_prediction():
    return random.choice(ALL_PREDICTIONS)

def create_progress_bar(probability):
    filled = probability // 10
    return "█" * filled + "░" * (10 - filled)

def is_probability_question(text):
    return any(phrase in text.lower() for phrase in PROBABILITY_PHRASES)

def is_weather_request(text):
    return any(phrase in text.lower() for phrase in WEATHER_PHRASES)

def is_currency_request(text):
    return any(phrase in text.lower() for phrase in CURRENCY_PHRASES)

def get_weather():
    url = f"https://api.open-meteo.com/v1/forecast?latitude={TOMSK_LAT}&longitude={TOMSK_LON}&current_weather=true&timezone=auto"
    try:
        data = requests.get(url, timeout=10).json()
        if "current_weather" not in data:
            return "❌ Ошибка погоды"
        w = data["current_weather"]
        codes = {0: "☀️ Ясно", 1: "🌤️ Облачно", 2: "⛅ Переменная облачность", 3: "☁️ Пасмурно", 61: "🌧️ Дождь", 71: "❄️ Снег"}
        return f"{codes.get(w['weathercode'], '🌡️')}\n\n🌡️ {int(w['temperature'])}°C\n🌬️ {int(w['windspeed'])} м/с"
    except:
        return "❌ Ошибка погоды"

def get_specific_rate(cur, to="RUB"):
    try:
        data = requests.get(f"https://api.exchangerate-api.com/v4/latest/{cur}", timeout=10).json()
        rate = data.get("rates", {}).get(to)
        return round(rate, 2) if rate else None
    except:
        return None

def get_exchange_rates():
    usd = get_specific_rate("USD")
    eur = get_specific_rate("EUR")
    cny = get_specific_rate("CNY")
    if not usd:
        return "❌ Ошибка курса"
    res = "💱 *Курс валют*\n\n"
    res += f"🇺🇸 Доллар: {usd} ₽\n"
    if eur: res += f"🇪🇺 Евро: {eur} ₽\n"
    if cny: res += f"🇨🇳 Юань: {cny} ₽\n"
    return res

def get_bitcoin_price():
    try:
        data = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd,rub", timeout=10).json()
        return f"₿ *Биткоин*\n🇺🇸 ${data['bitcoin']['usd']}\n🇷🇺 {data['bitcoin']['rub']} ₽"
    except:
        return "❌ Ошибка курса BTC"

def send_message(chat_id, text):
    try:
        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}, timeout=10)
    except Exception as e:
        print(f"Ошибка: {e}")

def send_kb_message(chat_id, text, game_id):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "reply_markup": {
            "inline_keyboard": [
                [
                    {"text": "✊ Камень", "callback_data": f"knb_{game_id}_камень"},
                    {"text": "✌️ Ножницы", "callback_data": f"knb_{game_id}_ножницы"},
                    {"text": "✋ Бумага", "callback_data": f"knb_{game_id}_бумага"}
                ]
            ]
        },
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Ошибка: {e}")

# ========== ОСНОВНОЙ ОБРАБОТЧИК ==========
def handle_message(message):
    global LAST_UPDATE_ID
    
    chat_id = message.get("chat", {}).get("id")
    chat_type = message.get("chat", {}).get("type")
    text = message.get("text", "")
    user_id = message.get("from", {}).get("id")
    user_name = message.get("from", {}).get("first_name", "Пользователь")
    username = message.get("from", {}).get("username", "")
    
    if not chat_id or not text:
        return
    
    # Сохраняем имя пользователя в кэш
    update_user_cache(user_id, user_name, username)
    
    is_private_chat = chat_type == "private"
    
    update_id = message.get("update_id")
    if update_id in PROCESSED_UPDATES:
        return
    PROCESSED_UPDATES.add(update_id)
    if len(PROCESSED_UPDATES) > 1000:
        PROCESSED_UPDATES.clear()
    
    # ===== ТОП РЕПУТАЦИИ =====
    if text.lower() == "/top_rep" or text.lower() == "/топ":
        top_positive, top_negative = get_reputation_top(10)
        
        result = "🏆 *ТОП ПОЛОЖИТЕЛЬНОЙ РЕПУТАЦИИ* 🏆\n\n"
        
        if top_positive:
            for i, (uid, name, rep, emoji) in enumerate(top_positive, 1):
                medal = ["🥇", "🥈", "🥉"][i-1] if i <= 3 else f"{i}."
                status_text = get_reputation_title(rep)
                result += f"{medal} *{name}* {emoji} — {rep} 👍 `{status_text}`\n"
        else:
            result += "😢 Нет пользователей с положительной репутацией\n"
        
        result += "\n💀 *ТОП ОТРИЦАТЕЛЬНОЙ РЕПУТАЦИИ* 💀\n\n"
        
        if top_negative:
            for i, (uid, name, rep, emoji) in enumerate(top_negative, 1):
                medal = ["🥇", "🥈", "🥉"][i-1] if i <= 3 else f"{i}."
                status_text = get_reputation_title(rep)
                result += f"{medal} *{name}* {emoji} — {rep} 👎 `{status_text}`\n"
        else:
            result += "😇 Нет пользователей с отрицательной репутацией\n"
        
        result += f"\n📊 Всего пользователей в базе: {len(REPUTATION)}"
        send_message(chat_id, result)
        return
    
    # ===== ИГРА КНБ =====
    if text.lower() == "/play" or text.lower() == "/игра":
        if chat_id in GAMES and GAMES[chat_id].get('waiting', False):
            if GAMES[chat_id]['player1'] != user_id:
                GAMES[chat_id]['player2'] = user_id
                GAMES[chat_id]['player2_name'] = user_name
                GAMES[chat_id]['waiting'] = False
                player1_name = GAMES[chat_id].get('player1_name', 'Игрок 1')
                send_message(chat_id, f"🎮 *Игра началась!*\n\n👤 {player1_name} vs 👤 {user_name}\n\nСделайте выбор в ЛИЧНЫХ СООБЩЕНИЯХ!")
                send_kb_message(user_id, f"🎮 Твой соперник: {player1_name}\nСделай выбор:", chat_id)
                send_kb_message(GAMES[chat_id]['player1'], f"🎮 Твой соперник: {user_name}\nСделай выбор:", chat_id)
                return
            else:
                send_message(chat_id, "❌ Нельзя играть с собой!")
                return
        else:
            GAMES[chat_id] = {
                'player1': user_id, 'player1_name': user_name,
                'player2': None, 'player2_name': None,
                'choice1': None, 'choice2': None, 'waiting': True
            }
            send_message(chat_id, f"🎮 *{user_name}* создал игру!\n\nНапиши `/play` чтобы присоединиться.")
            send_message(user_id, "🎮 Ты создал игру! Жди соперника.")
        return
    
    # ===== РЕПУТАЦИЯ В ГРУППАХ (с кулдауном) =====
    if not is_private_chat:
        is_cmd = text.startswith('/') or text.lower() in ["предсказание", "погода", "курс", "биткоин", "btc", "моя репутация", "/rep", "репутация", "/play", "/игра", "пасрал", "/top_rep", "/топ"]
        
        if not is_cmd and not is_probability_question(text) and not is_weather_request(text) and not is_currency_request(text):
            is_bad, bad_word = is_bad_word(text)
            is_good, good_word = is_good_word(text)
            
            if is_bad or is_good:
                # Проверка кулдауна
                can_change, cooldown_msg = check_rep_cooldown(user_id, user_id)
                if not can_change:
                    send_message(chat_id, cooldown_msg)
                    return
                
                if is_bad:
                    old_rep = get_reputation(user_id)
                    new_rep = update_reputation(user_id, -5, f"оскорбление: {bad_word}")
                    send_message(chat_id, f"😈 *{user_name}*, за слово '{bad_word}' репутация -5! ({old_rep} → {new_rep})")
                    return
                
                if is_good:
                    old_rep = get_reputation(user_id)
                    new_rep = update_reputation(user_id, +3, f"похвала: {good_word}")
                    send_message(chat_id, f"😇 *{user_name}*, за '{good_word}' репутация +3! ({old_rep} → {new_rep})")
                    return
    
    # ===== СПЕЦИАЛЬНЫЕ ОТВЕТЫ =====
    if username == "thugdaplug" and text.lower() == "пасрал":
        answers = [
            "Макс пасрал — мир полегчал.",
            "Тихо, гордо, без свидетелей. Мастер класс.",
            "Смыл — и даже не покраснел.",
            "Макс, ты сделал это быстрее, чем твой стул.",
            "Результат: минус килограмм, плюс уважение.",
            "Посрать как бог — и не мыть рук.",
            "Запах прошёл, а слава осталась.",
            "Макс сделал это. Остальное — вода.",
            "Унитаз плачет от счастья. Макс — нет.",
            "Пасрал, помылся, вышел героем."
        ]
        send_message(chat_id, f"💩 *@{username}* — {random.choice(answers)}")
        return
    
    # ===== /start =====
    if text == "/start":
        rep = get_reputation(user_id)
        send_message(chat_id, f"💀 *Привет, {user_name}!* {get_reputation_emoji(rep)}\n\n"
                     f"📊 Репутация: {rep} ({get_reputation_title(rep)})\n\n"
                     f"*Команды:*\n"
                     f"🎱 предсказание\n"
                     f"🎲 будет ли ...? — вероятность\n"
                     f"🌤️ погода — погода в Томске\n"
                     f"💱 курс — курс валют\n"
                     f"₿ биткоин — курс BTC\n"
                     f"✊ `/play` — игра КНБ с соперником\n"
                     f"📊 /rep — статистика репутации\n"
                     f"🏆 `/top_rep` — топ репутации\n\n"
                     f"⚡ Кулдаун: 10 минут между изменениями репутации")
        return
    
    # ===== РЕПУТАЦИЯ (команда) =====
    if text.lower() in ["моя репутация", "/rep", "репутация"]:
        rep = get_reputation(user_id)
        send_message(chat_id, f"{get_reputation_emoji(rep)} *Твоя репутация:* {rep}\n🏆 {get_reputation_title(rep)}")
        return
    
    # ===== ПРЕДСКАЗАНИЕ =====
    if text.lower() in ["предсказание", "/предсказание"]:
        send_message(chat_id, f"🎱 *Вселенная шепчет...*\n\n{get_prediction()}")
        return
    
    # ===== КУРС БИТКОИНА =====
    if text.lower() in ["биткоин", "btc", "/btc"]:
        send_message(chat_id, get_bitcoin_price())
        return
    
    # ===== КУРС ВАЛЮТ =====
    if is_currency_request(text):
        if "доллар" in text.lower():
            r = get_specific_rate("USD")
            send_message(chat_id, f"💵 Доллар: {r} ₽" if r else "❌ Ошибка")
        elif "евро" in text.lower():
            r = get_specific_rate("EUR")
            send_message(chat_id, f"💶 Евро: {r} ₽" if r else "❌ Ошибка")
        else:
            send_message(chat_id, get_exchange_rates())
        return
    
    # ===== ПОГОДА =====
    if is_weather_request(text):
        send_message(chat_id, get_weather())
        return
    
    # ===== ВЕРОЯТНОСТЬ =====
    if is_probability_question(text):
        prob = random.randint(0, 100)
        send_message(chat_id, f"🎲 *Вероятность:* {prob}%\n`{create_progress_bar(prob)}`\n`0%`               `100%`")
        return

# ========== ОБРАБОТКА CALLBACK-ЗАПРОСОВ ==========
def handle_callback_query(callback_query):
    global GAMES
    
    data = callback_query.get("data", "")
    user_id = callback_query.get("from", {}).get("id")
    message = callback_query.get("message", {})
    chat_id = message.get("chat", {}).get("id")
    message_id = message.get("message_id")
    
    if not data or not data.startswith("knb_"):
        return
    
    parts = data.split("_")
    if len(parts) < 3:
        return
    
    try:
        game_chat_id = int(parts[1])
    except:
        return
    
    choice = parts[2]
    
    if game_chat_id not in GAMES:
        return
    
    game = GAMES[game_chat_id]
    
    if game['player1'] == user_id and game.get('choice1') is None:
        game['choice1'] = choice
        url = f"https://api.telegram.org/bot{TOKEN}/editMessageText"
        requests.post(url, json={"chat_id": chat_id, "message_id": message_id, "text": f"✅ Твой выбор: {choice}\nОжидаем соперника..."}, timeout=10)
        
    elif game.get('player2') == user_id and game.get('choice2') is None:
        game['choice2'] = choice
        url = f"https://api.telegram.org/bot{TOKEN}/editMessageText"
        requests.post(url, json={"chat_id": chat_id, "message_id": message_id, "text": f"✅ Твой выбор: {choice}\nОжидаем соперника..."}, timeout=10)
    else:
        return
    
    if game['choice1'] and game['choice2']:
        c1, c2 = game['choice1'], game['choice2']
        p1_name = game.get('player1_name', 'Игрок 1')
        p2_name = game.get('player2_name', 'Игрок 2')
        emojis = {"камень": "✊", "ножницы": "✌️", "бумага": "✋"}
        
        if c1 == c2:
            result = "🤝 НИЧЬЯ!"
        elif (c1 == "камень" and c2 == "ножницы") or (c1 == "ножницы" and c2 == "бумага") or (c1 == "бумага" and c2 == "камень"):
            result = f"🎉 {p1_name} ПОБЕДИЛ!"
        else:
            result = f"🎉 {p2_name} ПОБЕДИЛ!"
        
        result_msg = (f"🎮 *РЕЗУЛЬТАТ ИГРЫ*\n\n"
                      f"🧑 {p1_name}: {emojis[c1]} *{c1}*\n"
                      f"🧑 {p2_name}: {emojis[c2]} *{c2}*\n\n"
                      f"{result}\n\n"
                      f"Напиши `/play` чтобы сыграть ещё!")
        
        send_message(game_chat_id, result_msg)
        del GAMES[game_chat_id]

def get_updates():
    global LAST_UPDATE_ID
    try:
        data = requests.get(f"https://api.telegram.org/bot{TOKEN}/getUpdates", params={"timeout": 30, "offset": LAST_UPDATE_ID + 1}, timeout=35).json()
        if data.get("ok") and data.get("result"):
            for upd in data["result"]:
                if upd.get("update_id"):
                    LAST_UPDATE_ID = upd["update_id"]
                if "message" in upd:
                    upd["message"]["update_id"] = upd["update_id"]
                    handle_message(upd["message"])
                if "callback_query" in upd:
                    handle_callback_query(upd["callback_query"])
    except Exception as e:
        print(f"Ошибка: {e}")

def main():
    print("Бот запущен!")
    print("Команды: предсказание, будет ли..., погода, курс, биткоин, /rep, /play, /top_rep")
    print("⚡ Репутация: кулдаун 10 минут между изменениями")
    print(f"📁 Кэш пользователей: {len(USERS_CACHE)} записей")
    
    try:
        info = requests.get(f"https://api.telegram.org/bot{TOKEN}/getMe", timeout=10).json()
        if info.get("ok"):
            print(f"✅ Бот @{info['result']['username']} готов!")
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return
    
    while True:
        try:
            get_updates()
        except KeyboardInterrupt:
            print("\n👋 Бот остановлен")
            break
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()