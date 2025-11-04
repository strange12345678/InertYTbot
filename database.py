# database.py
import os, json, time, datetime
from config import MONGODB_URI, SQLITE_DB, JSON_DB

USE_MONGO = False
USE_SQLITE = False
USE_JSON = False

# Try MongoDB (pymongo)
if MONGODB_URI:
    try:
        from pymongo import MongoClient
        client = MongoClient(MONGODB_URI)
        db = client.get_database("inert_downloader_db")
        users_coll = db.get_collection("users")
        downloads_coll = db.get_collection("downloads")
        USE_MONGO = True
    except Exception:
        USE_MONGO = False

# Try SQLite
if not USE_MONGO:
    try:
        import sqlite3
        conn = sqlite3.connect(SQLITE_DB, check_same_thread=False)
        cur = conn.cursor()
        # init tables
        cur.execute("""CREATE TABLE IF NOT EXISTS users (
                        user_id INTEGER PRIMARY KEY,
                        premium_until TEXT,
                        plan TEXT,
                        daily_count INTEGER DEFAULT 0,
                        last_reset INTEGER DEFAULT 0
                    )""")
        cur.execute("""CREATE TABLE IF NOT EXISTS downloads (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER,
                        title TEXT,
                        filepath TEXT,
                        filesize INTEGER,
                        created_at TEXT
                    )""")
        conn.commit()
        USE_SQLITE = True
    except Exception:
        USE_SQLITE = False

# Fallback to JSON
if not USE_MONGO and not USE_SQLITE:
    USE_JSON = True
    if not os.path.exists(JSON_DB):
        with open(JSON_DB, "w") as f:
            json.dump({"users":{}, "downloads":[]}, f, indent=2)

def now_ts():
    return int(time.time())

# ------------ Downloads record ------------
def add_download_record(user_id, title, filepath, filesize):
    created = datetime.datetime.utcnow().isoformat()
    if USE_MONGO:
        downloads_coll.insert_one({"user_id": user_id, "title": title, "filepath": filepath, "filesize": filesize, "created_at": created})
    elif USE_SQLITE:
        cur.execute("INSERT INTO downloads (user_id,title,filepath,filesize,created_at) VALUES (?,?,?,?,?)",
                    (user_id, title, filepath, filesize, created))
        conn.commit()
    else:
        with open(JSON_DB, "r+") as f:
            data = json.load(f)
            data["downloads"].append({"user_id":user_id,"title":title,"filepath":filepath,"filesize":filesize,"created_at":created})
            f.seek(0); f.truncate(); json.dump(data, f, indent=2)

# ------------ Premium ------------
def add_premium(user_id, days, plan="Gold"):
    until = (datetime.datetime.utcnow() + datetime.timedelta(days=int(days))).isoformat()
    if USE_MONGO:
        users_coll.update_one({"user_id": user_id}, {"$set": {"premium_until": until, "plan": plan, "daily_count":0, "last_reset": now_ts()}}, upsert=True)
    elif USE_SQLITE:
        cur.execute("INSERT OR REPLACE INTO users (user_id,premium_until,plan,last_reset,daily_count) VALUES (?,?,?,?,?)",
                    (user_id, until, plan, now_ts(), 0))
        conn.commit()
    else:
        with open(JSON_DB, "r+") as f:
            data = json.load(f)
            u = data["users"].get(str(user_id), {})
            u["premium_until"] = until
            u["plan"] = plan
            u["daily_count"] = 0
            u["last_reset"] = now_ts()
            data["users"][str(user_id)] = u
            f.seek(0); f.truncate(); json.dump(data, f, indent=2)

def remove_premium(user_id):
    if USE_MONGO:
        users_coll.update_one({"user_id": user_id}, {"$unset": {"premium_until": "", "plan": ""}})
    elif USE_SQLITE:
        cur.execute("UPDATE users SET premium_until=NULL, plan=NULL WHERE user_id=?", (user_id,))
        conn.commit()
    else:
        with open(JSON_DB, "r+") as f:
            data = json.load(f)
            u = data["users"].get(str(user_id), {})
            u.pop("premium_until", None)
            u.pop("plan", None)
            data["users"][str(user_id)] = u
            f.seek(0); f.truncate(); json.dump(data, f, indent=2)

def premium_info(user_id):
    if USE_MONGO:
        u = users_coll.find_one({"user_id": user_id}) or {}
        return u.get("premium_until"), u.get("plan")
    elif USE_SQLITE:
        cur.execute("SELECT premium_until, plan FROM users WHERE user_id=?", (user_id,))
        r = cur.fetchone()
        return (r[0], r[1]) if r else (None, None)
    else:
        with open(JSON_DB, "r") as f:
            data = json.load(f)
        u = data["users"].get(str(user_id), {})
        return u.get("premium_until"), u.get("plan")

