import os
import asyncio
import discord
from discord.ext import commands
from discord import app_commands
from flask import Flask
from threading import Thread
from googletrans_new import google_translator

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
translator = google_translator()

# -----------------------
# チャンネルごとの設定
# -----------------------
# 設定内容：
#   auto_translate: 自動翻訳 有効/無効
#   auto_lang: 自動翻訳先言語
#   forward_copy: 引用/転送メッセージも翻訳
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
# ユーティリティ：翻訳
# -----------------------
async def translate_text(text: str, src="auto", dest="en"):
    try:
        result = translator.translate(text, lang_src=src, lang_tgt=dest)
        return result
    except Exception as e:
        print("Translation error:", e)
        return None

# -----------------------
# /set_auto コマンド（自動翻訳設定）
# -----------------------
@bot.tree.command(name="set_auto", description="このチャンネルの自動翻訳を設定します")
@app_commands.describe(
    enable="True = 自動翻訳をオン / False = オフ",
    lang="翻訳言語（例：ja, en, zh-cn, ko, fr など）"
)
async def set_auto(interaction: discord.Interaction, enable: bool, lang: str):
    ch = get_ch_settings(interaction.channel_id)
    ch["auto_translate"] = enable
    ch["auto_lang"] = lang

    status = "オン" if enable else "オフ"
    await interaction.response.send_message(
        f"✅ 自動翻訳を **{status}** に設定しました\n翻訳先： **{lang}**"
    )

# -----------------------
# /set_forward コマンド（引用/転送翻訳 ON/OFF）
# -----------------------
@bot.tree.command(name="set_forward", description="引用/転送メッセージの翻訳 ON/OFF")
async def set_forward(interaction: discord.Interaction, enable: bool):
    ch = get_ch_settings(interaction.channel_id)
    ch["forward_copy"] = enable

    await interaction.response.send_message(
        f"🔁 引用/転送翻訳を **{'ON' if enable else 'OFF'}** にしました"
    )

# -----------------------
# 通常メッセージ受信 → 自動翻訳（任意）
# -----------------------
@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    ch = get_ch_settings(message.channel.id)

    # --- 1. 強制翻訳 !ja, !en, !zh-cn など ---
    if message.content.startswith("!"):
        parts = message.content.split(" ", 1)
        if len(parts) == 2:
            cmd = parts[0][1:]
            txt = parts[1]

            translated = await translate_text(txt, dest=cmd)
            if translated:
                await message.channel.send(f"**[{cmd}]** {translated}")
        return

    # --- 2. システム自動翻訳 ---
    if ch["auto_translate"]:
        translated = await translate_text(message.content, dest=ch["auto_lang"])
        if translated:
            await message.channel.send(f"🌐 **Auto:** {translated}")

    await bot.process_commands(message)

# -----------------------
# リアクション翻訳の管理
# -----------------------
# 保存形式：
# reaction_map[original_message_id][emoji] = translated_message_id
reaction_map = {}

emoji_lang = {
    "🇯🇵": "ja",
    "🇺🇸": "en",
    "🇨🇳": "zh-cn",
    "🇹🇼": "zh-tw",
    "🇰🇷": "ko",
    "🇫🇷": "fr",
}

# -----------------------
# リアクション追加 → 翻訳メッセージ生成
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

    # すでに翻訳済み
    if message.id in reaction_map and emoji in reaction_map[message.id]:
        return

    # 翻訳本文
    content = message.content
    if not content:
        return

    translated = await translate_text(content, dest=lang)
    if not translated:
        return

    # --- 引用メッセージにも対応 ---
    ref_txt = ""
    if message.reference and message.reference.resolved:
        ref_msg = message.reference.resolved
        ref_txt = f"\n> **引用:** {ref_msg.content}"

    sent = await message.channel.send(f"🔁 **{emoji} 翻訳**:\n{translated}{ref_txt}")

    # 保存
    if message.id not in reaction_map:
        reaction_map[message.id] = {}
    reaction_map[message.id][emoji] = sent.id

# -----------------------
# リアクション削除 → 翻訳メッセージも削除
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
    if len(reaction_map[message.id]) == 0:
        del reaction_map[message.id]

# -----------------------
# Bot Ready
# -----------------------
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"Slash commands synced: {len(synced)}")
    except Exception as e:
        print("Sync error:", e)

# -----------------------
# RUN
# -----------------------
bot.run(DISCORD_BOT_TOKEN)
