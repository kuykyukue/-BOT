import os
import json
import discord
from discord.ext import commands, tasks
from discord import app_commands
from deep_translator import GoogleTranslator
from flask import Flask
from threading import Thread
import aiohttp

# ============================================================
# Flask KeepAlive
# ============================================================
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is alive!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

Thread(target=run_flask, daemon=True).start()


# ============================================================
# Bot 基本設定
# ============================================================
intents = discord.Intents.all()

bot = commands.Bot(
    command_prefix="!",
    intents=intents,
    max_messages=None,
)


SETTINGS_FILE = "settings.json"
guild_settings = {}            # {guild_id: {"auto": True, "langs": ["ja", "en"]}}
translated_messages = {}       # {original_id: [translated_message_ids]}


# ============================================================
# 国旗 → 言語
# ============================================================
flags = {
    "en": "🇺🇸", "ja": "🇯🇵", "ko": "🇰🇷", "zh": "🇨🇳",
    "fr": "🇫🇷", "de": "🇩🇪", "es": "🇪🇸", "it": "🇮🇹",
    "ru": "🇷🇺", "pt": "🇧🇷", "id": "🇮🇩", "vi": "🇻🇳",
    "th": "🇹🇭"
}

# 国旗 → 言語の逆引き
flag_to_lang = {v: k for k, v in flags.items()}


# ============================================================
# JSON 設定の読み込み / 保存
# ============================================================
def load_settings():
    global guild_settings
    if not os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f, ensure_ascii=False, indent=4)

    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            guild_settings = json.load(f)
    except:
        guild_settings = {}

def save_settings():
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(guild_settings, f, ensure_ascii=False, indent=4)
    except:
        pass

load_settings()


# ============================================================
# テキスト抽出（完全版）
# ============================================================
def extract_text(message):
    parts = []

    # 通常メッセージ
    if message.content:
        parts.append(message.content)

    # Embed
    for embed in message.embeds:

        if embed.title:
            parts.append(embed.title)

        if embed.description:
            parts.append(embed.description)

        for field in embed.fields:
            if field.name:
                parts.append(field.name)
            if field.value:
                parts.append(field.value)

        if embed.author and embed.author.name:
            parts.append(embed.author.name)

        if embed.footer and embed.footer.text:
            parts.append(embed.footer.text)

        # image, thumbnail の URL 文も念のため抽出
        if embed.image and embed.image.url:
            parts.append(embed.image.url)
        if embed.thumbnail and embed.thumbnail.url:
            parts.append(embed.thumbnail.url)

    return "\n".join(parts).strip()


# ============================================================
# 翻訳
# ============================================================
async def translate_text(text, target):
    """ deep_translator ラッパー（例外処理付き） """
    if not text:
        return "(翻訳する内容がありません)"

    try:
        translated = GoogleTranslator(source="auto", target=target).translate(text)
        return translated
    except Exception as e:
        return f"[翻訳エラー: {e}]"


# ============================================================
# /auto
# ============================================================
@bot.tree.command(name="auto", description="自動翻訳 ON/OFF")
async def auto(interaction: discord.Interaction):
    guild_id = str(interaction.guild_id)

    settings = guild_settings.get(guild_id, {"auto": False, "langs": ["ja", "en"]})
    settings["auto"] = not settings["auto"]

    guild_settings[guild_id] = settings
    save_settings()

    status = "ON" if settings["auto"] else "OFF"
    await interaction.response.send_message(f"自動翻訳を **{status}** にしました。")


# ============================================================
# /setlang
# ============================================================
@bot.tree.command(name="setlang", description="翻訳対象言語を設定（例: /setlang en ja）")
async def setlang(interaction: discord.Interaction, langs: str):
    guild_id = str(interaction.guild_id)
    lang_list = langs.split()

    guild_settings[guild_id] = guild_settings.get(guild_id, {"auto": False})
    guild_settings[guild_id]["langs"] = lang_list
    save_settings()

    flags_display = " ".join(flags.get(l, l) for l in lang_list)
    await interaction.response.send_message(f"翻訳対象言語を {flags_display} に設定しました。")


# ============================================================
# 国旗リアクション → 翻訳
# ============================================================
@bot.event
async def on_raw_reaction_add(payload):
    if payload.user_id == bot.user.id:
        return

    emoji = str(payload.emoji)
    if emoji not in flag_to_lang:
        return

    lang = flag_to_lang[emoji]

    guild = bot.get_guild(payload.guild_id)
    channel = guild.get_channel(payload.channel_id)
    message = await channel.fetch_message(payload.message_id)

    text = extract_text(message)
    translated = await translate_text(text, lang)

    embed = discord.Embed(
        title=f"{emoji} 翻訳（{lang}）",
        description=translated,
        color=0x00BFFF
    )
    sent = await channel.send(embed=embed)

    translated_messages.setdefault(message.id, []).append(sent.id)


# ============================================================
# 国旗リアクションの削除 → 翻訳も削除
# ============================================================
@bot.event
async def on_raw_reaction_remove(payload):
    emoji = str(payload.emoji)
    if emoji not in flag_to_lang:
        return

    if payload.message_id not in translated_messages:
        return

    guild = bot.get_guild(payload.guild_id)
    channel = guild.get_channel(payload.channel_id)

    for msg_id in translated_messages[payload.message_id]:
        try:
            msg = await channel.fetch_message(msg_id)
            await msg.delete()
        except:
            pass

    translated_messages.pop(payload.message_id, None)


# ============================================================
# 自動翻訳
# ============================================================
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    guild_id = str(message.guild.id)
    settings = guild_settings.get(guild_id)

    if not settings or not settings.get("auto"):
        return

    langs = settings.get("langs", ["en", "ja"])
    text = extract_text(message)

    for lang in langs:
        translated = await translate_text(text, lang)
        emoji = flags.get(lang, lang)

        embed = discord.Embed(
            title=f"{emoji} 翻訳（{lang}）",
            description=translated,
            color=0x00BFFF
        )
        sent = await message.channel.send(embed=embed)

        translated_messages.setdefault(message.id, []).append(sent.id)

    await bot.process_commands(message)


# ============================================================
# 原文削除 → 翻訳も削除
# ============================================================
@bot.event
async def on_message_delete(message):
    if message.id not in translated_messages:
        return

    for msg_id in translated_messages[message.id]:
        try:
            msg = await message.channel.fetch_message(msg_id)
            await msg.delete()
        except:
            pass

    translated_messages.pop(message.id, None)


# ============================================================
# KeepAlive（Render用）
# ============================================================
@tasks.loop(seconds=60)
async def keepalive_ping():
    try:
        async with aiohttp.ClientSession() as session:
            await session.get("https://fan-yi-bot.onrender.com")
    except:
        pass


# ============================================================
# 起動処理
# ============================================================
@bot.event
async def on_ready():
    keepalive_ping.start()
    await bot.tree.sync()
    print(f"Logged in as {bot.user} | READY")


# ============================================================
# 実行
# ============================================================
bot.run(os.getenv("DISCORD_BOT_TOKEN"))
