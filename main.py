import os
import json
import asyncio
import discord
from discord.ext import commands
from deep_translator import GoogleTranslator
from flask import Flask
import threading

# ------------------------
# Flask（Render Keep-Alive用）
# ------------------------
app = Flask(__name__)
@app.route("/")
def home():
    return "Bot is running!"

# ------------------------
# Discord Bot 設定
# ------------------------
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.reactions = True
intents.guilds = True

bot = commands.Bot(command_prefix="/", intents=intents, reconnect=True)


# ------------------------
# 永続設定
# ------------------------
DATA_PATH = "data/settings.json"
os.makedirs("data", exist_ok=True)
if not os.path.exists(DATA_PATH):
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump({}, f, indent=4, ensure_ascii=False)

def load_settings():
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save_settings(data):
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

settings = load_settings()


# ------------------------
# 国旗・言語マップ（Discord emojiコード表示に使用）
# ------------------------
flag_to_lang = {
    "🇺🇸": "en",
    "🇯🇵": "ja",
    "🇰🇷": "ko",
    "🇻🇳": "vi",
    "🇪🇸": "es",
    "🇹🇼": "zh-TW",
    "🇨🇳": "zh-CN",
}

# 言語コード → 国旗 Emoji の逆引き
lang_to_flag = {v: k for k, v in flag_to_lang.items()}


# ------------------------
# 2: Discord 国旗コード (:flag_us:) に変換する関数
# ------------------------
def to_discord_flag(lang: str) -> str:
    """
    'en' → :flag_us:
    'ja' → :flag_jp:
    のように 2文字コードを Discord の絵文字コードへ変換
    """
    if "-" in lang:  # zh-TW → tw とか
        lang = lang.split("-")[1] if len(lang.split("-")) == 2 else lang.split("-")[0]

    country = lang.upper()
    # ISO 対応の国旗
    mapping = {
        "EN": "us",
        "JA": "jp",
        "KO": "kr",
        "VI": "vn",
        "ES": "es",
        "TW": "tw",
        "CN": "cn",
        "ZH": "cn",
    }

    code = mapping.get(country, "white_flag")
    if code == "white_flag":
        return ":white_flag:"
    return f":flag_{code}:"


# ------------------------
# 翻訳テキスト抽出（完全対応版）
# ------------------------
async def extract_text_from_message(message):
    texts = []

    # --- 通常メッセージ ---
    if message.content:
        texts.append(message.content)

    # --- Embed（引用共有・通常） ---
    for embed in message.embeds:

        # 引用共有（別チャンネル引用）
        if embed.type in ("message", "message_link"):
            if embed.description:
                texts.append(embed.description)
            for f in embed.fields:
                if f.value:
                    texts.append(f.value)

        # 通常の Embed
        if embed.title:
            texts.append(embed.title)
        if embed.description:
            texts.append(embed.description)
        for f in embed.fields:
            if f.name:
                texts.append(f.name)
            if f.value:
                texts.append(f.value)

    # --- スレッド開始引用 ---
    if message.type == discord.MessageType.thread_starter_message:
        if message.reference and message.reference.resolved:
            starter = message.reference.resolved
            if starter.content:
                texts.append(starter.content)

    # --- 通常リプライ引用 ---
    if message.reference and message.reference.message_id:
        try:
            ref = await message.channel.fetch_message(message.reference.message_id)

            if ref.content:
                texts.append(ref.content)

            for embed in ref.embeds:
                if embed.title:
                    texts.append(embed.title)
                if embed.description:
                    texts.append(embed.description)
                for f in embed.fields:
                    if f.name:
                        texts.append(f.name)
                    if f.value:
                        texts.append(f.value)
        except:
            pass

    cleaned = [t.strip() for t in texts if t.strip()]
    return list(dict.fromkeys(cleaned))


# ------------------------
# 非同期翻訳
# ------------------------
async def async_translate(text, target):
    return await asyncio.to_thread(
        GoogleTranslator(source="auto", target=target).translate,
        text
    )


# ------------------------
# 国旗リアクション追加 → 翻訳
# ------------------------
translated_message_map = {}

@bot.event
async def on_raw_reaction_add(payload):
    try:
        if payload.user_id == bot.user.id:
            return

        emoji = str(payload.emoji)
        if emoji not in flag_to_lang:
            return

        lang = flag_to_lang[emoji]

        guild = bot.get_guild(payload.guild_id)
        channel = guild.get_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)

        if message.author.bot:
            return

        # --- 抽出 ---
        texts = await extract_text_from_message(message)
        if not texts:
            return

        original = "\n".join(texts)
        translated = await async_translate(original, lang)

        # ② 国旗表示（:flag_us:）
        flag_code = to_discord_flag(lang)

        embed = discord.Embed(
            title=f"翻訳結果 {flag_code}",
            description=translated,
            color=0x00c19f
        )
        embed.set_footer(text=f"元メッセージID: {message.id}")

        sent = await channel.send(embed=embed)
        translated_message_map[(message.id, emoji)] = sent.id

    except Exception as e:
        print("on_raw_reaction_add エラー:", e)


# ------------------------
# 国旗リアクション削除 → 翻訳削除
# ------------------------
@bot.event
async def on_raw_reaction_remove(payload):
    try:
        emoji = str(payload.emoji)
        if emoji not in flag_to_lang:
            return

        channel = bot.get_channel(payload.channel_id)
        key = (payload.message_id, emoji)

        if key in translated_message_map:
            msg_id = translated_message_map[key]
            try:
                msg = await channel.fetch_message(msg_id)
                await msg.delete()
            except:
                pass
            del translated_message_map[key]

    except Exception as e:
        print("on_raw_reaction_remove エラー:", e)


# ------------------------
# Bot Ready
# ------------------------
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"✅ Logged in as {bot.user}")


# ------------------------
# Flask + Discord Bot
# ------------------------
def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    thread = threading.Thread(target=run_flask)
    thread.start()
    bot.run(os.environ["DISCORD_BOT_TOKEN"])
