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
from collections import defaultdict, deque, Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import urllib.parse

import pytz
import requests

try:
    import websocket
except ImportError:
    websocket = None

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ParseMode
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, CallbackContext

# ==================== LOGGING ====================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ==================== CONSTANTS ====================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8793013165:AAHLrFq615paXg88anY1BDqpG457oce37gY")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "7564889663"))
PORT = int(os.environ.get("PORT", 8443))
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "https://tbtool.onrender.com")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN khong duoc de trong!")
if not WEBHOOK_URL:
    raise ValueError("WEBHOOK_URL khong duoc de trong!")

tz = pytz.timezone("Asia/Ho_Chi_Minh")

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
ACTIVATION_FILE = "activation_tbtool.dat"
ACCOUNTS_FILE = "accounts.json"
KEYS_FILE = "keys.json"
SALT = "TbToolKeySalt2026"
ENCRYPTION_KEY = hashlib.sha256(b"TbTool_SECURE_KEY_2026_XxX_VIP").digest()

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
        expected_checksum = hashlib.sha256(
            f"{data.get('device_id', '')}:{data.get('key', '')}:{data.get('activation_time', '')}:{SALT}".encode()
        ).hexdigest()
        if data.get("checksum") != expected_checksum:
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
        if key_type == "FREE":
            vn_now = datetime.now(tz)
            today_midnight = vn_now.replace(hour=0, minute=0, second=0, microsecond=0)
            if vn_now >= today_midnight:
                next_midnight = today_midnight + timedelta(days=1)
            else:
                next_midnight = today_midnight
            if vn_now >= next_midnight:
                try:
                    os.remove(ACTIVATION_FILE)
                except: pass
                return False, "Key FREE đã reset", False
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

