# script.py
START = (
    "👋 Hi — *{bot_name}*\n\n"
    "Send a YouTube link and I'll show info + download options.\n\n"
    "✅ I only help you download videos you *own*.\n"
    "💎 Use /add_premium to add premium users (owner only)."
)

HELP = (
    "🛠️ Commands\n"
    "/start - start\n"
    "/help - this help\n"
    "/add_premium [user_id] [days] - owner only\n"
    "/rmpremium [user_id] - owner only\n"
    "/check_premium - check your premium status\n"
)

PREMIUM_TEXT = (
    "💎 *Premium Plans*\n\n"
    "Free: {free_limit} free downloads/day\n\n"
    "Silver: 7 days — Faster downloads, up to 1080p\n"
    "Gold: 30 days — Up to 4K, 320kbps audio, larger uploads, instant queue\n"
    "Platinum: 365 days — All Gold perks + file splitting, priority support\n\n"
    "Scan QR to pay & contact admin for activation."
)

FETCHING_INFO = "🔎 Fetching video info..."
NO_LINK = "❌ That doesn't look like a YouTube link. Send a valid URL."
FAILED_INFO = "⚠️ Failed to fetch info: {error}"
PREPARING_DOWNLOAD = "⏳ Preparing download..."
DOWNLOAD_FINISHED = "✅ Download finished, preparing upload..."
FILE_TOO_LARGE = "⚠️ File too large to send via Telegram ({size}). I can store in storage channel or split (Premium only)."
DL_ERROR = "❌ Download error: {error}"
FREE_LIMIT_REACHED = "⚠️ You reached your free daily download limit ({limit}/day). Upgrade to Premium to remove the limit."
RENAME_PROMPT = "✏️ Send the new filename (without extension) — Premium only. Reply /skip to keep original."
ENTER_CAPTION = "📝 Send a custom caption for the upload or /skip."
CORRECT_ADD_CMD = "❌ Wrong command format.\n\n✅ Correct format:\n`/add_premium [user_id] [days]`"
CORRECT_RM_CMD = "❌ Wrong command format.\n\n✅ Correct format:\n`/rmpremium [user_id]`"
