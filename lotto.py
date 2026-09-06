# -*- coding: utf-8 -*-
import os, time, json, random, logging, threading, requests, math
import telebot
from telebot import types
from flask import Flask, request
import sys

# ==================== CẤU HÌNH RENDER ====================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8385677064:AAHS5ZqmV9QPka3I1t84lyysLzLsLTp3N6g")
ADMIN_ID = [7564889663]
PORT = int(os.environ.get("PORT", 5000))
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "https://tbtool.onrender.com/webhook")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ==================== FLASK APP ====================
app = Flask(__name__)
bot = telebot.TeleBot(BOT_TOKEN, threaded=False)

# ==================== ICONS ====================
ICONS = {"crown":"👑","check":"✅","cross":"❌","warning":"⚠️","info":"ℹ️","user":"👤","key":"🔑","phone":"📞","chart":"📊","money":"💰","clock":"⏰","lotto":"🎲","target":"🎯","rocket":"🚀","vip":"💎","fire":"🔥"}

# ==================== ACCOUNT ====================
ACCOUNTS_FILE = "accounts.json"
def load_accounts():
    try:
        with open(ACCOUNTS_FILE, 'r') as f: return json.load(f)
    except: return []
def save_accounts(accounts):
    with open(ACCOUNTS_FILE, 'w') as f: json.dump(accounts, f, indent=2)

# ==================== API LOTTO ====================
LOTTO_HOME_API = "https://api.winhash.net/lucky_game/home"
LOTTO_BET_API = "https://api.winhash.net/lucky_game/v2/create_order"
LOTTO_WALLET_API = "https://wallet.3games.io/api/wallet/user_asset"
BET_IDS = {"small": 70309, "big": 71218, "draw": 71011}

def get_balance(user_id, secret_key):
    headers = {'user-id': str(user_id), 'user-secret-key': secret_key, 'content-type': 'application/json'}
    try:
        resp = requests.post(LOTTO_WALLET_API, json={"user_id": user_id, "source": "home"}, headers=headers, timeout=10)
        data = resp.json()
        if data.get('code') == 0:
            return data.get('data', {}).get('user_asset', {}).get('BUILD', 0)
        return 0
    except: return 0

def lotto_get_home(user_id, secret_key):
    headers = {'user-id': str(user_id), 'user-secret-key': secret_key}
    try:
        resp = requests.get(LOTTO_HOME_API, headers=headers, timeout=10)
        return resp.json()
    except: return {}

def lotto_place_bet(user_id, secret_key, issue_id, bet_type, amount):
    headers = {'user-id': str(user_id), 'user-secret-key': secret_key, 'content-type': 'application/json'}
    payload = {"game_id": 1, "issue_id": issue_id, "items": [{"id": BET_IDS.get(bet_type, 70309), "amount": str(amount), "asset": "BUILD"}]}
    try:
        resp = requests.post(LOTTO_BET_API, headers=headers, json=payload, timeout=10)
        return resp.json()
    except Exception as e:
        return {"error": str(e)}

# ==================== USER STATE ====================
user_states = {}
running_bots = {}
def init_user(chat_id):
    if chat_id not in user_states:
        user_states[chat_id] = {
            'bet_amount': 1,
            'multiplier': 2,
            'running': False,
            'account': None,
            'last_issue_placed': None,
            'bet_history': []
        }

# ========================================================================
# THUẬT TOÁN - GIỮ NGUYÊN (ĐÃ CÓ Ở TRÊN)
# ========================================================================

def entropy(arr):
    if not arr or len(arr) == 0: return 0
    freq = {}
    for v in arr: freq[v] = freq.get(v, 0) + 1
    e = 0; n = len(arr)
    for c in freq.values():
        p = c / n
        e -= p * math.log2(p)
    return e

def similarity(a, b):
    if len(a) != len(b) or len(a) == 0: return 0
    same = sum(1 for i in range(len(a)) if a[i] == b[i])
    return same / len(a)

def computeSlope(values):
    if not values or len(values) < 2: return 0
    n = len(values)
    sumX = sumY = sumXY = sumX2 = 0
    for i in range(n):
        x = i; y = values[i]
        sumX += x; sumY += y; sumXY += x*y; sumX2 += x*x
    denom = n*sumX2 - sumX*sumX
    if denom == 0: return 0
    return (n*sumXY - sumX*sumY) / denom

class PatternMemory:
    def __init__(self):
        self.tree = {}
        self.totalEntries = 0
    def add(self, seq, nextResult, isCorrect):
        if not seq or len(seq) < 2: return
        node = self.tree
        for ch in seq:
            if ch not in node: node[ch] = {}
            node = node[ch]
        if "_count" not in node: node["_count"] = {"LON": 0, "NHO": 0, "wins": 0, "total": 0}
        node["_count"][nextResult] = node["_count"].get(nextResult, 0) + 1
        node["_count"]["total"] += 1
        if isCorrect: node["_count"]["wins"] += 1
        self.totalEntries += 1
    def predict(self, seq):
        if not seq or len(seq) < 2: return None
        node = self.tree
        for ch in seq:
            if ch not in node: return None
            node = node[ch]
        if "_count" not in node or node["_count"]["total"] < 3: return None
        scoreLON = node["_count"].get("LON", 0) * (1 + node["_count"]["wins"] / max(1, node["_count"]["total"]))
        scoreNHO = node["_count"].get("NHO", 0) * (1 + node["_count"]["wins"] / max(1, node["_count"]["total"]))
        if scoreLON == scoreNHO: return None
        return "LON" if scoreLON > scoreNHO else "NHO"

def aZ_betCung(history):
    if len(history) < 3: return None
    tx = [h["tx"] for h in history]
    last = tx[-1]
    count = 1
    for i in range(len(tx)-2, -1, -1):
        if tx[i] == last: count += 1
        else: break
    if count >= 3: return last
    if count == 2:
        prev2 = tx[-3]
        if prev2 != last: return last
        return last
    return None

def aO_33_flex(history):
    if len(history) < 6: return None
    tx = [h["tx"] for h in history]
    last6 = tx[-6:]
    if len(last6) == 6 and last6[0]==last6[1] and last6[1]==last6[2] and last6[3]==last6[4] and last6[4]==last6[5] and last6[0]!=last6[3]:
        return "NHO" if last6[0] == "LON" else "LON"
    if len(tx) >= 5:
        last5 = tx[-5:]
        if last5[0]==last5[1] and last5[2]!=last5[0] and last5[3]==last5[4] and last5[3]==last5[0]:
            return "NHO" if last5[0] == "LON" else "LON"
    return None

