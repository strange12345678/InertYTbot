# bot.py
import os, uuid, asyncio
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from config import *
import script as S
from download import list_video_qualities, list_audio_qualities, download_and_prepare, split_file
import database
from functions.utils import human_size

# Fix asyncio policy early (Termux compatibility)
asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())

app = Client("inert_downloader", bot_token=BOT_TOKEN, api_id=API_ID, api_hash=API_HASH)

# In-memory sessions for progress and rename flows
SESSIONS = {}  # session_id -> {info, chat_id, user_id, msg_id, awaiting_rename, filepath, is_audio}

LAST_UPDATE = {}

async def async_progress_update(session_id, text):
    session = SESSIONS.get(session_id)
    if not session:
        return
    now = asyncio.get_event_loop().time()
    last = LAST_UPDATE.get(session_id, 0)
    if now - last < 1.0:
        return
    LAST_UPDATE[session_id] = now
    try:
        await app.edit_message_text(session["chat_id"], session["msg_id"], text)
    except Exception:
        pass

# ---------------- Commands ----------------
@app.on_message(filters.command("start") & filters.private)
async def start_cmd(_, message):
    await message.reply_text(S.START.format(bot_name=BOT_NAME), quote=True)

@app.on_message(filters.command("help") & filters.private)
async def help_cmd(_, message):
    await message.reply_text(S.HELP, quote=True)

# /add_premium [user_id] [days]
@app.on_message(filters.command("add_premium") & filters.user(*OWNER_IDS))
async def cmd_add_premium(_, message):
    parts = message.text.strip().split()
    if len(parts) != 3:
        return await message.reply_text(S.CORRECT_ADD_CMD)
    try:
        user_id = int(parts[1])
        days = int(parts[2])
    except:
        return await message.reply_text(S.CORRECT_ADD_CMD)
    try:
        database.add_premium(user_id, days)
        await message.reply_text(f"✅ Added premium for {user_id} for {days} days.")
    except Exception as e:
        await message.reply_text(f"❌ Error adding premium: {e}")

# /rmpremium [user_id]
@app.on_message(filters.command("rmpremium") & filters.user(*OWNER_IDS))
async def cmd_rmpremium(_, message):
    parts = message.text.strip().split()
    if len(parts) != 2:
        return await message.reply_text(S.CORRECT_RM_CMD)
    try:
        user_id = int(parts[1])
    except:
        return await message.reply_text(S.CORRECT_RM_CMD)
    try:
        database.remove_premium(user_id)
        await message.reply_text(f"✅ Removed premium for {user_id}.")
    except Exception as e:
        await message.reply_text(f"❌ Error removing premium: {e}")

@app.on_message(filters.command("check_premium") & filters.private)
async def cmd_check_premium(_, message):
    uid = message.from_user.id
    rem = database.get_remaining_days(uid)
    if database.is_premium(uid):
        await message.reply_text(f"💎 Premium active. Days left: {rem}")
    else:
        await message.reply_text("You are not premium. Use /add_premium (owner) or upgrade link.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("💎 Premium", url=QR_CODE)]]))

# ---------------- Handle incoming text (YouTube links) ----------------
@app.on_message(filters.private & filters.text)
async def handle_text(_, message):
    text = message.text.strip()
    # ignore commands already handled
    if text.startswith("/") or (not ("youtube.com" in text or "youtu.be" in text)):
        return
    url = text
    uid = message.from_user.id

    # Check free limit (non-premium)
    if not database.is_premium(uid):
        allowed = database.can_download_free(uid, FREE_DAILY_LIMIT)
        if not allowed:
            return await message.reply_text(S.FREE_LIMIT_REACHED.format(limit=FREE_DAILY_LIMIT))

    info_msg = await message.reply_text(S.FETCHING_INFO)
    # extract info with yt-dlp without download — use blocking in thread
    import yt_dlp
    def extract_info():
        with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True}) as ydl:
            return ydl.extract_info(url, download=False)
    try:
        loop = asyncio.get_event_loop()
        info = await loop.run_in_executor(None, extract_info)
    except Exception as e:
        return await info_msg.edit_text(S.FAILED_INFO.format(error=e))

    # build info + buttons
    sid = str(uuid.uuid4())
    SESSIONS[sid] = {"info": info, "chat_id": message.chat.id, "user_id": uid}
    title = info.get("title","Unknown")
    uploader = info.get("uploader","Unknown")
    duration = info.get("duration",0)
    views = info.get("view_count",0)
    upload = info.get("upload_date","")
    desc = (info.get("description") or "")[:300].replace("\n"," ")
    txt = (f"🎬 *{title}*\n👤 {uploader}\n🕒 {duration}s | 👁️ {views}\n📅 {upload}\n\n{desc}...\n\nChoose an action:")
    kb = [
        [InlineKeyboardButton("ℹ️ Info", callback_data=f"info|{sid}")],
        [InlineKeyboardButton("🎞️ Video", callback_data=f"choose_video|{sid}")],
        [InlineKeyboardButton("🎧 Audio", callback_data=f"choose_audio|{sid}")],
        [InlineKeyboardButton("💎 Premium", callback_data=f"premium|{sid}")],
    ]
    thumb = info.get("thumbnail")
    await info_msg.delete()
    if thumb:
        await message.reply_photo(thumb, caption=txt, reply_markup=InlineKeyboardMarkup(kb))
    else:
        await message.reply_text(txt, reply_markup=InlineKeyboardMarkup(kb))

