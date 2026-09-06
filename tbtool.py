# -*- coding: utf-8 -*-
# ============================================================
# 🚀 TBTOOL VIP ULTIMATE - BOT TELEGRAM FULL VERSION
# ============================================================
# DEPLOY RENDER.COM - WEBHOODK + FLASK + 85 LOGIC AI
# ============================================================

import os
import sys
import json
import time
import threading
import random
import logging
import math
import re
import hashlib
import uuid
import base64
import secrets
import urllib.parse
from collections import defaultdict, deque, Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from urllib.parse import urlparse, parse_qs

import pytz
import requests
import telebot
from telebot import types
from flask import Flask, request, jsonify

# ==================== LOGGING ====================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ==================== CONSTANTS ====================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8385677064:AAHS5ZqmV9QPka3I1t84lyysLzLsLTp3N6g")
ADMIN_ID = [int(x) for x in os.environ.get("ADMIN_ID", "7564889663").split(",")]
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "@duybmw")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "https://tbtool.onrender.com")
PORT = int(os.environ.get("PORT", 10000))

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN khong duoc de trong!")

bot = telebot.TeleBot(BOT_TOKEN, parse_mode='HTML')
app = Flask(__name__)

# ==================== ICONS ====================
ICONS = {
    "crown": "👑", "diamond": "💎", "star": "⭐", "fire": "🔥",
    "lightning": "⚡", "target": "🎯", "shield": "🛡️", "sword": "⚔️",
    "brain": "🧠", "robot": "🤖", "rocket": "🚀", "trophy": "🏆",
    "medal": "🏅", "gem": "💠", "sparkle": "✨", "settings": "⚙️",
    "user": "👤", "key": "🔑", "lock": "🔒", "unlock": "🔓",
    "check": "✅", "cross": "❌", "warning": "⚠️", "info": "ℹ️",
    "money": "💰", "chart": "📊", "clock": "⏰", "lotto": "🎲",
    "dice": "🎯", "plus": "➕", "minus": "➖", "arrow": "➡️",
    "heart": "❤️", "bell": "🔔", "gift": "🎁", "magic": "🔮",
    "phone": "📞", "vip": "💎", "user_id": "🆔", "admin": "🛡️"
}

# ==================== KEY / ACTIVATION ====================
DEVICE_ID_FILE = "device_id_tbtool.txt"
SALT = "TbToolKeySalt2026"
ACTIVATION_FILE = "activation_tbtool.dat"
ACCOUNTS_FILE = "accounts.json"
ENCRYPTION_KEY = hashlib.sha256(b"TbTool_SECURE_KEY_2026_XxX_VIP").digest()

SAVE_FILE = './bot_save.json'
valid_keys = {}
authorized_users = {}

def load_save_data():
    global valid_keys, authorized_users
    try:
        if os.path.exists(SAVE_FILE):
            with open(SAVE_FILE, 'r', encoding='utf-8') as f:
                d = json.load(f)
                valid_keys = d.get('valid_keys', {})
                authorized_users = {int(k): v for k, v in d.get('authorized_users', {}).items()}
    except Exception as e:
        logger.info(f'Chưa có dữ liệu lưu. Lỗi: {e}')

def save_data():
    try:
        with open(SAVE_FILE, 'w', encoding='utf-8') as f:
            json.dump({'valid_keys': valid_keys, 'authorized_users': authorized_users}, f, indent=2)
    except Exception as e:
        logger.error(f"Lỗi lưu file: {e}")

load_save_data()

# ==================== KEY FUNCTIONS ====================
def simple_encrypt(data: dict) -> str:
    try:
        json_str = json.dumps(data, sort_keys=True)
        key = ENCRYPTION_KEY
        encrypted = bytearray()
        for i, char in enumerate(json_str.encode('utf-8')):
            encrypted.append(char ^ key[i % len(key)])
        checksum = hashlib.sha256(json_str.encode()).hexdigest()
        result = base64.b64encode(bytes(encrypted)).decode()
        return f"{checksum}:{result}"
    except:
        return ""

def simple_decrypt(encrypted_str: str) -> Optional[dict]:
    try:
        if not encrypted_str: return None
        parts = encrypted_str.split(':', 1)
        if len(parts) != 2: return None
        stored_checksum, encrypted_data = parts
        key = ENCRYPTION_KEY
        encrypted = base64.b64decode(encrypted_data.encode())
        decrypted = bytearray()
        for i, char in enumerate(encrypted):
            decrypted.append(char ^ key[i % len(key)])
        json_str = decrypted.decode('utf-8')
        if hashlib.sha256(json_str.encode()).hexdigest() != stored_checksum: return None
        return json.loads(json_str)
    except:
        return None

def get_device_id() -> str:
    if Path(DEVICE_ID_FILE).exists():
        try:
            with open(DEVICE_ID_FILE, "r", encoding="utf-8") as f:
                return f.read().strip()
        except: pass
    new_id = str(uuid.uuid4()).replace("-", "")[:32]
    try:
        with open(DEVICE_ID_FILE, "w", encoding="utf-8") as f:
            f.write(new_id)
    except: pass
    return new_id

def save_activation(device_id: str, key: str, activation_time: datetime, duration_hours: int, key_type: str = "FREE"):
    is_vip = key_type != "FREE"
    data = {
        "device_id": device_id, "key": key, "key_type": key_type,
        "activation_time": activation_time.isoformat(),
        "expiry_time": (activation_time + timedelta(hours=duration_hours)).isoformat(),
        "duration_hours": duration_hours, "is_vip": is_vip,
        "checksum": hashlib.sha256(f"{device_id}:{key}:{activation_time.isoformat()}:{SALT}".encode()).hexdigest()
    }
    encrypted_data = simple_encrypt(data)
    if encrypted_data:
        try:
            with open(ACTIVATION_FILE, "w", encoding="utf-8") as f:
                f.write(encrypted_data)
            return True
        except: pass
    return False

def load_activation() -> Optional[Dict]:
    if not Path(ACTIVATION_FILE).exists(): return None
    try:
        with open(ACTIVATION_FILE, "r", encoding="utf-8") as f:
            encrypted_data = f.read().strip()
        if not encrypted_data: return None
        data = simple_decrypt(encrypted_data)
        if not data:
            try: os.remove(ACTIVATION_FILE)
            except: pass
            return None
        return data
    except:
        return None

def check_activation_valid() -> Tuple[bool, Optional[str], bool]:
    activation = load_activation()
    if not activation:
        return False, "Chưa kích hoạt", False
    try:
        current_device = get_device_id()
        if activation.get("device_id") != current_device:
            try: os.remove(ACTIVATION_FILE)
            except: pass
            return False, "Device ID không khớp", False
        key_type = activation.get("key_type", "FREE")
        expiry_time = datetime.fromisoformat(activation["expiry_time"])
        now = datetime.now()
        if now > expiry_time:
            try: os.remove(ACTIVATION_FILE)
            except: pass
            return False, "Key đã hết hạn", False
        remaining = expiry_time - now
        days = remaining.total_seconds() / 86400
        is_vip = activation.get("is_vip", False)
        if days >= 1:
            return True, f"Còn {days:.1f} ngày", is_vip
        else:
            return True, f"Còn {remaining.total_seconds() / 3600:.1f} giờ", is_vip
    except Exception as e:
        try: os.remove(ACTIVATION_FILE)
        except: pass
        return False, f"Lỗi: {e}", False

def is_vip_activated() -> bool:
    activation = load_activation()
    if not activation: return False
    return activation.get("key_type", "FREE") != "FREE"

def check_auth(chat_id):
    if chat_id in ADMIN_ID:
        return True
    if chat_id in authorized_users:
        if time.time() <= authorized_users[chat_id]:
            return True
        else:
            del authorized_users[chat_id]
            save_data()
    return False

def format_expire_time(ts):
    remain = ts - time.time()
    if remain <= 0: return "❌ ĐÃ HẾT HẠN"
    d = math.floor(remain / 86400)
    h = math.floor((remain % 86400) / 3600)
    m = math.floor((remain % 3600) / 60)
    if d > 0: return f"✅ CÒN {d} NGÀY {h} GIỜ {m} PHÚT"
    if h > 0: return f"✅ CÒN {h} GIỜ {m} PHÚT"
    return f"✅ CÒN {m} PHÚT"

def locked_msg():
    return f"""<pre>╔════════════════════════════════════════════╗
║    🔒 HỆ THỐNG BẢO MẬT VIP 🔒      ║
╠════════════════════════════════════════════╣
║ ⚠️ TÀI KHOẢN CHƯA KÍCH HOẠT BẢN QUYỀN VIP ║
║ ❌ KHÔNG THỂ TRUY CẬP HỆ THỐNG PHÂN TÍCH   ║
╠════════════════════════════════════════════╣
║ 🔑 MỞ KHÓA NGAY → LIÊN HỆ {ADMIN_USERNAME}
║ 💡 CÚ PHÁP KÍCH HOẠT: /nhapkey MÃ_KEY      ║
╚════════════════════════════════════════════╝</pre>"""

def generate_key(key_type: str = "VIP", duration_days: int = 30) -> str:
    if key_type == "VIP":
        key = 'VIP-' + ''.join(secrets.token_hex(5).upper())
    else:
        key = 'FREE-' + ''.join(secrets.token_hex(4).upper())
    valid_keys[key] = duration_days
    save_data()
    return key

