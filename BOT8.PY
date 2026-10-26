"""
╔══════════════════════════════════════════════════════════════════╗
║  SURESHOT UNIFIED BOT  —  best of both files, panel-configurable ║
╚══════════════════════════════════════════════════════════════════╝
"""
import asyncio
import re
import sqlite3
import json
import time
import os
import sys
import secrets
import threading
import traceback
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import date
from functools import partial, wraps
from types import SimpleNamespace

import aiohttp
from dotenv import load_dotenv

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.error import TelegramError, Forbidden, NetworkError, RetryAfter, TimedOut, BadRequest
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ChatJoinRequestHandler, ChatMemberHandler, filters, ContextTypes
)
from html import escape as html_escape, unescape as html_unescape

# ═══════════════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════════════
load_dotenv()

SUPERIOR_ADMIN_ID: int = int(os.getenv("SUPERIOR_ADMIN_ID", "0") or os.getenv("ADMIN_ID", "0") or 0)
BOT_TOKEN:      str = os.getenv("BOT_TOKEN", "")
SOURCE_CHAT_ID: int = int(os.getenv("SOURCE_CHAT_ID", "0") or 0)
CHANNEL_ID:     int = int(os.getenv("CHANNEL_ID", "0") or 0)
ADMIN_ID:       int = int(os.getenv("ADMIN_ID", "0") or 0)

ENV_ADMIN_PERMS = {
    "can_broadcast", "can_stats", "can_manage_seq", "can_toggle_auto_approve",
    "can_approve_requests", "can_test_sequence", "can_reply_users",
    "can_manage_prediction", "can_manage_subadmins", "can_change_source", "can_manage_bot_profile"
}

BROADCAST_CONCURRENCY: int = 40
APPROVAL_CONCURRENCY:  int = 30
SEQUENCE_CONCURRENCY:  int = 50
NOTIFY_CONCURRENCY:    int = 30
SEND_RATE:             float = 12.0
BROADCAST_RATE:        float = 20.0
SEQ_RATE:              float = 22.0
APPROVE_RATE:          float = 30.0
BROADCAST_REPORT:      bool  = True
MAX_RETRIES_DB:        int = 3
DB_PATH:               str = "bot.db"
API_URL:               str = f"https://api.telegram.org/bot{BOT_TOKEN}"
ALBUM_DEBOUNCE:        float = 1.3
MAX_BTNS_PER_ROW:      int = 8
WINGO_API_URL = "https://draw.ar-lottery01.com/WinGo/WinGo_1M/GetHistoryIssuePage.json"

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not set in .env")
if not SUPERIOR_ADMIN_ID and not ADMIN_ID:
    raise ValueError("Set SUPERIOR_ADMIN_ID or ADMIN_ID in .env")

# ═══════════════════════════════════════════════════════════════════
# PREMIUM EMOJI IDs
# ═══════════════════════════════════════════════════════════════════
EMOJI_BROADCAST    = "5931313689331241517"
EMOJI_STATS        = "5931583486291873493"
EMOJI_ADMINS       = "5931657428448842120"
EMOJI_SUBADMINS    = "5931303321280188466"
EMOJI_SEQUENCE     = "5931747300639510638"
EMOJI_APPROVE      = "5931619009966379290"
EMOJI_AUTO_APPROVE = "5931477774261817927"
EMOJI_PERMISSIONS  = "5931697573508158351"
EMOJI_BOT_PROFILE  = "5965320840949011222"
EMOJI_TEST_SEQ     = "6120648298849112199"
EMOJI_PREMIUM      = "6291764155313558218"
EMOJI_INTRO        = "6311999627440691097"
EMOJI_ADD_MSG      = "5397916757333654639"
EMOJI_REMOVE_MSG   = "6120511091823874486"
EMOJI_REORDER      = "5359441070201513074"
EMOJI_LIST_MSG     = "6168060795016976899"
EMOJI_REPLY_SET    = "6242498410822244114"
EMOJI_REPLY_REMOVE = "6266787717896476444"
EMOJI_BACK         = "6264961759795221684"
EMOJI_CANCEL       = "6276025694333966034"
EMOJI_BLUE         = "6321140649286442286"
EMOJI_RED          = "6163177640539721557"
EMOJI_GREEN        = "5260640681906419699"
EMOJI_DEFAULT      = "4956273117191213833"
EMOJI_YES          = "5260640681906419699"
EMOJI_NO           = "6120660741369369103"
EMOJI_SAME_ROW     = "4956591954088428445"
EMOJI_NEXT_ROW     = "4958845510543737828"
EMOJI_DONE         = "5260640681906419699"
EMOJI_ADD_ANOTHER  = "6269130601081608904"
EMOJI_CHANGE_NAME  = "6282641460093260838"
EMOJI_CHANGE_BIO   = "6269425390456935341"
EMOJI_CHANGE_DESC  = "6120953460570460166"
EMOJI_UP           = "5462995330163289902"
EMOJI_STAR1        = "6165853967805845075"
EMOJI_BUTTERFLY    = "6163205317308977224"
EMOJI_LIGHTNING1   = "6163348228050784800"
EMOJI_CHART        = "6203743692549788189"
EMOJI_STAR3        = "6163712312428468196"
EMOJI_TROPHY       = "6165711370596650697"
EMOJI_LIGHTNING2   = "6163534904509338440"
EMOJI_LIGHTNING3   = "6163348228050784800"
EMOJI_SKULL        = "6224482822606819520"
EMOJI_SKULL2       = "6264911817915505675"
EMOJI_ROCKET       = "6276311855119994929"
EMOJI_BRAIN        = "5373180412883378717"
EMOJI_THINK        = "5370919202796348364"
EMOJI_GEAR         = "5370935802844946281"
EMOJI_REPEAT       = "5415588516237157133"
EMOJI_OK           = "5260640681906419699"
EMOJI_SIREN        = "5260750418320836046"
EMOJI_FIREWORK     = "6199293238847740460"
EMOJI_DINO         = "6235524376070984680"
EMOJI_CHANNEL      = "6163667490149765932"
EMOJI_START        = "6276192588173154244"
EMOJI_CROWN        = "5415974569372565930"
EMOJI_LEAVE        = "6339164578328352187"
EMOJI_PIN          = "5416028557111474714"
EMOJI_PREDICTION   = "6266936886405633043"

# ═══════════════════════════════════════════════════════════════════
# FANCY FONTS + HELPERS
# ═══════════════════════════════════════════════════════════════════
_UP = {chr(65 + i): chr(0x1D5D4 + i) for i in range(26)}
_LO = {chr(97 + i): chr(0x1D5EE + i) for i in range(26)}
_DG = {chr(48 + i): chr(0x1D7EC + i) for i in range(10)}
_FX = str.maketrans({**_UP, **_LO, **_DG})
_FX_CAPS = str.maketrans({**{k.lower(): v for k, v in _UP.items()}, **_UP, **_DG})
_REV = str.maketrans({v: k for k, v in {**_UP, **_LO, **_DG}.items()})

def fx(s):  return (s or "").translate(_FX)
def fxc(s): return (s or "").translate(_FX_CAPS)

def K(s):
    s = (s or "").translate(_REV).replace("\u2011", "-").replace("\u2010", "-")
    return re.sub(r"\s+", " ", s).strip().upper()

_FX_SPLIT = re.compile(r"(<[^>]+>|&#?\w+;)")

def fx_html(s):
    if not s:
        return s
    out, skip = [], 0
    for part in _FX_SPLIT.split(s):
        if not part:
            continue
        if part.startswith("<"):
            low = part.lower()
            if low.startswith("<code") or low.startswith("<pre"):
                skip += 1
            elif low.startswith("</code") or low.startswith("</pre"):
                skip = max(0, skip - 1)
            out.append(part)
        elif part.startswith("&") and part.endswith(";"):
            out.append(part)
        else:
            out.append(part if skip else fx(part))
    return "".join(out)

def pe(emoji_id, fallback="⭐"):
    return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'

def card(emoji_id, fb, title, body="", foot="", expandable=False):
    s = f'{pe(emoji_id, fb)} <b>{title}</b>'
    if body:
        s += f'\n<blockquote{" expandable" if expandable else ""}>{body}</blockquote>'
    if foot:
        s += f'\n{foot}'
    return s

def no_perm():
    return card(EMOJI_SKULL, "💀", "No permission", "You don't have access to this action.")

def btn(text, style=None, emoji_id=None):
    b = {"text": fxc(text)}
    if style and style != "default":
        b["style"] = style
    if emoji_id:
        b["icon_custom_emoji_id"] = emoji_id
    return b

def _js(data):
    """Safe JSON state loader — never raises."""
    try:
        v = json.loads(data) if data else {}
        return v if isinstance(v, dict) else {}
    except Exception:
        return {}

# ═══════════════════════════════════════════════════════════════════
# SEMAPHORES + BACKGROUND TASKS
# ═══════════════════════════════════════════════════════════════════
sequence_semaphore = asyncio.Semaphore(SEQUENCE_CONCURRENCY)
notify_semaphore   = asyncio.Semaphore(NOTIFY_CONCURRENCY)
_bg_tasks = set()

def _task_done(t):
    _bg_tasks.discard(t)
    if not t.cancelled() and t.exception() is not None:
        traceback.print_exception(type(t.exception()), t.exception(), t.exception().__traceback__)

def spawn(coro):
    t = asyncio.create_task(coro)
    _bg_tasks.add(t)
    t.add_done_callback(_task_done)
    return t

# ═══════════════════════════════════════════════════════════════════
# RATE LIMITER
# ═══════════════════════════════════════════════════════════════════
class _Bucket:
    def __init__(self, rate):
        self.base_interval = 1.0 / rate
        self.interval = self.base_interval
        self.next = 0.0
        self.flood_until = 0.0
        self.last_flood = 0.0
    def reset(self):
        self.interval = self.base_interval
    async def wait(self):
        loop = asyncio.get_running_loop()
        while True:
            now = loop.time()
            if self.interval > self.base_interval and now - self.last_flood > 20:
                self.interval = max(self.base_interval, self.interval * 0.9)
            start = max(now, self.next, self.flood_until)
            self.next = start + self.interval
            if start > now:
                await asyncio.sleep(start - now)
            if loop.time() >= self.flood_until:
                return
    def flood(self, seconds):
        loop = asyncio.get_running_loop()
        self.flood_until = max(self.flood_until, loop.time() + seconds)
        self.last_flood = loop.time()
        self.interval = min(self.interval * 1.15, self.base_interval * 3)

msg_bucket     = _Bucket(SEND_RATE)
bcast_bucket   = _Bucket(BROADCAST_RATE)
approve_bucket = _Bucket(APPROVE_RATE)
seq_bucket     = _Bucket(SEQ_RATE)

def _retry_secs(e):
    ra = getattr(e, "retry_after", 1)
    return (ra.total_seconds() if hasattr(ra, "total_seconds") else float(ra)) + 0.3

print("""
╔══════════════════════════════════════════════╗
║  SURESHOT UNIFIED BOT — STARTED              ║
╚══════════════════════════════════════════════╝
""")

# ═══════════════════════════════════════════════════════════════════
# DATABASE
# ═══════════════════════════════════════════════════════════════════
class BotInternalError(Exception): pass
class DBError(BotInternalError): pass

def retry_db(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        for attempt in range(MAX_RETRIES_DB):
            try:
                return func(*args, **kwargs)
            except sqlite3.OperationalError as e:
                if attempt < MAX_RETRIES_DB - 1:
                    time.sleep(0.1 * (attempt + 1))
                else:
                    raise DBError(f"DB op failed: {e}")
            except Exception as e:
                raise DBError(f"DB unexpected: {e}")
        raise DBError("Unexpected retry exit")
    return wrapper

_tls = threading.local()

def _open_conn():
    conn = sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES, timeout=8)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=8000")
    return conn

@contextmanager
def get_conn():
    conn = getattr(_tls, "conn", None)
    if conn is None:
        conn = _open_conn()
        _tls.conn = conn
    try:
        yield conn
        conn.commit()
    except BaseException:
        try: conn.rollback()
        except Exception: pass
        raise

# Multi-message lists (each has its own <kind>_msgs table)
KINDS = ("approval", "leave", "start", "prediction")

