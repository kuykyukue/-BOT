import discord
from discord.ext import commands
from googletrans import Translator
import json
import os

# ------------------------------
# 初期設定
# ------------------------------
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True

bot = commands.Bot(command_prefix="/", intents=intents, help_command=None)
translator = Translator()

# 翻訳設定を保存するファイル
SETTINGS_FILE = "channel_lang.json"

# ------------------------------
# 国旗とコード対応表
# ------------------------------
FLAG_TO_LANG = {
    "🇺🇸": "en",
    "🇯🇵": "ja",
    "🇨🇳": "zh-cn",
    "🇰🇷": "ko",
    "🇫🇷": "fr",
    "🇩🇪": "de",
    "🇮🇹": "it",
    "🇪🇸": "es",
    "🇷🇺": "ru",
    "🇮🇳": "hi"
}

LANG_TO_FLAG = {v: k for k, v in FLAG_TO_LANG.items()}

# ------------------------------
# 設定ファイルの読み書き
# ------------------------------
def load_settings():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_settings(data):
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

channel_langs = load_settings()

# ------------------------------
# Bot起動時
# ------------------------------
@bot.event
async def on_ready():
    print(f"✅ Bot logged in as {bot.user}")

# ------------------------------
# /setlang 言語設定コマンド
# ------------------------------
@bot.command(name="setlang")
async def set_language(ctx, flag: str = None):
    """チャンネルごとの翻訳先言語を設定"""
    if flag not in FLAG_TO_LANG:
        flags = " ".join(FLAG_TO_LANG.keys())
        await ctx.send(f"🌍 設定したい言語の国旗を選んでください：\n{flags}\n\n例：`/setlang 🇯🇵`")
        return

    lang_code = FLAG_TO_LANG[flag]
    channel_langs[str(ctx.channel.id)] = lang_code
    save_settings(channel_langs)
    await ctx.send(f"✅ このチャンネルの翻訳先言語を {flag} に設定しました！")

# ------------------------------
# 翻訳処理（メッセージ受信時）
# ------------------------------
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    await bot.process_commands(message)  # コマンドを優先

    channel_id = str(message.channel.id)
    if channel_id not in channel_langs:
        return

    target_lang = channel_langs[channel_id]

    try:
        translated = translator.translate(message.content, dest=target_lang)
        # 絵文字などが壊れないよう safe_text
        safe_text = translated.text.encode("utf-8", "ignore").decode("utf-8")
        await message.reply(f"{LANG_TO_FLAG[target_lang]} {safe_text}")
    except Exception as e:
        await message.reply(f"⚠️ 翻訳中にエラーが発生しました: {e}")

# ------------------------------
# /help コマンド
# ------------------------------
@bot.command(name="help")
async def show_help(ctx):
    help_text = (
        "🤖 **自動翻訳BOT 使い方ガイド**\n\n"
        "🌍 **言語設定:**\n"
        "`/setlang [国旗]`\n"
        "例: `/setlang 🇯🇵` → このチャンネルの翻訳先を日本語に設定\n\n"
        "💬 **自動翻訳:**\n"
        "設定後、このチャンネルで投稿されたメッセージを自動的に翻訳します。\n\n"
        "🇺🇸 英語 🇯🇵 日本語 🇨🇳 中国語 🇰🇷 韓国語 🇫🇷 フランス語 🇩🇪 ドイツ語 🇮🇹 イタリア語 🇪🇸 スペイン語 🇷🇺 ロシア語 🇮🇳 ヒンディー語\n\n"
        "📁 設定は自動保存されます。"
    )
    await ctx.send(help_text)

# ------------------------------
# 実行
# ------------------------------
bot.run(os.getenv("DISCORD_TOKEN"))
