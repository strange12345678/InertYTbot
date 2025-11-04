# main.py
import asyncio
from bot import app
import database

# Ensure DB file exists for JSON fallback (database import handles creation)
print("Starting Inert Downloader Bot...")
asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
app.run()
