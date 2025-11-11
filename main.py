import discord
from discord.ext import commands
from flask import Flask
from threading import Thread
from deep_translator import GoogleTranslator
import json
import os

# ===============================
# Discord Bot 設定
# ===============================
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
bot = commands.Bot(command_prefix="/", intents=intents)

# ===============================
# Flask (Render keep-alive)
# ===============================
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

Thread(target=run_web).start()

# ===============================
# 翻訳設定関連
# ===============================
SETTINGS_FILE = "channel_settings.json"

def load_settings():
    """JSONファイルから設定を読み込む"""
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_settings():
    """設定をJSONファイルに保存"""
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(channel_settings, f, ensure_ascii=False, indent=2)

# チャンネル設定：{ channel_id: {"enabled": bool, "lang": "xx"} }
channel_settings = load_settings()

supported_langs = {
    "en": "英語 🇺🇸",
    "ja": "日本語 🇯🇵",
    "ko": "韓国語 🇰🇷",
    "zh": "中国語 🇨🇳",
    "fr": "フランス語 🇫🇷",
    "de": "ドイツ語 🇩🇪",
    "vi": "ベトナム語 🇻🇳",
    "es": "スペイン語 🇪🇸"
}

# ===============================
# /auto コマンド（ON/OFF切替）
# ===============================
@bot.command()
async def auto(ctx):
    """このチャンネルで自動翻訳をON/OFF"""
    cid = str(ctx.channel.id)
    setting = channel_settings.get(cid, {"enabled": False, "lang": "en"})

    setting["enabled"] = not setting["enabled"]
    channel_settings[cid] = setting
    save_settings()

    status = "✅ 翻訳ON" if setting["enabled"] else "❌ 翻訳OFF"
    await ctx.send(f"{status} に設定しました。")

# ===============================
# /setlang コマンド
# ===============================
@bot.command()
async def setlang(ctx, lang: str = None):
    """翻訳先の言語を設定（引数なしで一覧表示）"""
    cid = str(ctx.channel.id)
    if lang is None:
        lang_list = "\n".join([f"`{k}` → {v}" for k, v in supported_langs.items()])
        await ctx.send(f"🌐 使用可能な言語一覧:\n{lang_list}\n\n例: `/setlang en`")
        return

    lang = lang.lower()
    if lang not in supported_langs:
        await ctx.send("❌ 無効な言語コードです。 `/setlang` で一覧を確認できます。")
        return

    setting = channel_settings.get(cid, {"enabled": False, "lang": "en"})
    setting["lang"] = lang
    channel_settings[cid] = setting
    save_settings()

    await ctx.send(f"🌍 翻訳先を {supported_langs[lang]} に設定しました。")

# ===============================
# /status コマンド（確認用）
# ===============================
@bot.command()
async def status(ctx):
    """このチャンネルの翻訳設定を確認"""
    cid = str(ctx.channel.id)
    setting = channel_settings.get(cid, {"enabled": False, "lang": "en"})
    lang_display = supported_langs.get(setting["lang"], "不明")
    status = "ON ✅" if setting["enabled"] else "OFF ❌"
    await ctx.send(f"📋 このチャンネルの設定\n- 翻訳: {status}\n- 言語: {lang_display}")

# ===============================
# メッセージ受信時
# ===============================
@bot.event
async def on_message(message):
    try:
        if message.author.bot or message.author == message.guild.me:
            return

        cid = str(message.channel.id)
        setting = channel_settings.get(cid)
        if not setting or not setting.get("enabled"):
            await bot.process_commands(message)
            return

        target_lang = setting.get("lang", "en")
        translated = GoogleTranslator(source="auto", target=target_lang).translate(message.content)
        flag = supported_langs.get(target_lang, "🌐")

        await message.channel.send(f"{flag.split()[1]} {translated}")

    except Exception as e:
        await message.channel.send(f"⚠️ 翻訳時にエラーが発生しました: {e}")

    await bot.process_commands(message)

# ===============================
# 起動時
# ===============================
@bot.event
async def on_ready():
    print(f"✅ {bot.user} としてログインしました！")
    print(f"💾 {len(channel_settings)} 件のチャンネル設定を読み込みました。")

# ===============================
# 起動
# ===============================
try:
    bot.run(os.environ["DISCORD_BOT_TOKEN"])
except Exception as e:
    print(f"❌ BOT起動エラー: {e}")
