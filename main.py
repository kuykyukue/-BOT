import os
import discord
from discord import app_commands
from discord.ext import commands
from googletrans import Translator
from flask import Flask
import threading
import json

# =========================================================
# 🌐 Flask keep-alive server (Render無料プラン対応)
# =========================================================
app = Flask(__name__)

@app.route('/')
def home():
    return "✅ Bot is running on Render!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# =========================================================
# 🤖 Discord Bot設定
# =========================================================
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

translator = Translator()

# JSONファイル（設定保存用）
SETTINGS_FILE = "channel_settings.json"

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_settings(data):
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

settings = load_settings()

# =========================================================
# ⚙️ 翻訳関連ヘルパー
# =========================================================
def get_channel_settings(guild_id, channel_id):
    """サーバー＋チャンネルごとの設定を取得"""
    guild_id = str(guild_id)
