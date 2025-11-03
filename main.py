import os
import json
import discord
from discord import app_commands
from discord.ext import commands
from googletrans import Translator
from flask import Flask
from threading import Thread

# -------------------------------
# Flask（RenderのWebサーバー監視用）
# -------------------------------
app = Flask(__name__)

@app.route('/')
def home():
    return "✅ Discord Translation Bot is running on Render (Free Plan)."

def run_web():
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

Thread(target=run_web).start()

# -------------------------------
# Discord Bot 設定
# -------------------------------
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)
translator = Translator()

settings_file = "channel_settings.json"

# -------------------------------
# 言語設定ファイル操作
# -------------------------------
def load_settings():
    if os.path.exists(settings_file):
        with open(settings_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_settings(data):
    with open(settings_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

channel_languages = load_settings()

# -------------------------------
# 国旗と言語の対応表
# -------------------------------
flag_to_lang = {
    "🇯🇵": "ja", "🇺🇸": "en", "🇫🇷": "fr",
    "🇩🇪": "de", "🇨🇳": "zh-cn", "🇰🇷": "ko",
    "🇪🇸": "es", "🇮🇹": "it", "🇷🇺": "ru"
}
lang_to_flag = {v: k for k, v in flag_to_lang.items()}

# -------------------------------
# 起動時イベント
# -------------------------------
@bot.event
async def on_ready():
    print(f"✅ Bot logged in as {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"🌐 Synced {len(synced)} slash commands.")
    except Exception as e:
        print(f"⚠️ スラッシュコマンド同期エラー: {e}")

# -------------------------------
# スラッシュコマンド
# -------------------------------

@bot.tree.command(name="setlang", description="このチャンネルの翻訳先言語を設定します（例: /setlang 🇯🇵）")
async def setlang(interaction: discord.Interaction, flag: str):
    if flag not in flag_to_lang:
        await interaction.response.send_message(
            "⚙️ 対応言語: " + " ".join(flag_to_lang.keys()),
            ephemeral=True
        )
        return

    lang = flag_to_lang[flag]
    channel_languages[str(interaction.channel.id)] = lang
    save_settings(channel_languages)

    await interaction.response.send_message(f"✅ このチャンネルの翻訳先を {flag} に設定しました！")

@bot.tree.command(name="langinfo", description="このチャンネルの翻訳設定を確認します")
async def langinfo(interaction: discord.Interaction):
    lang = channel_languages.get(str(interaction.channel.id))
    if not lang:
        await interaction.response.send_message(
            "⚙️ このチャンネルは未設定です。`/setlang 🇺🇸` などで設定してください。",
            ephemeral=True
        )
        return

    flag = lang_to_flag.get(lang, "🌍")
    await interaction.response.send_message(f"🌍 現在の翻訳先: {flag}（{lang}）")

# -------------------------------
# メッセージ翻訳イベント
# -------------------------------
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    lang = channel_languages.get(str(message.channel.id))
    if not lang:
        await bot.process_commands(message)
        return

    try:
        translated = translator.translate(message.content, dest=lang)
        flag = lang_to_flag.get(lang, "🌐")
        await message.reply(f"{flag} **翻訳:** {translated.text}")
    except Exception as e:
        print("翻訳エラー:", e)
        await message.reply("⚠️ 翻訳に失敗しました。")

    await bot.process_commands(message)

# -------------------------------
# 実行
# -------------------------------
bot.run(TOKEN)