def aQ_313_flex(history):
    if len(history) < 7: return None
    tx = [h["tx"] for h in history]
    last7 = tx[-7:]
    if len(last7) < 7: return None
    a = last7[0]
    if last7[0]==last7[1] and last7[1]==last7[2] and last7[3]!=a and last7[4]==last7[5] and last7[5]==last7[6] and last7[4]==a:
        return "NHO" if a == "LON" else "LON"
    if len(tx) >= 6:
        last6 = tx[-6:]
        if last6[0]==last6[1] and last6[2]!=last6[0] and last6[3]==last6[4] and last6[4]==last6[0]:
            return "NHO" if last6[0] == "LON" else "LON"
    return None

def extractFeaturesLC(history):
    if not history or len(history) == 0:
        return {"tx": [], "totals": [], "freq": {}, "runs": [], "maxRun": 0, "meanTotal": 0, "stdTotal": 0, "entropy": 0, "last3": "", "last5": "", "last8": "", "trends": {"up": 0, "down": 0}, "lastRun": None, "prevRun": None, "runLengths": [], "avgRun": 0, "stdRun": 0, "tRatio": 0, "xRatio": 0, "is11": False, "isLong": False, "runDev": 0, "slope": 0, "scoreVolatility": 0}
    tx = [h["tx"] for h in history]
    totals = [h.get("total", 11) for h in history]
    freq = {}
    for v in tx: freq[v] = freq.get(v, 0) + 1
    runs = []
    cur = tx[0]; length = 1
    for i in range(1, len(tx)):
        if tx[i] == cur: length += 1
        else: runs.append({"val": cur, "len": length}); cur = tx[i]; length = 1
    runs.append({"val": cur, "len": length})
    n = len(tx)
    mean_t = sum(totals) / n
    std_t = math.sqrt(sum((x - mean_t)**2 for x in totals) / n) if n > 0 else 0
    rl = [r["len"] for r in runs]
    avg_r = sum(rl) / len(rl) if rl else 0
    std_r = math.sqrt(sum((x - avg_r)**2 for x in rl) / len(rl)) if rl else 0
    recent20 = totals[-20:] if len(totals) >= 20 else totals
    slope = computeSlope(recent20)
    return {"tx": tx, "totals": totals, "freq": freq, "runs": runs, "maxRun": max(rl) if rl else 0, "meanTotal": mean_t, "stdTotal": std_t, "entropy": entropy(tx), "last3": "".join(tx[-3:]) if len(tx)>=3 else "", "last5": "".join(tx[-5:]) if len(tx)>=5 else "", "last8": "".join(tx[-8:]) if len(tx)>=8 else "", "trends": {"up": 0, "down": 0}, "lastRun": runs[-1] if runs else None, "prevRun": runs[-2] if len(runs)>=2 else None, "runLengths": rl, "avgRun": avg_r, "stdRun": std_r, "tRatio": freq.get("LON", 0) / n, "xRatio": freq.get("NHO", 0) / n, "is11": len(runs) >= 4 and all(l == 1 for l in rl[-4:]), "isLong": runs and runs[-1]["len"] >= 4, "runDev": (runs[-1]["len"] - avg_r) / std_r if runs and std_r > 0 else 0, "slope": slope, "scoreVolatility": std_t}

PATTERN_LIB = [
    [[1,1,1,1,1,1], "1_1"],
    [[2,2,2,2], "2_2"],
    [[3,3,3], "3_3"],
    [[2,1,2,1,2], "2_1_2"],
    [[1,2,1,2,1], "1_2_1"],
    [[3,2,3,2,3], "3_2_3"],
    [[4,2,4,2,4], "4_2_4"],
    [[2,2,1,2,2], "2_2_1"],
    [[1,3,1,3,1], "1_3_1"],
    [[3,1,3,1,3], "3_1_3"]
]
def detectPatternLC(runs):
    if not runs or len(runs) < 3: return None
    lr = runs[-6:]
    lens = [r["len"] for r in lr]
    vals = [r["val"] for r in lr]
    alt = all(vals[i] != vals[i-1] for i in range(1, len(vals)))
    for pat, name in PATTERN_LIB:
        if len(lens) >= len(pat) and all(lens[-len(pat)+i] == pat[i] for i in range(len(pat))) and alt:
            return name + "_pattern"
    if lr[-1]["len"] >= 5: return "long_run_pattern"
    if len(lens) >= 6:
        last6 = vals[-6:]
        if last6[0]==last6[1] and last6[1]==last6[2] and last6[3]==last6[4] and last6[4]==last6[5] and last6[0]!=last6[3]:
            return "3_3_pattern"
    if len(vals) >= 7:
        last7 = vals[-7:]
        a = last7[0]
        if last7[0]==last7[1] and last7[1]==last7[2] and last7[3]!=a and last7[4]==last7[5] and last7[5]==last7[6] and last7[6]==a:
            return "313_pattern"
    return "random_pattern"

def predictByPatternLC(pt, runs, lastTx):
    if not pt or not runs: return None
    lr = runs[-1]
    if pt == "1_1_pattern": return "NHO" if lastTx == "LON" else "LON"
    if pt in ["2_2_pattern", "3_3_pattern"]:
        k = 2 if pt == "2_2_pattern" else 3
        return "NHO" if lr["len"] == k and lr["val"] == "LON" else ("LON" if lr["len"] == k and lr["val"] == "NHO" else lr["val"])
    if pt == "2_1_2_pattern":
        if lr["len"] == 2: return "NHO" if lr["val"] == "LON" else "LON"
        if lr["len"] == 1: return lr["val"]
    if pt == "1_2_1_pattern":
        if lr["len"] == 1: return "NHO" if lr["val"] == "LON" else "LON"
        if lr["len"] == 2: return lr["val"]
    if pt in ["3_2_3_pattern", "4_2_4_pattern"]:
        a = 3 if pt == "3_2_3_pattern" else 4
        if lr["len"] == a: return "NHO" if lr["val"] == "LON" else "LON"
        if lr["len"] == 2: return lr["val"]
    if pt == "long_run_pattern":
        if lr["len"] > 7: return "NHO" if lr["val"] == "LON" else "LON"
        if 4 <= lr["len"] <= 7: return lr["val"]
    if pt == "3_3_pattern":
        if lr["len"] == 3: return "NHO" if lr["val"] == "LON" else "LON"
        return lr["val"]
    if pt == "313_pattern":
        if lr["len"] == 1: return "NHO" if lr["val"] == "LON" else "LON"
        return lr["val"]
    return None

