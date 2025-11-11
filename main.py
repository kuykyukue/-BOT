import os
import json
import discord
from discord import app_commands
from discord.ext import commands
from deep_translator import GoogleTranslator
from flask import Flask
from threading import Thread

# ---- Flask (Render keep-alive) ----
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

def run_web():
    app.run(host="0.0.0.0", port=8080)

Thread(target=run_web).start()

# ---- Discord Bot 設定 ----
TOKEN = os.environ.get("DISCORD_BOT_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# ---- 設定保存ファイル ----
SETTINGS_FILE = "channel_settings.json"

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_settings():
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(channel_settings, f, ensure_ascii=False, indent=2)

# ---- 初期ロード ----
channel_settings = load_settings()

# ---- サポート言語 ----
supported_languages = {
    "en": "🇺🇸",
    "ja": "🇯🇵",
    "ko": "🇰🇷",
    "vi": "🇻🇳",
    "es": "🇪🇸"
}

# ===============================
# /setlang コマンド（国旗付き選択式）
# ===============================
@tree.command(name="setlang", description="翻訳先の言語を設定します")
@app_commands.describe(language="翻訳先の言語を選んでください")
@app_commands.choices(language=[
    app_commands.Choice(name=f"{flag} {code.upper()}", value=code)
    for code, flag in supported_languages.items()
])
async def setlang(interaction: discord.Interaction, language: app_commands.Choice[str]):
    channel_id = str(interaction.channel_id)

    if channel_id not in channel_settings:
        channel_settings[channel_id] = {"lang": "en", "auto": False}

    channel_settings[channel_id]["lang"] = language.value
    save_settings()

    await interaction.response.send_message(
        f"✅ 翻訳先を {supported_languages[language.value]} に設定しました！"
    )

# ===============================
# /auto コマンド（ON/OFF切替）
# ===============================
@tree.command(name="auto", description="このチャンネルの自動翻訳をオン／オフします")
async def auto(interaction: discord.Interaction):
    channel_id = str(interaction.channel_id)

    if channel_id not in channel_settings:
        channel_settings[channel_id] = {"lang": "en", "auto": False}

    current = channel_settings[channel_id]["auto"]
    channel_settings[channel_id]["auto"] = not current
    save_settings()

    status = "✅ オン" if not current else "❌ オフ"
    await interaction.response.send_message(f"🌍 自動翻訳を {status} にしました！")

# ===============================
# メッセージ受信・翻訳処理
# ===============================
@bot.event
async def on_message(message):
    if message.author.bot:
        return  # Botの発言は翻訳しない

    channel_id = str(message.channel.id)
    settings = channel_settings.get(channel_id, {"lang": "en", "auto": False})

    if not settings["auto"]:
        return

    lang = settings["lang"]
    try:
        translated = GoogleTranslator(source='auto', target=lang).translate(message.content)
        if translated and translated != message.content:
            await message.channel.send(f"{supported_languages[lang]} {translated}")
    except Exception as e:
        print(f"⚠️ 翻訳エラー: {e}")

# ===============================
# 起動イベント
# ===============================
@bot.event
async def on_ready():
    await tree.sync()
    print(f"✅ Logged in as {bot.user}")
    print("📂 設定読み込み:", channel_settings)

if __name__ == "__main__":
    bot.run(TOKEN)
