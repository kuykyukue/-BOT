import discord
from discord.ext import commands
from flask import Flask
from threading import Thread
from deep_translator import GoogleTranslator
import os

# ---- Discord Bot基本設定 ----
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True  # 🔹 メッセージ内容取得を許可
bot = commands.Bot(command_prefix="/", intents=intents)

# ---- Flask (Render用 keep-alive) ----
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

def run_web():
    app.run(host="0.0.0.0", port=8080)

Thread(target=run_web).start()

# ===============================
# 自動翻訳 ON/OFF & 多言語設定
# ===============================
auto_translate_channels = set()
target_languages = ["en", "ja", "ko"]  # ← 翻訳先をここで指定
flags = {"en": "🇺🇸", "ja": "🇯🇵", "ko": "🇰🇷"}

# 翻訳メッセージ対応表（削除連動用）
translated_message_map = {}  # {元メッセージID: [翻訳メッセージID,...]}

# ===============================
# /auto コマンド（ON/OFF切替）
# ===============================
@bot.command()
async def auto(ctx):
    """自動翻訳ON/OFF切り替え"""
    if ctx.channel.id in auto_translate_channels:
        auto_translate_channels.remove(ctx.channel.id)
        await ctx.send("❌ 自動翻訳をオフにしました。")
    else:
        auto_translate_channels.add(ctx.channel.id)
        await ctx.send("✅ 自動翻訳をオンにしました。")

# ===============================
# メッセージ受信 → 翻訳
# ===============================
@bot.event
async def on_message(message):
    if message.author.bot:
        return  # 🔸 Bot自身のメッセージは無視（重複防止）

    if message.channel.id i

bot.run(os.environ["DISCORD_TOKEN"])