ALL_ALGS_LC = [
    ("a5_freq", lambda h: None),
    ("aA_markov", lambda h: None),
    ("aB_ngram", lambda h: None),
    ("aS_neo", lambda h: None),
    ("aF_deep", lambda h: None),
    ("aE_trans", lambda h: None),
    ("aG_bridge", lambda h: None),
    ("aH_adapt", lambda h: None),
    ("aI_master", lambda h: None),
    ("aJ_entropy", lambda h: None),
    ("aK_11", lambda h: None),
    ("aL_dragon", lambda h: None),
    ("aM_fast", lambda h: None),
    ("aN_safe", lambda h: None),
    ("aZ_betCung", aZ_betCung),
    ("aO_33_flex", aO_33_flex),
    ("aQ_313_flex", aQ_313_flex)
]

class SEIU_TaiXiu:
    def __init__(self):
        self.w = {name: 1.0 for name, _ in ALL_ALGS_LC}
        s = sum(self.w.values())
        for k in self.w: self.w[k] /= s
        self.ph = {name: [] for name, _ in ALL_ALGS_LC}
        self.pm = {}
        self.mn = 0.02
        self.mx = 4.0
    def _best_for(self, pt):
        map = {
            "1_1_pattern": ["aK_11", "aS_neo", "aI_master", "aM_fast"],
            "long_run_pattern": ["aZ_betCung", "aL_dragon", "aG_bridge", "aJ_entropy", "aN_safe"],
            "2_2_pattern": ["aM_fast", "aI_master", "aS_neo"],
            "random_pattern": ["aA_markov", "aB_ngram", "aF_deep", "aH_adapt", "aE_trans"],
            "3_3_pattern": ["aO_33_flex", "aG_bridge", "aL_dragon"],
            "313_pattern": ["aQ_313_flex", "aI_master", "aJ_entropy"]
        }
        return map.get(pt, [])
    def update(self, hist, real_tx):
        if len(hist) < 10: return
        f = extractFeaturesLC(hist)
        pt = detectPatternLC(f["runs"]) or "random_pattern"
        rl = f["lastRun"]["len"] if f["lastRun"] else 0
        for name, fn in ALL_ALGS_LC:
            try:
                pr = fn(hist)
                ok = 1 if pr == real_tx else 0
                self.ph[name].append(ok)
                if len(self.ph[name]) > 80: self.ph[name].pop(0)
                ph = self.ph[name]
                r25 = ph[-25:]
                wa, ws = 0, 0
                for i in range(len(r25)):
                    k = pow(0.92, len(r25) - i - 1)
                    wa += r25[i] * k; ws += k
                a25 = wa / ws if ws else 0.5
                aa = sum(ph) / len(ph)
                acc = a25 * 0.7 + aa * 0.3
                pb = 0.18 if name in self._best_for(pt) else 0
                kk = name + "_" + pt
                ps = self.pm.get(kk, 0)
                pb += 0.12 if ps > 5 else (0.06 if ps > 2 else 0)
                al = 0.18 if rl <= 2 else (0.04 if rl >= 5 else 0.06)
                nw = al * (acc + 0.15) + (1 - al) * (self.w.get(name, 0.1))
                if name == "aZ_betCung": nw = min(4.0, nw * 2.0)
                if name in ["aO_33_flex", "aQ_313_flex"]: nw = min(3.0, nw * 1.8)
                nw = max(self.mn, min(self.mx, nw))
                if len(r25) == 3 and sum(r25) == 0: nw *= 0.72
                self.w[name] = nw
                if ok: self.pm[kk] = self.pm.get(kk, 0) + 1
            except:
                self.w[name] = max(self.mn, (self.w.get(name, 0.1) * 0.9))
        s = sum(self.w.values())
        if s > 0:
            for k in self.w: self.w[k] /= s
    def predict(self, hist):
        if len(hist) < 12:
            return {"pred": "LON", "conf": 0.5, "pt": "n/a", "vt": {"LON": 0, "NHO": 0}, "n": 0}
        f = extractFeaturesLC(hist)
        pt = detectPatternLC(f["runs"]) or "random_pattern"
        vt = {"LON": 0, "NHO": 0}
        det = []
        for name, fn in ALL_ALGS_LC:
            try:
                pr = fn(hist)
                if not pr: continue
                w = self.w.get(name, 0.1)
                if name in self._best_for(pt): w *= 1.3
                if name == "aZ_betCung" and f["lastRun"] and f["lastRun"]["len"] >= 3: w *= 1.5
                w = min(self.mx, w)
                vt[pr] += w
                det.append({"name": name, "pr": pr, "w": w})
            except: pass
        if vt["LON"] == 0 and vt["NHO"] == 0:
            return {"pred": "LON", "conf": 0.5, "pt": pt, "vt": {"LON": 0, "NHO": 0}, "n": 0}
        best = "LON" if vt["LON"] > vt["NHO"] else "NHO"
        tot = vt["LON"] + vt["NHO"]
        base = max(vt["LON"], vt["NHO"]) / tot
        tn = len([d for d in det if d["pr"] == "LON"])
        xn = len(det) - tn
        an = len(det)
        con = 0
        if an > 0:
            r = max(tn, xn) / an
            con = 0.18 if r >= 0.9 else (0.13 if r >= 0.8 else (0.07 if r >= 0.7 else 0))
        sf = 0
        if pt == "long_run_pattern" and f["lastRun"] and f["lastRun"]["len"] >= 8: sf -= 0.08
        if pt == "1_1_pattern" and f["lastRun"] and f["lastRun"]["len"] >= 10: sf -= 0.05
        if f["entropy"] > 0.92: sf -= 0.06
        conf = min(0.97, max(0.52, base + con + sf))
        return {"pred": best, "conf": round(conf, 3), "pt": pt, "vt": {"LON": round(vt["LON"], 3), "NHO": round(vt["NHO"], 3)}, "n": an}

