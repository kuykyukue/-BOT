import os
import discord
from discord.ext import commands
from googletrans import Translator
from flask import Flask
from threading import Thread
import json

# -------------------------------
# Flask（Render無料Webサービス対応用）
# -------------------------------
app = Flask(__name__)

@app.route('/')
def home():
    return "🌐 Translation Bot is running!"

def run():
    app.run(host='0.0.0.0', port=10000)

Thread(target=run).start()

# -------------------------------
# Discord Bot 初期設定
# -------------------------------
TOKEN = os.getenv("DISCORD_TOKEN")
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

translator = Translator()
settings_file = "channel_settings.json"

# -------------------------------
# 言語設定ファイルの読み書き
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
# 国旗→言語コードの対応表
# -------------------------------
flag_to_lang = {
    "🇯🇵": "ja",
    "🇺🇸": "en",
    "🇫🇷": "fr",
    "🇩🇪": "de",
    "🇨🇳": "zh-cn",
    "🇰🇷": "ko",
    "🇪🇸": "es",
    "🇮🇹": "it",
    "🇷🇺": "ru"
}

lang_to_flag = {v: k for k, v in flag_to_lang.items()}

# -------------------------------
# BOT起動時のイベント
# -------------------------------
@bot.event
async def on_ready():
    print(f"✅ {bot.user} としてログインしました！")

# -------------------------------
# 翻訳言語を設定するコマンド
# -------------------------------
@bot.command()
async def setlang(ctx, flag: str):
    """使用例: !setlang 🇺🇸"""
    if flag not in flag_to_lang:
        available = " ".join(flag_to_lang.keys())
        await ctx.send(f"⚙️ 対応している国旗: {available}")
        return

    lang = flag_to_lang[flag]
    channel_languages[str(ctx.channel.id)] = lang
    save_settings(channel_languages)

    await ctx.send(f"✅ このチャンネルの翻訳先は {flag} に設定されました！")

# -------------------------------
# 現在の設定を確認
# -------------------------------
@bot.command()
async def langinfo(ctx):
    lang = channel_languages.get(str(ctx.channel.id))
    if lang:
        flag = lang_to_flag.get(lang, "❓")
        await ctx.send(f"🌍 このチャンネルの翻訳先は {flag}（{lang}）です。")
    else:
        await ctx.send("⚙️ このチャンネルではまだ翻訳言語が設定されていません。")

# -------------------------------
# 翻訳機能（メッセージ受信時）
# -------------------------------
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # チャンネルの翻訳先を取得
    lang = channel_languages.get(str(message.channel.id))
    if not lang:
        await bot.process_commands(message)
        return

    try:
        translated = translator.translate(message.content, dest=lang)
        flag = lang_to_flag.get(lang, "🌐")

        # 絵文字は翻訳されずそのまま残る
        await message.reply(f"{flag} **翻訳:** {translated.text}")
    except Exception as e:
        print(f"翻訳エラー: {e}")
        await message.reply("⚠️ 翻訳中にエラーが発生しました。")

    await bot.process_commands(message)

# -------------------------------
# BOT起動
# -------------------------------
bot.run(TOKEN)