# ==================== KEY MANAGEMENT (ADMIN) ====================
def load_keys() -> dict:
    if Path(KEYS_FILE).exists():
        try:
            with open(KEYS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except: pass
    return {"keys": [], "next_id": 1}

def save_keys(keys_data: dict):
    with open(KEYS_FILE, 'w', encoding='utf-8') as f:
        json.dump(keys_data, f, indent=2)

def generate_key(key_type: str = "VIP", duration_hours: int = 87600) -> str:
    keys_data = load_keys()
    key_id = keys_data["next_id"]
    keys_data["next_id"] += 1
    
    if key_type == "VIP":
        duration_map = {
            24: "1D", 72: "3D", 168: "7D", 360: "15D",
            720: "30D", 4320: "6M", 8760: "1Y", 87600: "FOREVER"
        }
        duration_code = duration_map.get(duration_hours, "FOREVER")
        random_part = secrets.token_hex(4).upper()
        key = f"TBTOOL_VIP_{duration_code}_{random_part}"
    else:
        key = secrets.token_hex(4).upper()
    
    keys_data["keys"].append({
        "id": key_id,
        "key": key,
        "type": key_type,
        "duration_hours": duration_hours,
        "created_at": datetime.now().isoformat(),
        "used": False,
        "used_by": None,
        "used_at": None
    })
    save_keys(keys_data)
    return key

def verify_key_from_db(key: str) -> Optional[Dict]:
    keys_data = load_keys()
    for k in keys_data["keys"]:
        if k["key"] == key and not k.get("used", False):
            return k
    return None

def mark_key_used(key: str, device_id: str) -> bool:
    keys_data = load_keys()
    for k in keys_data["keys"]:
        if k["key"] == key and not k.get("used", False):
            k["used"] = True
            k["used_by"] = device_id
            k["used_at"] = datetime.now().isoformat()
            save_keys(keys_data)
            return True
    return False

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
        parsed = urllib.parse.urlparse(link)
        params = urllib.parse.parse_qs(parsed.query)
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

# ==================== API VTH ====================
VTH_BET_API = "https://api.escapemaster.net/escape_game/bet"
VTH_WS_URL = "wss://api.escapemaster.net/escape_master/ws"

def vth_place_bet(user_id: int, secret_key: str, issue_id: int, room_id: int, amount: float) -> dict:
    headers = {
        'user-id': str(user_id),
        'user-secret-key': secret_key,
        'content-type': 'application/json'
    }
    payload = {
        "asset_type": "BUILD",
        "user_id": user_id,
        "room_id": room_id,
        "bet_amount": amount
    }
    try:
        resp = requests.post(VTH_BET_API, headers=headers, json=payload, timeout=8)
        return resp.json()
    except Exception as e:
        return {"error": str(e)}

def vth_ws_connect(user_id: int, secret_key: str, on_message_callback):
    def on_open(ws):
        payload = {
            "msg_type": "handle_enter_game",
            "asset_type": "BUILD",
            "user_id": user_id,
            "user_secret_key": secret_key
        }
        ws.send(json.dumps(payload))
    
    def on_message(ws, message):
        try:
            data = json.loads(message)
            on_message_callback(data)
        except:
            pass
    
    if websocket:
        ws = websocket.WebSocketApp(
            VTH_WS_URL,
            on_open=on_open,
            on_message=on_message,
            on_error=lambda ws, err: logger.error(f"WS error: {err}"),
            on_close=lambda ws, code, reason: logger.info(f"WS closed: {reason}")
        )
        thread = threading.Thread(target=ws.run_forever, daemon=True)
        thread.start()
        return ws
    return None

# ==================== API VTD ====================
VTD_HOME_API = "https://api.sprintrun.win/sprint/home"
VTD_BET_API = "https://api.sprintrun.win/sprint/bet"
VTD_RESULT_API = "https://api.sprintrun.win/sprint/issue_result"

def vtd_get_home(user_id: int, secret_key: str, asset: str = "BUILD") -> dict:
    headers = {
        'user-id': str(user_id),
        'user-secret-key': secret_key,
        'content-type': 'application/json'
    }
    try:
        resp = requests.get(VTD_HOME_API, params={"asset": asset}, headers=headers, timeout=10)
        return resp.json()
    except:
        return {}

def vtd_place_bet(user_id: int, secret_key: str, issue_id: int, athlete_id: int, amount: float, bet_type: str = "not_winner") -> dict:
    headers = {
        'user-id': str(user_id),
        'user-secret-key': secret_key,
        'content-type': 'application/json'
    }
    payload = {
        "issue_id": issue_id,
        "bet_group": bet_type,
        "asset_type": "BUILD",
        "athlete_id": athlete_id,
        "bet_amount": amount
    }
    try:
        resp = requests.post(VTD_BET_API, headers=headers, json=payload, timeout=8)
        return resp.json()
    except Exception as e:
        return {"error": str(e)}

# ==================== API LOTTO ====================
LOTTO_HOME_API = "https://api.winhash.net/lucky_game/home"
LOTTO_BET_API = "https://api.winhash.net/lucky_game/v2/create_order"

def lotto_get_home(user_id: int, secret_key: str, asset: str = "BUILD") -> dict:
    headers = {
        'user-id': str(user_id),
        'user-secret-key': secret_key,
        'content-type': 'application/json',
        'country-code': 'vn'
    }
    try:
        resp = requests.get(LOTTO_HOME_API, params={"game_id": 1, "asset": asset}, headers=headers, timeout=10)
        return resp.json()
    except:
        return {}

def lotto_place_bet(user_id: int, secret_key: str, issue_id: int, bet_type: str, amount: float, asset: str = "BUILD") -> dict:
    bet_ids = {"small": 70309, "big": 71218, "draw": 71011}
    headers = {
        'user-id': str(user_id),
        'user-secret-key': secret_key,
        'content-type': 'application/json',
        'country-code': 'vn'
    }
    payload = {
        "game_id": 1,
        "issue_id": issue_id,
        "items": [{"id": bet_ids.get(bet_type, 70309), "amount": str(amount), "asset": asset}]
    }
    try:
        resp = requests.post(LOTTO_BET_API, headers=headers, json=payload, timeout=10)
        return resp.json()
    except Exception as e:
        return {"error": str(e)}

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

room_state = {r: {"players": 0, "bet": 0} for r in ROOM_ORDER}
room_stats = {r: {"kills": 0, "survives": 0} for r in ROOM_ORDER}
killer_history = deque(maxlen=20)
game_kill_log = deque(maxlen=10)
last_killed_room = None
last_killed_room_delayed = None
_sequential_bet_index = 0

# ==== 20 LOGIC FREE ====
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

# ==== 20 LOGIC VIP ====
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

# ==================== VTD - 35 LOGIC ====================
VTD_ATHLETES = {
    1: "⚔️ Bậc thầy tấn công",
    2: "🛡️ Quyền sắt",
    3: "🏊 Thợ lặn sâu",
    4: "🌪️ Cơn lốc sân cỏ",
    5: "🏇 Hiệp sĩ phi nhanh",
    6: "🏆 Vua home run"
}

VTD_ATHLETE_FULL = {
    1: "VĐV 1 - Bậc thầy tấn công",
    2: "VĐV 2 - Quyền sắt",
    3: "VĐV 3 - Thợ lặn sâu",
    4: "VĐV 4 - Cơn lốc sân cỏ",
    5: "VĐV 5 - Hiệp sĩ phi nhanh",
    6: "VĐV 6 - Vua home run"
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

# ==================== LOTTO - 10 LOGIC ====================
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

# ==================== BOT HANDLERS ====================
# (Tôi sẽ viết tiếp phần handlers trong comment tiếp theo vì quá dài)

def start(update: Update, context: CallbackContext):
    user = update.effective_user
    is_admin = user.id == ADMIN_ID
    
    keyboard = []
    if is_admin:
        keyboard.append([InlineKeyboardButton(f"{ICONS['admin']} ADMIN PANEL", callback_data='admin')])
    keyboard.extend([
        [InlineKeyboardButton(f"{ICONS['vip']} Kích hoạt VIP", callback_data='activate')],
        [InlineKeyboardButton(f"{ICONS['shield']} VUA THOÁT HIỂM", callback_data='vth')],
        [InlineKeyboardButton(f"{ICONS['rocket']} VUA TỐC ĐỘ", callback_data='vtd')],
        [InlineKeyboardButton(f"{ICONS['lotto']} LOTTO", callback_data='lotto')],
        [InlineKeyboardButton(f"{ICONS['user']} Quản lý tài khoản", callback_data='accounts')],
        [InlineKeyboardButton(f"{ICONS['chart']} Thống kê", callback_data='stats')],
        [InlineKeyboardButton(f"{ICONS['settings']} Hướng dẫn", callback_data='help')],
    ])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    is_valid, msg, is_vip = check_activation_valid()
    status = f"✅ {msg} 👑 VIP" if is_valid and is_vip else f"✅ {msg}" if is_valid else f"❌ {msg}"
    
    text = f"""
{ICONS['crown']} *TBTOOL VIP PREMIUM* {ICONS['crown']}

👤 *User:* {user.first_name}
{ICONS['user_id']} *ID:* `{user.id}`
📊 *Trạng thái:* {status}
{'🛡️ *Admin:* ✅' if is_admin else ''}

{ICONS['brain']} *Công cụ hỗ trợ game:*
• VUA THOÁT HIỂM - 40 Logic AI (20 FREE + 20 VIP)
• VUA TỐC ĐỘ - 35 Logic AI (20 FREE + 15 VIP)
• LOTTO - 10 Logic AI (5 FREE + 5 VIP)

{ICONS['phone']} *Liên hệ mua Key VIP: 0365463767*
👑 *Admin: Thanh Bình*
"""
    update.message.reply_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)

def button_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    user = update.effective_user
    is_admin = user.id == ADMIN_ID
    
    data = query.data
    
    if data == 'admin' and is_admin:
        keyboard = [
            [InlineKeyboardButton(f"{ICONS['plus']} Tạo Key VIP", callback_data='gen_vip')],
            [InlineKeyboardButton(f"{ICONS['plus']} Tạo Key FREE", callback_data='gen_free')],
            [InlineKeyboardButton(f"{ICONS['chart']} Danh sách Key", callback_data='list_keys')],
            [InlineKeyboardButton(f"{ICONS['user']} Danh sách User", callback_data='list_users')],
            [InlineKeyboardButton(f"🔙 Quay lại", callback_data='back')],
        ]
        query.edit_message_text(
            f"{ICONS['admin']} *ADMIN PANEL*\n\nChọn chức năng:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    if data == 'gen_vip' and is_admin:
        keyboard = [
            [InlineKeyboardButton("1 Ngày (24h)", callback_data='gen_vip_24')],
            [InlineKeyboardButton("7 Ngày (168h)", callback_data='gen_vip_168')],
            [InlineKeyboardButton("30 Ngày (720h)", callback_data='gen_vip_720')],
            [InlineKeyboardButton("Vĩnh viễn (87600h)", callback_data='gen_vip_87600')],
            [InlineKeyboardButton("🔙 Quay lại", callback_data='admin')],
        ]
        query.edit_message_text(
            f"{ICONS['vip']} *TẠO KEY VIP*\n\nChọn thời hạn:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    if data.startswith('gen_vip_') and is_admin:
        hours = int(data.replace('gen_vip_', ''))
        key = generate_key("VIP", hours)
        query.edit_message_text(
            f"{ICONS['check']} *ĐÃ TẠO KEY VIP*\n\n🔑 *Key:* `{key}`\n⏰ *Thời hạn:* {hours}h\n{ICONS['info']} User dùng /key <key> để kích hoạt",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    if data == 'gen_free' and is_admin:
        key = generate_key("FREE", 24)
        query.edit_message_text(
            f"{ICONS['check']} *ĐÃ TẠO KEY FREE*\n\n🔑 *Key:* `{key}`\n⏰ *Thời hạn:* 24h",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    if data == 'list_keys' and is_admin:
        keys_data = load_keys()
        if not keys_data.get('keys'):
            query.edit_message_text(f"{ICONS['warning']} *Chưa có Key nào*", parse_mode=ParseMode.MARKDOWN)
            return
        text = f"{ICONS['chart']} *DANH SÁCH KEY*\n\n"
        for k in keys_data['keys'][-20:]:
            status = "✅ Đã dùng" if k.get('used') else "🟢 Chưa dùng"
            text += f"• `{k['key']}` - {k['type']} - {status}\n"
        query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN)
        return
    
    if data == 'list_users' and is_admin:
        keys_data = load_keys()
        used_keys = [k for k in keys_data['keys'] if k.get('used')]
        if not used_keys:
            query.edit_message_text(f"{ICONS['warning']} *Chưa có User nào*", parse_mode=ParseMode.MARKDOWN)
            return
        text = f"{ICONS['user']} *DANH SÁCH USER*\n\n"
        for k in used_keys[-20:]:
            text += f"• 🆔 `{k.get('used_by', '?')}` - {k['type']}\n"
        query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN)
        return
    
    if data == 'activate':
        query.edit_message_text(
            f"{ICONS['key']} *Kích hoạt TBTOOL*\n\nDùng lệnh: `/key <mã_key>`\n\nVí dụ: `/key TBTOOL_VIP_FOREVER_ABCD`\n\n{ICONS['phone']} *Mua Key VIP: 0365463767*",
            parse_mode=ParseMode.MARKDOWN
        )
        
    elif data == 'vth':
        keyboard = [
            [InlineKeyboardButton(f"{ICONS['plus']} Thêm tài khoản", callback_data='add_acc_vth')],
            [InlineKeyboardButton(f"{ICONS['target']} Chọn logic & Chạy", callback_data='run_vth')],
            [InlineKeyboardButton(f"{ICONS['chart']} Danh sách logic", callback_data='list_vth')],
            [InlineKeyboardButton(f"🔙 Quay lại", callback_data='back')],
        ]
        query.edit_message_text(
            f"{ICONS['shield']} *VUA THOÁT HIỂM*\n\n📊 *40 Logic AI*\n{ICONS['info']} Dùng /vth_logic <số> để chọn logic",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
        
    elif data == 'vtd':
        keyboard = [
            [InlineKeyboardButton(f"{ICONS['plus']} Thêm tài khoản", callback_data='add_acc_vtd')],
            [InlineKeyboardButton(f"{ICONS['target']} Chọn logic & Chạy", callback_data='run_vtd')],
            [InlineKeyboardButton(f"{ICONS['chart']} Danh sách logic", callback_data='list_vtd')],
            [InlineKeyboardButton(f"🔙 Quay lại", callback_data='back')],
        ]
        query.edit_message_text(
            f"{ICONS['rocket']} *VUA TỐC ĐỘ*\n\n📊 *35 Logic AI*\n{ICONS['info']} Dùng /vtd_logic <số> để chọn logic",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
        
    elif data == 'lotto':
        keyboard = [
            [InlineKeyboardButton(f"{ICONS['plus']} Thêm tài khoản", callback_data='add_acc_lotto')],
            [InlineKeyboardButton(f"{ICONS['target']} Chọn logic & Chạy", callback_data='run_lotto')],
            [InlineKeyboardButton(f"🔙 Quay lại", callback_data='back')],
        ]
        query.edit_message_text(
            f"{ICONS['lotto']} *LOTTO*\n\n📊 *10 Logic AI*\n{ICONS['info']} Dùng /lotto_logic <số> để chọn logic",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
        
    elif data == 'accounts':
        accounts = load_accounts()
        if not accounts:
            text = f"{ICONS['warning']} *Chưa có tài khoản!*\n\nDùng /add_acc <userId> <secretKey>"
        else:
            text = f"{ICONS['user']} *Danh sách tài khoản:*\n\n"
            for i, acc in enumerate(accounts, 1):
                text += f"{i}. 🆔 `{acc.get('userId')}`\n"
        query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN)
        
    elif data == 'stats':
        is_valid, msg, is_vip = check_activation_valid()
        status = f"✅ {msg} 👑 VIP" if is_valid and is_vip else f"✅ {msg}" if is_valid else f"❌ {msg}"
        accounts = load_accounts()
        keys_data = load_keys()
        text = f"""
{ICONS['chart']} *THỐNG KÊ TBTOOL*

📊 *Trạng thái Key:* {status}
{ICONS['user']} *Số tài khoản:* {len(accounts)}
{ICONS['key']} *Tổng Key:* {len(keys_data.get('keys', []))}
{ICONS['brain']} *Logic FREE:* 45
{ICONS['vip']} *Logic VIP:* 40
{ICONS['crown']} *Tổng cộng:* 85 Logic AI

{ICONS['phone']} *Support: 0365463767*
"""
        query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN)
        
    elif data == 'help':
        text = f"""
{ICONS['info']} *HƯỚNG DẪN*

/key <mã> - Kích hoạt Key
/add_acc <userId> <secretKey> - Thêm tài khoản
/del_acc <userId> - Xóa tài khoản
/list_acc - Xem danh sách

/vth_logic <số> - Chọn logic VTH (1-40)
/vth_start <cược> <hệ số> - Chạy VTH
/vth_stop - Dừng VTH

/vtd_logic <số> - Chọn logic VTD (1-35)
/vtd_start <cược> <hệ số> - Chạy VTD
/vtd_stop - Dừng VTD

/lotto_logic <số> - Chọn logic LOTTO (1-10)
/lotto_start <cược> <hệ số> - Chạy LOTTO
/lotto_stop - Dừng LOTTO

{ICONS['phone']} *Support: 0365463767*
"""
        query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN)
        
    elif data == 'back':
        start(update, context)

def key_command(update: Update, context: CallbackContext):
    args = context.args
    if not args:
        update.message.reply_text(
            f"{ICONS['warning']} *Cách dùng:* `/key <mã_key>`\n\nVí dụ: `/key TBTOOL_VIP_FOREVER_ABCD`",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    key = args[0].strip()
    device_id = get_device_id()
    
    key_info = verify_key_from_db(key)
    if not key_info:
        update.message.reply_text(
            f"{ICONS['cross']} *Key không hợp lệ hoặc đã được sử dụng!*",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    duration = key_info['duration_hours']
    key_type = key_info['type']
    now = datetime.now()
    
    if save_activation(device_id, key, now, duration, key_type):
        mark_key_used(key, device_id)
        update.message.reply_text(
            f"{ICONS['check']} *Kích hoạt thành công!*\n\n{ICONS['vip']} *Loại:* {key_type}\n⏰ *Thời hạn:* {duration}h\n{ICONS['phone']} *Support: 0365463767*",
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        update.message.reply_text(f"{ICONS['cross']} *Lỗi kích hoạt!*", parse_mode=ParseMode.MARKDOWN)

def add_account_command(update: Update, context: CallbackContext):
    args = context.args
    if len(args) < 2:
        update.message.reply_text(
            f"{ICONS['warning']} *Cách dùng:* `/add_acc <userId> <secretKey>`\n\nVí dụ: `/add_acc 12345 abc123`",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    try:
        user_id = int(args[0])
        secret_key = args[1]
        accounts = load_accounts()
        
        if any(acc.get('userId') == user_id for acc in accounts):
            update.message.reply_text(f"{ICONS['warning']} *Tài khoản {user_id} đã tồn tại!*", parse_mode=ParseMode.MARKDOWN)
            return
        
        accounts.append({"userId": user_id, "secretKey": secret_key, "game": "Chung"})
        save_accounts(accounts)
        
        balance = get_balance(user_id, secret_key)
        build_balance = balance.get('BUILD', 0)
        
        update.message.reply_text(
            f"{ICONS['check']} *Đã thêm tài khoản!*\n\n🆔 *User ID:* `{user_id}`\n💰 *Số dư:* {build_balance:,.2f} BUILD",
            parse_mode=ParseMode.MARKDOWN
        )
    except ValueError:
        update.message.reply_text(f"{ICONS['cross']} *User ID phải là số!*", parse_mode=ParseMode.MARKDOWN)

def delete_account(update: Update, context: CallbackContext):
    args = context.args
    if not args:
        update.message.reply_text(f"{ICONS['warning']} *Cách dùng:* `/del_acc <userId>`", parse_mode=ParseMode.MARKDOWN)
        return
    
    try:
        user_id = int(args[0])
        accounts = load_accounts()
        for i, acc in enumerate(accounts):
            if acc.get('userId') == user_id:
                accounts.pop(i)
                save_accounts(accounts)
                update.message.reply_text(f"{ICONS['check']} *Đã xóa tài khoản {user_id}*", parse_mode=ParseMode.MARKDOWN)
                return
        update.message.reply_text(f"{ICONS['cross']} *Không tìm thấy tài khoản {user_id}*", parse_mode=ParseMode.MARKDOWN)
    except ValueError:
        update.message.reply_text(f"{ICONS['cross']} *User ID phải là số!*", parse_mode=ParseMode.MARKDOWN)

def list_accounts(update: Update, context: CallbackContext):
    accounts = load_accounts()
    if not accounts:
        update.message.reply_text(f"{ICONS['warning']} *Chưa có tài khoản nào!*", parse_mode=ParseMode.MARKDOWN)
        return
    text = f"{ICONS['user']} *Danh sách tài khoản:*\n\n"
    for i, acc in enumerate(accounts, 1):
        text += f"{i}. 🆔 `{acc.get('userId')}`\n"
    update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

# ==================== VTH COMMANDS ====================
def vth_logic_command(update: Update, context: CallbackContext):
    args = context.args
    if not args:
        text = f"{ICONS['warning']} *Cách dùng:* `/vth_logic <số>`\n\n"
        for i, (k, v) in enumerate(list(VTH_LOGIC_DESCRIPTIONS.items())[:10], 1):
            text += f"{i}. {v}\n"
        text += f"\n... và {len(VTH_LOGIC_DESCRIPTIONS)-10} logic khác\nVí dụ: `/vth_logic 1`"
        update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
        return
    
    try:
        num = int(args[0])
        logic_list = list(VTH_LOGIC_DESCRIPTIONS.items())
        is_valid, _, is_vip = check_activation_valid()
        
        if not is_vip:
            vip_keys = [k for k, _ in logic_list if "VIP" in k]
            logic_list = [(k, v) for k, v in logic_list if k not in vip_keys]
        
        if 1 <= num <= len(logic_list):
            selected_key, selected_desc = logic_list[num - 1]
            context.user_data['vth_logic'] = selected_key
            update.message.reply_text(
                f"{ICONS['check']} *Đã chọn logic:* `{selected_desc}`\n\n/vth_start <cược> <hệ số>",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            update.message.reply_text(f"{ICONS['cross']} *Số từ 1 đến {len(logic_list)}*", parse_mode=ParseMode.MARKDOWN)
    except ValueError:
        update.message.reply_text(f"{ICONS['cross']} *Phải nhập số!*", parse_mode=ParseMode.MARKDOWN)

def vth_start(update: Update, context: CallbackContext):
    args = context.args
    if len(args) < 2:
        update.message.reply_text(
            f"{ICONS['warning']} *Cách dùng:* `/vth_start <cược> <hệ số>`\n\nVí dụ: `/vth_start 1 2`",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    try:
        bet_amount = float(args[0])
        multiplier = float(args[1])
        logic = context.user_data.get('vth_logic', 'RANDOM')
        is_valid, _, is_vip = check_activation_valid()
        
        if not is_valid:
            update.message.reply_text(f"{ICONS['lock']} *Chưa kích hoạt Key!*", parse_mode=ParseMode.MARKDOWN)
            return
        
        accounts = load_accounts()
        if not accounts:
            update.message.reply_text(f"{ICONS['warning']} *Chưa có tài khoản!*", parse_mode=ParseMode.MARKDOWN)
            return
        
        acc = accounts[0]
        balance = get_balance(acc['userId'], acc['secretKey'])
        build_balance = balance.get('BUILD', 0)
        
        if build_balance < bet_amount:
            update.message.reply_text(
                f"{ICONS['cross']} *Số dư không đủ!*\n💰 Có: {build_balance:,.2f} BUILD",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        update.message.reply_text(
            f"{ICONS['rocket']} *ĐANG CHẠY VTH*\n\n📌 *Logic:* {logic}\n🆔 *TK:* {acc['userId']}\n💰 *Cược:* {bet_amount} BUILD\n📈 *Hệ số:* x{multiplier}\n👑 *Mode:* {'VIP' if is_vip else 'FREE'}",
            parse_mode=ParseMode.MARKDOWN
        )
        
        context.user_data['vth_stop'] = False
        
        def run_vth():
            while not context.user_data.get('vth_stop', False):
                chosen_room = choose_room_vth(logic)
                time.sleep(5)
                context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=f"{ICONS['target']} *Đặt cược VTH*\n🏠 Phòng: {ROOM_NAMES.get(chosen_room, chosen_room)}",
                    parse_mode=ParseMode.MARKDOWN
                )
        
        thread = threading.Thread(target=run_vth, daemon=True)
        thread.start()
        
    except ValueError:
        update.message.reply_text(f"{ICONS['cross']} *Số tiền và hệ số phải là số!*", parse_mode=ParseMode.MARKDOWN)

def vth_stop(update: Update, context: CallbackContext):
    context.user_data['vth_stop'] = True
    update.message.reply_text(f"{ICONS['check']} *Đã dừng VTH*", parse_mode=ParseMode.MARKDOWN)

# ==================== VTD COMMANDS ====================
def vtd_logic_command(update: Update, context: CallbackContext):
    args = context.args
    if not args:
        text = f"{ICONS['warning']} *Cách dùng:* `/vtd_logic <số>`\n\n"
        for i, (k, v) in enumerate(list(VTD_LOGIC_DESCRIPTIONS.items())[:10], 1):
            text += f"{i}. {v}\n"
        text += f"\n... và {len(VTD_LOGIC_DESCRIPTIONS)-10} logic khác\nVí dụ: `/vtd_logic 1`"
        update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
        return
    
    try:
        num = int(args[0])
        logic_list = list(VTD_LOGIC_DESCRIPTIONS.items())
        is_valid, _, is_vip = check_activation_valid()
        
        if not is_vip:
            vip_keys = [k for k, _ in logic_list if "VIP" in k]
            logic_list = [(k, v) for k, v in logic_list if k not in vip_keys]
        
        if 1 <= num <= len(logic_list):
            selected_key, selected_desc = logic_list[num - 1]
            context.user_data['vtd_logic'] = selected_key
            update.message.reply_text(
                f"{ICONS['check']} *Đã chọn logic:* `{selected_desc}`\n\n/vtd_start <cược> <hệ số>",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            update.message.reply_text(f"{ICONS['cross']} *Số từ 1 đến {len(logic_list)}*", parse_mode=ParseMode.MARKDOWN)
    except ValueError:
        update.message.reply_text(f"{ICONS['cross']} *Phải nhập số!*", parse_mode=ParseMode.MARKDOWN)

def vtd_start(update: Update, context: CallbackContext):
    args = context.args
    if len(args) < 2:
        update.message.reply_text(
            f"{ICONS['warning']} *Cách dùng:* `/vtd_start <cược> <hệ số>`\n\nVí dụ: `/vtd_start 1 2`",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    try:
        bet_amount = float(args[0])
        multiplier = float(args[1])
        logic = context.user_data.get('vtd_logic', 'RANDOM')
        is_valid, _, is_vip = check_activation_valid()
        
        if not is_valid:
            update.message.reply_text(f"{ICONS['lock']} *Chưa kích hoạt Key!*", parse_mode=ParseMode.MARKDOWN)
            return
        
        accounts = load_accounts()
        if not accounts:
            update.message.reply_text(f"{ICONS['warning']} *Chưa có tài khoản!*", parse_mode=ParseMode.MARKDOWN)
            return
        
        acc = accounts[0]
        balance = get_balance(acc['userId'], acc['secretKey'])
        build_balance = balance.get('BUILD', 0)
        
        if build_balance < bet_amount:
            update.message.reply_text(
                f"{ICONS['cross']} *Số dư không đủ!*\n💰 Có: {build_balance:,.2f} BUILD",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        update.message.reply_text(
            f"{ICONS['rocket']} *ĐANG CHẠY VTD*\n\n📌 *Logic:* {logic}\n🆔 *TK:* {acc['userId']}\n💰 *Cược:* {bet_amount} BUILD\n📈 *Hệ số:* x{multiplier}\n👑 *Mode:* {'VIP' if is_vip else 'FREE'}",
            parse_mode=ParseMode.MARKDOWN
        )
        
        context.user_data['vtd_stop'] = False
        
        def run_vtd():
            while not context.user_data.get('vtd_stop', False):
                athlete = vtd_choose_logic(logic)
                time.sleep(5)
                context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=f"{ICONS['target']} *Đặt cược VTD*\n🏃 VĐV: {VTD_ATHLETES.get(athlete, athlete)}",
                    parse_mode=ParseMode.MARKDOWN
                )
        
        thread = threading.Thread(target=run_vtd, daemon=True)
        thread.start()
        
    except ValueError:
        update.message.reply_text(f"{ICONS['cross']} *Số tiền và hệ số phải là số!*", parse_mode=ParseMode.MARKDOWN)

def vtd_stop(update: Update, context: CallbackContext):
    context.user_data['vtd_stop'] = True
    update.message.reply_text(f"{ICONS['check']} *Đã dừng VTD*", parse_mode=ParseMode.MARKDOWN)

# ==================== LOTTO COMMANDS ====================
def lotto_logic_command(update: Update, context: CallbackContext):
    args = context.args
    if not args:
        text = f"{ICONS['warning']} *Cách dùng:* `/lotto_logic <số>`\n\n"
        for i, (k, v) in enumerate(LOTTO_LOGIC_DESCRIPTIONS.items(), 1):
            text += f"{i}. {v}\n"
        text += f"\nVí dụ: `/lotto_logic 1`"
        update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
        return
    
    try:
        num = int(args[0])
        logic_list = list(LOTTO_LOGIC_DESCRIPTIONS.items())
        is_valid, _, is_vip = check_activation_valid()
        
        if not is_vip:
            vip_keys = [k for k, _ in logic_list if "VIP" in k]
            logic_list = [(k, v) for k, v in logic_list if k not in vip_keys]
        
        if 1 <= num <= len(logic_list):
            selected_key, selected_desc = logic_list[num - 1]
            context.user_data['lotto_logic'] = selected_key
            update.message.reply_text(
                f"{ICONS['check']} *Đã chọn logic:* `{selected_desc}`\n\n/lotto_start <cược> <hệ số>",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            update.message.reply_text(f"{ICONS['cross']} *Số từ 1 đến {len(logic_list)}*", parse_mode=ParseMode.MARKDOWN)
    except ValueError:
        update.message.reply_text(f"{ICONS['cross']} *Phải nhập số!*", parse_mode=ParseMode.MARKDOWN)

def lotto_start(update: Update, context: CallbackContext):
    args = context.args
    if len(args) < 2:
        update.message.reply_text(
            f"{ICONS['warning']} *Cách dùng:* `/lotto_start <cược> <hệ số>`\n\nVí dụ: `/lotto_start 1 2`",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    try:
        bet_amount = float(args[0])
        multiplier = float(args[1])
        logic = context.user_data.get('lotto_logic', 'RANDOM')
        is_valid, _, is_vip = check_activation_valid()
        
        if not is_valid:
            update.message.reply_text(f"{ICONS['lock']} *Chưa kích hoạt Key!*", parse_mode=ParseMode.MARKDOWN)
            return
        
        accounts = load_accounts()
        if not accounts:
            update.message.reply_text(f"{ICONS['warning']} *Chưa có tài khoản!*", parse_mode=ParseMode.MARKDOWN)
            return
        
        acc = accounts[0]
        balance = get_balance(acc['userId'], acc['secretKey'])
        build_balance = balance.get('BUILD', 0)
        
        if build_balance < bet_amount:
            update.message.reply_text(
                f"{ICONS['cross']} *Số dư không đủ!*\n💰 Có: {build_balance:,.2f} BUILD",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        update.message.reply_text(
            f"{ICONS['rocket']} *ĐANG CHẠY LOTTO*\n\n📌 *Logic:* {logic}\n🆔 *TK:* {acc['userId']}\n💰 *Cược:* {bet_amount} BUILD\n📈 *Hệ số:* x{multiplier}\n👑 *Mode:* {'VIP' if is_vip else 'FREE'}",
            parse_mode=ParseMode.MARKDOWN
        )
        
        context.user_data['lotto_stop'] = False
        
        def run_lotto():
            bet_types = ["small", "big", "draw"]
            while not context.user_data.get('lotto_stop', False):
                bet_type = random.choice(bet_types)
                time.sleep(5)
                context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=f"{ICONS['target']} *Đặt cược LOTTO*\n🎯 Loại: {bet_type.upper()}",
                    parse_mode=ParseMode.MARKDOWN
                )
        
        thread = threading.Thread(target=run_lotto, daemon=True)
        thread.start()
        
    except ValueError:
        update.message.reply_text(f"{ICONS['cross']} *Số tiền và hệ số phải là số!*", parse_mode=ParseMode.MARKDOWN)

def lotto_stop(update: Update, context: CallbackContext):
    context.user_data['lotto_stop'] = True
    update.message.reply_text(f"{ICONS['check']} *Đã dừng LOTTO*", parse_mode=ParseMode.MARKDOWN)

# ==================== MAIN ====================
def error_handler(update: Update, context: CallbackContext):
    logger.error(f"Update {update} caused error {context.error}")

def main():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN khong duoc de trong!")
        return
    
    if not WEBHOOK_URL:
        logger.error("WEBHOOK_URL khong duoc de trong!")
        return
    
    logger.info("🤖 TBTOOL Bot dang khoi dong...")
    logger.info(f"📱 Token: {BOT_TOKEN[:10]}...")
    logger.info(f"🔗 Webhook: {WEBHOOK_URL}/{BOT_TOKEN}")
    
    try:
        updater = Updater(BOT_TOKEN)
        dp = updater.dispatcher
        
        dp.add_handler(CommandHandler("start", start))
        dp.add_handler(CommandHandler("key", key_command))
        dp.add_handler(CommandHandler("add_acc", add_account_command))
        dp.add_handler(CommandHandler("del_acc", delete_account))
        dp.add_handler(CommandHandler("list_acc", list_accounts))
        
        dp.add_handler(CommandHandler("vth_logic", vth_logic_command))
        dp.add_handler(CommandHandler("vth_start", vth_start))
        dp.add_handler(CommandHandler("vth_stop", vth_stop))
        
        dp.add_handler(CommandHandler("vtd_logic", vtd_logic_command))
        dp.add_handler(CommandHandler("vtd_start", vtd_start))
        dp.add_handler(CommandHandler("vtd_stop", vtd_stop))
        
        dp.add_handler(CommandHandler("lotto_logic", lotto_logic_command))
        dp.add_handler(CommandHandler("lotto_start", lotto_start))
        dp.add_handler(CommandHandler("lotto_stop", lotto_stop))
        
        dp.add_handler(CallbackQueryHandler(button_callback))
        dp.add_error_handler(error_handler)
        
        updater.start_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=BOT_TOKEN,
            webhook_url=f"{WEBHOOK_URL}/{BOT_TOKEN}"
        )
        
        logger.info("✅ Bot da san sang!")
        updater.idle()
        
    except Exception as e:
        logger.error(f"LOI: {e}")
        raise

if __name__ == "__main__":
    main()