class TAV1Predictor:
    def __init__(self):
        self.model_predictions = {"trend": {}, "short": {}, "mean": {}, "switch": {}, "bridge": {}}
        self.history = []
    def setHistory(self, hist): self.history = hist[:]
    def _detectStreakAndBreak(self, history):
        if not history or len(history) == 0: return {"streak": 0, "currentResult": None, "breakProb": 0}
        currentResult = history[-1]["result"]
        streak = 1
        for i in range(len(history)-2, -1, -1):
            if history[i]["result"] == currentResult: streak += 1
            else: break
        last15 = [h["result"] for h in history[-15:]]
        switches = sum(1 for i in range(1, len(last15)) if last15[i] != last15[i-1]) if last15 else 0
        lon = sum(1 for r in last15 if r == "Lớn")
        nho = len(last15) - lon
        imbalance = abs(lon - nho) / len(last15) if last15 else 0
        breakProb = 0
        if streak >= 8: breakProb = min(0.6 + switches/15 + imbalance*0.15, 0.9)
        elif streak >= 5: breakProb = min(0.35 + switches/10 + imbalance*0.25, 0.85)
        elif streak >= 3 and switches >= 7: breakProb = 0.3
        return {"streak": streak, "currentResult": currentResult, "breakProb": breakProb}
    def _trendAndProb(self, history):
        if not history or len(history) < 3: return 0
        info = self._detectStreakAndBreak(history)
        streak = info["streak"]; current = info["currentResult"]; breakProb = info["breakProb"]
        if streak >= 5:
            return 2 if current == "Lớn" and breakProb > 0.75 else (1 if current == "Nhỏ" and breakProb > 0.75 else (1 if current == "Lớn" else 2))
        last15 = [h["result"] for h in history[-15:]]
        if not last15: return 0
        lonWeight = nhoWeight = 0
        for i in range(len(last15)):
            w = pow(1.2, i)
            if last15[i] == "Lớn": lonWeight += w
            else: nhoWeight += w
        total = lonWeight + nhoWeight
        if total > 0 and abs(lonWeight - nhoWeight) / total >= 0.25:
            return 2 if lonWeight > nhoWeight else 1
        return 1 if last15[-1] == "Nhỏ" else 2
    def _shortPattern(self, history):
        if not history or len(history) < 3: return 0
        info = self._detectStreakAndBreak(history)
        streak = info["streak"]; current = info["currentResult"]; breakProb = info["breakProb"]
        if streak >= 4:
            return 2 if current == "Lớn" and breakProb > 0.75 else (1 if current == "Nhỏ" and breakProb > 0.75 else (1 if current == "Lớn" else 2))
        last8 = [h["result"] for h in history[-8:]]
        return 1 if last8[-1] == "Nhỏ" else 2
    def _meanDeviation(self, history):
        if not history or len(history) < 3: return 0
        info = self._detectStreakAndBreak(history)
        streak = info["streak"]; current = info["currentResult"]; breakProb = info["breakProb"]
        if streak >= 4:
            return 2 if current == "Lớn" and breakProb > 0.75 else (1 if current == "Nhỏ" and breakProb > 0.75 else (1 if current == "Lớn" else 2))
        last12 = [h["result"] for h in history[-12:]]
        lon = sum(1 for r in last12 if r == "Lớn")
        nho = len(last12) - lon
        return 1 if nho > lon else 2
    def _recentSwitch(self, history):
        if not history or len(history) < 3: return 0
        info = self._detectStreakAndBreak(history)
        streak = info["streak"]; current = info["currentResult"]; breakProb = info["breakProb"]
        if streak >= 4:
            return 2 if current == "Lớn" and breakProb > 0.75 else (1 if current == "Nhỏ" and breakProb > 0.75 else (1 if current == "Lớn" else 2))
        last10 = [h["result"] for h in history[-10:]]
        switches = sum(1 for i in range(1, len(last10)) if last10[i] != last10[i-1])
        return 1 if last10[-1] == "Nhỏ" else 2
    def _smartBridgeBreak(self, history):
        if not history or len(history) < 3:
            return {"prediction": 0, "breakProb": 0, "reason": "Không đủ dữ liệu"}
        info = self._detectStreakAndBreak(history)
        streak = info["streak"]; current = info["currentResult"]; breakProb = info["breakProb"]
        finalBreak = breakProb
        if streak >= 6: finalBreak = min(finalBreak + 0.15, 0.9)
        elif streak >= 4: finalBreak = min(finalBreak + 0.1, 0.85)
        else: finalBreak = max(finalBreak - 0.15, 0.15)
        pred = 2 if current == "Lớn" and finalBreak > 0.65 else (1 if current == "Nhỏ" and finalBreak > 0.65 else (1 if current == "Lớn" else 2))
        return {"prediction": pred, "breakProb": finalBreak, "reason": "Bẻ cầu" if finalBreak > 0.65 else "Theo cầu"}
    def _aiHtddLogic(self, history):
        if not history or len(history) < 3:
            return {"prediction": random.choice(["Lớn", "Nhỏ"]), "reason": "Ngẫu nhiên", "source": "AI HTDD"}
        last5 = [h["result"] for h in history[-5:]]
        lonCount = sum(1 for r in last5 if r == "Lớn")
        nhoCount = len(last5) - lonCount
        if len(history) >= 3:
            last3 = [h["result"] for h in history[-3:]]
            if last3 == ["Lớn", "Nhỏ", "Lớn"]: return {"prediction": "Nhỏ", "reason": "Mẫu 1L1N", "source": "AI HTDD"}
            if last3 == ["Nhỏ", "Lớn", "Nhỏ"]: return {"prediction": "Lớn", "reason": "Mẫu 1N1L", "source": "AI HTDD"}
        if len(history) >= 9 and all(h["result"] == "Lớn" for h in history[-6:]): return {"prediction": "Nhỏ", "reason": "Chuỗi Lớn dài", "source": "AI HTDD"}
        if len(history) >= 9 and all(h["result"] == "Nhỏ" for h in history[-6:]): return {"prediction": "Lớn", "reason": "Chuỗi Nhỏ dài", "source": "AI HTDD"}
        totalLon = sum(1 for h in history if h["result"] == "Lớn")
        totalNho = len(history) - totalLon
        if totalLon > totalNho + 2: return {"prediction": "Nhỏ", "reason": "Lớn nhiều hơn", "source": "AI HTDD"}
        if totalNho > totalLon + 2: return {"prediction": "Lớn", "reason": "Nhỏ nhiều hơn", "source": "AI HTDD"}
        return {"prediction": random.choice(["Lớn", "Nhỏ"]), "reason": "Cân bằng", "source": "AI HTDD"}
    def predict(self, history):
        if not history or len(history) == 0:
            return {"prediction": random.choice(["Lớn", "Nhỏ"]), "confidence": 50, "reason": "Không có lịch sử"}
        self.setHistory(history)
        currentSession = history[-1]["session"] if "session" in history[-1] else len(history)
        trendPred = self._trendAndProb(history)
        shortPred = self._shortPattern(history)
        meanPred = self._meanDeviation(history)
        switchPred = self._recentSwitch(history)
        bridgePred = self._smartBridgeBreak(history)
        aiResult = self._aiHtddLogic(history)
        self.model_predictions["trend"][currentSession] = trendPred
        self.model_predictions["short"][currentSession] = shortPred
        self.model_predictions["mean"][currentSession] = meanPred
        self.model_predictions["switch"][currentSession] = switchPred
        self.model_predictions["bridge"][currentSession] = bridgePred["prediction"]
        weights = {"trend": 0.2, "short": 0.2, "mean": 0.25, "switch": 0.2, "bridge": 0.15, "aihtdd": 0.2}
        lonScore = nhoScore = 0
        def addScore(pred, w):
            nonlocal lonScore, nhoScore
            if pred == 1: lonScore += w
            elif pred == 2: nhoScore += w
        addScore(trendPred, weights["trend"])
        addScore(shortPred, weights["short"])
        addScore(meanPred, weights["mean"])
        addScore(switchPred, weights["switch"])
        addScore(bridgePred["prediction"], weights["bridge"])
        if aiResult["prediction"] == "Lớn": lonScore += weights["aihtdd"]
        else: nhoScore += weights["aihtdd"]
        if bridgePred["breakProb"] > 0.65:
            if bridgePred["prediction"] == 1: lonScore += 0.2
            else: nhoScore += 0.2
        finalPred = "Lớn" if lonScore > nhoScore else "Nhỏ"
        totalScore = lonScore + nhoScore
        confidence = 50
        if totalScore > 0:
            diff = abs(lonScore - nhoScore) / totalScore
            confidence = min(98, max(55, 50 + diff * 80))
        return {"prediction": finalPred, "confidence": round(confidence), "reason": aiResult["reason"], "scores": {"lon": round(lonScore, 3), "nho": round(nhoScore, 3)}}