@retry_db
def init_db():
    with get_conn() as c:
        c.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY, first_seen DATE NOT NULL DEFAULT (DATE('now')),
                username TEXT, first_name TEXT, last_name TEXT);
            CREATE TABLE IF NOT EXISTS subadmins (
                user_id INTEGER PRIMARY KEY, added_at TIMESTAMP DEFAULT (DATETIME('now')),
                role TEXT DEFAULT 'subadmin');
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT, message_id INTEGER NOT NULL,
                position INTEGER NOT NULL UNIQUE, content_json TEXT, buttons_json TEXT DEFAULT '[]',
                message_ids_json TEXT);
            CREATE TABLE IF NOT EXISTS state (user_id INTEGER PRIMARY KEY, action TEXT NOT NULL, data TEXT);
            CREATE TABLE IF NOT EXISTS pending_requests (
                user_id INTEGER, chat_id INTEGER, created_at TIMESTAMP DEFAULT (DATETIME('now')),
                PRIMARY KEY (user_id, chat_id));
            CREATE TABLE IF NOT EXISTS subadmin_perms (
                user_id INTEGER PRIMARY KEY,
                can_broadcast INTEGER DEFAULT 1, can_stats INTEGER DEFAULT 1,
                can_manage_seq INTEGER DEFAULT 0, can_manage_subadmins INTEGER DEFAULT 0,
                can_change_source INTEGER DEFAULT 0, can_manage_bot_profile INTEGER DEFAULT 0,
                can_test_sequence INTEGER DEFAULT 0, can_approve_requests INTEGER DEFAULT 0,
                can_toggle_auto_approve INTEGER DEFAULT 0, can_reply_users INTEGER DEFAULT 0,
                can_manage_prediction INTEGER DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES subadmins(user_id) ON DELETE CASCADE);
            CREATE TABLE IF NOT EXISTS config (key TEXT PRIMARY KEY, value TEXT);
            CREATE TABLE IF NOT EXISTS post_sequence (
                id INTEGER PRIMARY KEY CHECK (id = 1), message_text TEXT, buttons_json TEXT DEFAULT '[]');
            CREATE TABLE IF NOT EXISTS intro (
                id INTEGER PRIMARY KEY CHECK (id = 1), message_text TEXT, buttons_json TEXT DEFAULT '[]');
            CREATE TABLE IF NOT EXISTS direct_reply (
                id INTEGER PRIMARY KEY CHECK (id = 1), message_id INTEGER, content_json TEXT,
                buttons_json TEXT DEFAULT '[]');
            CREATE TABLE IF NOT EXISTS inbox_map (
                admin_id INTEGER NOT NULL, admin_message_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT (DATETIME('now')), PRIMARY KEY (admin_id, admin_message_id));
            CREATE TABLE IF NOT EXISTS broadcast_job (id INTEGER PRIMARY KEY CHECK (id=1), job_json TEXT);
            CREATE TABLE IF NOT EXISTS callback_msgs (
                id INTEGER PRIMARY KEY AUTOINCREMENT, btn_id TEXT UNIQUE, message_id INTEGER, content_json TEXT,
                message_ids_json TEXT);
        """)
        for sql in (
            "ALTER TABLE messages ADD COLUMN message_ids_json TEXT",
            "ALTER TABLE users ADD COLUMN username TEXT",
            "ALTER TABLE users ADD COLUMN first_name TEXT",
            "ALTER TABLE users ADD COLUMN last_name TEXT",
            "ALTER TABLE intro ADD COLUMN buttons_json TEXT DEFAULT '[]'",
            "ALTER TABLE subadmin_perms ADD COLUMN can_manage_bot_profile INTEGER DEFAULT 0",
            "ALTER TABLE subadmin_perms ADD COLUMN can_test_sequence INTEGER DEFAULT 0",
            "ALTER TABLE subadmin_perms ADD COLUMN can_approve_requests INTEGER DEFAULT 0",
            "ALTER TABLE subadmin_perms ADD COLUMN can_toggle_auto_approve INTEGER DEFAULT 0",
            "ALTER TABLE subadmin_perms ADD COLUMN can_reply_users INTEGER DEFAULT 0",
            "ALTER TABLE subadmin_perms ADD COLUMN can_manage_prediction INTEGER DEFAULT 0",
            "ALTER TABLE callback_msgs ADD COLUMN message_ids_json TEXT",
        ):
            try: c.execute(sql)
            except sqlite3.OperationalError: pass
        c.execute("INSERT OR IGNORE INTO config (key, value) VALUES ('source_chat_id', ?)", (str(SOURCE_CHAT_ID),))
        c.execute("INSERT OR IGNORE INTO config (key, value) VALUES ('tracked_channel_id', ?)", (str(CHANNEL_ID),))
        c.execute("INSERT OR IGNORE INTO config (key, value) VALUES ('auto_approve', '0')")
        c.execute("INSERT OR IGNORE INTO config (key, value) VALUES ('pin_position', '')")
        for t in ("post_sequence", "intro", "direct_reply"):
            c.execute(f"INSERT OR IGNORE INTO {t} (id) VALUES (1)")
        for k in KINDS:
            c.execute(f"CREATE TABLE IF NOT EXISTS {k}_msgs (id INTEGER PRIMARY KEY AUTOINCREMENT, message_id INTEGER NOT NULL, "
                      f"position INTEGER NOT NULL UNIQUE, content_json TEXT, buttons_json TEXT DEFAULT '[]', message_ids_json TEXT)")

_cfg_cache = {}

@retry_db
def _cfg_raw_get(key):
    with get_conn() as c:
        r = c.execute("SELECT value FROM config WHERE key=?", (key,)).fetchone()
        return r["value"] if r else None

@retry_db
def _cfg_raw_set(key, val):
    with get_conn() as c:
        c.execute("INSERT INTO config (key,value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, val))

def cfg_get(key):
    ck = "cfg:" + key
    if ck not in _cfg_cache:
        _cfg_cache[ck] = _cfg_raw_get(key)
    return _cfg_cache[ck]

def cfg_set(key, val):
    _cfg_raw_set(key, val)
    _cfg_cache["cfg:" + key] = val

# ── Users ──
@retry_db
def db_upsert_user(user_id, username=None, first_name=None, last_name=None):
    with get_conn() as c:
        return c.execute(
            "INSERT INTO users (user_id, username, first_name, last_name) VALUES (?,?,?,?) "
            "ON CONFLICT(user_id) DO UPDATE SET username=excluded.username, first_name=excluded.first_name, last_name=excluded.last_name",
            (user_id, username, first_name, last_name)).rowcount > 0

@retry_db
def db_get_user(user_id):
    with get_conn() as c:
        row = c.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
        return dict(row) if row else None

@retry_db
def db_total_users():
    with get_conn() as c:
        return c.execute("SELECT COUNT(*) FROM users").fetchone()[0]

@retry_db
def db_daily_users():
    with get_conn() as c:
        return c.execute("SELECT COUNT(*) FROM users WHERE first_seen = ?", (date.today().isoformat(),)).fetchone()[0]

@retry_db
def db_all_user_ids():
    with get_conn() as c:
        return [r["user_id"] for r in c.execute("SELECT user_id FROM users").fetchall()]

@retry_db
def db_users_map():
    with get_conn() as c:
        rows = c.execute("SELECT user_id, first_name, last_name, username FROM users").fetchall()
    return {r["user_id"]: SimpleNamespace(id=r["user_id"], first_name=r["first_name"] or "",
                                          last_name=r["last_name"] or "", username=r["username"] or "") for r in rows}

async def _user_stub(user_id):
    row = (await run(db_get_user, user_id)) or {}
    return SimpleNamespace(id=user_id, first_name=row.get("first_name") or "",
                           last_name=row.get("last_name") or "", username=row.get("username") or "")

# ── Broadcast job ──
@retry_db
def db_save_bcast(job_json):
    with get_conn() as c:
        c.execute("INSERT OR REPLACE INTO broadcast_job (id, job_json) VALUES (1, ?)", (job_json,))

@retry_db
def db_load_bcast():
    with get_conn() as c:
        r = c.execute("SELECT job_json FROM broadcast_job WHERE id=1").fetchone()
    return r["job_json"] if r else None

@retry_db
def db_clear_bcast():
    with get_conn() as c:
        c.execute("DELETE FROM broadcast_job WHERE id=1")

# ═══════════════════════════════════════════════════════════════════
# ROLES & PERMISSIONS
# ═══════════════════════════════════════════════════════════════════
def is_superior(uid): return uid == SUPERIOR_ADMIN_ID
def is_env_admin(uid): return bool(ADMIN_ID) and uid == ADMIN_ID and not is_superior(uid)

_admin_roles = {}
_admin_perms = {}
_cache_ready = False

def refresh_admin_cache():
    global _admin_roles, _admin_perms, _cache_ready
    try:
        with get_conn() as c:
            roles = {r["user_id"]: (r["role"] or "subadmin") for r in c.execute("SELECT user_id, role FROM subadmins")}
            for uid, role in roles.items():
                cur = c.execute("INSERT OR IGNORE INTO subadmin_perms (user_id) VALUES (?)", (uid,))
                if cur.rowcount and role == "admin":
                    c.execute("UPDATE subadmin_perms SET can_approve_requests=1, can_toggle_auto_approve=1 WHERE user_id=?", (uid,))
            perms = {}
            for row in c.execute("SELECT * FROM subadmin_perms"):
                if row["user_id"] in roles:
                    perms[row["user_id"]] = {k: bool(row[k]) for k in row.keys() if k != "user_id"}
        _admin_roles, _admin_perms, _cache_ready = roles, perms, True
        return True
    except Exception:
        traceback.print_exc()
        return False

def _ensure_cache():
    if not _cache_ready:
        refresh_admin_cache()

def db_get_admin_role(uid):
    _ensure_cache()
    return _admin_roles.get(uid)

def db_is_subadmin(uid): return db_get_admin_role(uid) is not None
def is_any_admin(uid): return is_superior(uid) or is_env_admin(uid) or db_is_subadmin(uid)

@retry_db
def _db_add_admin(uid, role):
    with get_conn() as c:
        try:
            c.execute("INSERT INTO subadmins (user_id, role) VALUES (?,?)", (uid, role))
        except sqlite3.IntegrityError:
            return False
        c.execute("INSERT OR IGNORE INTO subadmin_perms (user_id) VALUES (?)", (uid,))
        if role == "admin":
            c.execute("UPDATE subadmin_perms SET can_approve_requests=1, can_toggle_auto_approve=1 WHERE user_id=?", (uid,))
        return True

def db_add_admin(uid, role="subadmin"):
    ok = _db_add_admin(uid, role); refresh_admin_cache(); return ok

@retry_db
def _db_remove_subadmin(uid):
    with get_conn() as c:
        c.execute("DELETE FROM subadmin_perms WHERE user_id=?", (uid,))
        return c.execute("DELETE FROM subadmins WHERE user_id=?", (uid,)).rowcount > 0

def db_remove_subadmin(uid):
    ok = _db_remove_subadmin(uid); refresh_admin_cache(); return ok

def db_list_admins(role_filter=None):
    _ensure_cache()
    return [{"user_id": u, "role": r} for u, r in list(_admin_roles.items()) if not role_filter or r == role_filter]

PERMISSIONS = [
    "can_broadcast", "can_stats", "can_manage_seq", "can_test_sequence",
    "can_approve_requests", "can_toggle_auto_approve", "can_reply_users",
    "can_manage_prediction", "can_manage_subadmins", "can_change_source", "can_manage_bot_profile",
]
PERM_DISPLAY = {
    "can_broadcast": "Broadcast", "can_stats": "Stats", "can_manage_seq": "Set Messages",
    "can_test_sequence": "Test Sequence", "can_approve_requests": "Approve All Requests",
    "can_toggle_auto_approve": "Auto-Approve Toggle", "can_reply_users": "Reply To Users",
    "can_manage_prediction": "Prediction Msg", "can_manage_subadmins": "Manage Subadmins",
    "can_change_source": "Tracked Channel", "can_manage_bot_profile": "Bot Profile",
}

def db_get_subadmin_perms(uid):
    _ensure_cache()
    return dict(_admin_perms.get(uid, {}))

@retry_db
def _db_set_perm(uid, perm, value):
    with get_conn() as c:
        c.execute("INSERT OR IGNORE INTO subadmin_perms (user_id) VALUES (?)", (uid,))
        c.execute(f"UPDATE subadmin_perms SET {perm}=? WHERE user_id=?", (int(value), uid))

def db_set_subadmin_perm(uid, perm, value):
    if perm not in PERMISSIONS:
        return
    _db_set_perm(uid, perm, value)
    if uid in _admin_perms:
        _admin_perms[uid][perm] = bool(value)
    refresh_admin_cache()

def db_has_perm(uid, perm):
    if is_superior(uid):
        return True
    if is_env_admin(uid):
        return perm in ENV_ADMIN_PERMS
    return db_get_subadmin_perms(uid).get(perm, False)

def can_manage_subs(uid):
    return is_superior(uid) or is_env_admin(uid) or db_get_admin_role(uid) == "admin" or (db_is_subadmin(uid) and db_has_perm(uid, "can_manage_subadmins"))

def can_tracked_channel(uid):
    return is_superior(uid) or is_env_admin(uid) or (db_is_subadmin(uid) and db_has_perm(uid, "can_change_source"))

def can_bot_profile(uid):
    return is_superior(uid) or is_env_admin(uid) or (db_is_subadmin(uid) and db_has_perm(uid, "can_manage_bot_profile"))

def can_prediction(uid):
    return is_superior(uid) or is_env_admin(uid) or (db_is_subadmin(uid) and db_has_perm(uid, "can_manage_prediction"))

def _kind_perm(kind):
    return "can_manage_prediction" if kind == "prediction" else "can_manage_seq"

def _target_perm(target):
    return "can_manage_prediction" if target == "prediction" else "can_manage_seq"

# ── Auto-approve ──
_auto = {"v": False, "loaded": False}

def db_get_auto_approve():
    if _auto["loaded"]:
        return _auto["v"]
    try:
        with get_conn() as c:
            row = c.execute("SELECT value FROM config WHERE key='auto_approve'").fetchone()
        _auto.update(v=bool(row and row["value"] == "1"), loaded=True)
    except Exception:
        pass
    return _auto["v"]

@retry_db
def _db_set_auto_approve(value):
    with get_conn() as c:
        c.execute("UPDATE config SET value=? WHERE key='auto_approve'", ("1" if value else "0",))

def db_set_auto_approve(value):
    _db_set_auto_approve(value)
    _auto.update(v=bool(value), loaded=True)

# ── Pending requests ──
@retry_db
def db_add_pending_request(uid, chat_id):
    with get_conn() as c:
        c.execute("INSERT OR IGNORE INTO pending_requests (user_id,chat_id) VALUES (?,?)", (uid, chat_id))

@retry_db
def db_get_pending_requests():
    with get_conn() as c:
        return c.execute("SELECT user_id, chat_id FROM pending_requests").fetchall() or []

@retry_db
def db_get_stale_pending(secs):
    with get_conn() as c:
        return c.execute("SELECT user_id, chat_id FROM pending_requests WHERE created_at <= DATETIME('now', ?)",
                         (f"-{int(secs)} seconds",)).fetchall() or []

@retry_db
def db_remove_pending_request(uid, chat_id):
    with get_conn() as c:
        c.execute("DELETE FROM pending_requests WHERE user_id=? AND chat_id=?", (uid, chat_id))

@retry_db
def db_pop_pending_request(uid, chat_id):
    with get_conn() as c:
        return c.execute("DELETE FROM pending_requests WHERE user_id=? AND chat_id=?", (uid, chat_id)).rowcount > 0

# ── Intro / Direct reply ──
@retry_db
def db_get_intro():
    with get_conn() as c:
        row = c.execute("SELECT message_text FROM intro WHERE id=1").fetchone()
        return row["message_text"] if row and row["message_text"] else None

@retry_db
def db_set_intro(text):
    with get_conn() as c:
        c.execute("UPDATE intro SET message_text=? WHERE id=1", (text,))

@retry_db
def db_get_intro_buttons():
    with get_conn() as c:
        row = c.execute("SELECT buttons_json FROM intro WHERE id=1").fetchone()
        return row["buttons_json"] if row and row["buttons_json"] else "[]"

@retry_db
def db_set_intro_buttons(buttons_json):
    with get_conn() as c:
        c.execute("UPDATE intro SET buttons_json=? WHERE id=1", (buttons_json,))

@retry_db
def db_get_direct_reply():
    with get_conn() as c:
        row = c.execute("SELECT * FROM direct_reply WHERE id=1").fetchone()
        return dict(row) if row else {}

@retry_db
def db_set_direct_reply(message_id, content_json):
    with get_conn() as c:
        c.execute("UPDATE direct_reply SET message_id=?, content_json=?, buttons_json='[]' WHERE id=1", (message_id, content_json))

@retry_db
def db_clear_direct_reply():
    with get_conn() as c:
        c.execute("UPDATE direct_reply SET message_id=NULL, content_json=NULL, buttons_json='[]' WHERE id=1")

# ── Inbox map ──
@retry_db
def db_add_inbox_map(admin_id, admin_message_id, user_id):
    with get_conn() as c:
        c.execute("INSERT OR REPLACE INTO inbox_map (admin_id, admin_message_id, user_id) VALUES (?,?,?)",
                  (admin_id, admin_message_id, user_id))

@retry_db
def db_get_inbox_map(admin_id, admin_message_id):
    with get_conn() as c:
        row = c.execute("SELECT user_id FROM inbox_map WHERE admin_id=? AND admin_message_id=?",
                        (admin_id, admin_message_id)).fetchone()
        return row["user_id"] if row else None

# ── Pin position ──
@retry_db
def db_get_pin_position():
    with get_conn() as c:
        row = c.execute("SELECT value FROM config WHERE key='pin_position'").fetchone()
    try: return int(row["value"]) if row and row["value"] else None
    except Exception: return None

@retry_db
def db_set_pin_position(pos):
    with get_conn() as c:
        c.execute("INSERT INTO config (key, value) VALUES ('pin_position', ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                  ("" if pos is None else str(pos),))

# ── Join sequence ──
@retry_db
def db_add_message(message_id, position, content_json=None, buttons_json='[]', message_ids_json=None):
    with get_conn() as c:
        c.execute("INSERT OR REPLACE INTO messages (message_id,position,content_json,buttons_json,message_ids_json) VALUES (?,?,?,?,?)",
                  (message_id, position, content_json, buttons_json, message_ids_json))
        return True

@retry_db
def db_remove_message_pos(position):
    with get_conn() as c:
        return c.execute("DELETE FROM messages WHERE position=?", (position,)).rowcount > 0

@retry_db
def db_get_messages():
    with get_conn() as c:
        return c.execute("SELECT * FROM messages ORDER BY position ASC").fetchall() or []

@retry_db
def db_reorder_message(message_id, new_position):
    """Moves a message to new_position; the message already there swaps into the old slot (nothing is deleted)."""
    with get_conn() as c:
        row = c.execute("SELECT position FROM messages WHERE message_id=?", (message_id,)).fetchone()
        if not row:
            return False
        old = row["position"]
        if old == new_position:
            return True
        c.execute("UPDATE messages SET position=-1 WHERE message_id=?", (message_id,))
        c.execute("UPDATE messages SET position=? WHERE position=?", (old, new_position))
        c.execute("UPDATE messages SET position=? WHERE message_id=?", (new_position, message_id))
        return True

@retry_db
def db_update_message_buttons(position, buttons_json):
    with get_conn() as c:
        c.execute("UPDATE messages SET buttons_json=? WHERE position=?", (buttons_json, position))

# ── Source chat / tracked channel / post sequence ──
@retry_db
def db_get_source_chat_id():
    with get_conn() as c:
        row = c.execute("SELECT value FROM config WHERE key='source_chat_id'").fetchone()
    try: return int(row["value"]) if row and row["value"] else SOURCE_CHAT_ID
    except Exception: return SOURCE_CHAT_ID

@retry_db
def db_get_channel_id():
    with get_conn() as c:
        row = c.execute("SELECT value FROM config WHERE key='tracked_channel_id'").fetchone()
    try: return int(row["value"]) if row and row["value"] else CHANNEL_ID
    except Exception: return CHANNEL_ID

@retry_db
def db_set_channel_id(chat_id):
    with get_conn() as c:
        c.execute("INSERT INTO config (key, value) VALUES ('tracked_channel_id', ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                  (str(chat_id),))

@retry_db
def db_get_post_sequence():
    with get_conn() as c:
        row = c.execute("SELECT message_text, buttons_json FROM post_sequence WHERE id=1").fetchone()
        return dict(row) if row else {}

# ── Multi-message lists ──
def _k_raw_list(kind):
    with get_conn() as c:
        return list(c.execute(f"SELECT * FROM {kind}_msgs ORDER BY position ASC").fetchall() or [])

def db_k_list(kind):
    key = "k_" + kind
    if key not in _cfg_cache:
        _cfg_cache[key] = retry_db(_k_raw_list)(kind)
    return _cfg_cache[key]

@retry_db
def _k_write(sql, params):
    with get_conn() as c:
        return c.execute(sql, params).rowcount

def db_k_add(kind, message_id, position, content_json, buttons_json="[]", ids_json=None):
    _k_write(f"INSERT OR REPLACE INTO {kind}_msgs (message_id,position,content_json,buttons_json,message_ids_json) VALUES (?,?,?,?,?)",
             (message_id, position, content_json, buttons_json, ids_json))
    _cfg_cache["k_" + kind] = retry_db(_k_raw_list)(kind)
    return True

def db_k_remove_pos(kind, position):
    n = _k_write(f"DELETE FROM {kind}_msgs WHERE position=?", (position,))
    _cfg_cache["k_" + kind] = retry_db(_k_raw_list)(kind)
    return n > 0

def db_k_set_buttons(kind, position, buttons_json):
    _k_write(f"UPDATE {kind}_msgs SET buttons_json=? WHERE position=?", (buttons_json, position))
    _cfg_cache["k_" + kind] = retry_db(_k_raw_list)(kind)

# ── Callback Messages ──
@retry_db
def db_add_callback_msg(btn_id, message_id, content_json, ids_json=None):
    with get_conn() as c:
        c.execute("INSERT INTO callback_msgs (btn_id, message_id, content_json, message_ids_json) VALUES (?,?,?,?)",
                  (btn_id, message_id, content_json, ids_json))

@retry_db
def db_get_callback_msg(btn_id):
    with get_conn() as c:
        row = c.execute("SELECT * FROM callback_msgs WHERE btn_id=?", (btn_id,)).fetchone()
        return dict(row) if row else None

# ── State machine ──
_state_cache = {}
_state_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="state")

def _persist(sql, params):
    for attempt in range(6):
        try:
            with get_conn() as c:
                c.execute(sql, params)
            return
        except Exception:
            time.sleep(0.2 * (attempt + 1))

def db_set_state(uid, action, data=""):
    _state_cache[uid] = (action, data)
    _state_pool.submit(_persist, "INSERT OR REPLACE INTO state (user_id,action,data) VALUES (?,?,?)", (uid, action, data))

def db_get_state(uid):
    return _state_cache.get(uid, (None, None))

def db_clear_state(uid):
    if _state_cache.pop(uid, None) is not None:
        _state_pool.submit(_persist, "DELETE FROM state WHERE user_id=?", (uid,))

def _load_states():
    with get_conn() as c:
        for row in c.execute("SELECT user_id, action, data FROM state"):
            _state_cache[row["user_id"]] = (row["action"], row["data"])

# ── Read-through caches ──
_READERS = {}
def _cached_reader(key, fn):
    _READERS[key] = fn
    @wraps(fn)
    def w():
        if key not in _cfg_cache:
            _cfg_cache[key] = fn()
        return _cfg_cache[key]
    return w

def _writer(fn, *keys):
    @wraps(fn)
    def w(*a, **k):
        r = fn(*a, **k)
        for key in keys:
            try: _cfg_cache[key] = _READERS[key]()
            except Exception: _cfg_cache.pop(key, None)
        return r
    return w

db_get_intro            = _cached_reader("intro", db_get_intro)
db_get_intro_buttons    = _cached_reader("intro_btns", db_get_intro_buttons)
db_get_direct_reply     = _cached_reader("reply", db_get_direct_reply)
db_get_pin_position     = _cached_reader("pin", db_get_pin_position)
db_get_messages         = _cached_reader("messages", db_get_messages)
db_get_source_chat_id   = _cached_reader("source", db_get_source_chat_id)
db_get_channel_id       = _cached_reader("channel", db_get_channel_id)
db_get_post_sequence    = _cached_reader("post", db_get_post_sequence)

db_set_intro              = _writer(db_set_intro, "intro")
db_set_intro_buttons      = _writer(db_set_intro_buttons, "intro_btns")
db_set_direct_reply       = _writer(db_set_direct_reply, "reply")
db_clear_direct_reply     = _writer(db_clear_direct_reply, "reply")
db_set_pin_position       = _writer(db_set_pin_position, "pin")
db_add_message            = _writer(db_add_message, "messages")
db_remove_message_pos     = _writer(db_remove_message_pos, "messages")
db_reorder_message        = _writer(db_reorder_message, "messages")
db_update_message_buttons = _writer(db_update_message_buttons, "messages")
db_set_channel_id         = _writer(db_set_channel_id, "channel")

def _warm_cache():
    for key, fn in _READERS.items():
        _cfg_cache[key] = fn()
    for kind in KINDS:
        _cfg_cache["k_" + kind] = retry_db(_k_raw_list)(kind)
    cfg_get("intro_lpo")
    _load_states()
    db_get_auto_approve()

# ═══════════════════════════════════════════════════════════════════
# THREAD POOLS + run()
# ═══════════════════════════════════════════════════════════════════
_db_pool = ThreadPoolExecutor(max_workers=8, thread_name_prefix="db")
_bg_pool = ThreadPoolExecutor(max_workers=12, thread_name_prefix="dbbg")

_INSTANT = {
    db_set_state, db_get_state, db_clear_state, db_get_auto_approve, db_k_list, cfg_get,
    db_get_intro, db_get_direct_reply, db_get_pin_position, db_get_messages,
    db_get_source_chat_id, db_get_channel_id, db_get_post_sequence, db_list_admins,
}
_BG = {
    db_upsert_user, db_add_pending_request, db_remove_pending_request, db_pop_pending_request,
    db_get_user, db_add_inbox_map, db_get_stale_pending, db_get_pending_requests,
}

async def run(func, *args):
    if func in _INSTANT:
        return func(*args)
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_bg_pool if func in _BG else _db_pool, partial(func, *args))

# ═══════════════════════════════════════════════════════════════════
# HTTP / BOT API
# ═══════════════════════════════════════════════════════════════════
_http_session = None

async def _get_session():
    global _http_session
    if _http_session is None or _http_session.closed:
        _http_session = aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=0))
    return _http_session

async def close_http_session():
    if _http_session and not _http_session.closed:
        await _http_session.close()

async def _post(endpoint, payload, bucket=None):
    b = bucket or msg_bucket
    net = floods = 0
    while True:
        await b.wait()
        try:
            session = await _get_session()
            async with session.post(f"{API_URL}/{endpoint}", json=payload,
                                    timeout=aiohttp.ClientTimeout(total=30)) as r:
                data = await r.json(content_type=None)
        except (aiohttp.ClientError, asyncio.TimeoutError):
            net += 1
            if net >= 6:
                return None
            await asyncio.sleep(0.5 * net)
            continue
        except Exception:
            return None
        if not isinstance(data, dict):
            return None
        if data.get("ok"):
            return data
        code = data.get("error_code")
        if code == 429:
            floods += 1
            if floods > 40:
                return data
            b.flood(float((data.get("parameters") or {}).get("retry_after", 1)) + 0.3)
            continue
        if code and code >= 500:
            net += 1
            if net >= 6:
                return data
            await asyncio.sleep(0.5 * net)
            continue
        return data

def _strip_html(s):
    return html_unescape(re.sub(r"<[^>]+>", "", s or ""))

def _needs_plain_retry(resp):
    if not resp or resp.get("ok"):
        return False
    d = str(resp.get("description", "")).lower()
    return any(k in d for k in ("parse", "entit", "emoji", "identifier", "caption"))

async def _send_payload(payload, bucket=None):
    bucket = bucket or seq_bucket
    resp = await _post("sendMessage", payload, bucket)
    if resp and not resp.get("ok") and _needs_plain_retry(resp):
        p2 = {k: v for k, v in payload.items() if k != "parse_mode"}
        p2["text"] = _strip_html(payload.get("text", ""))
        resp = await _post("sendMessage", p2, bucket)
    return resp

async def send_raw_message(chat_id, text, reply_markup_dict=None, parse_mode="HTML"):
    if not chat_id:
        return None
    payload = {"chat_id": chat_id, "text": fx_html(text), "parse_mode": parse_mode,
               "link_preview_options": {"is_disabled": True}}
    if reply_markup_dict:
        payload["reply_markup"] = reply_markup_dict
    resp = await _post("sendMessage", payload)
    if resp and not resp.get("ok") and _needs_plain_retry(resp):
        payload.pop("parse_mode", None)
        payload["text"] = _strip_html(payload["text"])
        resp = await _post("sendMessage", payload)
    return resp

def _build_inline_keyboard(buttons_json):
    if not buttons_json or buttons_json == "[]":
        return None
    try:
        buttons = json.loads(buttons_json)
    except Exception:
        return None
    if not buttons:
        return None
    rows = {}
    for b in buttons:
        rows.setdefault(b.get("row", 0), []).append(b)
    kb = []
    for idx in sorted(rows):
        r = []
        for b in rows[idx]:
            d = {"text": b.get("text") or "•"}
            if b.get("url"):
                d["url"] = b["url"]
            elif b.get("callback_data"):
                d["callback_data"] = b["callback_data"]
            else:
                continue
            if b.get("emoji_id"):
                d["icon_custom_emoji_id"] = b["emoji_id"]
            if b.get("style") and b["style"] != "default":
                d["style"] = b["style"]
            r.append(d)
        if r:
            kb.append(r)
    return {"inline_keyboard": kb} if kb else None

async def _copy_retry(bot, chat_id, from_chat_id, message_id, tries=6, bucket=None):
    last = None
    bucket = bucket or msg_bucket
    for attempt in range(tries):
        await bucket.wait()
        try:
            return await bot.copy_message(chat_id=chat_id, from_chat_id=from_chat_id, message_id=message_id)
        except RetryAfter as e:
            bucket.flood(_retry_secs(e)); last = e
        except (Forbidden, BadRequest):
            raise
        except (NetworkError, TimedOut) as e:
            last = e
            await asyncio.sleep(0.5 * (attempt + 1))
    raise last if last else TelegramError("copy failed")

async def copy_album(bot, chat_id, from_chat_id, message_ids, bucket=None):
    bucket = bucket or msg_bucket
    for attempt in range(6):
        await bucket.wait()
        try:
            sent = await bot.copy_messages(chat_id=chat_id, from_chat_id=from_chat_id, message_ids=message_ids)
            return [s.message_id for s in sent]
        except AttributeError:
            break
        except RetryAfter as e:
            bucket.flood(_retry_secs(e))
        except Forbidden:
            raise
        except BadRequest:
            break
        except (NetworkError, TimedOut):
            await asyncio.sleep(0.5 * (attempt + 1))
    ids = []
    for mid in message_ids:
        try:
            s = await _copy_retry(bot, chat_id, from_chat_id, mid, bucket=bucket)
            ids.append(s.message_id)
        except Forbidden:
            raise
        except Exception:
            pass
    return ids or None

async def forward_album(bot, chat_id, from_chat_id, message_ids):
    if not chat_id:
        raise RuntimeError("Source chat is not set")
    try:
        sent = await bot.forward_messages(chat_id=chat_id, from_chat_id=from_chat_id, message_ids=message_ids)
        return [s.message_id for s in sent]
    except AttributeError:
        ids = []
        for mid in message_ids:
            s = await bot.forward_message(chat_id=chat_id, from_chat_id=from_chat_id, message_id=mid)
            ids.append(s.message_id)
        return ids

def build_reply_keyboard_raw(rows, resize_keyboard=True):
    return {"keyboard": [[b if isinstance(b, dict) else {"text": str(b)} for b in row] for row in rows],
            "resize_keyboard": resize_keyboard}

# ═══════════════════════════════════════════════════════════════════
# ENTITIES -> HTML (premium emoji auto-captured)
# ═══════════════════════════════════════════════════════════════════
_ENT_TAGS = {
    "bold": ("<b>", "</b>"), "italic": ("<i>", "</i>"), "underline": ("<u>", "</u>"),
    "strikethrough": ("<s>", "</s>"), "spoiler": ("<tg-spoiler>", "</tg-spoiler>"),
    "code": ("<code>", "</code>"), "blockquote": ("<blockquote>", "</blockquote>"),
    "expandable_blockquote": ("<blockquote expandable>", "</blockquote>"),
}

def _ent_tags(e):
    t = str(getattr(e, "type", ""))
    if t in _ENT_TAGS:
        return _ENT_TAGS[t]
    if t == "custom_emoji" and getattr(e, "custom_emoji_id", None):
        return (f'<tg-emoji emoji-id="{e.custom_emoji_id}">', "</tg-emoji>")
    if t == "text_link" and getattr(e, "url", None):
        return (f'<a href="{html_escape(e.url, quote=True)}">', "</a>")
    if t == "text_mention" and getattr(e, "user", None):
        return (f'<a href="tg://user?id={e.user.id}">', "</a>")
    if t == "pre":
        lang = getattr(e, "language", None)
        if lang:
            return (f'<pre><code class="language-{html_escape(lang, quote=True)}">', "</code></pre>")
        return ("<pre>", "</pre>")
    return None

def entities_to_html(text, entities):
    if not text:
        return ""
    ents = []
    for e in (entities or []):
        tg = _ent_tags(e)
        if tg:
            ents.append((e.offset, e.offset + e.length, tg))
    ents.sort(key=lambda x: (x[0], -x[1]))
    opens = {}
    for st, en, tg in ents:
        opens.setdefault(st, []).append((en, tg))
    out, stack, p16 = [], [], 0
    def close_due(pos):
        due = [i for i, (en, _) in enumerate(stack) if en <= pos]
        if not due:
            return
        low = min(due)
        popped = stack[low:]
        del stack[low:]
        for en, tg in reversed(popped):
            out.append(tg[1])
        for en, tg in popped:
            if en > pos:
                out.append(tg[0]); stack.append((en, tg))
    for ch in text:
        close_due(p16)
        for en, tg in opens.get(p16, []):
            out.append(tg[0]); stack.append((en, tg))
        out.append(html_escape(ch, quote=False))
        p16 += 2 if ord(ch) > 0xFFFF else 1
    close_due(p16)
    for en, tg in reversed(stack):
        out.append(tg[1])
    return "".join(out)

_RAW_HTML_RE = re.compile(r"</?(b|i|u|s|a|code|pre|tg-emoji|tg-spoiler|blockquote)\b", re.I)

def msg_to_html(msg):
    text = msg.text or msg.caption or ""
    ents = msg.entities if msg.text else msg.caption_entities
    if not ents and _RAW_HTML_RE.search(text):
        return text.strip()
    return entities_to_html(text, ents).strip()

def lpo_of(msg):
    o = getattr(msg, "link_preview_options", None)
    if o is None:
        return None
    try:
        d = o.to_dict()
        return d or None
    except Exception:
        return {"is_disabled": True} if getattr(o, "is_disabled", False) else None

def custom_emojis_in(msg):
    ents = (msg.entities if msg.text else msg.caption_entities) or []
    return [e for e in ents if str(e.type) == "custom_emoji" and e.custom_emoji_id]

def _emoji_note(msg):
    n = len(custom_emojis_in(msg))
    return f'\n{pe(EMOJI_PREMIUM,"💎")} <b>Premium emoji captured:</b> <code>{n}</code>' if n else ""

def split_button_text(msg):
    raw = msg.text or msg.caption or ""
    ems = sorted(custom_emojis_in(msg), key=lambda e: e.offset)
    if not ems:
        return raw.strip(), None
    first = ems[0]
    u = raw.encode("utf-16-le")
    fallback = u[2 * first.offset: 2 * (first.offset + first.length)].decode("utf-16-le")
    clean = (u[: 2 * first.offset] + u[2 * (first.offset + first.length):]).decode("utf-16-le").strip()
    return (clean or fallback), first.custom_emoji_id

def normalize_url(t):
    t = (t or "").strip()
    if re.match(r"^(https?://|tg://)", t, re.I):
        return t
    if t.startswith("@") and len(t) > 1:
        return "https://t.me/" + t[1:]
    if re.match(r"^[\w.-]+\.[a-z]{2,}(/.*)?$", t, re.I):
        return "https://" + t
    return None

def extract_message_content(msg):
    data = {}
    if msg.text:
        data.update(type="text", text=msg.text, html=msg_to_html(msg))
        lpo = lpo_of(msg)
        if lpo:
            data["lpo"] = lpo
    elif msg.caption:
        data.update(type="caption", caption=msg.caption, caption_html=msg_to_html(msg))
    else:
        data["type"] = "media"
    for attr in ("video", "document", "audio", "voice", "sticker", "animation", "video_note"):
        v = getattr(msg, attr, None)
        if v:
            data[attr] = v.file_id
    if msg.photo:
        data["photo"] = msg.photo[-1].file_id
    return json.dumps(data)

# ═══════════════════════════════════════════════════════════════════
# PLACEHOLDERS
# ═══════════════════════════════════════════════════════════════════
PLACEHOLDER_HELP = (
    f'{pe(EMOJI_BRAIN,"🧠")} <b>Placeholders</b> (text, captions, albums, broadcast)\n'
    "<blockquote expandable>"
    "<code>{first_name}</code> – first name\n"
    "<code>{last_name}</code> – last name\n"
    "<code>{full_name}</code> – full name\n"
    "<code>{username}</code> – @username\n"
    "<code>{mention}</code> – clickable name\n"
    "<code>{id}</code> – user ID\n"
    "<code>{channel}</code> – channel name\n"
    "<code>{date}</code> – today's date\n"
    "<b>Prediction only:</b>\n"
    "<code>{period}</code> – WinGo period\n"
    "<code>{number}</code> – result number\n"
    "<code>{color}</code> – Red/Green/Violet\n"
    "<code>{bigsmall}</code> – BIG or SMALL\n"
    "<code>{color_emoji}</code> – coloured dot"
    "</blockquote>"
)

_PH_NAMES = ("first_name", "last_name", "full_name", "username", "mention", "id", "channel", "date",
             "period", "number", "color", "bigsmall", "color_emoji")
_PH_RE = re.compile(r"\{((?:[^{}<]|<[^>]*>){1,80}?)\}")
_TAG_RE = re.compile(r"<[^>]*>")
_channel_title = {"v": ""}

def _ph_name(inner):
    n = _TAG_RE.sub("", inner).strip().lower()
    return n if n in _PH_NAMES else None

def has_placeholders(text):
    return bool(text) and any(_ph_name(m.group(1)) for m in _PH_RE.finditer(text))

def render_placeholders(text, user, pred=None):
    if not text or "{" not in text:
        return text
    first = html_escape(getattr(user, "first_name", "") or "")
    last = html_escape(getattr(user, "last_name", "") or "")
    uname = getattr(user, "username", "") or ""
    uid = getattr(user, "id", 0)
    nice = first or "dost"
    vals = {
        "first_name": nice, "last_name": last,
        "full_name": (first + " " + last).strip() or "dost",
        "username": ("@" + html_escape(uname)) if uname else nice,
        "mention": f'<a href="tg://user?id={uid}">{nice}</a>',
        "id": str(uid),
        "channel": html_escape(_channel_title["v"]) or "our channel",
        "date": date.today().strftime("%d %b %Y"),
    }
    if pred:
        num = pred.get("number")
        is_num = isinstance(num, int)
        vals.update(
            period=str(pred.get("period") or "—"),
            number=str(num if num is not None else "—"),
            color=str(pred.get("color") or "—"),
            bigsmall=("BIG" if is_num and num >= 5 else ("SMALL" if is_num else "—")),
            color_emoji=pred.get("color_emoji") or "—",
        )
    else:
        for k in ("period", "number", "color", "bigsmall", "color_emoji"):
            vals[k] = "—"
    def sub(mo):
        name = _ph_name(mo.group(1))
        if not name:
            return mo.group(0)
        return vals[name] + "".join(_TAG_RE.findall(mo.group(1)))
    return _PH_RE.sub(sub, text)

def album_items(msgs):
    out = []
    for m in msgs:
        if m.photo: t, f = "photo", m.photo[-1].file_id
        elif m.video: t, f = "video", m.video.file_id
        elif m.document: t, f = "document", m.document.file_id
        elif m.audio: t, f = "audio", m.audio.file_id
        else: return []
        out.append({"t": t, "file_id": f, "caption_html": msg_to_html(m) if m.caption else ""})
    return out

def album_media(items, user, pred=None):
    media = []
    for it in items:
        d = {"type": it["t"], "media": it["file_id"]}
        if it.get("caption_html"):
            d["caption"] = render_placeholders(it["caption_html"], user, pred)
            d["parse_mode"] = "HTML"
        media.append(d)
    return media

# ═══════════════════════════════════════════════════════════════════
# WINGO API
# ═══════════════════════════════════════════════════════════════════
def _get_color(number):
    if number in (0, 5): return "Violet"
    if number in (1, 3, 7, 9): return "Green"
    return "Red"

def _get_color_emoji(color):
    if color == "Red": return "🔴"
    if color == "Green": return "🟢"
    if color == "Violet": return "🟣"
    return ""

async def fetch_latest_result():
    try:
        session = await _get_session()
        async with session.get(WINGO_API_URL, timeout=aiohttp.ClientTimeout(total=8)) as resp:
            if resp.status != 200:
                return None
            data = await resp.json(content_type=None)
    except Exception:
        return None
    try:
        list_data = data.get("data", {}).get("list", [])
        if not list_data:
            return None
        latest = list_data[0]
        period = latest.get("issueNumber", "Unknown")
        number = int(latest.get("number", 0))
    except Exception:
        return None
    color = _get_color(number)
    return {"period": str(period), "number": number, "color": color, "color_emoji": _get_color_emoji(color)}

# ═══════════════════════════════════════════════════════════════════
# ALBUM BUFFERING
# ═══════════════════════════════════════════════════════════════════
_album_buffers = {}

def buffer_album_part(key, msg, finalize):
    buf = _album_buffers.setdefault(key, {"messages": [], "task": None})
    buf["messages"].append(msg)
    if buf["task"] is not None:
        buf["task"].cancel()
    async def _waiter():
        try:
            await asyncio.sleep(ALBUM_DEBOUNCE)
        except asyncio.CancelledError:
            return
        b = _album_buffers.pop(key, None)
        if b:
            await finalize(sorted(b["messages"], key=lambda m: m.message_id))
    buf["task"] = spawn(_waiter())

# ═══════════════════════════════════════════════════════════════════
# DELIVERY
# ═══════════════════════════════════════════════════════════════════
_PERMANENT = ("blocked", "deactivated", "chat not found", "user not found",
              "peer_id_invalid", "initiate conversation", "kicked", "not a member", "forbidden")

def _row_get(row, key, default=None):
    try:
        v = row[key]
    except (KeyError, IndexError, TypeError):
        return default
    return default if v is None else v

def _is_blocked_resp(resp):
    if not resp or resp.get("ok"):
        return False
    d = str(resp.get("description", "")).lower()
    return resp.get("error_code") == 403 or any(k in d for k in _PERMANENT)

def _state_of(resp):
    if resp and resp.get("ok"):
        res = resp.get("result")
        if isinstance(res, list):
            return "ok", (res[0] or {}).get("message_id") if res else None
        return "ok", (res or {}).get("message_id") if isinstance(res, dict) else None
    return ("blocked" if _is_blocked_resp(resp) else "fail"), None

async def deliver_row(bot, user_id, user, row, source, bucket=None, pred=None):
    bucket = bucket or seq_bucket
    try:
        content = json.loads(_row_get(row, "content_json", "") or "{}")
    except Exception:
        content = {}
    kb = _build_inline_keyboard(_row_get(row, "buttons_json", "[]") or "[]")

    # 1) Text messages — rebuilt from saved HTML (premium emoji + placeholders kept)
    if content.get("type") == "text" and content.get("html"):
        payload = {"chat_id": user_id, "text": render_placeholders(content["html"], user, pred), "parse_mode": "HTML"}
        if content.get("lpo"):
            payload["link_preview_options"] = content["lpo"]
        if kb:
            payload["reply_markup"] = kb
        st, mid = _state_of(await _send_payload(payload, bucket))
        if st != "fail":
            return st, mid
        if _row_get(row, "message_id") and source:
            p = {"chat_id": user_id, "from_chat_id": source, "message_id": _row_get(row, "message_id")}
            if kb:
                p["reply_markup"] = kb
            return _state_of(await _post("copyMessage", p, bucket))
        return "fail", None

    # 2) Albums
    ids_json = _row_get(row, "message_ids_json")
    if ids_json:
        items = content.get("items") or []
        if items and any(has_placeholders(i.get("caption_html")) for i in items):
            st, mid = _state_of(await _post("sendMediaGroup", {"chat_id": user_id, "media": album_media(items, user, pred)}, bucket))
            if st != "fail":
                return st, mid
        try:
            ids = json.loads(ids_json)
        except Exception:
            ids = []
        if ids and source:
            try:
                new_ids = await copy_album(bot, user_id, source, ids, bucket=bucket)
            except Forbidden:
                return "blocked", None
            except Exception:
                new_ids = None
            if new_ids:
                return "ok", new_ids[0]
        return "fail", None

    # 3) Single media — copied from the source channel
    if not source or not _row_get(row, "message_id"):
        return "fail", None
    payload = {"chat_id": user_id, "from_chat_id": source, "message_id": _row_get(row, "message_id")}
    cap = content.get("caption_html")
    if cap and has_placeholders(cap):
        payload["caption"] = render_placeholders(cap, user, pred)
        payload["parse_mode"] = "HTML"
    if kb:
        payload["reply_markup"] = kb
    resp = await _post("copyMessage", payload, bucket)
    if resp and not resp.get("ok") and not _is_blocked_resp(resp):
        d = str(resp.get("description", "")).lower()
        if any(w in d for w in ("button", "url", "markup", "parse", "entit", "caption")):
            for k in ("reply_markup", "caption", "parse_mode"):
                payload.pop(k, None)
            resp = await _post("copyMessage", payload, bucket)
    return _state_of(resp)

async def send_kind_messages(bot, user_id, user, kind, pred=None):
    rows = await run(db_k_list, kind)
    if not rows:
        return False
    source = await run(db_get_source_chat_id)
    for row in rows:
        try:
            status, _ = await deliver_row(bot, user_id, user, row, source, pred=pred)
        except Exception:
            traceback.print_exc()
            continue
        if status == "blocked":
            break
    return True

async def notify_user_approved(bot, user_id):
    async with notify_semaphore:
        user = await _user_stub(user_id)
        if await send_kind_messages(bot, user_id, user, "approval"):
            return
        name = html_escape(user.first_name or "dost")
        text = fx_html(card(EMOJI_OK, "✅", f"Hello {name}",
                            f'Aapki request <b>successfully approve</b> kar di gayi hai! {pe(EMOJI_FIREWORK,"🎇")}'))
        payload = {"chat_id": user_id, "text": text, "parse_mode": "HTML"}
        await _send_payload(payload)

async def send_sequence_to_user(bot, user_id, user=None):
    async with sequence_semaphore:
        if user is None:
            user = await _user_stub(user_id)
        intro = await run(db_get_intro)
        if intro:
            p = {"chat_id": user_id, "text": fx_html(render_placeholders(intro, user)), "parse_mode": "HTML"}
            lpo = await run(cfg_get, "intro_lpo")
            if lpo:
                try: p["link_preview_options"] = json.loads(lpo)
                except Exception: pass
            kb = _build_inline_keyboard(await run(db_get_intro_buttons))
            if kb:
                p["reply_markup"] = kb
            st, _ = _state_of(await _send_payload(p))
            if st == "blocked":
                return
        source = await run(db_get_source_chat_id)
        pin_position = await run(db_get_pin_position)
        for row in await run(db_get_messages):
            try:
                status, mid = await deliver_row(bot, user_id, user, row, source)
            except Exception:
                traceback.print_exc()
                continue
            if status == "blocked":
                return
            if status == "ok" and mid and pin_position is not None and row["position"] == pin_position:
                await _post("pinChatMessage", {"chat_id": user_id, "message_id": mid, "disable_notification": True}, seq_bucket)
        post = await run(db_get_post_sequence)
        if post.get("message_text"):
            p = {"chat_id": user_id, "text": fx_html(render_placeholders(post["message_text"], user)), "parse_mode": "HTML"}
            kb = _build_inline_keyboard(post.get("buttons_json", "[]"))
            if kb:
                p["reply_markup"] = kb
            await _send_payload(p)

async def send_prediction_to_user(bot, user_id, user=None, pred=None):
    if user is None:
        user = await _user_stub(user_id)
    if pred is None:
        pred = await fetch_latest_result()
    return await send_kind_messages(bot, user_id, user, "prediction", pred=pred)

# ═══════════════════════════════════════════════════════════════════
# BROADCAST
# ═══════════════════════════════════════════════════════════════════
async def _run_pool(items, handler, concurrency):
    if not items:
        return []
    q = asyncio.Queue()
    for i, it in enumerate(items):
        q.put_nowait((i, it))
    results = ["failed"] * len(items)
    async def w():
        while True:
            try:
                i, it = q.get_nowait()
            except asyncio.QueueEmpty:
                return
            try:
                results[i] = await handler(it)
            except Exception:
                results[i] = "failed"
    await asyncio.gather(*(w() for _ in range(min(concurrency, len(items)))))
    return results

_FATAL_BCAST = ("message to copy not found", "message can't be copied", "message_id_invalid",
                "message to forward not found", "message identifier is not specified")
_bcast = {"running": False, "cancel": False}
BCAST_CHECKPOINT_SECS = 1.5

def _bcast_state(resp):
    if resp and resp.get("ok"):
        return "sent"
    if resp is None:
        return "failed"
    d = str(resp.get("description", "")).lower()
    if any(k in d for k in _FATAL_BCAST):
        return "fatal"
    if resp.get("error_code") == 403 or any(k in d for k in _PERMANENT):
        return "blocked"
    if "parse" in d or "entit" in d or "caption" in d or "emoji" in d or "identifier" in d:
        return "plain"
    return "failed"

async def _bcast_one(bot, job, uid, user):
    mode, fc, ids = job["mode"], job["from_chat"], job["ids"]
    try:
        if mode == "text":
            p = {"chat_id": uid, "text": render_placeholders(job["html"], user), "parse_mode": "HTML"}
            if job.get("lpo"):
                p["link_preview_options"] = job["lpo"]
            resp = await _post("sendMessage", p, bcast_bucket)
            st = _bcast_state(resp)
            if st == "plain":
                p.pop("parse_mode", None)
                p["text"] = _strip_html(p["text"])
                resp = await _post("sendMessage", p, bcast_bucket)
            elif st == "failed":
                resp = await _post("copyMessage", {"chat_id": uid, "from_chat_id": fc, "message_id": ids[0]}, bcast_bucket)
        elif mode in ("copy", "caption"):
            p = {"chat_id": uid, "from_chat_id": fc, "message_id": ids[0]}
            if mode == "caption":
                p["caption"] = render_placeholders(job["caption_html"], user)
                p["parse_mode"] = "HTML"
            resp = await _post("copyMessage", p, bcast_bucket)
            if _bcast_state(resp) == "plain":
                resp = await _post("copyMessage", {"chat_id": uid, "from_chat_id": fc, "message_id": ids[0]}, bcast_bucket)
        elif mode == "album_media":
            resp = await _post("sendMediaGroup", {"chat_id": uid, "media": album_media(job["items"], user)}, bcast_bucket)
            if _bcast_state(resp) in ("plain", "failed"):
                resp = await _post("copyMessages", {"chat_id": uid, "from_chat_id": fc, "message_ids": ids}, bcast_bucket)
        else:
            resp = await _post("copyMessages", {"chat_id": uid, "from_chat_id": fc, "message_ids": ids}, bcast_bucket)
            if _bcast_state(resp) == "failed":
                ok = 0
                for mid in ids:
                    r = await _post("copyMessage", {"chat_id": uid, "from_chat_id": fc, "message_id": mid}, bcast_bucket)
                    ok += 1 if (r and r.get("ok")) else 0
                resp = {"ok": True} if ok else resp
        st = _bcast_state(resp)
        return "failed" if st == "plain" else st
    except Exception:
        return "failed"

def _bcast_text(job, state="running"):
    done = job["sent"] + job["blocked"]
    pct = int(done * 100 / job["total"]) if job["total"] else 100
    head = {"running": (EMOJI_BROADCAST, "📡", "Broadcasting..."),
            "done": (EMOJI_ROCKET, "🚀", "Broadcast Finished"),
            "stopped": (EMOJI_SIREN, "🚨", "Broadcast Stopped"),
            "fatal": (EMOJI_SKULL, "💀", "Broadcast Aborted")}[state]
    lines = [f'{pe(EMOJI_OK,"✅")} Delivered: <code>{job["sent"]}</code> / <code>{job["total"]}</code> (<code>{pct}%</code>)',
             f'{pe(EMOJI_SKULL,"💀")} Unreachable: <code>{job["blocked"]}</code>']
    left = len(job["pending"])
    if state in ("done", "stopped") and left:
        lines.append(f'{pe(EMOJI_SIREN,"🚨")} Not delivered: <code>{left}</code>')
    if state == "fatal":
        lines.append("The message no longer exists (deleted / not copyable). Send it again.")
    foot = "<i>Stop it with</i> <code>/stopbroadcast</code>" if state == "running" else ""
    return fx_html(card(head[0], head[1], head[2], "\n".join(lines), foot))

async def run_broadcast_job(bot, job, resumed=False):
    if _bcast["running"]:
        return
    _bcast.update(running=True, cancel=False)
    bcast_bucket.reset()
    admin, t0 = job.get("admin"), time.time()
    last_save, last_edit = 0.0, 0.0
    state, progress_mid = "interrupted", None
    try:
        users = await run(db_users_map)
        if admin:
            pre = card(EMOJI_REPEAT, "🔂", "Resuming broadcast after restart") + "\n" if resumed else ""
            r = await send_raw_message(admin, pre + _bcast_text(job), staff_kb_raw(admin))
            progress_mid = ((r or {}).get("result") or {}).get("message_id")
        for p in range(4):
            todo, retry = list(job["pending"]), []
            i = 0
            while i < len(todo):
                if _bcast["cancel"]:
                    state = "stopped"
                    break
                chunk, i = todo[i:i + BROADCAST_CONCURRENCY], i + BROADCAST_CONCURRENCY
                async def one(u):
                    return await _bcast_one(bot, job, u, users.get(u) or SimpleNamespace(id=u, first_name="", last_name="", username=""))
                results = await _run_pool(chunk, one, BROADCAST_CONCURRENCY)
                for u, r in zip(chunk, results):
                    if r == "sent": job["sent"] += 1
                    elif r == "blocked": job["blocked"] += 1
                    elif r == "fatal": state = "fatal"
                    else: retry.append(u)
                job["pending"] = retry + todo[i:]
                if state == "fatal" or time.time() - last_save >= BCAST_CHECKPOINT_SECS:
                    last_save = time.time()
                    await run(db_save_bcast, json.dumps(job))
                if state == "fatal":
                    break
                if admin and progress_mid and time.time() - last_edit > 8:
                    last_edit = time.time()
                    await _post("editMessageText", {"chat_id": admin, "message_id": progress_mid,
                                                    "text": _bcast_text(job), "parse_mode": "HTML"})
            if state in ("stopped", "fatal") or not retry:
                break
            job["pending"] = retry
            await run(db_save_bcast, json.dumps(job))
            await asyncio.sleep(3 * (p + 1))
        if state == "fatal":
            job["pending"] = []
        if state == "interrupted":
            state = "done"
    except Exception:
        traceback.print_exc()
        state = "stopped"
    finally:
        _bcast["running"] = False
        if state in ("done", "fatal") or (state == "stopped" and _bcast["cancel"]):
            try: await run(db_clear_bcast)
            except Exception: traceback.print_exc()
        secs = time.time() - t0
        print(f"[broadcast] {secs:.0f}s - sent {job['sent']}/{job['total']}, unreachable {job['blocked']}, left {len(job['pending'])}")
        if BROADCAST_REPORT and admin and state != "interrupted":
            try:
                txt = _bcast_text(job, state) + fx_html(f"\n<i>Time: {secs:.0f}s</i>")
                if progress_mid:
                    await _post("editMessageText", {"chat_id": admin, "message_id": progress_mid, "text": txt, "parse_mode": "HTML"})
                await send_raw_message(admin, txt, staff_kb_raw(admin))
            except Exception:
                pass

async def start_broadcast(bot, admin_id, msgs):
    if _bcast["running"]:
        await send_raw_message(admin_id, card(EMOJI_SIREN, "🚨", "Broadcast already running",
                               "Wait for it to finish or send <code>/stopbroadcast</code>."), staff_kb_raw(admin_id))
        return
    uids = list(dict.fromkeys(await run(db_all_user_ids)))
    if not uids:
        await send_raw_message(admin_id, card(EMOJI_THINK, "🤔", "No users yet", "Nobody to broadcast to."), staff_kb_raw(admin_id))
        return
    first = msgs[0]
    job = {"mode": "copy", "from_chat": first.chat_id, "ids": [m.message_id for m in msgs], "html": None,
           "caption_html": None, "items": None, "lpo": None, "admin": admin_id, "pending": uids,
           "total": len(uids), "sent": 0, "blocked": 0, "started": int(time.time())}
    if len(msgs) > 1:
        items = album_items(msgs)
        job["mode"] = "album_copy"
        if items and len(items) == len(msgs) and any(has_placeholders(i["caption_html"]) for i in items):
            job["mode"], job["items"] = "album_media", items
    elif first.text:
        job["mode"], job["html"], job["lpo"] = "text", msg_to_html(first), lpo_of(first)
    elif first.caption:
        html = msg_to_html(first)
        if has_placeholders(html):
            job["mode"], job["caption_html"] = "caption", html
    await run(db_save_bcast, json.dumps(job))
    await run_broadcast_job(bot, job)

async def cmd_stopbroadcast(update, context):
    user = update.effective_user
    if not user or not is_any_admin(user.id) or not db_has_perm(user.id, "can_broadcast"):
        return
    if _bcast["running"]:
        _bcast["cancel"] = True
        await send_raw_message(user.id, card(EMOJI_SIREN, "🚨", "Stopping broadcast..."), staff_kb_raw(user.id))
    else:
        await send_raw_message(user.id, card(EMOJI_THINK, "🤔", "No broadcast is running"), staff_kb_raw(user.id))

async def _resume_broadcast(bot):
    try:
        raw = await run(db_load_bcast)
        job = json.loads(raw) if raw else None
        if job and job.get("pending"):
            await run_broadcast_job(bot, job, resumed=True)
        elif raw:
            await run(db_clear_bcast)
    except Exception:
        traceback.print_exc()

# ═══════════════════════════════════════════════════════════════════
# APPROVALS
# ═══════════════════════════════════════════════════════════════════
async def _approve_call(bot, chat_id, user_id):
    deadline = time.time() + 900
    net_fail = 0
    while time.time() < deadline:
        await approve_bucket.wait()
        try:
            await bot.approve_chat_join_request(chat_id=chat_id, user_id=user_id)
            return "ok"
        except RetryAfter as e:
            approve_bucket.flood(_retry_secs(e))
        except Forbidden:
            return "retry"
        except BadRequest as e:
            m = str(e).lower()
            return "ok" if ("already" in m or "participant" in m) else "gone"
        except Exception:
            net_fail += 1
            if net_fail >= 6:
                return "retry"
            await asyncio.sleep(0.5 * net_fail)
    return "retry"

async def _approve_one(chat_id, user_id, bot):
    result = await _approve_call(bot, chat_id, user_id)
    if result == "retry":
        return False
    if result == "gone":
        await run(db_remove_pending_request, user_id, chat_id)
        return False
    if await run(db_pop_pending_request, user_id, chat_id):
        spawn(notify_user_approved(bot, user_id))
    return True

async def approve_all_pending(bot):
    approve_bucket.reset()
    approved = 0
    for round_no in range(8):
        pending = await run(db_get_pending_requests)
        if not pending:
            break
        async def h(req): return await _approve_one(req["chat_id"], req["user_id"], bot)
        results = await _run_pool(list(pending), h, APPROVAL_CONCURRENCY)
        got = sum(1 for r in results if r is True)
        approved += got
        if got == 0 and round_no >= 1:
            break
        await asyncio.sleep(2)
    return approved, len(await run(db_get_pending_requests))

async def _run_approve_all(bot, admin_id):
    approved, left = await approve_all_pending(bot)
    await send_raw_message(admin_id, card(EMOJI_OK, "✅", "Approval finished",
        f'{pe(EMOJI_OK,"✅")} Approved: <code>{approved}</code>\n{pe(EMOJI_SIREN,"🚨")} Still pending: <code>{left}</code>'),
        staff_kb_raw(admin_id))

_sweeping = {"v": False}
async def _pending_sweeper(bot):
    while True:
        await asyncio.sleep(45)
        if _sweeping["v"]:
            continue
        try:
            if not await run(db_get_auto_approve):
                continue
            stale = await run(db_get_stale_pending, 120)
            if not stale:
                continue
            _sweeping["v"] = True
            async def h(req): return await _approve_one(req["chat_id"], req["user_id"], bot)
            await _run_pool(list(stale), h, APPROVAL_CONCURRENCY)
        except Exception:
            traceback.print_exc()
        finally:
            _sweeping["v"] = False

# ═══════════════════════════════════════════════════════════════════
# KEYBOARDS
# ═══════════════════════════════════════════════════════════════════
def _auto_btn():
    auto = db_get_auto_approve()
    return btn(f"Auto-Approve: {'ON' if auto else 'OFF'}", "success" if auto else "danger", EMOJI_AUTO_APPROVE)

def staff_kb_raw(uid):
    P = lambda perm: db_has_perm(uid, perm)
    rows = []
    def add(*bs):
        r = [b for b in bs if b]
        if r:
            rows.append(r)
    add(P("can_broadcast") and btn("Broadcast", "primary", EMOJI_BROADCAST),
        P("can_stats") and btn("Stats", "primary", EMOJI_CHART))
    add(P("can_manage_seq") and btn("Message Sequence", "success", EMOJI_SEQUENCE),
        P("can_manage_seq") and btn("Start Message", "success", EMOJI_START))
    add(P("can_manage_prediction") and btn("Prediction Msg", "primary", EMOJI_PREDICTION))
    add(P("can_approve_requests") and btn("Approve All Requests", "danger", EMOJI_APPROVE),
        P("can_toggle_auto_approve") and _auto_btn())
    add(P("can_test_sequence") and btn("Test Sequence", "primary", EMOJI_TEST_SEQ))
    add((is_superior(uid) or is_env_admin(uid)) and btn("Admins", "success", EMOJI_TROPHY),
        can_manage_subs(uid) and btn("Subadmins", "primary", EMOJI_SUBADMINS))
    add(is_superior(uid) and btn("Permissions", "primary", EMOJI_PERMISSIONS),
        can_bot_profile(uid) and btn("Bot Profile", "primary", EMOJI_BOT_PROFILE))
    add(can_tracked_channel(uid) and btn("Tracked Channel", "primary", EMOJI_CHANNEL))
    if not rows:
        rows.append([btn("No Permissions")])
    return build_reply_keyboard_raw(rows)

def sequence_panel_kb_raw():
    intro_lbl = "Update Intro Msg" if db_get_intro() else "Set Intro Msg"
    r = db_get_direct_reply()
    reply_lbl = "Update Reply Msg" if (r.get("message_id") or r.get("content_json")) else "Set Reply Msg"
    pin_pos = db_get_pin_position()
    pin_lbl = "Toggle Pin Msg: OFF" if pin_pos is None else f"Toggle Pin Msg: Pos {pin_pos}"
    return build_reply_keyboard_raw([
        [btn(intro_lbl, "primary", EMOJI_INTRO)],
        [btn("Add Message", "success", EMOJI_ADD_MSG), btn("Remove Message", "danger", EMOJI_REMOVE_MSG)],
        [btn("Reorder Message", "primary", EMOJI_REORDER), btn("List Messages", "primary", EMOJI_LIST_MSG)],
        [btn("Add Approval Msg", "success", EMOJI_APPROVE), btn("Remove Approval Msg", "danger", EMOJI_REPLY_REMOVE)],
        [btn("Add Leave Msg", "success", EMOJI_LEAVE), btn("Remove Leave Msg", "danger", EMOJI_REPLY_REMOVE)],
        [btn("List Approval Msgs", "primary", EMOJI_LIST_MSG), btn("List Leave Msgs", "primary", EMOJI_LIST_MSG)],
        [btn(reply_lbl, "success", EMOJI_REPLY_SET), btn("Remove Reply Msg", "danger", EMOJI_REPLY_REMOVE)],
        [btn(pin_lbl, "success" if pin_pos is not None else "primary", EMOJI_PIN)],
        [btn("Back to Panel", "danger", EMOJI_BACK)],
    ])

def start_panel_kb_raw():
    return build_reply_keyboard_raw([
        [btn("Add Start Msg", "success", EMOJI_ADD_MSG), btn("Remove Start Msg", "danger", EMOJI_REMOVE_MSG)],
        [btn("List Start Msgs", "primary", EMOJI_LIST_MSG), btn("Preview Start Msg", "success", EMOJI_TEST_SEQ)],
        [btn("Back to Panel", "danger", EMOJI_BACK)],
    ])

def prediction_panel_kb_raw():
    return build_reply_keyboard_raw([
        [btn("Add Prediction Msg", "success", EMOJI_ADD_MSG), btn("Remove Prediction Msg", "danger", EMOJI_REMOVE_MSG)],
        [btn("List Prediction Msgs", "primary", EMOJI_LIST_MSG), btn("Preview Prediction", "success", EMOJI_TEST_SEQ)],
        [btn("Back to Panel", "danger", EMOJI_BACK)],
    ])

def bot_profile_kb_raw():
    return build_reply_keyboard_raw([
        [btn("Change Name", "primary", EMOJI_CHANGE_NAME), btn("Change Bio", "primary", EMOJI_CHANGE_BIO)],
        [btn("Change Description", "primary", EMOJI_CHANGE_DESC)],
        [btn("Back to Panel", "success", EMOJI_BACK)],
    ])

def cancel_kb_raw():
    return build_reply_keyboard_raw([[btn("Cancel", "danger", EMOJI_CANCEL)]])

def yes_no_kb():
    return build_reply_keyboard_raw([[btn("Yes", "success", EMOJI_YES), btn("No", "danger", EMOJI_NO)],
                                     [btn("Cancel", "danger", EMOJI_CANCEL)]])

def color_kb():
    return build_reply_keyboard_raw([
        [btn("Blue", "primary", EMOJI_BLUE), btn("Red", "danger", EMOJI_RED)],
        [btn("Green", "success", EMOJI_GREEN), btn("Default", "default", EMOJI_DEFAULT)],
        [btn("Cancel", "danger", EMOJI_CANCEL)],
    ])

def link_or_callback_kb():
    return build_reply_keyboard_raw([
        [btn("Link (URL)", "primary", EMOJI_LIGHTNING1), btn("Callback (Msg)", "success", EMOJI_LEAVE)],
        [btn("Cancel", "danger", EMOJI_CANCEL)],
    ])

def done_kb():
    return build_reply_keyboard_raw([[btn("Done", "success", EMOJI_DONE), btn("Add Another", "primary", EMOJI_ADD_ANOTHER)],
                                     [btn("Cancel", "danger", EMOJI_CANCEL)]])

def row_choice_kb():
    return build_reply_keyboard_raw([[btn("Same Row", "primary", EMOJI_SAME_ROW), btn("Next Row", "primary", EMOJI_NEXT_ROW)],
                                     [btn("Cancel", "danger", EMOJI_CANCEL)]])

def kind_panel_kb(kind):
    if kind == "start":
        return start_panel_kb_raw()
    if kind == "prediction":
        return prediction_panel_kb_raw()
    return sequence_panel_kb_raw()

# ═══════════════════════════════════════════════════════════════════
# PANELS
# ═══════════════════════════════════════════════════════════════════
async def open_panel(update, uid, note=""):
    await run(db_clear_state, uid)
    if is_superior(uid):
        txt = card(EMOJI_CROWN, "👑", "SUPERIOR ADMIN PANEL", "Full control — every option is unlocked for you.")
    elif is_env_admin(uid):
        txt = card(EMOJI_TROPHY, "🏆", "ADMIN PANEL", "Broadcast • Set Msgs • Prediction • Approvals • Test • Stats")
    elif db_is_subadmin(uid):
        title = "ADMIN PANEL" if db_get_admin_role(uid) == "admin" else "SUBADMIN PANEL"
        txt = card(EMOJI_GEAR, "⚙️", title, "Your accessible actions are below.")
    else:
        return
    if note:
        txt = f"{note}\n\n{txt}"
    await send_raw_message(uid, txt, staff_kb_raw(uid))

async def _open_sequence_panel(update, uid, note=""):
    txt = card(EMOJI_SEQUENCE, "📨", "Message Sequence",
               "These messages are sent <b>only when someone sends a join request</b>.")
    await send_raw_message(uid, f"{note}\n\n{txt}" if note else txt, sequence_panel_kb_raw())

async def _open_start_panel(update, uid, note=""):
    txt = card(EMOJI_START, "🎁", "Start Message",
               "These messages are sent when <b>anyone presses /start</b> on the bot. "
               "Separate from the join-request sequence.")
    await send_raw_message(uid, f"{note}\n\n{txt}" if note else txt, start_panel_kb_raw())

async def _open_prediction_panel(update, uid, note=""):
    txt = card(EMOJI_PREDICTION, "📊", "Prediction Message",
               "Sent when you trigger a prediction. Supports premium emoji + placeholders: "
               "<code>{period}</code> <code>{number}</code> <code>{color}</code> <code>{bigsmall}</code> <code>{color_emoji}</code>\n"
               "Preview shows real WinGo data.")
    await send_raw_message(uid, f"{note}\n\n{txt}" if note else txt, prediction_panel_kb_raw())

async def _open_kind_panel(update, uid, kind, note=""):
    if kind == "start":
        await _open_start_panel(update, uid, note)
    elif kind == "prediction":
        await _open_prediction_panel(update, uid, note)
    else:
        await _open_sequence_panel(update, uid, note)

async def _open_bot_profile_panel(update, uid, note=""):
    txt = card(EMOJI_BOT_PROFILE, "🤖", "Bot Profile", "Change the bot's name, bio or description.")
    await send_raw_message(uid, f"{note}\n\n{txt}" if note else txt, bot_profile_kb_raw())

async def send_stats(bot, uid):
    total = await run(db_total_users)
    daily = await run(db_daily_users)
    pending = len(await run(db_get_pending_requests))
    auto = "ON" if await run(db_get_auto_approve) else "OFF"
    seq_count = len(await run(db_get_messages))
    start_count = len(await run(db_k_list, "start"))
    pred_count = len(await run(db_k_list, "prediction"))
    admins_count = len(await run(db_list_admins, "admin"))
    subs_count = len(await run(db_list_admins, "subadmin"))
    channel_id = await run(db_get_channel_id)
    members = "N/A"
    if channel_id:
        try:
            members = str(await bot.get_chat_member_count(channel_id))
        except Exception:
            members = "N/A (bot not admin there)"
    body = (
        f'{pe(EMOJI_STAR1,"⭐")} Total users: <code>{total}</code>\n'
        f'{pe(EMOJI_FIREWORK,"🎇")} New today: <code>{daily}</code>\n'
        f'{pe(EMOJI_CHANNEL,"☯️")} Channel members: <code>{members}</code>\n'
        f'{pe(EMOJI_SIREN,"🚨")} Pending requests: <code>{pending}</code>\n'
        f'{pe(EMOJI_REPEAT,"🔂")} Auto-approve: <code>{auto}</code>\n'
        f'{pe(EMOJI_SEQUENCE,"📨")} Sequence msgs: <code>{seq_count}</code>\n'
        f'{pe(EMOJI_START,"🎁")} Start msgs: <code>{start_count}</code>\n'
        f'{pe(EMOJI_PREDICTION,"📊")} Prediction msgs: <code>{pred_count}</code>\n'
        f'{pe(EMOJI_TROPHY,"🏆")} Admins / Subadmins: <code>{admins_count} / {subs_count}</code>'
    )
    await send_raw_message(uid, card(EMOJI_CHART, "📊", "Bot Statistics", body), staff_kb_raw(uid))

# ═══════════════════════════════════════════════════════════════════
# COMMANDS
# ═══════════════════════════════════════════════════════════════════
async def cmd_start(update, context):
    user = update.effective_user
    if not user or not update.effective_chat or update.effective_chat.type != "private":
        return
    spawn(run(db_upsert_user, user.id, user.username, user.first_name, user.last_name))
    await run(db_clear_state, user.id)
    if is_any_admin(user.id):
        await open_panel(update, user.id)
    else:
        spawn(send_kind_messages(context.bot, user.id, user, "start"))

async def cmd_stats(update, context):
    user = update.effective_user
    if not user or not is_any_admin(user.id):
        return
    if not db_has_perm(user.id, "can_stats"):
        await send_raw_message(user.id, no_perm(), staff_kb_raw(user.id)); return
    await send_stats(context.bot, user.id)

async def cmd_prediction(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user:
        return
    if not is_any_admin(user.id):
        await send_raw_message(user.id, f'{pe(EMOJI_SKULL, "💀")} <b>Wrong command.</b>\n'
                                        f'<i>This command is only available for Admins & Subadmins.</i>')
        return
    await send_raw_message(user.id, f"{pe(EMOJI_GEAR, '⚙️')} <b>Fetching latest result...</b>")
    result = await fetch_latest_result()
    if not result:
        result = {"period": "—", "number": None, "color": "—", "color_emoji": "—"}
        await send_raw_message(user.id, f"{pe(EMOJI_SIREN, '🚨')} <b>Warning:</b> Could not fetch live WinGo data. Placeholders will show —.")
    sent = await send_kind_messages(context.bot, user.id, user, "prediction", pred=result)
    if not sent:
        await send_raw_message(user.id, f"{pe(EMOJI_SKULL, '💀')} <b>No prediction messages set.</b>\n\n"
                                        f"<i>Go to /start → Prediction Msg to set them.</i>")

async def cmd_help(update, context):
    u = update.effective_user
    if not u:
        return
    if is_any_admin(u.id):
        await send_raw_message(u.id, card(EMOJI_BOT_PROFILE, "🤖", "Help",
            "Use <code>/start</code> to open your panel.\nUse <code>/stopbroadcast</code> to stop a running broadcast.\n"
            "Reply (swipe) on any user message to answer that user."), staff_kb_raw(u.id))

# ═══════════════════════════════════════════════════════════════════
# JOIN REQUESTS
# ═══════════════════════════════════════════════════════════════════
async def on_join_request(update, context):
    jr = update.chat_join_request
    if not jr or not jr.from_user:
        return
    user = jr.from_user
    chat_id = jr.chat.id
    await run(db_add_pending_request, user.id, chat_id)
    spawn(run(db_upsert_user, user.id, user.username, user.first_name, user.last_name))
    if await run(db_get_auto_approve):
        spawn(_approve_one(chat_id, user.id, context.bot))
    channel_id = await run(db_get_channel_id)
    if (not channel_id) or chat_id == channel_id:
        if jr.chat.title:
            _channel_title["v"] = jr.chat.title
        spawn(send_sequence_to_user(context.bot, user.id, user))

# ═══════════════════════════════════════════════════════════════════
# USER -> ADMIN INBOX
# ═══════════════════════════════════════════════════════════════════
async def _forward_to_admins_for_reply(bot, user, msg):
    recipients = set()
    if SUPERIOR_ADMIN_ID:
        recipients.add(SUPERIOR_ADMIN_ID)
    if ADMIN_ID:
        recipients.add(ADMIN_ID)
    for r in await run(db_list_admins):
        if db_has_perm(r["user_id"], "can_reply_users"):
            recipients.add(r["user_id"])
    async def _send_to(admin_id):
        try:
            fwd = await bot.copy_message(chat_id=admin_id, from_chat_id=user.id, message_id=msg.message_id)
        except Exception:
            return
        await run(db_add_inbox_map, admin_id, fwd.message_id, user.id)
    await asyncio.gather(*(_send_to(a) for a in recipients), return_exceptions=True)

# ═══════════════════════════════════════════════════════════════════
# INLINE CALLBACK BUTTONS (user taps a "Callback" button)
# ═══════════════════════════════════════════════════════════════════
async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    data = q.data or ""
    if not data.startswith("cb_"):
        await q.answer(); return
    row = await run(db_get_callback_msg, data[3:])
    if not row:
        await q.answer("Message not found.", show_alert=True); return
    await q.answer()
    uid = q.from_user.id
    source = await run(db_get_source_chat_id)
    try:
        st, _ = await deliver_row(context.bot, uid, q.from_user, row, source, msg_bucket)
    except Exception:
        traceback.print_exc(); st = "fail"
    if st == "fail":
        await send_raw_message(uid, card(EMOJI_SKULL, "💀", "Could not load message"))

# ═══════════════════════════════════════════════════════════════════
# BUTTON BUILDER HELPERS
# ═══════════════════════════════════════════════════════════════════
_BTN_TEMP = ("current_btn_text", "current_btn_url", "current_cb_id", "current_icon_id", "current_btn_style")

async def _ask_btn_text(uid, state, title="Send the button text"):
    await run(db_set_state, uid, "awaiting_addmsg_btn_text_input", json.dumps(state))
    await send_raw_message(uid, card(EMOJI_STAR3, "⭐", title,
        "Put a premium emoji inside the text and it becomes the button icon automatically."), cancel_kb_raw())

async def _ask_btn_type(uid, state):
    await run(db_set_state, uid, "awaiting_addmsg_btn_type", json.dumps(state))
    await send_raw_message(uid, card(EMOJI_LIGHTNING1, "🔗", "Select button type",
        "<b>Link</b> — opens a URL.\n<b>Callback</b> — sends a message to the user when tapped."), link_or_callback_kb())

async def _ask_btn_color(uid, state, note=""):
    await run(db_set_state, uid, "awaiting_addmsg_btn_color", json.dumps(state))
    icon = (f'Premium icon captured {pe(state["current_icon_id"], "💎")}' if state.get("current_icon_id")
            else "No premium icon — button text is used as it is.")
    await send_raw_message(uid, card(EMOJI_BUTTERFLY, "🦋", "Select button colour", (note + "\n" if note else "") + icon), color_kb())

async def _finish_button_flow(update, uid, state):
    btns_json = json.dumps(state.get("buttons", []))
    target = state.get("target", "message")
    count = len(state.get("buttons", []))
    await run(db_clear_state, uid)
    if target == "intro":
        await run(db_set_intro_buttons, btns_json)
        await _open_sequence_panel(update, uid, card(EMOJI_OK, "✅", "Intro message updated", f"Saved with <code>{count}</code> button(s)."))
        return
    note = card(EMOJI_OK, "✅", "Saved", f'Position <code>{state.get("pos")}</code> saved with <code>{count}</code> button(s).')
    if target in KINDS:
        await run(db_k_set_buttons, target, state["pos"], btns_json)
        await _open_kind_panel(update, uid, target, note)
        return
    await run(db_update_message_buttons, state["pos"], btns_json)
    await _open_sequence_panel(update, uid, note)

def _preview(content_json, n=40):
    try:
        c = json.loads(content_json or "{}")
    except Exception:
        return "[unknown]"
    if c.get("type") == "text":
        return html_escape(_strip_html(c.get("html") or c.get("text", ""))[:n])
    if c.get("type") == "album":
        return f"[album x{c.get('count', '?')}]"
    if c.get("caption"):
        return html_escape(c["caption"][:n])
    return "[media]"

# ═══════════════════════════════════════════════════════════════════
# MAIN MESSAGE HANDLER
# ═══════════════════════════════════════════════════════════════════
async def on_message(update, context):
    msg = update.message
    user = update.effective_user
    if not user or not msg or msg.chat.type != "private":
        return
    uid = user.id
    text = (msg.text or msg.caption or "").strip()
    T = K(text)
    media_group_id = msg.media_group_id

    # ── normal users ──
    if not is_any_admin(uid):
        async def _handle_user_message():
            spawn(run(db_upsert_user, uid, user.username, user.first_name, user.last_name))
            reply = await run(db_get_direct_reply)
            if reply.get("message_id") or reply.get("content_json"):
                source = await run(db_get_source_chat_id)
                try:
                    await deliver_row(context.bot, uid, user, reply, source, msg_bucket)
                except Exception:
                    traceback.print_exc()
            await _forward_to_admins_for_reply(context.bot, user, msg)
        spawn(_handle_user_message())
        return

    async def deny():
        await open_panel(update, uid, no_perm())

    # ── admin replying to a user (swipe reply) ──
    if msg.reply_to_message:
        target_user = await run(db_get_inbox_map, uid, msg.reply_to_message.message_id)
        if target_user:
            if not db_has_perm(uid, "can_reply_users"):
                await send_raw_message(uid, no_perm(), staff_kb_raw(uid)); return
            async def _send_admin_reply():
                try:
                    await context.bot.copy_message(chat_id=target_user, from_chat_id=uid, message_id=msg.message_id)
                    await _post("setMessageReaction", {"chat_id": uid, "message_id": msg.message_id,
                                                       "reaction": [{"type": "emoji", "emoji": "👍"}]})
                except Forbidden:
                    await send_raw_message(uid, card(EMOJI_SKULL, "💀", "User blocked the bot"), staff_kb_raw(uid))
                except Exception as e:
                    await send_raw_message(uid, card(EMOJI_SKULL, "💀", "Failed", f"<code>{html_escape(str(e))}</code>"), staff_kb_raw(uid))
            spawn(_send_admin_reply())
            return

    action, data = await run(db_get_state, uid)

    if T in ("CANCEL", "BACK TO PANEL"):
        await open_panel(update, uid, card(EMOJI_BACK, "↩️", "Cancelled") if action else "")
        return

    # ═════════════════════════════════════════════════════════════
    # BUTTON BUILDER FLOW
    # Add button? → Text → Link/Callback → (URL | callback msg → source channel)
    #   → Colour → Done/Add Another → Same/Next Row → Text → ...
    # ═════════════════════════════════════════════════════════════
    if action in ("awaiting_addmsg_btn_text", "awaiting_addmsg_btn_text_input", "awaiting_addmsg_btn_type",
                  "awaiting_addmsg_btn_url", "awaiting_callback_msg", "awaiting_addmsg_btn_color",
                  "awaiting_addmsg_another", "awaiting_addmsg_row_choice"):
        state = _js(data)
        if not db_has_perm(uid, _target_perm(state.get("target"))):
            await deny(); return

        # Step 0 — "Add a button?"
        if action == "awaiting_addmsg_btn_text":
            if T == "NO":
                await _finish_button_flow(update, uid, state); return
            if T == "YES":
                await _ask_btn_text(uid, state); return
            await send_raw_message(uid, card(EMOJI_THINK, "🤔", "Choose Yes or No"), yes_no_kb()); return

        # Step 1 — button text
        if action == "awaiting_addmsg_btn_text_input":
            clean, auto_id = split_button_text(msg)
            if not clean:
                await send_raw_message(uid, card(EMOJI_SKULL, "💀", "Send some text for the button"), cancel_kb_raw()); return
            for k in _BTN_TEMP:
                state.pop(k, None)
            state["current_btn_text"] = clean[:64]
            state["current_icon_id"] = auto_id
            await _ask_btn_type(uid, state); return

        # Step 2 — Link or Callback
        if action == "awaiting_addmsg_btn_type":
            if T.startswith("LINK"):
                await run(db_set_state, uid, "awaiting_addmsg_btn_url", json.dumps(state))
                await send_raw_message(uid, card(EMOJI_ROCKET, "🚀", "Send the button URL",
                    "Example: <code>https://t.me/yourchannel</code> or <code>@yourchannel</code>"), cancel_kb_raw()); return
            if T.startswith("CALLBACK"):
                await run(db_set_state, uid, "awaiting_callback_msg", json.dumps(state))
                await send_raw_message(uid, card(EMOJI_ROCKET, "🚀", "Send the callback message",
                    "Text, photo, video, sticker or a whole album.\n"
                    "It is saved to the source channel (like the sequence) and sent to the user when they tap the button.")
                    + "\n" + PLACEHOLDER_HELP, cancel_kb_raw()); return
            await send_raw_message(uid, card(EMOJI_THINK, "🤔", "Choose Link or Callback"), link_or_callback_kb()); return

        # Step 3a — URL
        if action == "awaiting_addmsg_btn_url":
            url = normalize_url(text)
            if not url:
                await send_raw_message(uid, card(EMOJI_SKULL, "💀", "Invalid link",
                    "Send a URL like <code>https://t.me/yourchannel</code>"), cancel_kb_raw()); return
            state.pop("current_cb_id", None)
            state["current_btn_url"] = url
            await _ask_btn_color(uid, state); return

        # Step 3b — callback message → saved into source channel
        if action == "awaiting_callback_msg":
            source = await run(db_get_source_chat_id)
            if media_group_id:
                async def _cb_album(msgs, admin_id=uid, st=state, chat=msg.chat_id):
                    try:
                        new_ids = await forward_album(context.bot, source, chat, [m.message_id for m in msgs])
                    except Exception as e:
                        await send_raw_message(admin_id, card(EMOJI_SKULL, "💀", "Could not save album",
                            f"<code>{html_escape(str(e))}</code>\nMake sure the bot is admin in the source channel, then send it again."),
                            cancel_kb_raw()); return
                    cb_id = secrets.token_hex(5)
                    await run(db_add_callback_msg, cb_id, new_ids[0],
                              json.dumps({"type": "album", "count": len(new_ids), "items": album_items(msgs)}),
                              json.dumps(new_ids))
                    st.pop("current_btn_url", None)
                    st["current_cb_id"] = cb_id
                    await _ask_btn_color(admin_id, st, f'{pe(EMOJI_OK,"✅")} Callback album saved (<code>{len(new_ids)}</code> items).')
                buffer_album_part(f"cb:{uid}:{media_group_id}", msg, _cb_album)
                return
            mid = None
            try:
                if not source:
                    raise RuntimeError("Source chat is not set")
                mid = (await msg.forward(chat_id=source)).message_id
            except Exception as e:
                if not msg.text:
                    await send_raw_message(uid, card(EMOJI_SKULL, "💀", "Could not save",
                        f"<code>{html_escape(str(e))}</code>\nMake sure the bot is admin in the source channel, then send it again."),
                        cancel_kb_raw()); return
                mid = msg.message_id   # text still works without the source copy
            cb_id = secrets.token_hex(5)
            await run(db_add_callback_msg, cb_id, mid, extract_message_content(msg))
            state.pop("current_btn_url", None)
            state["current_cb_id"] = cb_id
            await _ask_btn_color(uid, state, f'{pe(EMOJI_OK,"✅")} Callback message saved.{_emoji_note(msg)}'); return

        # Step 4 — colour → button is created
        if action == "awaiting_addmsg_btn_color":
            style = {"BLUE": "primary", "RED": "danger", "GREEN": "success", "DEFAULT": "default"}.get(T)
            if not style:
                await send_raw_message(uid, card(EMOJI_SIREN, "🚨", "Choose a valid colour"), color_kb()); return
            b = {"text": state.get("current_btn_text") or "Button", "style": style, "row": state.get("current_row", 0)}
            if state.get("current_btn_url"):
                b["url"] = state["current_btn_url"]
            elif state.get("current_cb_id"):
                b["callback_data"] = "cb_" + state["current_cb_id"]
            else:
                await _ask_btn_type(uid, state); return
            if state.get("current_icon_id"):
                b["emoji_id"] = state["current_icon_id"]
            state.setdefault("buttons", []).append(b)
            for k in _BTN_TEMP:
                state.pop(k, None)
            await run(db_set_state, uid, "awaiting_addmsg_another", json.dumps(state))
            await send_raw_message(uid, card(EMOJI_OK, "✅", "Button added",
                f'Total buttons: <code>{len(state["buttons"])}</code>\nAdd another one or press Done.'), done_kb()); return

        # Step 5 — Done / Add Another
        if action == "awaiting_addmsg_another":
            if T == "DONE":
                await _finish_button_flow(update, uid, state); return
            if T == "ADD ANOTHER":
                await run(db_set_state, uid, "awaiting_addmsg_row_choice", json.dumps(state))
                await send_raw_message(uid, card(EMOJI_LIGHTNING3, "⚡", "Same row or next row?"), row_choice_kb()); return
            await send_raw_message(uid, card(EMOJI_THINK, "🤔", "Choose Done or Add Another"), done_kb()); return

        # Step 6 — Same Row / Next Row → back to Step 1
        if action == "awaiting_addmsg_row_choice":
            if T not in ("SAME ROW", "NEXT ROW"):
                await send_raw_message(uid, card(EMOJI_THINK, "🤔", "Choose Same Row or Next Row"), row_choice_kb()); return
            row_now = state.get("current_row", 0)
            in_row = sum(1 for x in state.get("buttons", []) if x.get("row", 0) == row_now)
            note = ""
            if T == "NEXT ROW" or in_row >= MAX_BTNS_PER_ROW:
                state["current_row"] = row_now + 1
                if T == "SAME ROW":
                    note = " (row was full, moved to next row)"
            await _ask_btn_text(uid, state, "Send the button text" + note); return
        return

    # ── Broadcast ──
    if action == "awaiting_broadcast":
        if not db_has_perm(uid, "can_broadcast"):
            await deny(); return
        if media_group_id:
            async def _finalize(msgs, admin_id=uid):
                await run(db_clear_state, admin_id)
                await open_panel(update, admin_id, card(EMOJI_ROCKET, "🚀", "Album broadcast launched",
                                                        f"<code>{len(msgs)}</code> items are going out."))
                spawn(start_broadcast(context.bot, admin_id, msgs))
            buffer_album_part(f"bc:{uid}:{media_group_id}", msg, _finalize)
            return
        await run(db_clear_state, uid)
        await open_panel(update, uid, card(EMOJI_ROCKET, "🚀", "Broadcast launched", "Panel is free — keep working."))
        spawn(start_broadcast(context.bot, uid, [msg]))
        return

    # ── Admin management ──
    if action == "awaiting_add_admin":
        if not is_superior(uid) and not is_env_admin(uid): await deny(); return
        await run(db_clear_state, uid)
        await open_panel(update, uid, await run(_handle_add_admin, text, "admin")); return
    if action == "awaiting_add_subadmin":
        if not can_manage_subs(uid): await deny(); return
        await run(db_clear_state, uid)
        await open_panel(update, uid, await run(_handle_add_admin, text, "subadmin")); return
    if action in ("awaiting_remove_admin", "awaiting_remove_subadmin"):
        if action == "awaiting_remove_admin" and not is_superior(uid) and not is_env_admin(uid): await deny(); return
        if action == "awaiting_remove_subadmin" and not can_manage_subs(uid): await deny(); return
        await run(db_clear_state, uid)
        await open_panel(update, uid, await run(_handle_remove_admin, uid, text)); return

    # ── Intro ──
    if action == "awaiting_set_intro":
        if not db_has_perm(uid, "can_manage_seq"): await deny(); return
        if not msg.text:
            await send_raw_message(uid, card(EMOJI_SKULL, "💀", "Intro must be text", "Send a text message."), cancel_kb_raw()); return
        await run(db_set_intro, msg_to_html(msg))
        lpo = lpo_of(msg)
        await run(cfg_set, "intro_lpo", json.dumps(lpo) if lpo else "")
        await run(db_set_state, uid, "awaiting_addmsg_btn_text", json.dumps({"target": "intro", "buttons": [], "current_row": 0}))
        await send_raw_message(uid, card(EMOJI_OK, "✅", "Intro message saved",
            "Saved exactly as you sent it." + _emoji_note(msg) + "\n\nAdd a button? (e.g. a Support button)"), yes_no_kb())
        return

    # ── Auto-reply ──
    if action == "awaiting_set_reply":
        if not db_has_perm(uid, "can_manage_seq"): await deny(); return
        source = await run(db_get_source_chat_id)
        mid = None
        try:
            if source:
                mid = (await msg.forward(chat_id=source)).message_id
        except Exception:
            mid = None
        if mid is None and not msg.text:
            await open_panel(update, uid, card(EMOJI_SKULL, "💀", "Could not save", "Media needs a working source chat (bot must be admin there).")); return
        await run(db_set_direct_reply, mid or msg.message_id, extract_message_content(msg))
        await run(db_clear_state, uid)
        await _open_sequence_panel(update, uid, card(EMOJI_OK, "✅", "Reply message saved")); return
    if action == "awaiting_confirm_remove_reply":
        if not db_has_perm(uid, "can_manage_seq"): await deny(); return
        await run(db_clear_state, uid)
        if T != "YES":
            await _open_sequence_panel(update, uid, card(EMOJI_BACK, "↩️", "Removal cancelled")); return
        await run(db_clear_direct_reply)
        await _open_sequence_panel(update, uid, card(EMOJI_OK, "✅", "Reply message removed")); return

    # ── Pin ──
    if action == "awaiting_pin_position":
        if not db_has_perm(uid, "can_manage_seq"): await deny(); return
        try:
            pos = int(T)
            if pos < 1:
                raise ValueError
        except ValueError:
            await send_raw_message(uid, card(EMOJI_SKULL, "💀", "Invalid position", "Send a number ≥ 1."), cancel_kb_raw()); return
        await run(db_clear_state, uid)
        await run(db_set_pin_position, pos)
        await _open_sequence_panel(update, uid, card(EMOJI_OK, "✅", "Pin enabled", f"Message at position <code>{pos}</code> will be pinned for every user."))
        return

    # ── Tracked channel ──
    if action == "awaiting_channel_id":
        if not can_tracked_channel(uid): await deny(); return
        try:
            cid = int(text.translate(_REV).strip())
        except ValueError:
            await send_raw_message(uid, card(EMOJI_SKULL, "💀", "Invalid channel ID", "Send a number like <code>-1001234567890</code>."), cancel_kb_raw()); return
        await run(db_clear_state, uid)
        await run(db_set_channel_id, cid)
        await open_panel(update, uid, card(EMOJI_OK, "✅", "Tracked channel updated", f"Now tracking <code>{cid}</code>.")); return

    # ── Kind messages (approval / leave / start / prediction) ──
    if action == "awaiting_kadd_pos":
        kind = data
        if not db_has_perm(uid, _kind_perm(kind)): await deny(); return
        try:
            pos = int(T)
            if pos < 1:
                raise ValueError
        except ValueError:
            await send_raw_message(uid, card(EMOJI_SKULL, "💀", "Send a valid number", "Position must be ≥ 1."), cancel_kb_raw()); return
        await run(db_set_state, uid, "awaiting_kadd_msg", json.dumps({"kind": kind, "pos": pos}))
        await send_raw_message(uid, card(EMOJI_OK, "✅", f"Position {pos} set",
            "Now send the message — text, photo, video, sticker or a whole album.\n"
            "Premium emoji, formatting and link-preview setting are kept exactly.") + "\n" + PLACEHOLDER_HELP, cancel_kb_raw())
        return
    if action == "awaiting_kadd_msg":
        st = _js(data)
        kind, pos = st.get("kind"), st.get("pos")
        if kind not in KINDS or not pos:
            await open_panel(update, uid, card(EMOJI_SKULL, "💀", "State error", "Please start again.")); return
        if not db_has_perm(uid, _kind_perm(kind)): await deny(); return
        pos = int(pos)
        if media_group_id:
            async def _kfinalize(msgs, admin_id=uid, kind=kind, position=pos, chat=msg.chat_id):
                source = await run(db_get_source_chat_id)
                try:
                    new_ids = await forward_album(context.bot, source, chat, [m.message_id for m in msgs])
                except Exception as e:
                    await _open_kind_panel(update, admin_id, kind, card(EMOJI_SKULL, "💀", "Could not save album", f"<code>{html_escape(str(e))}</code>"))
                    await run(db_clear_state, admin_id); return
                await run(db_k_add, kind, new_ids[0], position,
                          json.dumps({"type": "album", "count": len(new_ids), "items": album_items(msgs)}), "[]", json.dumps(new_ids))
                await run(db_clear_state, admin_id)
                await _open_kind_panel(update, admin_id, kind, card(EMOJI_OK, "✅", f"{kind.capitalize()} album saved",
                                       f"<code>{len(new_ids)}</code> items at position <code>{position}</code>."))
            buffer_album_part(f"ka:{uid}:{media_group_id}", msg, _kfinalize)
            return
        source = await run(db_get_source_chat_id)
        mid = msg.message_id
        try:
            if not source:
                raise RuntimeError("Source chat is not set")
            mid = (await msg.forward(chat_id=source)).message_id
        except Exception as e:
            if not msg.text:
                await send_raw_message(uid, card(EMOJI_SKULL, "💀", "Could not save",
                    f"<code>{html_escape(str(e))}</code>\nMake sure the bot is admin in the source channel, then send it again."), cancel_kb_raw()); return
        await run(db_k_add, kind, mid, pos, extract_message_content(msg), "[]")
        await run(db_set_state, uid, "awaiting_addmsg_btn_text", json.dumps({"target": kind, "pos": pos, "buttons": [], "current_row": 0}))
        await send_raw_message(uid, card(EMOJI_OK, "✅", f"{kind.capitalize()} message saved",
                               f"Position <code>{pos}</code>.{_emoji_note(msg)}\n\nAdd a button?"), yes_no_kb())
        return
    if action == "awaiting_kremove_pos":
        kind = data
        if not db_has_perm(uid, _kind_perm(kind)): await deny(); return
        try:
            pos = int(T)
        except ValueError:
            await send_raw_message(uid, card(EMOJI_SKULL, "💀", "Invalid position", "Send the position number."), cancel_kb_raw()); return
        await run(db_clear_state, uid)
        ok = await run(db_k_remove_pos, kind, pos)
        await _open_kind_panel(update, uid, kind,
            card(EMOJI_OK, "✅", "Removed", f"{kind.capitalize()} message at <code>{pos}</code> removed.") if ok
            else card(EMOJI_THINK, "🤔", "Not found", f"No {kind} message at <code>{pos}</code>."))
        return

    # ── Join sequence messages ──
    if action == "awaiting_addmsg_pos":
        if not db_has_perm(uid, "can_manage_seq"): await deny(); return
        try:
            pos = int(T)
            if pos < 1:
                raise ValueError
        except ValueError:
            await send_raw_message(uid, card(EMOJI_SKULL, "💀", "Send a valid number", "Position must be ≥ 1."), cancel_kb_raw()); return
        await run(db_set_state, uid, "awaiting_addmsg_msg", str(pos))
        await send_raw_message(uid, card(EMOJI_OK, "✅", f"Position {pos} set",
            "Now send the message — text, photo, video, sticker or a whole album.") + "\n" + PLACEHOLDER_HELP, cancel_kb_raw())
        return
    if action == "awaiting_addmsg_msg":
        if not db_has_perm(uid, "can_manage_seq"): await deny(); return
        try:
            pos = int(data)
        except Exception:
            await open_panel(update, uid, card(EMOJI_SKULL, "💀", "State error")); return
        if media_group_id:
            async def _finalize(msgs, admin_id=uid, position=pos, chat=msg.chat_id):
                source = await run(db_get_source_chat_id)
                try:
                    new_ids = await forward_album(context.bot, source, chat, [m.message_id for m in msgs])
                except Exception as e:
                    await run(db_clear_state, admin_id)
                    await _open_sequence_panel(update, admin_id, card(EMOJI_SKULL, "💀", "Could not save album", f"<code>{html_escape(str(e))}</code>")); return
                content = json.dumps({"type": "album", "count": len(new_ids), "items": album_items(msgs)})
                await run(db_add_message, new_ids[0], position, content, "[]", json.dumps(new_ids))
                await run(db_clear_state, admin_id)
                await _open_sequence_panel(update, admin_id, card(EMOJI_OK, "✅", "Album saved",
                                           f"<code>{len(new_ids)}</code> items at position <code>{position}</code>."))
            buffer_album_part(f"am:{uid}:{media_group_id}", msg, _finalize)
            return
        source = await run(db_get_source_chat_id)
        try:
            if not source:
                raise RuntimeError("Source chat is not set")
            mid = (await msg.forward(chat_id=source)).message_id
        except Exception as e:
            await send_raw_message(uid, card(EMOJI_SKULL, "💀", "Could not save",
                f"Source chat error: <code>{html_escape(str(e))}</code>\nMake sure the bot is admin there, then send again."), cancel_kb_raw()); return
        await run(db_add_message, mid, pos, extract_message_content(msg), "[]")
        await run(db_set_state, uid, "awaiting_addmsg_btn_text", json.dumps({"target": "message", "mid": mid, "pos": pos, "buttons": [], "current_row": 0}))
        await send_raw_message(uid, card(EMOJI_OK, "✅", "Message saved", f"Position <code>{pos}</code>.{_emoji_note(msg)}\n\nAdd a button?"), yes_no_kb())
        return

    if action == "awaiting_removemsg_pos":
        if not db_has_perm(uid, "can_manage_seq"): await deny(); return
        try:
            pos = int(T)
        except ValueError:
            await send_raw_message(uid, card(EMOJI_SKULL, "💀", "Invalid position", "Send the position number."), cancel_kb_raw()); return
        await run(db_clear_state, uid)
        ok = await run(db_remove_message_pos, pos)
        await _open_sequence_panel(update, uid, card(EMOJI_OK, "✅", "Removed", f"Message at <code>{pos}</code> removed.") if ok
                                   else card(EMOJI_THINK, "🤔", "Not found", f"No message at <code>{pos}</code>."))
        return
    if action == "awaiting_reordermsg":
        if not db_has_perm(uid, "can_manage_seq"): await deny(); return
        try:
            parts = T.split()
            mid, new_pos = int(parts[0]), int(parts[1])
            if new_pos < 1:
                raise ValueError
        except (ValueError, IndexError):
            await send_raw_message(uid, card(EMOJI_SKULL, "💀", "Wrong format", "Send: <code>msg_id new_position</code>"), cancel_kb_raw()); return
        await run(db_clear_state, uid)
        ok = await run(db_reorder_message, mid, new_pos)
        reply = (card(EMOJI_OK, "✅", "Moved", f"Message <code>{mid}</code> → position <code>{new_pos}</code>.") if ok
                 else card(EMOJI_THINK, "🤔", "Not found", f"Message <code>{mid}</code> not found."))
        await _open_sequence_panel(update, uid, reply); return

    # ── Bot profile ──
    if action in ("awaiting_bot_name", "awaiting_bot_bio", "awaiting_bot_description"):
        if not can_bot_profile(uid): await deny(); return
        await run(db_clear_state, uid)
        try:
            if action == "awaiting_bot_name":
                await context.bot.set_my_name(name=text); what = "Bot name"
            elif action == "awaiting_bot_bio":
                await context.bot.set_my_description(description=text); what = "Bot bio"
            else:
                await context.bot.set_my_short_description(short_description=text); what = "Bot description"
            reply = card(EMOJI_OK, "✅", f"{what} updated")
        except Exception as e:
            reply = card(EMOJI_SKULL, "💀", "Error", f"<code>{html_escape(str(e))}</code>")
        await _open_bot_profile_panel(update, uid, reply); return

    # Unknown / stale state → reset quietly
    if action:
        await run(db_clear_state, uid)

    # ═════════════════════════════════════════════════════════════
    # MENU BUTTONS
    # ═════════════════════════════════════════════════════════════
    if T == "BROADCAST":
        if not db_has_perm(uid, "can_broadcast"): await deny(); return
        await run(db_set_state, uid, "awaiting_broadcast")
        await send_raw_message(uid, card(EMOJI_BROADCAST, "📡", "Send the message to broadcast",
            "Text, photo, video, file, sticker or a full album.\nPremium emoji, formatting and link-preview setting go out exactly as you send them."), cancel_kb_raw())
        return

    if T == "STATS":
        if not db_has_perm(uid, "can_stats"): await deny(); return
        await send_stats(context.bot, uid); return

    if T == "ADMINS":
        if not is_superior(uid) and not is_env_admin(uid): await deny(); return
        rows = await run(db_list_admins, "admin")
        listing = "\n".join(f"• <code>{r['user_id']}</code>" for r in rows) or "No admins yet."
        env_line = f"\n\n.env admin: <code>{ADMIN_ID}</code>" if ADMIN_ID else ""
        await send_raw_message(uid, card(EMOJI_TROPHY, "🏆", "Admins", listing + env_line),
            build_reply_keyboard_raw([[btn("Add Admin", "success", EMOJI_TROPHY), btn("Remove Admin", "danger", EMOJI_SKULL)],
                                      [btn("Back to Panel", "default", EMOJI_BACK)]]))
        return
    if T == "ADD ADMIN":
        if not is_superior(uid) and not is_env_admin(uid): await deny(); return
        await run(db_set_state, uid, "awaiting_add_admin")
        await send_raw_message(uid, card(EMOJI_STAR3, "⭐", "Send the user ID to add as Admin"), cancel_kb_raw()); return
    if T == "REMOVE ADMIN":
        if not is_superior(uid) and not is_env_admin(uid): await deny(); return
        rows = await run(db_list_admins, "admin")
        if not rows:
            await open_panel(update, uid, card(EMOJI_THINK, "🤔", "No admins to remove")); return
        await run(db_set_state, uid, "awaiting_remove_admin")
        await send_raw_message(uid, card(EMOJI_SKULL, "💀", "Send the ID to remove",
                               "\n".join(f"• <code>{r['user_id']}</code>" for r in rows)), cancel_kb_raw()); return

    if T == "SUBADMINS":
        if not can_manage_subs(uid): await deny(); return
        rows = await run(db_list_admins) if is_superior(uid) else await run(db_list_admins, "subadmin")
        listing = "\n".join(f"• <code>{r['user_id']}</code> ({r['role'].capitalize()})" for r in rows) or "None yet."
        await send_raw_message(uid, card(EMOJI_LIGHTNING2, "⚡", "Subadmins", listing),
            build_reply_keyboard_raw([[btn("Add Subadmin", "success", EMOJI_LIGHTNING2), btn("Remove Subadmin", "danger", EMOJI_SKULL)],
                                      [btn("Back to Panel", "default", EMOJI_BACK)]]))
        return
    if T == "ADD SUBADMIN":
        if not can_manage_subs(uid): await deny(); return
        await run(db_set_state, uid, "awaiting_add_subadmin")
        await send_raw_message(uid, card(EMOJI_LIGHTNING2, "⚡", "Send the user ID to add as Subadmin"), cancel_kb_raw()); return
    if T == "REMOVE SUBADMIN":
        if not can_manage_subs(uid): await deny(); return
        rows = await run(db_list_admins) if is_superior(uid) else await run(db_list_admins, "subadmin")
        if not rows:
            await open_panel(update, uid, card(EMOJI_THINK, "🤔", "No subadmins to remove")); return
        await run(db_set_state, uid, "awaiting_remove_subadmin")
        await send_raw_message(uid, card(EMOJI_SKULL, "💀", "Send the ID to remove",
                               "\n".join(f"• <code>{r['user_id']}</code>" for r in rows)), cancel_kb_raw()); return

    if T == "APPROVE ALL REQUESTS":
        if not db_has_perm(uid, "can_approve_requests"): await deny(); return
        n = len(await run(db_get_pending_requests))
        if n == 0:
            await open_panel(update, uid, card(EMOJI_THINK, "🤔", "No pending requests")); return
        await open_panel(update, uid, card(EMOJI_SIREN, "🚨", f"Approving {n} requests",
                                           "Running in the background — panel is free, keep using it."))
        spawn(_run_approve_all(context.bot, uid))
        return

    if T.startswith("AUTO-APPROVE"):
        if not db_has_perm(uid, "can_toggle_auto_approve"): await deny(); return
        new_val = not await run(db_get_auto_approve)
        await run(db_set_auto_approve, new_val)
        await open_panel(update, uid, card(EMOJI_REPEAT, "🔂", f"Auto-Approve {'ON' if new_val else 'OFF'}",
            "New join requests are approved instantly." if new_val else "Requests now wait for manual approval."))
        if new_val:
            spawn(_run_approve_all(context.bot, uid))
        return

    if T == "PERMISSIONS":
        if not is_superior(uid): await deny(); return
        subs = await run(db_list_admins)
        if not subs:
            await open_panel(update, uid, card(EMOJI_THINK, "🤔", "No admins / subadmins yet")); return
        await send_raw_message(uid, card(EMOJI_GEAR, "⚙️", "Select an admin", "Tap a person to edit what they can do."), _perm_list_markup(subs))
        return

    if T == "BOT PROFILE":
        if not can_bot_profile(uid): await deny(); return
        await _open_bot_profile_panel(update, uid); return
    if T in ("CHANGE NAME", "CHANGE BIO", "CHANGE DESCRIPTION"):
        if not can_bot_profile(uid): await deny(); return
        st = {"CHANGE NAME": "awaiting_bot_name", "CHANGE BIO": "awaiting_bot_bio", "CHANGE DESCRIPTION": "awaiting_bot_description"}[T]
        await run(db_set_state, uid, st)
        await send_raw_message(uid, card(EMOJI_CHANGE_NAME, "✏️", "Send the new value"), cancel_kb_raw()); return

    if T == "TRACKED CHANNEL":
        if not can_tracked_channel(uid): await deny(); return
        current = await run(db_get_channel_id)
        await run(db_set_state, uid, "awaiting_channel_id")
        await send_raw_message(uid, card(EMOJI_CHANNEL, "☯️", "Tracked Channel",
            f"Current: <code>{current or 'Not set'}</code>\n\n"
            "Join requests from this channel trigger the sequence, and leaves trigger the leave message.\n"
            "Send the new channel ID (e.g. <code>-1001234567890</code>). The bot must be admin there."), cancel_kb_raw())
        return

    if T == "TEST SEQUENCE":
        if not db_has_perm(uid, "can_test_sequence"): await deny(); return
        spawn(send_sequence_to_user(context.bot, uid))
        await open_panel(update, uid, card(EMOJI_DINO, "🦖", "Test sequence sent", "Check the messages above/below — this is what joiners get."))
        return

    # ── Prediction panel ──
    if T == "PREDICTION MSG":
        if not db_has_perm(uid, "can_manage_prediction"): await deny(); return
        await _open_prediction_panel(update, uid); return
    if T == "PREVIEW PREDICTION":
        if not db_has_perm(uid, "can_manage_prediction"): await deny(); return
        if not await run(db_k_list, "prediction"):
            await _open_prediction_panel(update, uid, card(EMOJI_THINK, "🤔", "No prediction messages set")); return
        await send_raw_message(uid, card(EMOJI_GEAR, "⚙️", "Fetching WinGo data…"))
        pred = await fetch_latest_result()
        if not pred:
            await send_raw_message(uid, card(EMOJI_SIREN, "🚨", "WinGo API failed — placeholders will show —"))
        spawn(send_prediction_to_user(context.bot, uid, user=user, pred=pred or {}))
        return

    if T == "MESSAGE SEQUENCE":
        if not db_has_perm(uid, "can_manage_seq"): await deny(); return
        await _open_sequence_panel(update, uid); return
    if T == "START MESSAGE":
        if not db_has_perm(uid, "can_manage_seq"): await deny(); return
        await _open_start_panel(update, uid); return
    if T == "PREVIEW START MSG":
        if not db_has_perm(uid, "can_manage_seq"): await deny(); return
        if not await run(db_k_list, "start"):
            await _open_start_panel(update, uid, card(EMOJI_THINK, "🤔", "No start messages set")); return
        spawn(send_kind_messages(context.bot, uid, user, "start"))
        return

    if T in ("SET INTRO MSG", "UPDATE INTRO MSG"):
        if not db_has_perm(uid, "can_manage_seq"): await deny(); return
        await run(db_set_state, uid, "awaiting_set_intro")
        await send_raw_message(uid, card(EMOJI_INTRO, "📋", "Send the intro text", "Sent first, before the sequence.") + "\n" + PLACEHOLDER_HELP, cancel_kb_raw()); return
    if T in ("SET REPLY MSG", "UPDATE REPLY MSG"):
        if not db_has_perm(uid, "can_manage_seq"): await deny(); return
        await run(db_set_state, uid, "awaiting_set_reply")
        await send_raw_message(uid, card(EMOJI_REPLY_SET, "💬", "Send the auto-reply", "Users get this whenever they message the bot."), cancel_kb_raw()); return
    if T == "REMOVE REPLY MSG":
        if not db_has_perm(uid, "can_manage_seq"): await deny(); return
        await run(db_set_state, uid, "awaiting_confirm_remove_reply")
        await send_raw_message(uid, card(EMOJI_SKULL2, "☠️", "Remove the auto-reply?"), yes_no_kb()); return

    for _kind in KINDS:
        L = _kind.upper()
        if T == f"ADD {L} MSG":
            if not db_has_perm(uid, _kind_perm(_kind)): await deny(); return
            await run(db_set_state, uid, "awaiting_kadd_pos", _kind)
            await send_raw_message(uid, card(EMOJI_UP, "⏫", f"Position for this {_kind} message?",
                                   "1 = first. Add as many as you like."), cancel_kb_raw()); return
        if T in (f"REMOVE {L} MSG", f"LIST {L} MSGS"):
            if not db_has_perm(uid, _kind_perm(_kind)): await deny(); return
            rows = await run(db_k_list, _kind)
            if not rows:
                extra = "The default message is used." if _kind == "approval" else ""
                await _open_kind_panel(update, uid, _kind, card(EMOJI_THINK, "🤔", f"No {_kind} messages set", extra)); return
            lines = []
            for r in rows[:40]:
                mark = " 🔘" if r["buttons_json"] and r["buttons_json"] != "[]" else ""
                lines.append(f"<code>{r['position']}.</code>{mark} {_preview(r['content_json'])}")
            body = "\n".join(lines)
            if T.startswith("LIST"):
                await send_raw_message(uid, card(EMOJI_LIST_MSG, "📋", f"{_kind.capitalize()} messages ({len(rows)})", body, expandable=True), kind_panel_kb(_kind)); return
            await run(db_set_state, uid, "awaiting_kremove_pos", _kind)
            await send_raw_message(uid, card(EMOJI_LIST_MSG, "📋", f"{_kind.capitalize()} messages", body, "Send the position number to remove.", expandable=True), cancel_kb_raw()); return

    if T.startswith("TOGGLE PIN MSG"):
        if not db_has_perm(uid, "can_manage_seq"): await deny(); return
        if await run(db_get_pin_position) is not None:
            await run(db_set_pin_position, None)
            await _open_sequence_panel(update, uid, card(EMOJI_OK, "✅", "Pin disabled"))
        else:
            await run(db_set_state, uid, "awaiting_pin_position")
            await send_raw_message(uid, card(EMOJI_PIN, "📌", "Send the position to pin", "That message gets pinned in each user's chat."), cancel_kb_raw())
        return

    if T == "ADD MESSAGE":
        if not db_has_perm(uid, "can_manage_seq"): await deny(); return
        await run(db_set_state, uid, "awaiting_addmsg_pos")
        await send_raw_message(uid, card(EMOJI_UP, "⏫", "Enter position number", "1 = first message."), cancel_kb_raw()); return
    if T in ("REMOVE MESSAGE", "REORDER MESSAGE", "LIST MESSAGES"):
        if not db_has_perm(uid, "can_manage_seq"): await deny(); return
        rows = await run(db_get_messages)
        if not rows:
            await _open_sequence_panel(update, uid, card(EMOJI_THINK, "🤔", "Sequence is empty")); return
        lines = []
        for r in rows[:40]:
            mark = " 🔘" if r["buttons_json"] and r["buttons_json"] != "[]" else ""
            lines.append(f"<code>{r['position']}.</code> id <code>{r['message_id']}</code>{mark} {_preview(r['content_json'])}")
        body = "\n".join(lines)
        if T == "LIST MESSAGES":
            await send_raw_message(uid, card(EMOJI_LIST_MSG, "📋", f"Sequence ({len(rows)})", body, expandable=True), sequence_panel_kb_raw()); return
        if T == "REMOVE MESSAGE":
            await run(db_set_state, uid, "awaiting_removemsg_pos")
            await send_raw_message(uid, card(EMOJI_LIST_MSG, "📋", "Current sequence", body, "Send the position number to remove.", expandable=True), cancel_kb_raw()); return
        await run(db_set_state, uid, "awaiting_reordermsg")
        await send_raw_message(uid, card(EMOJI_REORDER, "🔀", "Current order", body, "Send <code>msg_id new_position</code>", expandable=True), cancel_kb_raw()); return

    await open_panel(update, uid)

def _handle_add_admin(text, role):
    try:
        tid = int(K(text))
    except ValueError:
        return card(EMOJI_SKULL, "💀", "Invalid ID", "Send a numeric user ID.")
    if tid == SUPERIOR_ADMIN_ID or (ADMIN_ID and tid == ADMIN_ID):
        return card(EMOJI_THINK, "🤔", "Already a built-in admin")
    ok = db_add_admin(tid, role)
    return card(EMOJI_OK, "✅", f"{role.capitalize()} added", f"<code>{tid}</code> is now {role}.") if ok \
        else card(EMOJI_THINK, "🤔", "Already exists")

def _handle_remove_admin(uid, text):
    try:
        tid = int(K(text))
    except ValueError:
        return card(EMOJI_SKULL, "💀", "Invalid ID")
    if tid == SUPERIOR_ADMIN_ID or (ADMIN_ID and tid == ADMIN_ID):
        return card(EMOJI_THINK, "🤔", "Built-in admins cannot be removed")
    if not is_superior(uid) and not is_env_admin(uid) and db_get_admin_role(tid) != "subadmin":
        return card(EMOJI_SKULL2, "☠️", "Only the Superior Admin can remove admins")
    ok = db_remove_subadmin(tid)
    return card(EMOJI_OK, "✅", "Removed", f"<code>{tid}</code>") if ok else card(EMOJI_THINK, "🤔", "Not found")

# ═══════════════════════════════════════════════════════════════════
# PERMISSION CALLBACKS
# ═══════════════════════════════════════════════════════════════════
def _perm_list_markup(subs):
    kb = [[{"text": fxc(f"👤 {s['user_id']} ({s['role']})"), "callback_data": f"perm_sub_{s['user_id']}"}] for s in subs]
    kb.append([{"text": fxc("✖ Close"), "callback_data": "perm_close"}])
    return {"inline_keyboard": kb}

def _perm_menu_markup(sub_id, perms):
    kb = [[InlineKeyboardButton(f"{'✅' if perms.get(p) else '❌'} {fxc(PERM_DISPLAY[p])}",
                                callback_data=f"perm_toggle_{sub_id}_{p}")] for p in PERMISSIONS]
    kb.append([InlineKeyboardButton(fxc("⬅ Back"), callback_data="perm_list"),
               InlineKeyboardButton(fxc("✖ Close"), callback_data="perm_close")])
    return InlineKeyboardMarkup(kb)

async def _cb_edit(q, html, markup=None):
    try:
        await q.edit_message_text(fx_html(html), parse_mode="HTML", reply_markup=markup)
    except BadRequest:
        pass

async def subadmin_list_callback(update, context):
    q = update.callback_query
    await q.answer()
    if not is_superior(q.from_user.id):
        await _cb_edit(q, card(EMOJI_SKULL2, "☠️", "Superior Admin only")); return
    subs = await run(db_list_admins)
    if not subs:
        await _cb_edit(q, card(EMOJI_THINK, "🤔", "No admins / subadmins")); return
    kb = [[InlineKeyboardButton(fxc(f"👤 {s['user_id']} ({s['role']})"), callback_data=f"perm_sub_{s['user_id']}")] for s in subs]
    kb.append([InlineKeyboardButton(fxc("✖ Close"), callback_data="perm_close")])
    await _cb_edit(q, card(EMOJI_GEAR, "⚙️", "Select an admin"), InlineKeyboardMarkup(kb))

async def subadmin_perm_menu_callback(update, context):
    q = update.callback_query
    await q.answer()
    if not is_superior(q.from_user.id):
        await _cb_edit(q, card(EMOJI_SKULL2, "☠️", "Superior Admin only")); return
    try:
        sub_id = int(q.data.split("_")[2])
    except Exception:
        return
    perms = db_get_subadmin_perms(sub_id)
    if not perms:
        await _cb_edit(q, card(EMOJI_THINK, "🤔", "Not found")); return
    role = db_get_admin_role(sub_id) or "subadmin"
    await _cb_edit(q, card(EMOJI_GEAR, "⚙️", f"Permissions — {role.upper()}", f"<code>{sub_id}</code>"), _perm_menu_markup(sub_id, perms))

async def perm_toggle_callback(update, context):
    q = update.callback_query
    if not is_superior(q.from_user.id):
        await q.answer("Superior Admin only", show_alert=True); return
    parts = q.data.split("_")
    try:
        sub_id = int(parts[2])
    except Exception:
        await q.answer(); return
    perm = "_".join(parts[3:])
    if perm not in PERMISSIONS:
        await q.answer("Invalid permission", show_alert=True); return
    perms = db_get_subadmin_perms(sub_id)
    new_val = not perms.get(perm, False)
    await run(db_set_subadmin_perm, sub_id, perm, new_val)
    await q.answer(f"{PERM_DISPLAY[perm]}: {'ON' if new_val else 'OFF'}")
    perms = db_get_subadmin_perms(sub_id)
    role = db_get_admin_role(sub_id) or "subadmin"
    await _cb_edit(q, card(EMOJI_GEAR, "⚙️", f"Permissions — {role.upper()}",
                           f"<code>{sub_id}</code>\n{PERM_DISPLAY[perm]} is now {'✅ ON' if new_val else '❌ OFF'}"),
                   _perm_menu_markup(sub_id, perms))

async def perm_close_callback(update, context):
    q = update.callback_query
    await q.answer()
    try:
        await q.delete_message()
    except Exception:
        pass

# ═══════════════════════════════════════════════════════════════════
# CHANNEL MEMBER TRACKING
# ═══════════════════════════════════════════════════════════════════
_JOINED = ("member", "administrator", "creator", "restricted")
_LEFT = ("left", "kicked")

async def on_chat_member_update(update, context):
    cmu = update.chat_member
    if not cmu:
        return
    channel_id = await run(db_get_channel_id) or await run(db_get_source_chat_id)
    if cmu.chat.id != channel_id:
        return
    if cmu.chat.title:
        _channel_title["v"] = cmu.chat.title
    old, new = cmu.old_chat_member.status, cmu.new_chat_member.status
    user = cmu.new_chat_member.user
    if not user or user.is_bot:
        return
    if old in _JOINED and new in _LEFT:
        spawn(send_kind_messages(context.bot, user.id, user, "leave"))
        return
    if old in _LEFT and new in _JOINED:
        if await run(db_pop_pending_request, user.id, cmu.chat.id):
            spawn(notify_user_approved(context.bot, user.id))

@retry_db
def db_get_known_channels():
    with get_conn() as c:
        row = c.execute("SELECT value FROM config WHERE key='known_channels'").fetchone()
    try:
        v = json.loads(row["value"]) if row and row["value"] else []
        return v if isinstance(v, list) else []
    except Exception:
        return []

@retry_db
def db_save_known_channels(lst):
    with get_conn() as c:
        c.execute(
            "INSERT INTO config (key, value) VALUES ('known_channels', ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (json.dumps(lst, ensure_ascii=False),)
        )

async def on_my_chat_member(update, context):
    cmu = update.my_chat_member
    if not cmu:
        return
    chat = cmu.chat
    if chat.type not in ("channel", "supergroup", "group"):
        return
    old_status = cmu.old_chat_member.status
    new_status = cmu.new_chat_member.status
    actor = cmu.from_user
    try:
        source_id = await run(db_get_source_chat_id)
    except Exception:
        source_id = 0
    if source_id and chat.id == source_id:
        return

    known = [k for k in (await run(db_get_known_channels)) if k.get("id") != chat.id]
    title = html_escape(chat.title or "your channel")

    if new_status == "administrator":
        known.append({"id": chat.id, "title": chat.title or "", "username": chat.username or "",
                      "type": chat.type, "at": int(time.time())})
        await run(db_save_known_channels, known[-30:])
        allowed = bool(actor) and not actor.is_bot and (actor.id == ADMIN_ID or is_any_admin(actor.id))
        try:
            already_tracked = await run(db_get_channel_id)
        except Exception:
            already_tracked = 0
        newly_set = allowed and not already_tracked
        if newly_set:
            await run(db_set_channel_id, chat.id)
            if chat.title:
                _channel_title["v"] = chat.title
        if old_status == "administrator":
            return
        target = actor.id if allowed else (ADMIN_ID or SUPERIOR_ADMIN_ID)
        lines = []
        if newly_set:
            lines.append(f"✅ <b>Tracked channel connected</b>\n\n📣 <b>{title}</b>\n<code>{chat.id}</code>")
            lines.append("\nJoin requests to this channel now trigger your welcome sequence. "
                         "Nothing is ever posted into the channel by this bot.")
        elif allowed and already_tracked and chat.id != already_tracked:
            lines.append(f"ℹ️ Bot was made admin in <b>{title}</b> too.\n"
                         "Your tracked channel stays unchanged — this one was <b>not</b> switched automatically. "
                         "Change it from <b>Tracked Channel</b> if you actually want this one instead.")
        else:
            who = html_escape((actor.full_name if actor else "someone"))
            lines.append(f"ℹ️ <b>{who}</b> added this bot to <b>{title}</b>.\n"
                         "Open the panel → <b>Tracked Channel</b> to make it your tracked channel.")
        if not getattr(cmu.new_chat_member, "can_invite_users", True):
            lines.append("\n⚠️ Enable the <b>Invite Users</b> permission so join requests can be approved.")
        try:
            await send_raw_message(target, "\n".join(lines))
        except Exception:
            pass
        return

    if new_status in ("left", "kicked"):
        await run(db_save_known_channels, known[-30:])
        try:
            tracked = await run(db_get_channel_id)
        except Exception:
            tracked = 0
        if tracked and chat.id == tracked:
            try:
                await send_raw_message(SUPERIOR_ADMIN_ID or ADMIN_ID,
                                       f"⚠️ <b>Bot removed from tracked channel</b>\n\n📣 {title}\n\n"
                                       "Add the bot as admin again from the panel's <b>Tracked Channel</b>.")
            except Exception:
                pass

# ═══════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════
async def _post_shutdown(app):
    await close_http_session()

async def _admin_cache_loop():
    while True:
        await asyncio.sleep(30)
        try:
            await run(refresh_admin_cache)
        except Exception:
            traceback.print_exc()

async def _post_init(app):
    await run(refresh_admin_cache)
    spawn(_admin_cache_loop())
    spawn(_pending_sweeper(app.bot))
    spawn(_resume_broadcast(app.bot))

async def _on_error(update, context):
    print("[handler error]", repr(context.error))
    traceback.print_exception(type(context.error), context.error, context.error.__traceback__)

def guard(fn):
    @wraps(fn)
    async def wrapper(update, context):
        try:
            return await fn(update, context)
        except Exception:
            traceback.print_exc()
            try:
                u = update.effective_user
                if u and is_any_admin(u.id):
                    await send_raw_message(u.id, card(EMOJI_SIREN, "⚠️", "Temporary error", "Please press the button again."), staff_kb_raw(u.id))
            except Exception:
                pass
    return wrapper

def main():
    init_db()
    refresh_admin_cache()
    _warm_cache()
    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .concurrent_updates(True)
        .connection_pool_size(256)
        .pool_timeout(30)
        .connect_timeout(15)
        .read_timeout(30)
        .write_timeout(30)
        .post_init(_post_init)
        .post_shutdown(_post_shutdown)
        .build()
    )
    app.add_error_handler(_on_error)
    app.add_handler(CommandHandler("start", guard(cmd_start)))
    app.add_handler(CommandHandler("stats", guard(cmd_stats)))
    app.add_handler(CommandHandler("help", guard(cmd_help)))
    app.add_handler(CommandHandler("stopbroadcast", guard(cmd_stopbroadcast)))
    app.add_handler(CommandHandler("prediction", guard(cmd_prediction)))
    app.add_handler(ChatJoinRequestHandler(guard(on_join_request)))
    app.add_handler(ChatMemberHandler(guard(on_chat_member_update), ChatMemberHandler.CHAT_MEMBER))
    app.add_handler(ChatMemberHandler(guard(on_my_chat_member), ChatMemberHandler.MY_CHAT_MEMBER))
    app.add_handler(CallbackQueryHandler(guard(subadmin_list_callback), pattern="^perm_list$"))
    app.add_handler(CallbackQueryHandler(guard(subadmin_perm_menu_callback), pattern="^perm_sub_"))
    app.add_handler(CallbackQueryHandler(guard(perm_toggle_callback), pattern="^perm_toggle_"))
    app.add_handler(CallbackQueryHandler(guard(perm_close_callback), pattern="^perm_close$"))
    app.add_handler(CallbackQueryHandler(guard(on_callback), pattern="^cb_"))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, guard(on_message)))
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=False)

if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception:
        traceback.print_exc()
        print("[supervisor] bot crashed - restarting in 5 seconds ...")
        time.sleep(5)
        os.execv(sys.executable, [sys.executable] + sys.argv)
