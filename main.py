import os
import json
import discord
from discord.ext import commands, tasks
from discord import app_commands
from deep_translator import GoogleTranslator
from flask import Flask
from threading import Thread
import asyncio
import aiohttp
import re

# ============================================================
# Flask KeepAlive（Render + UptimeRobot）
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
# Bot 設定
# ============================================================
intents = discord.Intents.all()
bot = commands.Bot(
    command_prefix="!",
    intents=intents,
    max_messages=None,
    heartbeat_timeout=60,
)
GUILD_SETTINGS_FILE = "settings.json"

# 設定データ
guild_settings = {}            # {guild_id: {"auto": False, "langs": ["ja","en"]}}
translated_messages = {}       # {original_id: [translated_message_ids]}

# 国旗と言語
flags = {
    "en": "🇺🇸", "ja": "🇯🇵", "ko": "🇰🇷", "zh": "🇨🇳",
    "fr": "🇫🇷", "de": "🇩🇪", "es": "🇪🇸", "it": "🇮🇹",
    "ru": "🇷🇺", "pt": "🇧🇷", "id": "🇮🇩", "vi": "🇻🇳",
    "th": "🇹🇭"
}

# ============================================================
# JSON 設定の読み込み / 保存
# ============================================================
def load_settings():
    global guild_settings
    try:
        if not os.path.exists(GUILD_SETTINGS_FILE):
            with open(GUILD_SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump({}, f, ensure_ascii=False, indent=4)
        with open(GUILD_SETTINGS_FILE, "r", encoding="utf-8") as f:
            guild_settings = json.load(f)
    except Exception:
        guild_settings = {}

def save_settings():
    try:
        with open(GUILD_SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(guild_settings, f, ensure_ascii=False, indent=4)
    except Exception:
        pass

load_settings()

# ============================================================
# embed / メッセージからテキスト抽出
# ============================================================
def extract_text(message):
    parts = []

    if message.content:
        parts.append(message.content)

    for embed in message.embeds:
        if embed.title:
            parts.append(embed.title)
        if embed.description:
            parts.append(embed.description)
        for field in embed.fields:
            parts.append(field.name)
            parts.append(field.value)

    return "\n".join(parts).strip()

# ============================================================
# 翻訳処理
# ============================================================
async def translate_message(text, target_lang):
    try:
        result = GoogleTranslator(source='auto', target=target_lang).translate(text)
        return result
    except Exception as e:
        return f"[翻訳エラー: {e}]"

# ============================================================
# /auto コマンド（自動翻訳 ON/OFF）
# ============================================================
@bot.tree.command(name="auto", description="サーバーの自動翻訳を ON/OFF します")
async def auto(interaction: discord.Interaction):
    guild_id = str(interaction.guild_id)

    if guild_id not in guild_settings:
        guild_settings[guild_id] = {"auto": False, "langs": ["en", "ja"]}

    guild_settings[guild_id]["auto"] = not guild_settings[guild_id]["auto"]
    save_settings()

    status = "ON" if guild_settings[guild_id]["auto"] else "OFF"
    await interaction.response.send_message(f"自動翻訳を **{status}** にしました。")

# ============================================================
# /setlang コマンド（翻訳言語設定）
# ============================================================
@bot.tree.command(name="setlang", description="翻訳対象言語を設定（例: /setlang en ja）")
async def setlang(interaction: discord.Interaction, langs: str):
    guild_id = str(interaction.guild_id)
    lang_list = langs.split()

    guild_settings[guild_id] = guild_settings.get(guild_id, {})
    guild_settings[guild_id]["langs"] = lang_list
    save_settings()

    flags_display = " ".join(flags.get(lang, lang) for lang in lang_list)
    await interaction.response.send_message(f"翻訳対象言語を {flags_display} に設定しました。")

# ============================================================
# 国旗リアクション → 翻訳
# ============================================================
@bot.event
async def on_raw_reaction_add(payload):
    if payload.user_id == bot.user.id:
        return

    guild = bot.get_guild(payload.guild_id)
    channel = guild.get_channel(payload.channel_id)
    message = await channel.fetch_message(payload.message_id)

    emoji = str(payload.emoji)

    # 国旗→言語変換
    lang = None
    for k, v in flags.items():
        if v == emoji:
            lang = k
            break

    if not lang:
        return

    text = extract_text(message)
    translated = await translate_message(text, lang)

    embed = discord.Embed(
        title=f"{emoji} 翻訳 ({lang})",
        description=translated,
        color=0x00BFFF
    )

    sent = await channel.send(embed=embed)

    # 翻訳削除用に保存
    translated_messages.setdefault(message.id, []).append(sent.id)

# ============================================================
# リアクション削除 → 翻訳削除
# ============================================================
@bot.event
async def on_raw_reaction_remove(payload):
    emoji = str(payload.emoji)
    if emoji not in flags.values():
        return

    guild = bot.get_guild(payload.guild_id)
    channel = guild.get_channel(payload.channel_id)

    if payload.message_id not in translated_messages:
        return

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

    if guild_id not in guild_settings:
        return

    if not guild_settings[guild_id]["auto"]:
        return

    langs = guild_settings[guild_id].get("langs", ["en", "ja"])
    text = extract_text(message)

    for lang in langs:
        translated = await translate_message(text, lang)
        emoji = flags.get(lang, lang)

        embed = discord.Embed(
            title=f"{emoji} 翻訳 ({lang})",
            description=translated,
            color=0x00BFFF
        )
        sent = await message.channel.send(embed=embed)
        translated_messages.setdefault(message.id, []).append(sent.id)

    await bot.process_commands(message)

# ============================================================
# 翻訳元削除 → 翻訳も削除
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
# KeepAlive
# ============================================================
@tasks.loop(seconds=60)
async def keepalive_ping():
    try:
        async with aiohttp.ClientSession() as session:
            await session.get("https://fan-yi-bot.onrender.com")
    except:
        pass

# ============================================================
# 起動時
# ============================================================
@bot.event
async def on_ready():
    keepalive_ping.start()
    await bot.tree.sync()
    print(f"Logged in as {bot.user} (ready)")

# ============================================================
# 実行
# ============================================================
bot.run(os.getenv("DISCORD_BOT_TOKEN"), reconnect=True)