class DeepBrainV2:
    def __init__(self):
        self.layers = [
            {"weights": self._init(20, 32), "bias": [0]*32},
            {"weights": self._init(32, 64), "bias": [0]*64},
            {"weights": self._init(64, 32), "bias": [0]*32},
            {"weights": self._init(32, 16), "bias": [0]*16},
            {"weights": self._init(16, 2), "bias": [0]*2}
        ]
        self.lr = 0.001; self.momentum = 0.9; self.memory = []; self.lossHistory = []
    def _init(self, input, output):
        return [[(random.random()-0.5)*0.1 for _ in range(output)] for __ in range(input)]
    def _relu(self, x): return x if x > 0 else 0.01*x
    def _softmax(self, x):
        maxv = max(x)
        expv = [math.exp(v - maxv) for v in x]
        s = sum(expv)
        return [v/s for v in expv]
    def _forward(self, input):
        output = input
        for i, layer in enumerate(self.layers):
            next = [0]*len(layer["weights"][0])
            for j in range(len(next)):
                s = layer["bias"][j]
                for k in range(len(output)):
                    s += output[k] * layer["weights"][k][j]
                next[j] = self._relu(s) if i < len(self.layers)-1 else s
            output = next
        return self._softmax(output)
    def train(self, input, target):
        pred = self._forward(input)
        errors = [pred[i] - target[i] for i in range(len(target))]
        for l in range(len(self.layers)-1, -1, -1):
            layer = self.layers[l]
            newErrors = [0]*len(layer["weights"])
            for i in range(len(layer["weights"])):
                grad = 0
                for j in range(len(layer["weights"][0])):
                    grad += errors[j] * layer["weights"][i][j]
                newErrors[i] = grad * (1 if i < len(input) and input[i] > 0 else 0.01)
            for i in range(len(layer["weights"])):
                for j in range(len(layer["weights"][0])):
                    gradient = errors[j] * (input[i] if i < len(input) else 1)
                    layer["weights"][i][j] -= self.lr * gradient
            for j in range(len(layer["bias"])):
                layer["bias"][j] -= self.lr * errors[j]
            errors = newErrors
        loss = -math.log(pred[target.index(1)])
        self.lossHistory.append(loss)
        if len(self.lossHistory) > 100: self.lossHistory.pop(0)
        if len(self.lossHistory) > 10:
            avg = sum(self.lossHistory) / len(self.lossHistory)
            self.lr = min(0.01, max(0.0001, self.lr * (0.99 if avg < 0.1 else 1.01)))
    def predict(self, input):
        prob = self._forward(input)
        return {"LON": prob[0], "NHO": prob[1]}
    def getConfidenceAdjustment(self):
        if len(self.lossHistory) < 10: return 0
        avg = sum(self.lossHistory) / len(self.lossHistory)
        return (0.5 - min(avg, 0.5)) * 20

class Agent:
    def __init__(self, name, strategy):
        self.name = name; self.strategy = strategy
        self.qTable = {}; self.alpha = 0.1; self.gamma = 0.9; self.epsilon = 0.1
        self.rewardSum = 0; self.lastAction = None; self.lastState = None
    def predict(self, history):
        if random.random() < self.epsilon:
            act = random.choice(["LON", "NHO"])
            self.lastAction = act; return act
        state = self._stateKey(history)
        if state not in self.qTable: self.qTable[state] = {"LON": 0, "NHO": 0}
        vals = self.qTable[state]
        act = "LON" if vals["LON"] >= vals["NHO"] else "NHO"
        self.lastAction = act; self.lastState = state; return act
    def update(self, history, action, reward, nextHistory):
        state = self._stateKey(history); nextState = self._stateKey(nextHistory)
        if state not in self.qTable: self.qTable[state] = {"LON": 0, "NHO": 0}
        if nextState not in self.qTable: self.qTable[nextState] = {"LON": 0, "NHO": 0}
        maxNext = max(self.qTable[nextState]["LON"], self.qTable[nextState]["NHO"])
        oldVal = self.qTable[state][action]
        self.qTable[state][action] = oldVal + self.alpha * (reward + self.gamma * maxNext - oldVal)
        self.rewardSum += reward
    def _stateKey(self, history):
        tx = "".join([h["tx"] for h in history[-8:]])
        scores = ",".join([str(h.get("total", 11)) for h in history[-8:]])
        return tx + "|" + scores