# ==================== ACCOUNT MANAGER ====================
def load_accounts() -> list:
    if Path(ACCOUNTS_FILE).exists():
        try:
            with open(ACCOUNTS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except: pass
    return []

def save_accounts(accounts: list):
    with open(ACCOUNTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(accounts, f, indent=2)

def parse_account_link(link: str) -> Optional[Dict]:
    try:
        parsed = urlparse(link)
        params = parse_qs(parsed.query)
        if 'userId' in params and 'secretKey' in params:
            return {"userId": int(params['userId'][0]), "secretKey": params['secretKey'][0]}
    except:
        pass
    return None

# ==================== API CHUNG ====================
WALLET_API = "https://wallet.3games.io/api/wallet/user_asset"

def get_balance(user_id: int, secret_key: str) -> dict:
    headers = {
        'user-id': str(user_id),
        'user-secret-key': secret_key,
        'content-type': 'application/json'
    }
    try:
        resp = requests.post(
            WALLET_API,
            json={"user_id": user_id, "source": "home"},
            headers=headers,
            timeout=10
        )
        data = resp.json()
        if data.get('code') == 0:
            assets = data.get('data', {}).get('user_asset', {})
            return {
                'BUILD': assets.get('BUILD', 0),
                'USDT': assets.get('USDT', 0),
                'WORLD': assets.get('WORLD', 0)
            }
        return {}
    except Exception as e:
        logger.error(f"Get balance error: {e}")
        return {}

# ==================== VTH - 40 LOGIC ====================
ROOM_ORDER = [1, 2, 3, 4, 5, 6, 7, 8]
ROOM_NAMES = {1: "📦 Nhà kho", 2: "🪑 Phòng họp", 3: "👔 Phòng giám đốc", 4: "💬 Phòng trò chuyện", 5: "🎥 Phòng giám sát", 6: "🏢 Văn phòng", 7: "💰 Phòng tài vụ", 8: "👥 Phòng nhân sự"}

VTH_LOGIC_DESCRIPTIONS = {
    "RANDOM": "1. PHẬT ĐỘ (Random)",
    "MIN_PLAYER_BET": "2. AN TOÀN (Min Players & Bet)",
    "PROBABILITY": "3. XÁC SUẤT (Probability)",
    "FOLLOW_KILLER": "4. THEO SÁT THỦ (Follow Killer)",
    "SEQUENTIAL": "5. TUẦN TỰ (Sequential)",
    "KILLER_PERSONALITY": "6. TÍNH CÁCH SÁT THỦ (AI)",
    "SMART_SAFE": "7. THÔNG MINH (AI Smart)",
    "FOLLOW_KILLER_DELAYED": "8. THEO VẾT SÁT THỦ (Delay 1 ván)",
    "HIDE_SEEK_MASTER": "9. THÁNH TRỐN TÌM (Master AI)",
    "BALANCE": "10. CÂN BẰNG (Balance)",
    "MOST_PLAYERS": "11. ĐÔNG NHẤT (Most Players)",
    "LEAST_PLAYERS": "12. ÍT NHẤT (Least Players)",
    "RICHEST": "13. GIÀU NHẤT (Richest)",
    "POOREST": "14. NGHÈO NHẤT (Poorest)",
    "ALTERNATE": "15. XEN KẼ (Alternate)",
    "AVOID_RESULT": "16. TRÁNH KẾT QUẢ (Avoid Result)",
    "COLD": "17. PHÒNG LẠNH (Cold Room)",
    "HOT": "18. PHÒNG NÓNG (Hot Room)",
    "MEDIAN": "19. TRUNG VỊ (Median)",
    "PATTERN": "20. MẪU LẶP (Pattern)",
    "VIP_RANDOM": "21. VIP RANDOM (Random 20 logic)",
    "KILLER_WAVE": "22. BẮT SÓNG SÁT THỦ (VIP)",
    "PSYCHO_ANALYSIS": "23. PHÂN TÍCH TÂM LÝ (VIP)",
    "MARKOV_CHAIN": "24. CHUỖI MARKOV (VIP)",
    "DEEP_LEARNING": "25. HỌC SÂU (VIP)",
    "REINFORCEMENT": "26. HỌC TĂNG CƯỜNG (VIP)",
    "BAYESIAN": "27. XÁC SUẤT BAYES (VIP)",
    "K_MEANS": "28. PHÂN CỤM K-MEANS (VIP)",
    "NEURAL": "29. MẠNG NƠ-RON (VIP)",
    "FUZZY": "30. LOGIC MỜ (VIP)",
    "GENETIC": "31. THUẬT TOÁN DI TRUYỀN (VIP)",
    "ANT_COLONY": "32. KIẾN BÒ (VIP)",
    "PARTICLE_SWARM": "33. BẦY ĐÀN (VIP)",
    "KNN": "34. K-NEAREST NEIGHBORS (VIP)",
    "DECISION_TREE": "35. CÂY QUYẾT ĐỊNH (VIP)",
    "RANDOM_FOREST": "36. RỪNG NGẪU NHIÊN (VIP)",
    "GRADIENT_BOOST": "37. TĂNG CƯỜNG GRADIENT (VIP)",
    "LSTM": "38. LSTM (VIP)",
    "TRANSFORMER": "39. TRANSFORMER (VIP)",
    "ENSEMBLE": "40. TỔNG HỢP (VIP)",
}

# ==================== VTH STATE ====================
room_state = {r: {"players": 0, "bet": 0} for r in ROOM_ORDER}
room_stats = {r: {"kills": 0, "survives": 0} for r in ROOM_ORDER}
killer_history = deque(maxlen=20)
game_kill_log = deque(maxlen=10)
last_killed_room = None
_sequential_bet_index = 0

# ==================== 40 LOGIC VTH ====================
def choose_random() -> int:
    return random.choice(ROOM_ORDER)

def choose_min_player_bet() -> int:
    if not any(rs.get('players', 0) > 0 or rs.get('bet', 0) > 0 for rs in room_state.values()):
        return choose_random()
    scores = defaultdict(int)
    for r in ROOM_ORDER:
        scores[r] = room_state[r]['players'] + room_state[r]['bet'] / 100.0
    return min(scores, key=scores.get)

def choose_probability() -> int:
    scores = {}
    for r in ROOM_ORDER:
        kills = room_stats[r].get('kills', 0)
        survives = room_stats[r].get('survives', 0)
        survival_rate = (survives + 1) / (kills + survives + 2)
        scores[r] = survival_rate
    return max(scores, key=scores.get)

def choose_follow_killer() -> int:
    global last_killed_room
    if last_killed_room is not None and last_killed_room in ROOM_ORDER:
        return last_killed_room
    return random.choice(ROOM_ORDER)

def choose_sequential() -> int:
    global _sequential_bet_index
    room = ROOM_ORDER[_sequential_bet_index]
    _sequential_bet_index = (_sequential_bet_index + 1) % len(ROOM_ORDER)
    return room

def choose_killer_personality() -> int:
    if not killer_history: return choose_random()
    avg_players = sum(h['players'] for h in killer_history) / len(killer_history)
    avg_bet = sum(h['bet'] for h in killer_history) / len(killer_history)
    scores = {}
    for r in ROOM_ORDER:
        if r == last_killed_room:
            scores[r] = -999999
            continue
        scores[r] = abs(room_state[r]['players'] - avg_players) + abs(room_state[r]['bet'] - avg_bet)
    return max(scores, key=scores.get)

def choose_smart_safe() -> int:
    scores = {}
    max_players = max(rs['players'] for rs in room_state.values()) or 1
    max_bet = max(rs['bet'] for rs in room_state.values()) or 1
    for r in ROOM_ORDER:
        kills = room_stats[r].get('kills', 0)
        survives = room_stats[r].get('survives', 0)
        survival_rate = (survives + 1) / (kills + survives + 2)
        player_score = 1 - (room_state[r]['players'] / max_players)
        bet_score = 1 - (room_state[r]['bet'] / max_bet)
        last_kill_penalty = 0.5 if r == last_killed_room else 0
        scores[r] = (0.4 * survival_rate) + (0.3 * player_score) + (0.3 * bet_score) - last_kill_penalty
    return max(scores, key=scores.get)

def choose_follow_killer_delayed() -> int:
    global last_killed_room_delayed
    if last_killed_room_delayed is not None and last_killed_room_delayed in ROOM_ORDER:
        return last_killed_room_delayed
    return random.choice(ROOM_ORDER)

def choose_hide_seek_master() -> int:
    scores = {}
    max_players = max(rs['players'] for rs in room_state.values()) or 1
    max_bet = max(rs['bet'] for rs in room_state.values()) or 1
    for r in ROOM_ORDER:
        kills = room_stats[r].get('kills', 0)
        survives = room_stats[r].get('survives', 0)
        hist_danger = (kills + 1) / (kills + survives + 2)
        crowd_danger = room_state[r]['players'] / max_players
        money_danger = room_state[r]['bet'] / max_bet
        recency_penalty = 1.0 if r == last_killed_room else 0
        scores[r] = (0.3 * hist_danger) + (0.2 * crowd_danger) + (0.2 * money_danger) + recency_penalty
    return min(scores, key=scores.get)

def choose_balance() -> int:
    total_players = sum(rs['players'] for rs in room_state.values())
    total_bet = sum(rs['bet'] for rs in room_state.values())
    avg_players = total_players / len(ROOM_ORDER) if total_players > 0 else 0
    avg_bet = total_bet / len(ROOM_ORDER) if total_bet > 0 else 0
    scores = {}
    for r in ROOM_ORDER:
        scores[r] = abs(room_state[r]['players'] - avg_players) + abs(room_state[r]['bet'] - avg_bet)
    return min(scores, key=scores.get)

def choose_most_players() -> int:
    return max(ROOM_ORDER, key=lambda r: room_state[r]['players'])

def choose_least_players() -> int:
    return min(ROOM_ORDER, key=lambda r: room_state[r]['players'])

def choose_richest() -> int:
    return max(ROOM_ORDER, key=lambda r: room_state[r]['bet'])

def choose_poorest() -> int:
    return min(ROOM_ORDER, key=lambda r: room_state[r]['bet'])

def choose_alternate() -> int:
    if len(game_kill_log) < 2: return random.choice(ROOM_ORDER)
    last_rooms = list(game_kill_log)[-3:]
    candidates = [r for r in ROOM_ORDER if r not in last_rooms]
    return random.choice(candidates) if candidates else random.choice(ROOM_ORDER)

def choose_avoid_result() -> int:
    if last_killed_room is None: return random.choice(ROOM_ORDER)
    candidates = [r for r in ROOM_ORDER if r != last_killed_room]
    return random.choice(candidates) if candidates else random.choice(ROOM_ORDER)

def choose_cold() -> int:
    scores = defaultdict(int)
    player_ranks = sorted(ROOM_ORDER, key=lambda r: room_state[r]['players'])
    bet_ranks = sorted(ROOM_ORDER, key=lambda r: room_state[r]['bet'])
    for i, r in enumerate(reversed(player_ranks)):
        scores[r] += i
    for i, r in enumerate(reversed(bet_ranks)):
        scores[r] += i
    return min(scores, key=scores.get)

def choose_hot() -> int:
    scores = defaultdict(int)
    player_ranks = sorted(ROOM_ORDER, key=lambda r: room_state[r]['players'])
    bet_ranks = sorted(ROOM_ORDER, key=lambda r: room_state[r]['bet'])
    for i, r in enumerate(player_ranks):
        scores[r] += i
    for i, r in enumerate(bet_ranks):
        scores[r] += i
    return max(scores, key=scores.get)

def choose_median() -> int:
    if not any(rs['players'] > 0 for rs in room_state.values()):
        return random.choice(ROOM_ORDER)
    players_list = sorted(ROOM_ORDER, key=lambda r: room_state[r]['players'])
    bet_list = sorted(ROOM_ORDER, key=lambda r: room_state[r]['bet'])
    median_players = players_list[len(players_list) // 2]
    median_bet = bet_list[len(bet_list) // 2]
    scores = {}
    for r in ROOM_ORDER:
        scores[r] = abs(room_state[r]['players'] - room_state[median_players]['players']) + abs(room_state[r]['bet'] - room_state[median_bet]['bet'])
    return min(scores, key=scores.get)

def choose_pattern() -> int:
    if len(game_kill_log) < 3: return random.choice(ROOM_ORDER)
    last_3 = list(game_kill_log)[-3:]
    if len(last_3) == 3 and last_3[0] == last_3[2]:
        return last_3[1]
    return random.choice(ROOM_ORDER)

def choose_vip_random() -> int:
    logic_list = [
        choose_random, choose_min_player_bet, choose_probability,
        choose_follow_killer, choose_sequential, choose_killer_personality,
        choose_smart_safe, choose_follow_killer_delayed, choose_hide_seek_master,
        choose_balance, choose_most_players, choose_least_players,
        choose_richest, choose_poorest, choose_alternate,
        choose_avoid_result, choose_cold, choose_hot, choose_median, choose_pattern
    ]
    return random.choice(logic_list)()

def choose_killer_wave() -> int:
    if len(game_kill_log) < 4: return choose_random()
    last_4 = list(game_kill_log)[-4:]
    for i in range(1, 4):
        if len(last_4) >= i*2 and last_4[-i:] == last_4[-i*2:-i]:
            return last_4[-i-1] if len(last_4) > i else last_4[-1]
    return choose_smart_safe()

def choose_psycho_analysis() -> int:
    max_players_room = max(ROOM_ORDER, key=lambda r: room_state[r]['players'])
    max_bet_room = max(ROOM_ORDER, key=lambda r: room_state[r]['bet'])
    crowd_favorite = max_players_room if room_state[max_players_room]['players'] > room_state[max_bet_room]['players'] else max_bet_room
    candidates = [r for r in ROOM_ORDER if r != crowd_favorite]
    if candidates:
        return min(candidates, key=lambda r: room_state[r]['players'] + room_state[r]['bet'] * 0.01)
    return choose_random()

def choose_markov_chain() -> int:
    if len(game_kill_log) < 5: return choose_random()
    transitions = defaultdict(lambda: defaultdict(int))
    for i in range(len(game_kill_log) - 1):
        transitions[game_kill_log[i]][game_kill_log[i+1]] += 1
    last = game_kill_log[-1]
    if transitions[last]:
        return max(transitions[last].items(), key=lambda x: x[1])[0]
    return choose_smart_safe()

def choose_deep_learning() -> int:
    if len(killer_history) < 5: return choose_random()
    weights = {}
    for r in ROOM_ORDER:
        kills = room_stats[r].get('kills', 0)
        survives = room_stats[r].get('survives', 0)
        survival_rate = (survives + 1) / (kills + survives + 2)
        recent_boost = -0.5 if r == last_killed_room else 0
        crowd_boost = 1 - (room_state[r]['players'] / max(1, max(rs['players'] for rs in room_state.values())))
        money_boost = 1 - (room_state[r]['bet'] / max(1, max(rs['bet'] for rs in room_state.values())))
        weights[r] = (0.3 * survival_rate) + (0.2 * recent_boost) + (0.2 * crowd_boost) + (0.15 * money_boost) + random.uniform(-0.1, 0.1)
    return max(weights, key=weights.get)

def choose_reinforcement() -> int:
    if len(game_kill_log) < 3: return choose_random()
    scores = {r: 0 for r in ROOM_ORDER}
    for i, room in enumerate(list(game_kill_log)[-10:]):
        if room in scores:
            scores[room] += 1 if i < 3 else -0.5
    max_score = max(scores.values())
    if max_score <= 0: return choose_random()
    best_rooms = [r for r, s in scores.items() if s == max_score]
    return random.choice(best_rooms)

def choose_bayesian() -> int:
    if len(game_kill_log) < 3: return choose_random()
    counts = Counter(game_kill_log)
    total = len(game_kill_log)
    posterior = {}
    for r in ROOM_ORDER:
        posterior[r] = (counts.get(r, 0) + 1) / (total + len(ROOM_ORDER))
    return min(posterior, key=posterior.get)

def choose_k_means() -> int:
    if len(game_kill_log) < 6: return choose_random()
    features = defaultdict(lambda: [0, 0])
    for i, room in enumerate(list(game_kill_log)[-10:]):
        features[room][0] += 1
        features[room][1] = i
    cluster_1 = set()
    cluster_2 = set()
    for room, f in features.items():
        if f[0] < 2:
            cluster_1.add(room)
        else:
            cluster_2.add(room)
    if cluster_1:
        return random.choice(list(cluster_1))
    return choose_random()

def choose_neural() -> int:
    if len(killer_history) < 3: return choose_random()
    scores = {}
    for r in ROOM_ORDER:
        players = room_state[r]['players']
        bet = room_state[r]['bet']
        kills = room_stats[r].get('kills', 0)
        survives = room_stats[r].get('survives', 0)
        layer1 = (0.3 * survives) - (0.5 * kills) + (0.2 * players) - (0.3 * bet)
        layer2 = (0.4 * layer1) + (0.2 * (survives - kills))
        layer3 = (0.5 * layer2) + (0.3 * (1 - players/max(1, max(rs['players'] for rs in room_state.values()))))
        scores[r] = 1 / (1 + math.exp(-layer3))
    return max(scores, key=scores.get)

def choose_fuzzy() -> int:
    if len(killer_history) < 2: return choose_random()
    scores = {}
    for r in ROOM_ORDER:
        players = room_state[r]['players']
        bet = room_state[r]['bet']
        players_young = max(0, 1 - players/2) if players < 2 else 0
        players_old = max(0, (players-4)/2) if players > 4 else 0
        bet_low = max(0, 1 - bet/100) if bet < 100 else 0
        bet_high = max(0, (bet-400)/200) if bet > 400 else 0
        rule1 = min(players_young, bet_low)
        rule2 = min(players_old, bet_high)
        scores[r] = (rule1 * 1.0 + rule2 * 0.0) / (rule1 + rule2 + 0.01)
    return max(scores, key=scores.get)

def choose_genetic() -> int:
    if len(killer_history) < 5: return choose_random()
    fitness = {}
    for r in ROOM_ORDER:
        kills = room_stats[r].get('kills', 0)
        survives = room_stats[r].get('survives', 0)
        fitness[r] = (survives + 1) / (kills + survives + 2)
    return max(fitness, key=fitness.get)

def choose_ant_colony() -> int:
    if len(game_kill_log) < 3: return choose_random()
    pheromone = {}
    for r in ROOM_ORDER:
        pheromone[r] = list(game_kill_log).count(r) / len(game_kill_log)
    return min(pheromone, key=pheromone.get)

def choose_particle_swarm() -> int:
    if len(killer_history) < 3: return choose_random()
    scores = {}
    for r in ROOM_ORDER:
        kills = room_stats[r].get('kills', 0)
        survives = room_stats[r].get('survives', 0)
        scores[r] = (survives + 1) / (kills + survives + 2) + (0.3 if r in list(game_kill_log)[-3:] else 0)
    return max(scores, key=scores.get)

def choose_knn() -> int:
    if len(game_kill_log) < 3: return choose_random()
    k = min(3, len(game_kill_log))
    nearest = list(game_kill_log)[-k:]
    counts = Counter(nearest)
    min_count = min(counts.values())
    candidates = [r for r, c in counts.items() if c == min_count]
    return random.choice(candidates) if candidates else choose_random()

def choose_decision_tree() -> int:
    if len(killer_history) < 5: return choose_random()
    if last_killed_room:
        if room_state[last_killed_room]['players'] > 5:
            candidates = [r for r in ROOM_ORDER if r != last_killed_room]
            return random.choice(candidates) if candidates else choose_probability()
    return choose_probability()

def choose_random_forest() -> int:
    if len(killer_history) < 3: return choose_random()
    predictions = []
    for _ in range(5):
        predictions.append(choose_probability() if random.random() > 0.5 else choose_min_player_bet())
    counts = Counter(predictions)
    return max(counts, key=counts.get)

def choose_gradient_boost() -> int:
    if len(killer_history) < 3: return choose_random()
    scores = {}
    for r in ROOM_ORDER:
        kills = room_stats[r].get('kills', 0)
        survives = room_stats[r].get('survives', 0)
        survival_rate = (survives + 1) / (kills + survives + 2)
        scores[r] = 0.5 + 0.3 * survival_rate - 0.1 * (room_state[r]['players'] / max(1, max(rs['players'] for rs in room_state.values())))
    return max(scores, key=scores.get)

def choose_lstm() -> int:
    if len(game_kill_log) < 4: return choose_random()
    last_5 = list(game_kill_log)[-5:]
    if len(last_5) == 5 and last_5[0] == last_5[3] and last_5[1] == last_5[4]:
        return last_5[2]
    return choose_markov_chain()

def choose_transformer() -> int:
    if len(game_kill_log) < 4: return choose_random()
    scores = {}
    for r in ROOM_ORDER:
        kills = room_stats[r].get('kills', 0)
        survives = room_stats[r].get('survives', 0)
        recency = 1 - (list(game_kill_log).count(r) / max(1, len(game_kill_log)))
        scores[r] = (0.4 * recency) + (0.3 * (survives / max(1, kills + survives))) + (0.3 * (1 - room_state[r]['players'] / max(1, max(rs['players'] for rs in room_state.values()))))
    return max(scores, key=scores.get)

def choose_ensemble() -> int:
    if len(killer_history) < 3: return choose_random()
    votes = defaultdict(int)
    vip_funcs = [
        choose_killer_wave, choose_psycho_analysis, choose_markov_chain,
        choose_deep_learning, choose_reinforcement, choose_bayesian,
        choose_k_means, choose_neural, choose_fuzzy, choose_genetic,
        choose_ant_colony, choose_particle_swarm, choose_knn,
        choose_decision_tree, choose_random_forest, choose_gradient_boost,
        choose_lstm, choose_transformer
    ]
    for func in vip_funcs:
        try:
            votes[func()] += 1
        except:
            continue
    return max(votes, key=votes.get) if votes else choose_random()

def choose_room_vth(mode: str) -> int:
    logic_map = {
        "RANDOM": choose_random, "MIN_PLAYER_BET": choose_min_player_bet,
        "PROBABILITY": choose_probability, "FOLLOW_KILLER": choose_follow_killer,
        "SEQUENTIAL": choose_sequential, "KILLER_PERSONALITY": choose_killer_personality,
        "SMART_SAFE": choose_smart_safe, "FOLLOW_KILLER_DELAYED": choose_follow_killer_delayed,
        "HIDE_SEEK_MASTER": choose_hide_seek_master, "BALANCE": choose_balance,
        "MOST_PLAYERS": choose_most_players, "LEAST_PLAYERS": choose_least_players,
        "RICHEST": choose_richest, "POOREST": choose_poorest,
        "ALTERNATE": choose_alternate, "AVOID_RESULT": choose_avoid_result,
        "COLD": choose_cold, "HOT": choose_hot,
        "MEDIAN": choose_median, "PATTERN": choose_pattern,
        "VIP_RANDOM": choose_vip_random, "KILLER_WAVE": choose_killer_wave,
        "PSYCHO_ANALYSIS": choose_psycho_analysis, "MARKOV_CHAIN": choose_markov_chain,
        "DEEP_LEARNING": choose_deep_learning, "REINFORCEMENT": choose_reinforcement,
        "BAYESIAN": choose_bayesian, "K_MEANS": choose_k_means,
        "NEURAL": choose_neural, "FUZZY": choose_fuzzy,
        "GENETIC": choose_genetic, "ANT_COLONY": choose_ant_colony,
        "PARTICLE_SWARM": choose_particle_swarm, "KNN": choose_knn,
        "DECISION_TREE": choose_decision_tree, "RANDOM_FOREST": choose_random_forest,
        "GRADIENT_BOOST": choose_gradient_boost, "LSTM": choose_lstm,
        "TRANSFORMER": choose_transformer, "ENSEMBLE": choose_ensemble,
    }
    func = logic_map.get(mode, choose_random)
    return func()

# ==================== API VTH ====================
BET_API_URL = "https://api.escapemaster.net/escape_game/bet"

def vth_place_bet(user_id: int, secret_key: str, issue_id: int, room_id: int, amount: float) -> dict:
    headers = {'user-id': str(user_id), 'user-secret-key': secret_key, 'content-type': 'application/json'}
    payload = {"asset_type": "BUILD", "user_id": user_id, "room_id": room_id, "bet_amount": amount}
    try:
        resp = requests.post(BET_API_URL, headers=headers, json=payload, timeout=8)
        return resp.json()
    except Exception as e:
        return {"error": str(e)}

# ==================== VTD - 35 LOGIC ====================
VTD_ATHLETES = {
    1: "⚔️ Bậc thầy tấn công",
    2: "🛡️ Quyền sắt",
    3: "🏊 Thợ lặn sâu",
    4: "🌪️ Cơn lốc sân cỏ",
    5: "🏇 Hiệp sĩ phi nhanh",
    6: "🏆 Vua home run"
}

VTD_LOGIC_DESCRIPTIONS = {
    "RANDOM": "1. Ngẫu nhiên (Random) - FREE",
    "HOT": "2. VĐV nóng (Hot) - FREE",
    "COLD": "3. VĐV lạnh (Cold) - FREE",
    "LAST_BOTTOM": "4. Về cuối ván trước - FREE",
    "SEQUENTIAL": "5. Tuần tự (Sequential) - FREE",
    "TREND_REVERSE": "6. Đảo xu hướng - FREE",
    "MOST_CONSISTENT": "7. Ổn định nhất - FREE",
    "LEAST_FREQUENT": "8. Ít xuất hiện nhất - FREE",
    "MOST_FREQUENT": "9. Xuất hiện nhiều nhất - FREE",
    "AVOID_LAST": "10. Tránh ván trước - FREE",
    "ALTERNATE": "11. Xen kẽ - FREE",
    "SECOND_LAST": "12. Về nhất ván trước - FREE",
    "THIRD_LAST": "13. Về nhất 2 ván trước - FREE",
    "BALANCE": "14. Cân bằng - FREE",
    "MIDDLE_RANK": "15. Vị trí giữa - FREE",
    "EXTREME": "16. Đầu hoặc cuối - FREE",
    "AGAINST_TREND": "17. Chống xu hướng - FREE",
    "FOLLOW_WINNER": "18. Theo VĐV về nhất - FREE",
    "FOLLOW_LOSER": "19. Theo VĐV về cuối - FREE",
    "RANDOM_PATTERN": "20. Mẫu ngẫu nhiên - FREE",
    "VIP_RANDOM": "21. VIP Random - VIP",
    "MARKOV": "22. Chuỗi Markov - VIP",
    "BAYES": "23. Xác suất Bayes - VIP",
    "NEURAL": "24. Mạng nơ-ron - VIP",
    "FUZZY": "25. Logic mờ - VIP",
    "GENETIC": "26. Di truyền - VIP",
    "ANT_COLONY": "27. Kiến bò - VIP",
    "PARTICLE_SWARM": "28. Bầy đàn - VIP",
    "KNN": "29. KNN - VIP",
    "DECISION_TREE": "30. Cây quyết định - VIP",
    "RANDOM_FOREST": "31. Rừng ngẫu nhiên - VIP",
    "GRADIENT_BOOST": "32. Gradient Boost - VIP",
    "LSTM": "33. LSTM - VIP",
    "TRANSFORMER": "34. Transformer - VIP",
    "ENSEMBLE": "35. Tổng hợp - VIP",
}

vtd_stats = deque(maxlen=100)
vtd_last_bottom = None
vtd_seq_index = 0

def vtd_choose_random() -> int:
    return random.randint(1, 6)

def vtd_choose_hot() -> int:
    if not vtd_stats: return random.randint(1, 6)
    counts = Counter([h['winner'] for h in vtd_stats])
    return counts.most_common(1)[0][0]

def vtd_choose_cold() -> int:
    if not vtd_stats: return random.randint(1, 6)
    counts = Counter([h['winner'] for h in vtd_stats])
    return min(counts, key=counts.get)

def vtd_choose_last_bottom() -> int:
    global vtd_last_bottom
    if vtd_last_bottom is not None:
        return vtd_last_bottom
    return random.randint(1, 6)

def vtd_choose_sequential() -> int:
    global vtd_seq_index
    room = vtd_seq_index
    vtd_seq_index = (vtd_seq_index + 1) % 6
    return room + 1

def vtd_choose_trend_reverse() -> int:
    if len(vtd_stats) < 3: return random.randint(1, 6)
    last_winners = [h['winner'] for h in vtd_stats[-3:]]
    candidates = [i for i in range(1, 7) if i not in last_winners]
    return random.choice(candidates) if candidates else random.randint(1, 6)

def vtd_choose_most_consistent() -> int:
    if not vtd_stats: return random.randint(1, 6)
    changes = {i: 0 for i in range(1, 7)}
    for i in range(1, len(vtd_stats)):
        if vtd_stats[i-1]['winner'] == vtd_stats[i]['winner']:
            changes[vtd_stats[i]['winner']] += 1
    return max(changes, key=changes.get)

def vtd_choose_least_frequent() -> int:
    if not vtd_stats: return random.randint(1, 6)
    counts = Counter([h['winner'] for h in vtd_stats])
    return min(counts, key=counts.get)

def vtd_choose_most_frequent() -> int:
    if not vtd_stats: return random.randint(1, 6)
    counts = Counter([h['winner'] for h in vtd_stats])
    return max(counts, key=counts.get)

def vtd_choose_avoid_last() -> int:
    if not vtd_stats: return random.randint(1, 6)
    last = vtd_stats[-1]['winner']
    candidates = [i for i in range(1, 7) if i != last]
    return random.choice(candidates) if candidates else random.randint(1, 6)

def vtd_choose_alternate() -> int:
    if len(vtd_stats) < 2: return random.randint(1, 6)
    last = vtd_stats[-1]['winner']
    prev = vtd_stats[-2]['winner']
    if last == prev:
        candidates = [i for i in range(1, 7) if i != last]
        return random.choice(candidates) if candidates else random.randint(1, 6)
    return random.randint(1, 6)

def vtd_choose_second_last() -> int:
    if len(vtd_stats) < 2: return random.randint(1, 6)
    return vtd_stats[-2]['winner']

def vtd_choose_third_last() -> int:
    if len(vtd_stats) < 3: return random.randint(1, 6)
    return vtd_stats[-3]['winner']

def vtd_choose_balance() -> int:
    if not vtd_stats: return random.randint(1, 6)
    counts = Counter([h['winner'] for h in vtd_stats])
    avg = len(vtd_stats) / 6
    candidates = [i for i, c in counts.items() if abs(c - avg) < 1]
    return random.choice(candidates) if candidates else random.randint(1, 6)

def vtd_choose_middle_rank() -> int:
    if not vtd_stats: return random.randint(1, 6)
    ranks = [h['winner'] for h in vtd_stats]
    mid_counts = Counter([r for r in ranks if r in [3, 4]])
    return mid_counts.most_common(1)[0][0] if mid_counts else random.randint(1, 6)

def vtd_choose_extreme() -> int:
    if not vtd_stats: return random.randint(1, 6)
    ranks = [h['winner'] for h in vtd_stats]
    ext_counts = Counter([r for r in ranks if r in [1, 6]])
    return ext_counts.most_common(1)[0][0] if ext_counts else random.randint(1, 6)

def vtd_choose_against_trend() -> int:
    if len(vtd_stats) < 3: return random.randint(1, 6)
    last_winners = [h['winner'] for h in vtd_stats[-3:]]
    candidates = [i for i in range(1, 7) if i not in last_winners]
    return random.choice(candidates) if candidates else random.randint(1, 6)

def vtd_choose_follow_winner() -> int:
    if not vtd_stats: return random.randint(1, 6)
    return vtd_stats[-1]['winner']

def vtd_choose_follow_loser() -> int:
    if not vtd_stats: return random.randint(1, 6)
    return vtd_stats[-1]['loser']

def vtd_choose_random_pattern() -> int:
    if len(vtd_stats) < 3: return random.randint(1, 6)
    last_2 = [h['winner'] for h in vtd_stats[-2:]]
    for i in range(len(vtd_stats) - 3, -1, -1):
        if vtd_stats[i]['winner'] == last_2[0] and vtd_stats[i+1]['winner'] == last_2[1]:
            if i+2 < len(vtd_stats):
                return vtd_stats[i+2]['winner']
    return random.randint(1, 6)

def vtd_choose_vip_random() -> int:
    funcs = [
        vtd_choose_random, vtd_choose_hot, vtd_choose_cold,
        vtd_choose_last_bottom, vtd_choose_sequential, vtd_choose_trend_reverse,
        vtd_choose_most_consistent, vtd_choose_least_frequent, vtd_choose_most_frequent,
        vtd_choose_avoid_last, vtd_choose_alternate, vtd_choose_second_last,
        vtd_choose_third_last, vtd_choose_balance, vtd_choose_middle_rank,
        vtd_choose_extreme, vtd_choose_against_trend, vtd_choose_follow_winner,
        vtd_choose_follow_loser, vtd_choose_random_pattern
    ]
    return random.choice(funcs)()

def vtd_choose_markov() -> int:
    if len(vtd_stats) < 5: return random.randint(1, 6)
    transitions = defaultdict(lambda: defaultdict(int))
    for i in range(len(vtd_stats) - 1):
        transitions[vtd_stats[i]['winner']][vtd_stats[i+1]['winner']] += 1
    last = vtd_stats[-1]['winner']
    if transitions[last]:
        return max(transitions[last], key=transitions[last].get)
    return random.randint(1, 6)

def vtd_choose_bayes() -> int:
    if len(vtd_stats) < 5: return random.randint(1, 6)
    total = len(vtd_stats)
    likelihood = defaultdict(float)
    for h in vtd_stats:
        likelihood[h['winner']] += 1
    for i in range(1, 7):
        likelihood[i] = (likelihood[i] + 1) / (total + 6)
    posterior = {i: (1/6) * likelihood[i] for i in range(1, 7)}
    total_post = sum(posterior.values())
    for i in posterior:
        posterior[i] /= total_post
    return min(posterior, key=posterior.get)

def vtd_choose_neural() -> int:
    if len(vtd_stats) < 5: return random.randint(1, 6)
    scores = {}
    for i in range(1, 7):
        count = sum(1 for h in vtd_stats if h['winner'] == i)
        recency = sum(1 for h in vtd_stats[-5:] if h['winner'] == i) * 1.5
        scores[i] = count + recency
    return min(scores, key=scores.get)

def vtd_choose_fuzzy() -> int:
    if len(vtd_stats) < 3: return random.randint(1, 6)
    scores = {}
    for i in range(1, 7):
        count = sum(1 for h in vtd_stats if h['winner'] == i)
        scores[i] = 1.0 if count < 2 else 0.5 if count < 4 else 0.0
    return max(scores, key=scores.get)

def vtd_choose_genetic() -> int:
    if len(vtd_stats) < 3: return random.randint(1, 6)
    fitness = {}
    for i in range(1, 7):
        fitness[i] = sum(1 for h in vtd_stats if h['winner'] == i) / len(vtd_stats)
    return max(fitness, key=fitness.get)

def vtd_choose_ant_colony() -> int:
    if not vtd_stats: return random.randint(1, 6)
    pheromone = {}
    for i in range(1, 7):
        pheromone[i] = sum(1 for h in vtd_stats if h['winner'] == i) / len(vtd_stats)
    return min(pheromone, key=pheromone.get)

def vtd_choose_particle_swarm() -> int:
    if len(vtd_stats) < 3: return random.randint(1, 6)
    scores = {}
    for i in range(1, 7):
        count = sum(1 for h in vtd_stats if h['winner'] == i)
        recency = sum(1 for h in vtd_stats[-3:] if h['winner'] == i) * 0.8
        scores[i] = count + recency
    return max(scores, key=scores.get)

def vtd_choose_knn() -> int:
    if len(vtd_stats) < 3: return random.randint(1, 6)
    k = min(3, len(vtd_stats))
    nearest = [h['winner'] for h in vtd_stats[-k:]]
    counts = Counter(nearest)
    return min(counts, key=counts.get)

def vtd_choose_decision_tree() -> int:
    if len(vtd_stats) < 5: return random.randint(1, 6)
    last = vtd_stats[-1]['winner']
    if last in [1, 6]:
        candidates = [i for i in range(1, 7) if i != last]
        return random.choice(candidates) if candidates else random.randint(1, 6)
    return vtd_choose_random()

def vtd_choose_random_forest() -> int:
    predictions = []
    for _ in range(5):
        predictions.append(vtd_choose_hot() if random.random() > 0.5 else vtd_choose_cold())
    counts = Counter(predictions)
    return max(counts, key=counts.get)

def vtd_choose_gradient_boost() -> int:
    if len(vtd_stats) < 3: return random.randint(1, 6)
    scores = {}
    for i in range(1, 7):
        scores[i] = 0.5 + 0.3 * (sum(1 for h in vtd_stats if h['winner'] == i) / len(vtd_stats))
    return max(scores, key=scores.get)

def vtd_choose_lstm() -> int:
    if len(vtd_stats) < 4: return random.randint(1, 6)
    last_4 = [h['winner'] for h in vtd_stats[-4:]]
    if len(last_4) == 4 and last_4[0] == last_4[3]:
        return last_4[2]
    return vtd_choose_markov()

def vtd_choose_transformer() -> int:
    if len(vtd_stats) < 4: return random.randint(1, 6)
    attention = {}
    for i in range(1, 7):
        attention[i] = 1 - (sum(1 for h in vtd_stats if h['winner'] == i) / len(vtd_stats))
    return max(attention, key=attention.get)

def vtd_choose_ensemble() -> int:
    votes = defaultdict(int)
    funcs = [
        vtd_choose_markov, vtd_choose_bayes, vtd_choose_neural,
        vtd_choose_fuzzy, vtd_choose_genetic, vtd_choose_ant_colony,
        vtd_choose_particle_swarm, vtd_choose_knn, vtd_choose_decision_tree,
        vtd_choose_random_forest, vtd_choose_gradient_boost, vtd_choose_lstm,
        vtd_choose_transformer
    ]
    for func in funcs:
        try:
            votes[func()] += 1
        except:
            continue
    return max(votes, key=votes.get) if votes else random.randint(1, 6)

def vtd_choose_logic(mode: str) -> int:
    logic_map = {
        "RANDOM": vtd_choose_random, "HOT": vtd_choose_hot,
        "COLD": vtd_choose_cold, "LAST_BOTTOM": vtd_choose_last_bottom,
        "SEQUENTIAL": vtd_choose_sequential, "TREND_REVERSE": vtd_choose_trend_reverse,
        "MOST_CONSISTENT": vtd_choose_most_consistent, "LEAST_FREQUENT": vtd_choose_least_frequent,
        "MOST_FREQUENT": vtd_choose_most_frequent, "AVOID_LAST": vtd_choose_avoid_last,
        "ALTERNATE": vtd_choose_alternate, "SECOND_LAST": vtd_choose_second_last,
        "THIRD_LAST": vtd_choose_third_last, "BALANCE": vtd_choose_balance,
        "MIDDLE_RANK": vtd_choose_middle_rank, "EXTREME": vtd_choose_extreme,
        "AGAINST_TREND": vtd_choose_against_trend, "FOLLOW_WINNER": vtd_choose_follow_winner,
        "FOLLOW_LOSER": vtd_choose_follow_loser, "RANDOM_PATTERN": vtd_choose_random_pattern,
        "VIP_RANDOM": vtd_choose_vip_random, "MARKOV": vtd_choose_markov,
        "BAYES": vtd_choose_bayes, "NEURAL": vtd_choose_neural,
        "FUZZY": vtd_choose_fuzzy, "GENETIC": vtd_choose_genetic,
        "ANT_COLONY": vtd_choose_ant_colony, "PARTICLE_SWARM": vtd_choose_particle_swarm,
        "KNN": vtd_choose_knn, "DECISION_TREE": vtd_choose_decision_tree,
        "RANDOM_FOREST": vtd_choose_random_forest, "GRADIENT_BOOST": vtd_choose_gradient_boost,
        "LSTM": vtd_choose_lstm, "TRANSFORMER": vtd_choose_transformer,
        "ENSEMBLE": vtd_choose_ensemble,
    }
    func = logic_map.get(mode, vtd_choose_random)
    return func()

# ==================== API VTD ====================
VTD_HOME_API = "https://api.sprintrun.win/sprint/home"
VTD_BET_API = "https://api.sprintrun.win/sprint/bet"

def vtd_get_home(user_id: int, secret_key: str, asset: str = "BUILD") -> dict:
    headers = {'user-id': str(user_id), 'user-secret-key': secret_key}
    try:
        resp = requests.get(VTD_HOME_API, params={"asset": asset}, headers=headers, timeout=10)
        return resp.json()
    except:
        return {}

def vtd_place_bet(user_id: int, secret_key: str, issue_id: int, athlete_id: int, amount: float, bet_type: str = "not_winner") -> dict:
    headers = {'user-id': str(user_id), 'user-secret-key': secret_key, 'content-type': 'application/json'}
    payload = {"issue_id": issue_id, "bet_group": bet_type, "asset_type": "BUILD", "athlete_id": athlete_id, "bet_amount": amount}
    try:
        resp = requests.post(VTD_BET_API, headers=headers, json=payload, timeout=8)
        return resp.json()
    except Exception as e:
        return {"error": str(e)}

# ==================== API LOTTO ====================
LOTTO_HOME_API = "https://api.winhash.net/lucky_game/home"
LOTTO_BET_API = "https://api.winhash.net/lucky_game/v2/create_order"

LOTTO_LOGIC_DESCRIPTIONS = {
    "RANDOM": "1. Ngẫu nhiên (Random) - FREE",
    "HOT_COLD": "2. Số nóng/lạnh (Hot/Cold) - FREE",
    "TREND": "3. Xu hướng (Trend) - FREE",
    "PATTERN_MATCH": "4. So khớp mẫu (Pattern Match) - FREE",
    "LAST_3": "5. Dựa trên 3 số gần nhất (Last 3) - FREE",
    "MARKOV_CHAIN": "6. Chuỗi Markov (Markov Chain) - VIP",
    "BAYESIAN": "7. Xác suất Bayes (Bayesian) - VIP",
    "NEURAL": "8. Mạng nơ-ron (Neural Network) - VIP",
    "ENSEMBLE": "9. Tổng hợp AI (Ensemble) - VIP",
    "DEEP_LEARNING": "10. Học sâu (Deep Learning) - VIP",
}

def lotto_get_home(user_id: int, secret_key: str, asset: str = "BUILD") -> dict:
    headers = {'user-id': str(user_id), 'user-secret-key': secret_key, 'country-code': 'vn'}
    try:
        resp = requests.get(LOTTO_HOME_API, params={"game_id": 1, "asset": asset}, headers=headers, timeout=10)
        return resp.json()
    except:
        return {}

def lotto_place_bet(user_id: int, secret_key: str, issue_id: int, bet_type: str, amount: float, asset: str = "BUILD") -> dict:
    bet_ids = {"small": 70309, "big": 71218, "draw": 71011}
    headers = {'user-id': str(user_id), 'user-secret-key': secret_key, 'country-code': 'vn', 'content-type': 'application/json'}
    payload = {"game_id": 1, "issue_id": issue_id, "items": [{"id": bet_ids.get(bet_type, 70309), "amount": str(amount), "asset": asset}]}
    try:
        resp = requests.post(LOTTO_BET_API, headers=headers, json=payload, timeout=10)
        return resp.json()
    except Exception as e:
        return {"error": str(e)}

# ==================== USER STATE ====================
user_states = {}

def init_user_state(chat_id):
    if chat_id not in user_states:
        user_states[chat_id] = {
            'history': [],
            'auto_bet_enabled': False,
            'bet_amount': 10000,
            'base_bet': 10000,
            'x2_enabled': False,
            'current_prediction': None,
            'balance': 0,
            'win_streak': 0,
            'lose_streak': 0,
            'total_win': 0,
            'total_lose': 0,
            'profit_loss': 0,
            'vth_logic': 'RANDOM',
            'vtd_logic': 'RANDOM',
            'lotto_logic': 'RANDOM'
        }

# ==================== BOT COMMANDS ====================

@bot.message_handler(commands=['start'])
def send_start(message):
    cid = message.chat.id
    init_user_state(cid)
    
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton(f"{ICONS['vip']} Kích hoạt", callback_data='activate'),
        types.InlineKeyboardButton(f"{ICONS['shield']} VTH", callback_data='vth')
    )
    keyboard.add(
        types.InlineKeyboardButton(f"{ICONS['rocket']} VTD", callback_data='vtd'),
        types.InlineKeyboardButton(f"{ICONS['lotto']} LOTTO", callback_data='lotto')
    )
    keyboard.add(
        types.InlineKeyboardButton(f"{ICONS['user']} Tài khoản", callback_data='accounts'),
        types.InlineKeyboardButton(f"{ICONS['chart']} Thống kê", callback_data='stats')
    )
    keyboard.add(
        types.InlineKeyboardButton(f"{ICONS['settings']} Hướng dẫn", callback_data='help')
    )
    
    if check_auth(cid):
        is_valid, msg, is_vip = check_activation_valid()
        status = f"✅ {msg} 👑 VIP" if is_vip else f"✅ {msg}"
        text = f"""
{ICONS['crown']} *TBTOOL VIP ULTIMATE* {ICONS['crown']}

👤 *User:* {message.from_user.first_name}
📊 *Trạng thái:* {status}

{ICONS['brain']} *Công cụ hỗ trợ:*
• VUA THOÁT HIỂM - 40 Logic AI
• VUA TỐC ĐỘ - 35 Logic AI  
• LOTTO - 10 Logic AI

📌 *Lệnh:*
/nhapkey <key> - Kích hoạt
/add_acc <userId> <secretKey> - Thêm TK
/help - Hướng dẫn

📞 *LH: 0365463767*
"""
    else:
        text = f"""
{ICONS['crown']} *TBTOOL VIP ULTIMATE* {ICONS['crown']}

🔒 *TRẠNG THÁI: CHƯA KÍCH HOẠT*

{ICONS['key']} *Kích hoạt ngay:*
/nhapkey <mã_key>

📩 *Mua Key: {ADMIN_USERNAME}*
"""
    
    bot.reply_to(message, text, reply_markup=keyboard, parse_mode='Markdown')

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    cid = call.message.chat.id
    data = call.data
    
    if data == 'activate':
        bot.answer_callback_query(call.id)
        bot.send_message(cid, f"""
{ICONS['key']} *KÍCH HOẠT TBTOOL*

Dùng lệnh: `/nhapkey <mã_key>`

Ví dụ: `/nhapkey VIP-ABCD1234`

📞 *Mua Key: {ADMIN_USERNAME}*
""", parse_mode='Markdown')
    
    elif data == 'vth':
        bot.answer_callback_query(call.id)
        if not check_auth(cid):
            bot.send_message(cid, locked_msg(), parse_mode='HTML')
            return
        bot.send_message(cid, f"""
{ICONS['shield']} *VUA THOÁT HIỂM*

📊 *40 Logic AI (20 FREE + 20 VIP)*
{ICONS['info']} Dùng /vth_logic <số> để chọn logic
Ví dụ: `/vth_logic 1` cho RANDOM

{ICONS['target']} Để chạy:
/vth_start <cược> <hệ số>
Ví dụ: `/vth_start 1 2`
""", parse_mode='Markdown')
    
    elif data == 'vtd':
        bot.answer_callback_query(call.id)
        if not check_auth(cid):
            bot.send_message(cid, locked_msg(), parse_mode='HTML')
            return
        bot.send_message(cid, f"""
{ICONS['rocket']} *VUA TỐC ĐỘ*

📊 *35 Logic AI (20 FREE + 15 VIP)*
{ICONS['info']} Dùng /vtd_logic <số> để chọn logic
Ví dụ: `/vtd_logic 1` cho RANDOM

{ICONS['target']} Để chạy:
/vtd_start <cược> <hệ số>
""", parse_mode='Markdown')
    
    elif data == 'lotto':
        bot.answer_callback_query(call.id)
        if not check_auth(cid):
            bot.send_message(cid, locked_msg(), parse_mode='HTML')
            return
        bot.send_message(cid, f"""
{ICONS['lotto']} *LOTTO*

📊 *10 Logic AI (5 FREE + 5 VIP)*
{ICONS['info']} Dùng /lotto_logic <số> để chọn logic
Ví dụ: `/lotto_logic 1` cho RANDOM

{ICONS['target']} Để chạy:
/lotto_start <cược> <hệ số>
""", parse_mode='Markdown')
    
    elif data == 'accounts':
        bot.answer_callback_query(call.id)
        accounts = load_accounts()
        if not accounts:
            text = f"{ICONS['warning']} *Chưa có tài khoản!*\n\nDùng /add_acc <userId> <secretKey>"
        else:
            text = f"{ICONS['user']} *Danh sách tài khoản:*\n\n"
            for i, acc in enumerate(accounts, 1):
                text += f"{i}. 🆔 `{acc.get('userId')}`\n"
        bot.send_message(cid, text, parse_mode='Markdown')
    
    elif data == 'stats':
        bot.answer_callback_query(call.id)
        is_valid, msg, is_vip = check_activation_valid()
        status = f"✅ {msg} 👑 VIP" if is_vip else f"✅ {msg}" if is_valid else f"❌ {msg}"
        accounts = load_accounts()
        text = f"""
{ICONS['chart']} *THỐNG KÊ TBTOOL*

📊 *Trạng thái Key:* {status}
{ICONS['user']} *Số tài khoản:* {len(accounts)}
{ICONS['brain']} *Logic FREE:* 45
{ICONS['vip']} *Logic VIP:* 40
{ICONS['crown']} *Tổng cộng:* 85 Logic AI

📞 *Support: 0365463767*
"""
        bot.send_message(cid, text, parse_mode='Markdown')
    
    elif data == 'help':
        bot.answer_callback_query(call.id)
        text = f"""
{ICONS['info']} *HƯỚNG DẪN TBTOOL*

*Lệnh cơ bản:*
/start - Menu chính
/nhapkey <key> - Kích hoạt Key
/add_acc <userId> <secretKey> - Thêm tài khoản
/del_acc <userId> - Xóa tài khoản
/list_acc - Xem danh sách

*VUA THOÁT HIỂM:*
/vth_logic <số> - Chọn logic (1-40)
/vth_start <cược> <hệ số> - Chạy VTH
/vth_stop - Dừng VTH

*VUA TỐC ĐỘ:*
/vtd_logic <số> - Chọn logic (1-35)
/vtd_start <cược> <hệ số> - Chạy VTD
/vtd_stop - Dừng VTD

*LOTTO:*
/lotto_logic <số> - Chọn logic (1-10)
/lotto_start <cược> <hệ số> - Chạy LOTTO
/lotto_stop - Dừng LOTTO

📞 *Support: 0365463767*
"""
        bot.send_message(cid, text, parse_mode='Markdown')

@bot.message_handler(commands=['nhapkey'])
def send_nhapkey(message):
    cid = message.chat.id
    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message, f"""
{ICONS['warning']} *Cách dùng:*
/nhapkey <mã_key>

Ví dụ: `/nhapkey VIP-ABCD1234`
""", parse_mode='Markdown')
        return
    
    key = parts[1].strip()
    device_id = get_device_id()
    
    if key in valid_keys:
        duration_days = valid_keys[key]
        duration_hours = duration_days * 24
        now = datetime.now()
        
        if save_activation(device_id, key, now, duration_hours, "VIP"):
            del valid_keys[key]
            save_data()
            bot.reply_to(message, f"""
{ICONS['check']} *Kích hoạt thành công!*

{ICONS['vip']} *Loại:* VIP
⏰ *Thời hạn:* {duration_days} ngày
{ICONS['crown']} *Quyền lợi:* 85 Logic AI

📞 *Support: 0365463767*
""", parse_mode='Markdown')
        else:
            bot.reply_to(message, f"{ICONS['cross']} *Lỗi kích hoạt!*", parse_mode='Markdown')
    else:
        bot.reply_to(message, f"""
{ICONS['cross']} *Key không hợp lệ hoặc đã dùng!*

📩 *Mua Key mới: {ADMIN_USERNAME}*
""", parse_mode='Markdown')

@bot.message_handler(commands=['add_acc'])
def send_add_acc(message):
    cid = message.chat.id
    if not check_auth(cid):
        bot.reply_to(message, locked_msg(), parse_mode='HTML')
        return
    
    parts = message.text.split()
    if len(parts) < 3:
        bot.reply_to(message, f"""
{ICONS['warning']} *Cách dùng:*
/add_acc <userId> <secretKey>

Ví dụ: `/add_acc 12345 abc123`
""", parse_mode='Markdown')
        return
    
    try:
        user_id = int(parts[1])
        secret_key = parts[2]
        accounts = load_accounts()
        
        if any(acc.get('userId') == user_id for acc in accounts):
            bot.reply_to(message, f"{ICONS['warning']} *Tài khoản {user_id} đã tồn tại!*", parse_mode='Markdown')
            return
        
        accounts.append({"userId": user_id, "secretKey": secret_key, "game": "Chung"})
        save_accounts(accounts)
        
        balance = get_balance(user_id, secret_key)
        build_balance = balance.get('BUILD', 0)
        
        bot.reply_to(message, f"""
{ICONS['check']} *Đã thêm tài khoản!*

🆔 *User ID:* `{user_id}`
💰 *Số dư:* {build_balance:,.2f} BUILD
""", parse_mode='Markdown')
    except ValueError:
        bot.reply_to(message, f"{ICONS['cross']} *User ID phải là số!*", parse_mode='Markdown')

@bot.message_handler(commands=['del_acc'])
def send_del_acc(message):
    cid = message.chat.id
    if not check_auth(cid):
        bot.reply_to(message, locked_msg(), parse_mode='HTML')
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message, f"""
{ICONS['warning']} *Cách dùng:*
/del_acc <userId>

Ví dụ: `/del_acc 12345`
""", parse_mode='Markdown')
        return
    
    try:
        user_id = int(parts[1])
        accounts = load_accounts()
        for i, acc in enumerate(accounts):
            if acc.get('userId') == user_id:
                accounts.pop(i)
                save_accounts(accounts)
                bot.reply_to(message, f"{ICONS['check']} *Đã xóa tài khoản {user_id}*", parse_mode='Markdown')
                return
        bot.reply_to(message, f"{ICONS['cross']} *Không tìm thấy tài khoản {user_id}*", parse_mode='Markdown')
    except ValueError:
        bot.reply_to(message, f"{ICONS['cross']} *User ID phải là số!*", parse_mode='Markdown')

@bot.message_handler(commands=['list_acc'])
def send_list_acc(message):
    cid = message.chat.id
    if not check_auth(cid):
        bot.reply_to(message, locked_msg(), parse_mode='HTML')
        return
    
    accounts = load_accounts()
    if not accounts:
        bot.reply_to(message, f"{ICONS['warning']} *Chưa có tài khoản nào!*", parse_mode='Markdown')
        return
    
    text = f"{ICONS['user']} *Danh sách tài khoản:*\n\n"
    for i, acc in enumerate(accounts, 1):
        text += f"{i}. 🆔 `{acc.get('userId')}`\n"
    bot.reply_to(message, text, parse_mode='Markdown')

@bot.message_handler(commands=['vth_logic'])
def send_vth_logic(message):
    cid = message.chat.id
    if not check_auth(cid):
        bot.reply_to(message, locked_msg(), parse_mode='HTML')
        return
    
    args = message.text.split()
    if len(args) < 2:
        text = f"{ICONS['warning']} *Cách dùng:* `/vth_logic <số>`\n\n"
        for i, (k, v) in enumerate(list(VTH_LOGIC_DESCRIPTIONS.items())[:10], 1):
            text += f"{i}. {v}\n"
        text += f"\n... và {len(VTH_LOGIC_DESCRIPTIONS)-10} logic khác"
        bot.reply_to(message, text, parse_mode='Markdown')
        return
    
    try:
        num = int(args[1])
        logic_list = list(VTH_LOGIC_DESCRIPTIONS.items())
        is_vip = is_vip_activated()
        
        if not is_vip:
            vip_keys = [k for k, _ in logic_list if "VIP" in k]
            logic_list = [(k, v) for k, v in logic_list if k not in vip_keys]
        
        if 1 <= num <= len(logic_list):
            selected_key, selected_desc = logic_list[num - 1]
            user_states[cid]['vth_logic'] = selected_key
            bot.reply_to(message, f"""
{ICONS['check']} *Đã chọn logic VTH:*

📌 `{selected_desc}`
🔑 *Mã:* `{selected_key}`

{ICONS['target']} Để chạy:
/vth_start <cược> <hệ số>
Ví dụ: `/vth_start 1 2`
""", parse_mode='Markdown')
        else:
            bot.reply_to(message, f"{ICONS['cross']} *Số từ 1 đến {len(logic_list)}*", parse_mode='Markdown')
    except ValueError:
        bot.reply_to(message, f"{ICONS['cross']} *Phải nhập số!*", parse_mode='Markdown')

@bot.message_handler(commands=['vth_start'])
def send_vth_start(message):
    cid = message.chat.id
    if not check_auth(cid):
        bot.reply_to(message, locked_msg(), parse_mode='HTML')
        return
    
    args = message.text.split()
    if len(args) < 3:
        bot.reply_to(message, f"""
{ICONS['warning']} *Cách dùng:*
/vth_start <cược> <hệ số>

Ví dụ: `/vth_start 1 2`
""", parse_mode='Markdown')
        return
    
    try:
        bet_amount = float(args[1])
        multiplier = float(args[2])
        logic = user_states.get(cid, {}).get('vth_logic', 'RANDOM')
        is_vip = is_vip_activated()
        
        accounts = load_accounts()
        if not accounts:
            bot.reply_to(message, f"{ICONS['warning']} *Chưa có tài khoản!*\nDùng /add_acc để thêm", parse_mode='Markdown')
            return
        
        acc = accounts[0]
        balance = get_balance(acc['userId'], acc['secretKey'])
        build_balance = balance.get('BUILD', 0)
        
        if build_balance < bet_amount:
            bot.reply_to(message, f"""
{ICONS['cross']} *Số dư không đủ!*
💰 Có: {build_balance:,.2f} BUILD
📌 Cần: {bet_amount:,.2f} BUILD
""", parse_mode='Markdown')
            return
        
        bot.reply_to(message, f"""
{ICONS['rocket']} *ĐANG CHẠY VTH*

📌 *Logic:* `{logic}`
🆔 *TK:* `{acc['userId']}`
💰 *Cược:* {bet_amount} BUILD
📈 *Hệ số:* x{multiplier}
👑 *Mode:* {'VIP' if is_vip else 'FREE'}
""", parse_mode='Markdown')
        
        def run_vth():
            chosen_room = choose_room_vth(logic)
            result = vth_place_bet(acc['userId'], acc['secretKey'], 0, chosen_room, bet_amount)
            bot.send_message(cid, f"""
{ICONS['target']} *Đã đặt cược VTH*

🏠 *Phòng:* {ROOM_NAMES.get(chosen_room, chosen_room)}
💰 *Tiền:* {bet_amount} BUILD
📊 *Kết quả:* {result.get('msg', 'Đã gửi')}
""", parse_mode='Markdown')
        
        thread = threading.Thread(target=run_vth, daemon=True)
        thread.start()
        
    except ValueError:
        bot.reply_to(message, f"{ICONS['cross']} *Số tiền và hệ số phải là số!*", parse_mode='Markdown')

@bot.message_handler(commands=['vth_stop'])
def send_vth_stop(message):
    bot.reply_to(message, f"{ICONS['check']} *Đã dừng VTH*", parse_mode='Markdown')

@bot.message_handler(commands=['vtd_logic'])
def send_vtd_logic(message):
    cid = message.chat.id
    if not check_auth(cid):
        bot.reply_to(message, locked_msg(), parse_mode='HTML')
        return
    
    args = message.text.split()
    if len(args) < 2:
        text = f"{ICONS['warning']} *Cách dùng:* `/vtd_logic <số>`\n\n"
        for i, (k, v) in enumerate(list(VTD_LOGIC_DESCRIPTIONS.items())[:10], 1):
            text += f"{i}. {v}\n"
        text += f"\n... và {len(VTD_LOGIC_DESCRIPTIONS)-10} logic khác"
        bot.reply_to(message, text, parse_mode='Markdown')
        return
    
    try:
        num = int(args[1])
        logic_list = list(VTD_LOGIC_DESCRIPTIONS.items())
        is_vip = is_vip_activated()
        
        if not is_vip:
            vip_keys = [k for k, _ in logic_list if "VIP" in k]
            logic_list = [(k, v) for k, v in logic_list if k not in vip_keys]
        
        if 1 <= num <= len(logic_list):
            selected_key, selected_desc = logic_list[num - 1]
            user_states[cid]['vtd_logic'] = selected_key
            bot.reply_to(message, f"""
{ICONS['check']} *Đã chọn logic VTD:*

📌 `{selected_desc}`
🔑 *Mã:* `{selected_key}`

{ICONS['target']} Để chạy:
/vtd_start <cược> <hệ số>
""", parse_mode='Markdown')
        else:
            bot.reply_to(message, f"{ICONS['cross']} *Số từ 1 đến {len(logic_list)}*", parse_mode='Markdown')
    except ValueError:
        bot.reply_to(message, f"{ICONS['cross']} *Phải nhập số!*", parse_mode='Markdown')

@bot.message_handler(commands=['vtd_start'])
def send_vtd_start(message):
    cid = message.chat.id
    if not check_auth(cid):
        bot.reply_to(message, locked_msg(), parse_mode='HTML')
        return
    
    args = message.text.split()
    if len(args) < 3:
        bot.reply_to(message, f"""
{ICONS['warning']} *Cách dùng:*
/vtd_start <cược> <hệ số>

Ví dụ: `/vtd_start 1 2`
""", parse_mode='Markdown')
        return
    
    try:
        bet_amount = float(args[1])
        multiplier = float(args[2])
        logic = user_states.get(cid, {}).get('vtd_logic', 'RANDOM')
        is_vip = is_vip_activated()
        
        accounts = load_accounts()
        if not accounts:
            bot.reply_to(message, f"{ICONS['warning']} *Chưa có tài khoản!*", parse_mode='Markdown')
            return
        
        acc = accounts[0]
        balance = get_balance(acc['userId'], acc['secretKey'])
        build_balance = balance.get('BUILD', 0)
        
        if build_balance < bet_amount:
            bot.reply_to(message, f"""
{ICONS['cross']} *Số dư không đủ!*
💰 Có: {build_balance:,.2f} BUILD
""", parse_mode='Markdown')
            return
        
        bot.reply_to(message, f"""
{ICONS['rocket']} *ĐANG CHẠY VTD*

📌 *Logic:* `{logic}`
🆔 *TK:* `{acc['userId']}`
💰 *Cược:* {bet_amount} BUILD
📈 *Hệ số:* x{multiplier}
👑 *Mode:* {'VIP' if is_vip else 'FREE'}
""", parse_mode='Markdown')
        
        def run_vtd():
            athlete = vtd_choose_logic(logic)
            result = vtd_place_bet(acc['userId'], acc['secretKey'], 0, athlete, bet_amount)
            bot.send_message(cid, f"""
{ICONS['target']} *Đã đặt cược VTD*

🏃 *VĐV:* {VTD_ATHLETES.get(athlete, athlete)}
💰 *Tiền:* {bet_amount} BUILD
📊 *KQ:* {result.get('msg', 'Đã gửi')}
""", parse_mode='Markdown')
        
        thread = threading.Thread(target=run_vtd, daemon=True)
        thread.start()
        
    except ValueError:
        bot.reply_to(message, f"{ICONS['cross']} *Số tiền và hệ số phải là số!*", parse_mode='Markdown')

@bot.message_handler(commands=['vtd_stop'])
def send_vtd_stop(message):
    bot.reply_to(message, f"{ICONS['check']} *Đã dừng VTD*", parse_mode='Markdown')

@bot.message_handler(commands=['lotto_logic'])
def send_lotto_logic(message):
    cid = message.chat.id
    if not check_auth(cid):
        bot.reply_to(message, locked_msg(), parse_mode='HTML')
        return
    
    args = message.text.split()
    if len(args) < 2:
        text = f"{ICONS['warning']} *Cách dùng:* `/lotto_logic <số>`\n\n"
        for i, (k, v) in enumerate(LOTTO_LOGIC_DESCRIPTIONS.items(), 1):
            text += f"{i}. {v}\n"
        bot.reply_to(message, text, parse_mode='Markdown')
        return
    
    try:
        num = int(args[1])
        logic_list = list(LOTTO_LOGIC_DESCRIPTIONS.items())
        is_vip = is_vip_activated()
        
        if not is_vip:
            vip_keys = [k for k, _ in logic_list if "VIP" in k]
            logic_list = [(k, v) for k, v in logic_list if k not in vip_keys]
        
        if 1 <= num <= len(logic_list):
            selected_key, selected_desc = logic_list[num - 1]
            user_states[cid]['lotto_logic'] = selected_key
            bot.reply_to(message, f"""
{ICONS['check']} *Đã chọn logic LOTTO:*

📌 `{selected_desc}`
🔑 *Mã:* `{selected_key}`

{ICONS['target']} Để chạy:
/lotto_start <cược> <hệ số>
""", parse_mode='Markdown')
        else:
            bot.reply_to(message, f"{ICONS['cross']} *Số từ 1 đến {len(logic_list)}*", parse_mode='Markdown')
    except ValueError:
        bot.reply_to(message, f"{ICONS['cross']} *Phải nhập số!*", parse_mode='Markdown')

@bot.message_handler(commands=['lotto_start'])
def send_lotto_start(message):
    cid = message.chat.id
    if not check_auth(cid):
        bot.reply_to(message, locked_msg(), parse_mode='HTML')
        return
    
    args = message.text.split()
    if len(args) < 3:
        bot.reply_to(message, f"""
{ICONS['warning']} *Cách dùng:*
/lotto_start <cược> <hệ số>

Ví dụ: `/lotto_start 1 2`
""", parse_mode='Markdown')
        return
    
    try:
        bet_amount = float(args[1])
        multiplier = float(args[2])
        logic = user_states.get(cid, {}).get('lotto_logic', 'RANDOM')
        is_vip = is_vip_activated()
        
        accounts = load_accounts()
        if not accounts:
            bot.reply_to(message, f"{ICONS['warning']} *Chưa có tài khoản!*", parse_mode='Markdown')
            return
        
        acc = accounts[0]
        balance = get_balance(acc['userId'], acc['secretKey'])
        build_balance = balance.get('BUILD', 0)
        
        if build_balance < bet_amount:
            bot.reply_to(message, f"""
{ICONS['cross']} *Số dư không đủ!*
💰 Có: {build_balance:,.2f} BUILD
""", parse_mode='Markdown')
            return
        
        bot.reply_to(message, f"""
{ICONS['rocket']} *ĐANG CHẠY LOTTO*

📌 *Logic:* `{logic}`
🆔 *TK:* `{acc['userId']}`
💰 *Cược:* {bet_amount} BUILD
📈 *Hệ số:* x{multiplier}
👑 *Mode:* {'VIP' if is_vip else 'FREE'}
""", parse_mode='Markdown')
        
        def run_lotto():
            bet_types = ["small", "big", "draw"]
            bet_type = random.choice(bet_types)
            result = lotto_place_bet(acc['userId'], acc['secretKey'], 0, bet_type, bet_amount)
            bot.send_message(cid, f"""
{ICONS['target']} *Đã đặt cược LOTTO*

🎯 *Loại:* {bet_type.upper()}
💰 *Tiền:* {bet_amount} BUILD
📊 *KQ:* {result.get('msg', 'Đã gửi')}
""", parse_mode='Markdown')
        
        thread = threading.Thread(target=run_lotto, daemon=True)
        thread.start()
        
    except ValueError:
        bot.reply_to(message, f"{ICONS['cross']} *Số tiền và hệ số phải là số!*", parse_mode='Markdown')

@bot.message_handler(commands=['lotto_stop'])
def send_lotto_stop(message):
    bot.reply_to(message, f"{ICONS['check']} *Đã dừng LOTTO*", parse_mode='Markdown')

@bot.message_handler(commands=['help'])
def send_help(message):
    text = f"""
{ICONS['info']} *HƯỚNG DẪN TBTOOL*

*Lệnh cơ bản:*
/start - Menu chính
/nhapkey <key> - Kích hoạt Key
/add_acc <userId> <secretKey> - Thêm tài khoản
/del_acc <userId> - Xóa tài khoản
/list_acc - Xem danh sách

*VUA THOÁT HIỂM:*
/vth_logic <số> - Chọn logic (1-40)
/vth_start <cược> <hệ số> - Chạy VTH
/vth_stop - Dừng VTH

*VUA TỐC ĐỘ:*
/vtd_logic <số> - Chọn logic (1-35)
/vtd_start <cược> <hệ số> - Chạy VTD
/vtd_stop - Dừng VTD

*LOTTO:*
/lotto_logic <số> - Chọn logic (1-10)
/lotto_start <cược> <hệ số> - Chạy LOTTO
/lotto_stop - Dừng LOTTO

📞 *Support: 0365463767*
"""
    bot.reply_to(message, text, parse_mode='Markdown')

@bot.message_handler(commands=['taokey'])
def send_taokey(message):
    cid = message.chat.id
    if cid not in ADMIN_ID:
        bot.reply_to(message, "⛔ Chỉ admin mới có quyền!")
        return
    
    args = message.text.split()
    days = 30
    if len(args) > 1 and args[1].isdigit():
        days = int(args[1])
    
    key = generate_key("VIP", days)
    bot.reply_to(message, f"""
{ICONS['check']} *ĐÃ TẠO KEY VIP*

🔑 *Key:* `{key}`
⏰ *Thời hạn:* {days} ngày
📊 *Tổng key còn lại:* {len(valid_keys)}
""", parse_mode='Markdown')

@bot.message_handler(commands=['danhsachkey'])
def send_danhsachkey(message):
    cid = message.chat.id
    if cid not in ADMIN_ID:
        bot.reply_to(message, "⛔ Chỉ admin!")
        return
    
    if not valid_keys:
        bot.reply_to(message, "📭 Không có key nào!")
        return
    
    text = f"{ICONS['chart']} *DANH SÁCH KEY*\n\n"
    for k, v in valid_keys.items():
        text += f"• `{k}` - {v} ngày\n"
    text += f"\n📊 *Tổng:* {len(valid_keys)} key"
    bot.reply_to(message, text, parse_mode='Markdown')

# ==================== WEBHOOK ROUTE ====================
@app.route(f'/{BOT_TOKEN}', methods=['POST'])
def webhook():
    try:
        json_data = request.get_json()
        if json_data is None:
            return 'Bad Request', 400
        
        update = telebot.types.Update.de_json(json_data)
        bot.process_new_updates([update])
        return 'OK', 200
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return 'Error', 500

# ==================== TRANG CHỦ ====================
@app.route('/', methods=['GET'])
def index():
    return '🚀 TBTOOL VIP BOT ĐANG HOẠT ĐỘNG!'

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok", "time": datetime.now().isoformat()})

# ==================== MAIN ====================
if __name__ == '__main__':
    logger.info("🚀 TBTOOL VIP BOT đang khởi động...")
    logger.info(f"📱 BOT_TOKEN: {BOT_TOKEN[:10]}...")
    logger.info(f"🔗 WEBHOOK_URL: {WEBHOOK_URL}")
    logger.info(f"🔌 PORT: {PORT}")
    
    # Xóa webhook cũ
    try:
        bot.remove_webhook()
        time.sleep(1)
        logger.info("✅ Đã xóa webhook cũ")
    except Exception as e:
        logger.warning(f"Không xóa được webhook cũ: {e}")
    
    # Set webhook mới
    webhook_url = f"{WEBHOOK_URL}/{BOT_TOKEN}"
    try:
        result = bot.set_webhook(url=webhook_url)
        logger.info(f"✅ Set webhook: {webhook_url} - {result}")
    except Exception as e:
        logger.error(f"❌ Lỗi set webhook: {e}")
    
    # Chạy Flask
    logger.info("🚀 Đang chạy Flask server...")
    app.run(host='0.0.0.0', port=PORT, debug=False, threaded=True)
