import discord
from discord.ext import commands
from googletrans import Translator
import os
import json
from flask import Flask
from threading import Thread

# ====== BOT設定 ======
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="/", intents=intents)
translator = Translator()

SETTINGS_FILE = "channel_settings.json"

# ====== 設定ファイルの読み書き ======
def load_settings():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_settings():
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(channel_settings, f, ensure_ascii=False, indent=2)

channel_settings = load_settings()

# ====== BOT起動時 ======
@bot.event
async def on_ready():
    print(f"✅ ログイン完了: {bot.user}")
    print("翻訳BOTが起動しました！")

# ====== 言語設定コマンド ======
@bot.command()
async def setlang(ctx, source, target):
    """このチャンネルの翻訳元と翻訳先を設定します。例: /setlang ja en"""
    channel_id = str(ctx.channel.id)
    if channel_id not in channel_settings:
        channel_settings[channel_id] = {}

    channel_settings[channel_id]["source"] = source.lower()
    channel_settings[channel_id]["target"] = target.lower()
    channel_settings[channel_id]["enabled"] = True

    save_settings()
    await ctx.send(f"✅ 翻訳設定を保存しました: {source} ↔ {target}")

# ====== 翻訳ON/OFF切り替え ======
@bot.command()
async def toggletranslate(ctx):
    """このチャンネルの翻訳ON/OFFを切り替えます"""
    channel_id = str(ctx.channel.id)

    if channel_id not in channel_settings:
        channel_settings[channel_id] = {"enabled": True, "source": "ja", "target": "en"}

    channel_settings[channel_id]["enabled"] = not channel_settings[channel_id]["enabled"]
    save_settings()

    state = "ON" if channel_settings[channel_id]["enabled"] else "OFF"
    await ctx.send(f"🔁 このチャンネルの翻訳機能を {state} にしました。")

# ====== メッセージ監視（翻訳処理） ======
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    channel_id = str(message.channel.id)
    settings = channel_settings.get(channel_id, {})

    await bot.process_commands(message)

    if not settings.get("enabled", False):
        return  # 翻訳OFFならスキップ

    source_lang = settings.get("source", "ja")
    target_lang = settings.get("target", "en")
    text = message.content.strip()

    if not text:
        return

    try:
        detected = translator.detect(text).lang

        # 双方向翻訳（ja→en / en→ja）
        if detected == source_lang and target_lang:
            translated = translator.translate(text, src=source_lang, dest=target_lang).text
            await message.channel.send(f"{message.author.name} 🌐 {source_lang}→{target_lang}: {translated}")

        elif detected == target_lang and source_lang:
            translated = translator.translate(text, src=target_lang, dest=source_lang).text
            await message.channel.send(f"{message.author.name} 🌐 {target_lang}→{source_lang}: {translated}")

    except Exception as e:
        print("翻訳エラー:", e)

# ====== Render用 Webサーバー（プロセス停止防止） ======
app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!"

def run():
    app.run(host='0.0.0.0', port=8080)

Thread(target=run).start()

# ====== Discordトークン起動 ======
bot.run(os.getenv("DISCORD_TOKEN"))