class KnowledgeGraph:
    def __init__(self): self.nodes = {}
    def addTransition(self, state, nextState, weight=1):
        if state not in self.nodes: self.nodes[state] = {}
        if nextState not in self.nodes[state]: self.nodes[state][nextState] = 0
        self.nodes[state][nextState] += weight
    def predict(self, state):
        if state not in self.nodes: return None
        transitions = self.nodes[state]
        return max(transitions, key=transitions.get)

def extractAdvancedFeatures(history):
    if len(history) < 10: return [0]*20
    tx = [1 if h["tx"] == "LON" else 0 for h in history[-10:]]
    scores = [h.get("total", 11) for h in history[-10:]]
    features = tx[:]
    avg = sum(scores) / len(scores)
    std = math.sqrt(sum((x - avg)**2 for x in scores) / len(scores))
    slope = computeSlope(scores)
    ent = entropy(["LON" if v == 1 else "NHO" for v in tx])
    totalLon = sum(1 for h in history[-20:] if h["tx"] == "LON") / 20
    features.extend([avg/20, std/10, slope/5, ent, totalLon, len(history) % 10])
    while len(features) < 20: features.append(0)
    return features

class TaiXiuCombinedAnalyzer:
    def __init__(self):
        self.lc_model = SEIU_TaiXiu()
        self.tav1_model = TAV1Predictor()
        self.deep_brain = DeepBrainV2()
        self.patternMem = PatternMemory()
        self.agents = [
            Agent("Bệt", lambda h: h[-1]["tx"] if h else "LON"),
            Agent("Đảo", lambda h: "NHO" if h[-1]["tx"] == "LON" else "LON" if h else "LON"),
            Agent("Điểm", lambda h: "LON" if sum(h[-5:].get("total", 11) for h in h[-5:])/5 > 12 else "NHO" if h else "LON"),
            Agent("Ngẫu nhiên", lambda h: random.choice(["LON", "NHO"]))
        ]
        self.kg = KnowledgeGraph()
        self.history_raw = []; self.history_lc = []; self.history_tav1 = []
        self.lastVotes = {"LON": 0, "NHO": 0}
    def loadHistory(self, history):
        self.history_raw = history[:]
        self.history_lc = [{"tx": "LON" if h["result"] == "Lớn" else "NHO", "total": h.get("score", 11), "session": h.get("session", i)} for i, h in enumerate(history)]
        self.history_tav1 = [{"session": h.get("session", i), "result": h["result"], "score": h.get("score", 0)} for i, h in enumerate(history)]
        self.tav1_model.setHistory(self.history_tav1)
        for i in range(len(history)-1):
            seq = "".join(["LON" if h["result"] == "Lớn" else "NHO" for h in history[:i+1]])
            if len(seq) >= 2:
                next = "LON" if history[i+1]["result"] == "Lớn" else "NHO"
                correct = history[i+1].get("correct", False)
                self.patternMem.add(seq[-8:], next, correct)
    def updateWithResult(self, actualResult, score=11):
        real_tx = "LON" if actualResult == "Lớn" else "NHO"
        real_vn = actualResult
        if len(self.history_lc) >= 2:
            self.lc_model.update(self.history_lc[:-1], real_tx)
        self.history_lc.append({"tx": real_tx, "total": score, "session": len(self.history_lc)+1})
        self.history_tav1.append({"session": len(self.history_tav1)+1, "result": real_vn, "score": score})
        self.tav1_model.setHistory(self.history_tav1)
        seq = "".join([h["tx"] for h in self.history_lc[-8:]])
        lastPred = self.history_raw[-1]["prediction"] if self.history_raw else None
        correct = (lastPred == actualResult)
        self.patternMem.add(seq, real_tx, correct)
        histBefore = self.history_lc[:-1]; histAfter = self.history_lc
        for a in self.agents:
            if a.lastAction and a.lastState:
                reward = 1 if a.lastAction == real_tx else -1
                a.update(histBefore, a.lastAction, reward, histAfter)
        curState = "|".join([h["tx"] for h in self.history_lc[-8:]])
        nextState = "|".join([h["tx"] for h in self.history_lc[-7:]]) if len(self.history_lc) >= 7 else curState
        self.kg.addTransition(curState, nextState)
        features = extractAdvancedFeatures(self.history_lc[:-1])
        if len(features) == 20:
            self.deep_brain.train(features, [1, 0] if actualResult == "Lớn" else [0, 1])
        self.history_raw.append({"session": len(self.history_raw)+1, "result": actualResult, "score": score})
    def multiAgentPredict(self, history):
        votes = {"LON": 0, "NHO": 0}
        for a in self.agents:
            pred = a.predict(history)
            votes[pred] += 1
        state = "|".join([h["tx"] for h in history[-8:]])
        kgPred = self.kg.predict(state)
        if kgPred: votes[kgPred] += 2
        seq = "".join([h["tx"] for h in history[-8:]])
        memPred = self.patternMem.predict(seq)
        if memPred: votes[memPred] += 1.5
        self.lastVotes = votes
        return "LON" if votes["LON"] >= votes["NHO"] else "NHO"
    def predictOnHistory(self, historyBefore):
        if len(historyBefore) < 3: return None
        histLC = [{"tx": "LON" if h["result"] == "Lớn" else "NHO", "total": h.get("score", 11)} for h in historyBefore]
        histTAV1 = [{"session": h.get("session", i), "result": h["result"], "score": h.get("score", 0)} for i, h in enumerate(historyBefore)]
        predLC = self.lc_model.predict(histLC)
        predTAV1 = self.tav1_model.predict(histTAV1)
        predDeep = self.deep_brain.predict(extractAdvancedFeatures(histLC))
        predMulti = self.multiAgentPredict(histLC)
        probLonLC = predLC["conf"] if predLC["pred"] == "LON" else 1 - predLC["conf"]
        probLonTAV1 = predTAV1["confidence"] / 100
        probLonDeep = predDeep["LON"] if predDeep else 0.5
        probLonMulti = 0.7 if predMulti == "LON" else 0.3
        deepAdj = self.deep_brain.getConfidenceAdjustment()
        probLonDeep = max(0.1, min(0.9, probLonDeep + deepAdj/100))
        betPred = aZ_betCung(histLC)
        betBoost = 0.35 if betPred else 0
        weights = {"lc": 0.25, "tav1": 0.25, "deep": 0.2, "multi": 0.15, "bet": 0.15}
        probLon = weights["lc"] * probLonLC + weights["tav1"] * probLonTAV1 + weights["deep"] * probLonDeep + weights["multi"] * probLonMulti
        if betPred == "LON": probLon += weights["bet"] + betBoost
        elif betPred == "NHO": probLon -= weights["bet"] + betBoost
        probLon = max(0.01, min(0.99, probLon))
        probNho = 1 - probLon
        pred = "LON" if probLon >= 0.5 else "NHO"
        confidence = min(98, max(55, round((probLon if probLon >= 0.5 else probNho) * 100)))
        return {
            "prediction": "Lớn" if pred == "LON" else "Nhỏ",
            "confidence": confidence,
            "prob_lon": round(probLon * 100, 1),
            "prob_nho": round(probNho * 100, 1),
            "lc_detail": predLC,
            "tav1_detail": predTAV1,
            "deep_detail": predDeep,
            "multi_detail": predMulti,
            "bet_detail": betPred
        }