# ---------------- Callback handler ----------------
@app.on_callback_query()
async def callbacks(_, cq):
    data = (cq.data or "")
    parts = data.split("|")
    cmd = parts[0]

    if cmd == "info":
        sid = parts[1]; session = SESSIONS.get(sid)
        if not session: return await cq.answer("Session expired", show_alert=True)
        info = session["info"]
        txt = f"📋 *{info.get('title','Unknown')}*\n\n" + (info.get("description","")[:800] or "No description")
        await cq.answer(); await cq.message.edit_text(txt)

    elif cmd == "choose_video":
        sid = parts[1]; session = SESSIONS.get(sid)
        if not session: return await cq.answer("Session expired", show_alert=True)
        info = session["info"]
        choices = list_video_qualities(info)
        if not choices: return await cq.answer("No video formats found", show_alert=True)
        allowed = []
        is_prem = database.is_premium(cq.from_user.id)
        for label, fmt in choices:
            # parse numeric height if possible
            try:
                h = int(label.replace("p",""))
            except:
                h = 0
            if (not is_prem) and (h > 720):
                continue
            allowed.append((label, fmt))
        if not allowed:
            return await cq.answer("Higher qualities are premium only", show_alert=True)
        kb = [[InlineKeyboardButton(label, callback_data=f"dl|video|{sid}|{fmt}")] for label,fmt in allowed]
        kb.append([InlineKeyboardButton("↩️ Back", callback_data=f"back|{sid}")])
        await cq.message.edit_text("Select video quality (lowest → highest):", reply_markup=InlineKeyboardMarkup(kb))
        await cq.answer()

    elif cmd == "choose_audio":
        sid = parts[1]; session = SESSIONS.get(sid)
        if not session: return await cq.answer("Session expired", show_alert=True)
        info = session["info"]
        choices = list_audio_qualities(info)
        if not choices: return await cq.answer("No audio formats found", show_alert=True)
        allowed = []
        is_prem = database.is_premium(cq.from_user.id)
        for label, fmt in choices:
            try:
                abr = int(label.replace("kbps",""))
            except:
                abr = 0
            if (not is_prem) and (abr > 192):
                continue
            allowed.append((label, fmt))
        if not allowed:
            return await cq.answer("High bitrates are premium only", show_alert=True)
        kb = [[InlineKeyboardButton(label, callback_data=f"dl|audio|{sid}|{fmt}")] for label,fmt in allowed]
        kb.append([InlineKeyboardButton("↩️ Back", callback_data=f"back|{sid}")])
        await cq.message.edit_text("Select audio quality (lowest → highest):", reply_markup=InlineKeyboardMarkup(kb))
        await cq.answer()

    elif cmd == "back":
        sid = parts[1]; session = SESSIONS.get(sid)
        if not session: return await cq.answer("Session expired", show_alert=True)
        info = session["info"]
        txt = (f"🎬 *{info.get('title','Unknown')}*\nChoose an action:")
        kb = [
            [InlineKeyboardButton("ℹ️ Info", callback_data=f"info|{sid}")],
            [InlineKeyboardButton("🎞️ Video", callback_data=f"choose_video|{sid}")],
            [InlineKeyboardButton("🎧 Audio", callback_data=f"choose_audio|{sid}")],
            [InlineKeyboardButton("💎 Premium", callback_data=f"premium|{sid}")],
        ]
        await cq.message.edit_text(txt, reply_markup=InlineKeyboardMarkup(kb))
        await cq.answer()

    elif cmd == "premium":
        sid = parts[1]
        await cq.answer()
        try:
            await cq.message.reply_photo(QR_CODE, caption=S.PREMIUM_TEXT.format(free_limit=FREE_DAILY_LIMIT), reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Open QR image", url=QR_CODE)]]))
        except:
            await cq.answer("Open premium link", url=QR_CODE)

    elif cmd == "dl":
        # dl|type|sid|format
        typ = parts[1]; sid = parts[2]; fmt = parts[3]
        session = SESSIONS.get(sid)
        if not session: return await cq.answer("Session expired", show_alert=True)
        info = session["info"]
        url = info.get("webpage_url") or info.get("original_url")
        user_id = cq.from_user.id

        # enforce free daily limits (re-check)
        if not database.is_premium(user_id):
            allowed = database.can_download_free(user_id, FREE_DAILY_LIMIT)
            if not allowed:
                return await cq.answer(S.FREE_LIMIT_REACHED.format(limit=FREE_DAILY_LIMIT), show_alert=True)
            database.increment_daily_count(user_id)

        # create status msg
        status_msg = await cq.message.edit_text(S.PREPARING_DOWNLOAD)
        prog_sid = str(uuid.uuid4())
        SESSIONS[prog_sid] = {"info": info, "chat_id": cq.message.chat.id, "msg_id": status_msg.id, "user_id": user_id}
        is_audio = (typ == "audio")

        # run download in executor
        loop = asyncio.get_event_loop()
        async def run_download():
            try:
                res = await download_and_prepare(url, fmt, is_audio, async_progress_update)
                filepath = res.get("filepath")
                title = res.get("title")
                filesize = res.get("filesize", 0)
                # if too large for Telegram
                if filesize > MAX_UPLOAD_FILESIZE:
                    if database.is_premium(user_id):
                        # split and send parts
                        parts = split_file(filepath)
                        for p in parts:
                            await app.send_document(cq.message.chat.id, p, caption=f"{title} (part) - by {BOT_NAME}")
                            try: os.remove(p)
                            except: pass
                    else:
                        # upload to storage channel
                        try:
                            await app.send_message(cq.message.chat.id, S.FILE_TOO_LARGE.format(size=human_size(filesize)))
                            await app.send_document(int(STORAGE_CHANNEL), filepath, caption=f"Stored for user {user_id} - {title}")
                            await app.send_message(cq.message.chat.id, f"Your file was uploaded to storage channel {STORAGE_CHANNEL}.")
                        except Exception as e:
                            await app.send_message(cq.message.chat.id, f"Failed to store file: {e}")
                else:
                    # Premium rename flow
                    if database.is_premium(user_id):
                        # set awaiting rename in session
                        SESSIONS[prog_sid].update({"awaiting_rename": True, "filepath": filepath, "is_audio": is_audio, "title": title, "info": info})
                        await app.send_message(cq.message.chat.id, S.RENAME_PROMPT)
                    else:
                        caption = f"✅ *{title}*\nDownloaded by @{BOT_NAME}"
                        if is_audio:
                            await app.send_audio(cq.message.chat.id, filepath, caption=caption)
                        else:
                            thumb = info.get("thumbnail")
                            if thumb:
                                await app.send_video(cq.message.chat.id, filepath, caption=caption, thumb=thumb)
                            else:
                                await app.send_video(cq.message.chat.id, filepath, caption=caption)
                        # record
                        try:
                            database.add_download_record(user_id, title, filepath, filesize)
                        except:
                            pass
                        try: os.remove(filepath)
                        except: pass
                # show premium CTA
                await app.send_message(cq.message.chat.id, "💎 Want more features? Upgrade:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("💎 Get Premium", url=QR_CODE)]]))
            except Exception as e:
                await app.send_message(cq.message.chat.id, S.DL_ERROR.format(error=e))
            finally:
                SESSIONS.pop(prog_sid, None)
        loop.create_task(run_download())
        await cq.answer("Download started. Progress will update shortly.")

    else:
        await cq.answer("Unknown action", show_alert=True)

# ---------------- Handler to accept rename reply (premium only) ----------------
@app.on_message(filters.private & filters.text)
async def rename_handler(_, message):
    # find session awaiting rename for this user
    for sid, s in list(SESSIONS.items()):
        if s.get("awaiting_rename") and s.get("user_id") == message.from_user.id:
            text = message.text.strip()
            filepath = s.get("filepath")
            is_audio = s.get("is_audio")
            title = s.get("title")
            info = s.get("info")
            if text == "/skip":
                newname = None
            else:
                newname = text
            # rename if requested
            if newname:
                base, ext = os.path.splitext(filepath)
                newpath = os.path.join(os.path.dirname(filepath), newname + ext)
                try:
                    os.rename(filepath, newpath)
                    filepath = newpath
                except Exception:
                    pass
            caption = f"✅ *{newname or title}*\nDownloaded by @{BOT_NAME}"
            try:
                if is_audio:
                    await app.send_audio(message.chat.id, filepath, caption=caption)
                else:
                    thumb = info.get("thumbnail")
                    if thumb:
                        await app.send_video(message.chat.id, filepath, caption=caption, thumb=thumb)
                    else:
                        await app.send_video(message.chat.id, filepath, caption=caption)
                database.add_download_record(message.from_user.id, newname or title, filepath, os.path.getsize(filepath))
            except Exception as e:
                await message.reply_text(f"Error sending file: {e}")
            try:
                os.remove(filepath)
            except:
                pass
            # cleanup
            s.pop("awaiting_rename", None)
            s.pop("filepath", None)
            s.pop("is_audio", None)
            s.pop("title", None)
            break

# ---------------- Admin stats ----------------
@app.on_message(filters.command("stats") & filters.user(*OWNER_IDS))
async def cmd_stats(_, message):
    try:
        cnt = "unknown"
        # rough count
        if database.USE_MONGO:
            cnt = database.downloads_coll.count_documents({})
        elif database.USE_SQLITE:
            database.cur.execute("SELECT COUNT(*) FROM downloads")
            cnt = database.cur.fetchone()[0]
        else:
            with open(database.JSON_DB, "r") as f:
                data = json.load(f)
            cnt = len(data.get("downloads", []))
        await message.reply_text(f"📊 Total downloads recorded: {cnt}")
    except Exception as e:
        await message.reply_text(f"Error fetching stats: {e}")

# ---------------- Run ----------------
if __name__ == "__main__":
    app.run()
