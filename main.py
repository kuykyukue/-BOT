import os
import asyncio
import discord
from discord.ext import commands
from discord import app_commands
from flask import Flask
from threading import Thread
from deep_translator import GoogleTranslator

# -----------------------
# Flask KeepAlive for Render / UptimeRobot
# -----------------------
app = Flask(__name__)

@app.route("/")
def home():
    return "BOT RUNNING OK", 200

def run_flask():
    app.run(host="0.0.0.0", port=10000)

Thread(target=run_flask).start()

# -----------------------
# Discord BOT 設定
# -----------------------
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.guilds = True
intents.reactions = True

bot = commands.Bot(command_prefix="!", intents=intents)

# -----------------------
# チャンネルごとの設定
# -----------------------
channel_settings = {}

default_settings = {
    "auto_translate": False,
    "auto_lang": "en",
    "forward_copy": True,
}

def get_ch_settings(channel_id):
    if channel_id not in channel_settings:
        channel_settings[channel_id] = default_settings.copy()
    return channel_settings[channel_id]

# -----------------------
# 翻訳関数（deep-translator）
# -----------------------
async def translate_text(text: str, dest="en"):
    try:
        translation = GoogleTranslator(source='auto', target=dest).translate(text)
        return translation
    except Exception as e:
        print("Translation error:", e)
        return None

# -----------------------
# /set_auto
# -----------------------
@bot.tree.command(name="set_auto", description="自動翻訳を ON/OFF します")
async def set_auto(interaction: discord.Interaction, enable: bool, lang: str):
    ch = get_ch_settings(interaction.channel_id)
    ch["auto_translate"] = enable
    ch["auto_lang"] = lang

    await interaction.response.send_message(
        f"✅ 自動翻訳: **{'ON' if enable else 'OFF'}**\n翻訳言語: **{lang}**"
    )

# -----------------------
# /set_forward
# -----------------------
@bot.tree.command(name="set_forward", description="引用/転送メッセージの翻訳 ON/OFF")
async def set_forward(interaction: discord.Interaction, enable: bool):
    ch = get_ch_settings(interaction.channel_id)
    ch["forward_copy"] = enable

    await interaction.response.send_message(
        f"🔁 引用/転送メッセージ翻訳: **{'ON' if enable else 'OFF'}**"
    )

# -----------------------
# on_message （自動翻訳 & 強制翻訳）
# -----------------------
@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    ch = get_ch_settings(message.channel.id)

    # 強制翻訳 (!ja こんにちは)
    if message.content.startswith("!"):
        parts = message.content.split(" ", 1)
        if len(parts) == 2:
            lang = parts[0][1:]
            txt = parts[1]
            translated = await translate_text(txt, dest=lang)
            if translated:
                await message.channel.send(f"**[{lang}]** {translated}")
        return

    # 自動翻訳
    if ch["auto_translate"]:
        translated = await translate_text(message.content, dest=ch["auto_lang"])
        if translated:
            await message.channel.send(f"🌐 **Auto:** {translated}")

    await bot.process_commands(message)

# -----------------------
# リアクション翻訳の管理
# -----------------------
reaction_map = {}

emoji_lang = {
    "🇯🇵": "ja",
    "🇺🇸": "en",
    "🇨🇳": "zh-CN",
    "🇹🇼": "zh-TW",
    "🇰🇷": "ko",
    "🇫🇷": "fr",
}

# -----------------------
# on_reaction_add
# -----------------------
@bot.event
async def on_reaction_add(reaction, user):
    if user.bot:
        return

    emoji = str(reaction.emoji)
    if emoji not in emoji_lang:
        return

    lang = emoji_lang[emoji]
    message = reaction.message

    # 多重翻訳防止
    if message.id in reaction_map and emoji in reaction_map[message.id]:
        return

    translated = await translate_text(message.content, dest=lang)
    if not translated:
        return

    # 引用メッセージも翻訳
    ref_text = ""
    if message.reference and message.reference.resolved:
        ref_text = f"\n> 引用: {message.reference.resolved.content}"

    sent = await message.channel.send(
        f"🔁 **{emoji} 翻訳**:\n{translated}{ref_text}"
    )

    # 記録
    if message.id not in reaction_map:
        reaction_map[message.id] = {}
    reaction_map[message.id][emoji] = sent.id

# -----------------------
# on_reaction_remove（削除連動）
# -----------------------
@bot.event
async def on_reaction_remove(reaction, user):
    if user.bot:
        return

    emoji = str(reaction.emoji)
    if emoji not in emoji_lang:
        return

    message = reaction.message

    if message.id not in reaction_map:
        return
    if emoji not in reaction_map[message.id]:
        return

    msg_id = reaction_map[message.id][emoji]

    try:
        target = await message.channel.fetch_message(msg_id)
        await target.delete()
    except:
        pass

    del reaction_map[message.id][emoji]
    if not reaction_map[message.id]:
        del reaction_map[message.id]

# -----------------------
# Ready
# -----------------------
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    await bot.tree.sync()
    print("Slash Commands Synced")

# -----------------------
# RUN
# -----------------------
bot.run(DISCORD_BOT_TOKEN)