# ========================================================================
# BOT COMMANDS
# ========================================================================

@bot.message_handler(commands=['start'])
def send_start(message):
    cid = message.chat.id
    init_user(cid)
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton("➕ Thêm TK", callback_data='add_acc'),
        types.InlineKeyboardButton("🎲 LOTTO", callback_data='lotto')
    )
    keyboard.add(
        types.InlineKeyboardButton("▶️ Bắt đầu", callback_data='start_bot'),
        types.InlineKeyboardButton("⏹ Dừng", callback_data='stop_bot')
    )
    keyboard.add(
        types.InlineKeyboardButton("📊 Lịch sử", callback_data='history')
    )
    bot.reply_to(message, f"""
👑 *LOTTO VIP BOT* 👑
✅ Bot tự động đặt cược LỚN/NHỎ
📞 Support: 0365463767
""", reply_markup=keyboard, parse_mode='Markdown')

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    cid = call.message.chat.id
    data = call.data
    if data == 'add_acc':
        bot.answer_callback_query(call.id)
        bot.send_message(cid, "📌 /add_acc <userId> <secretKey>")
    elif data == 'lotto':
        bot.answer_callback_query(call.id)
        bot.send_message(cid, "💰 /set_bet <số> - Đặt cược\n📈 /set_multiplier <số> - Gấp thếp")
    elif data == 'start_bot':
        bot.answer_callback_query(call.id)
        if cid in running_bots and running_bots[cid].is_alive():
            bot.send_message(cid, "⚠️ Bot đang chạy!")
            return
        if not user_states.get(cid, {}).get('account'):
            bot.send_message(cid, "❌ Chưa có TK! /add_acc")
            return
        user_states[cid]['last_issue_placed'] = None
        user_states[cid]['bet_history'] = []
        thread = threading.Thread(target=run_lotto, args=(cid,))
        thread.daemon = True
        thread.start()
        running_bots[cid] = thread
        bot.send_message(cid, "🚀 Đã bắt đầu!")
    elif data == 'stop_bot':
        bot.answer_callback_query(call.id)
        if cid in user_states:
            user_states[cid]['running'] = False
            bot.send_message(cid, "🛑 Đã dừng!")
    elif data == 'history':
        bot.answer_callback_query(call.id)
        show_history(cid)

@bot.message_handler(commands=['add_acc'])
def add_acc(message):
    parts = message.text.split()
    if len(parts) < 3:
        bot.reply_to(message, "❌ /add_acc <userId> <secretKey>")
        return
    try:
        user_id = int(parts[1]); secret_key = parts[2]
        accounts = load_accounts()
        if any(a.get('userId') == user_id for a in accounts):
            bot.reply_to(message, f"⚠️ TK {user_id} đã tồn tại!")
            return
        accounts.append({"userId": user_id, "secretKey": secret_key})
        save_accounts(accounts)
        balance = get_balance(user_id, secret_key)
        user_states[message.chat.id]['account'] = {"userId": user_id, "secretKey": secret_key}
        bot.reply_to(message, f"✅ Đã thêm! Số dư: {balance:,.0f} BUILD")
    except ValueError:
        bot.reply_to(message, "❌ User ID phải là số!")

@bot.message_handler(commands=['set_bet'])
def set_bet(message):
    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message, "❌ /set_bet <số tiền>")
        return
    try:
        amount = int(parts[1])
        if amount < 1:
            bot.reply_to(message, "⚠️ Tối thiểu 1 BUILD")
            return
        cid = message.chat.id
        init_user(cid)
        user_states[cid]['bet_amount'] = amount
        bot.reply_to(message, f"✅ Cược: {amount:,} BUILD")
    except ValueError:
        bot.reply_to(message, "❌ Phải là số!")

@bot.message_handler(commands=['set_multiplier'])
def set_multiplier(message):
    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message, "❌ /set_multiplier <hệ số>")
        return
    try:
        multiplier = float(parts[1])
        if multiplier < 1.1:
            bot.reply_to(message, "⚠️ Hệ số phải > 1.1")
            return
        cid = message.chat.id
        init_user(cid)
        user_states[cid]['multiplier'] = multiplier
        bot.reply_to(message, f"✅ Gấp thếp: x{multiplier}")
    except ValueError:
        bot.reply_to(message, "❌ Phải là số!")

@bot.message_handler(commands=['history'])
def show_history_command(message):
    show_history(message.chat.id)

def show_history(cid):
    state = user_states.get(cid, {})
    history = state.get('bet_history', [])
    if not history:
        bot.send_message(cid, "📭 Chưa có lịch sử cược nào!")
        return
    msg = "📊 *LỊCH SỬ CƯỢC*\n" + "═" * 30 + "\n"
    total_win = 0
    total_lose = 0
    for h in history[-20:]:
        status = "✅ THẮNG" if h.get('result') == 'win' else "❌ THUA" if h.get('result') == 'lose' else "⏳ CHỜ"
        msg += f"🆔 Phiên: {h.get('issue')}\n"
        msg += f"🎯 Cược: {h.get('bet_type')} | 💰 {h.get('amount')} BUILD\n"
        msg += f"📊 {status} | Số dư: {h.get('balance_after', 0):,.0f} BUILD\n"
        msg += "─" * 20 + "\n"
        if h.get('result') == 'win':
            total_win += 1
        elif h.get('result') == 'lose':
            total_lose += 1
    msg += f"\n📈 Tổng: ✅ {total_win} | ❌ {total_lose}"
    bot.send_message(cid, msg, parse_mode='Markdown')