def is_premium(user_id):
    now = datetime.datetime.utcnow()
    if USE_MONGO:
        u = users_coll.find_one({"user_id": user_id}) or {}
        until = u.get("premium_until")
        if not until: return False
        try:
            return datetime.datetime.fromisoformat(until) > now
        except:
            return False
    elif USE_SQLITE:
        cur.execute("SELECT premium_until FROM users WHERE user_id=?", (user_id,))
        r = cur.fetchone()
        if not r or not r[0]:
            return False
        try:
            return datetime.datetime.fromisoformat(r[0]) > now
        except:
            return False
    else:
        with open(JSON_DB, "r") as f:
            data = json.load(f)
        u = data["users"].get(str(user_id), {})
        until = u.get("premium_until")
        if not until: return False
        try:
            return datetime.datetime.fromisoformat(until) > now
        except:
            return False

def get_remaining_days(user_id):
    if USE_MONGO:
        u = users_coll.find_one({"user_id": user_id}) or {}
        until = u.get("premium_until")
        if not until: return 0
        try:
            delta = datetime.datetime.fromisoformat(until) - datetime.datetime.utcnow()
            return max(0, delta.days)
        except:
            return 0
    elif USE_SQLITE:
        cur.execute("SELECT premium_until FROM users WHERE user_id=?", (user_id,))
        r = cur.fetchone()
        if not r or not r[0]:
            return 0
        try:
            delta = datetime.datetime.fromisoformat(r[0]) - datetime.datetime.utcnow()
            return max(0, delta.days)
        except:
            return 0
    else:
        with open(JSON_DB, "r") as f:
            data = json.load(f)
        u = data["users"].get(str(user_id), {})
        until = u.get("premium_until")
        if not until: return 0
        try:
            delta = datetime.datetime.fromisoformat(until) - datetime.datetime.utcnow()
            return max(0, delta.days)
        except:
            return 0

# ------------ Daily free limit ------------
def can_download_free(user_id, free_limit):
    ts = now_ts()
    if USE_MONGO:
        u = users_coll.find_one({"user_id": user_id}) or {}
        last_reset = u.get("last_reset", 0)
        daily_count = u.get("daily_count", 0)
        if ts - last_reset > 86400:
            users_coll.update_one({"user_id": user_id}, {"$set": {"daily_count": 0, "last_reset": ts}}, upsert=True)
            daily_count = 0
        return daily_count < free_limit
    elif USE_SQLITE:
        cur.execute("SELECT daily_count,last_reset FROM users WHERE user_id=?", (user_id,))
        r = cur.fetchone()
        if not r:
            cur.execute("INSERT INTO users (user_id,daily_count,last_reset) VALUES (?,?,?)", (user_id,0,ts))
            conn.commit()
            return 0 < free_limit
        daily_count, last_reset = r
        if ts - last_reset > 86400:
            cur.execute("UPDATE users SET daily_count=0,last_reset=? WHERE user_id=?", (ts,user_id))
            conn.commit()
            daily_count = 0
        return daily_count < free_limit
    else:
        with open(JSON_DB, "r+") as f:
            data = json.load(f)
            u = data["users"].get(str(user_id), {"daily_count":0,"last_reset":0})
            if ts - u.get("last_reset",0) > 86400:
                u["daily_count"] = 0
                u["last_reset"] = ts
            allowed = u.get("daily_count",0) < free_limit
            # save
            data["users"][str(user_id)] = u
            f.seek(0); f.truncate()
            json.dump(data, f, indent=2)
            return allowed

def increment_daily_count(user_id):
    ts = now_ts()
    if USE_MONGO:
        users_coll.update_one({"user_id": user_id}, {"$inc": {"daily_count":1}, "$set": {"last_reset": ts}}, upsert=True)
    elif USE_SQLITE:
        cur.execute("SELECT daily_count,last_reset FROM users WHERE user_id=?", (user_id,))
        r = cur.fetchone()
        if not r:
            cur.execute("INSERT INTO users (user_id,daily_count,last_reset) VALUES (?,?,?)", (user_id,1,ts))
        else:
            daily_count, last_reset = r
            if ts - last_reset > 86400:
                cur.execute("UPDATE users SET daily_count=1,last_reset=? WHERE user_id=?", (ts,user_id))
            else:
                cur.execute("UPDATE users SET daily_count=daily_count+1 WHERE user_id=?", (user_id,))
        conn.commit()
    else:
        with open(JSON_DB, "r+") as f:
            data = json.load(f)
            u = data["users"].get(str(user_id), {"daily_count":0,"last_reset":0})
            if ts - u.get("last_reset",0) > 86400:
                u["daily_count"] = 1
                u["last_reset"] = ts
            else:
                u["daily_count"] = u.get("daily_count",0) + 1
            data["users"][str(user_id)] = u
            f.seek(0); f.truncate(); json.dump(data, f, indent=2)