def run_lotto(chat_id):
    state = user_states.get(chat_id, {})
    account = state.get('account')
    if not account:
        bot.send_message(chat_id, "❌ Chưa có TK!")
        return
    user_id = account['userId']; secret_key = account['secretKey']
    bet_amount = state.get('bet_amount', 1)
    multiplier = state.get('multiplier', 2)
    state['running'] = True
    current_bet = bet_amount
    history = []
    analyzer = TaiXiuCombinedAnalyzer()
    win_count = lose_count = 0
    last_issue_placed = None
    bot.send_message(chat_id, f"🚀 Bắt đầu LOTTO\n💰 Cược: {bet_amount:,}\n📈 Gấp thếp: x{multiplier}")
    while state.get('running', False):
        try:
            home = lotto_get_home(user_id, secret_key)
            if not home or home.get('code') != 0:
                time.sleep(2)
                continue
            data = home.get('data', {})
            last_issue = data.get('last_issue_id')
            last_result = data.get('last_issue_result')
            lucky_codes = data.get('last_issue_lucky_code', [])
            current_balance = get_balance(user_id, secret_key)
            if last_issue is not None and last_issue != last_issue_placed:
                last_issue_placed = None
                if last_result:
                    result_vn = "Lớn" if last_result == "TAI" else "Nhỏ"
                    history.append({"session": last_issue, "result": result_vn, "score": sum(lucky_codes)})
                    if len(history) > 100: history.pop(0)
                    analyzer.loadHistory(history)
                if len(history) >= 3 and last_issue_placed is None:
                    pred = analyzer.predictOnHistory(history)
                    if pred:
                        bet_type = "big" if pred["prediction"] == "Lớn" else "small"
                        if current_balance < current_bet:
                            bot.send_message(chat_id, f"⚠️ Không đủ BUILD! Cần {current_bet}, có {current_balance:,.0f}")
                            current_bet = bet_amount
                            time.sleep(5)
                            continue
                        bot.send_message(chat_id, f"""
🎯 *DỰ ĐOÁN PHIÊN {last_issue}*
━━━━━━━━━━━━━━━━━━━
📌 Cược vào: *{pred['prediction'].upper()}*
💰 Số tiền: *{current_bet:,} BUILD*
📊 Độ tin cậy: *{pred['confidence']}%*
💳 Số dư: *{current_balance:,.0f} BUILD*
━━━━━━━━━━━━━━━━━━━
⏳ Đang đặt cược...
""", parse_mode='Markdown')
                        result = lotto_place_bet(user_id, secret_key, last_issue + 1, bet_type, current_bet)
                        if result.get('code') == 0:
                            state['bet_history'].append({
                                'issue': last_issue,
                                'bet_type': pred['prediction'].upper(),
                                'amount': current_bet,
                                'result': 'waiting',
                                'balance_before': current_balance,
                                'balance_after': None
                            })
                            last_issue_placed = last_issue
                            bot.send_message(chat_id, f"✅ Đã đặt cược thành công!\n🆔 Phiên: {last_issue}\n🎯 Cửa: {pred['prediction'].upper()}\n💰 {current_bet:,} BUILD")
                            time.sleep(10)
                            home_result = lotto_get_home(user_id, secret_key)
                            if home_result and home_result.get('code') == 0:
                                result_data = home_result.get('data', {})
                                actual_result = result_data.get('last_issue_result')
                                if actual_result:
                                    actual_vn = "Lớn" if actual_result == "TAI" else "Nhỏ"
                                    is_win = (pred['prediction'] == actual_vn)
                                    new_balance = get_balance(user_id, secret_key)
                                    if state['bet_history']:
                                        last_entry = state['bet_history'][-1]
                                        last_entry['result'] = 'win' if is_win else 'lose'
                                        last_entry['balance_after'] = new_balance
                                    if is_win:
                                        win_count += 1
                                        current_bet = bet_amount
                                        bot.send_message(chat_id, f"""
🎉 *KẾT QUẢ PHIÊN {last_issue}*
━━━━━━━━━━━━━━━━━━━
✅ *THẮNG!*
🎯 Cửa cược: {pred['prediction'].upper()}
📊 Kết quả thực tế: {actual_vn}
💰 Số dư hiện tại: {new_balance:,.0f} BUILD
━━━━━━━━━━━━━━━━━━━
🔄 Reset cược về {bet_amount:,} BUILD
""", parse_mode='Markdown')
                                    else:
                                        lose_count += 1
                                        current_bet = int(current_bet * multiplier)
                                        bot.send_message(chat_id, f"""
💀 *KẾT QUẢ PHIÊN {last_issue}*
━━━━━━━━━━━━━━━━━━━
❌ *THUA!*
🎯 Cửa cược: {pred['prediction'].upper()}
📊 Kết quả thực tế: {actual_vn}
💰 Số dư hiện tại: {new_balance:,.0f} BUILD
━━━━━━━━━━━━━━━━━━━
🔄 Cược mới: {current_bet:,} BUILD (x{multiplier})
""", parse_mode='Markdown')
            else:
                time.sleep(3)
        except Exception as e:
            logger.error(f"Lotto error: {e}")
            time.sleep(5)
    bot.send_message(chat_id, f"""
🛑 *ĐÃ DỪNG BOT*
━━━━━━━━━━━━━━━━━━━
✅ Thắng: {win_count}
❌ Thua: {lose_count}
📊 Tổng: {win_count + lose_count} ván
💳 Số dư cuối: {get_balance(user_id, secret_key):,.0f} BUILD
━━━━━━━━━━━━━━━━━━━
""", parse_mode='Markdown')

# ========================================================================
# WEBHOOK ROUTES
# ========================================================================

@app.route('/webhook', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return '', 200
    return '', 403

@app.route('/set_webhook', methods=['GET'])
def set_webhook():
    try:
        bot.remove_webhook()
        time.sleep(1)
        bot.set_webhook(url=WEBHOOK_URL)
        return f"✅ Webhook set to {WEBHOOK_URL}", 200
    except Exception as e:
        return f"❌ Error: {e}", 500

@app.route('/', methods=['GET'])
def index():
    return "🤖 Bot is running!", 200

# ========================================================================
# MAIN
# ========================================================================

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'polling':
        print("🚀 LOTTO BOT polling mode...")
        bot.polling(none_stop=True)
    else:
        print(f"🚀 LOTTO BOT webhook mode on port {PORT}")
        app.run(host='0.0.0.0', port=PORT)
