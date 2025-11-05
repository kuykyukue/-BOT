import discord
from discord.ext import commands
from flask import Flask
from threading import Thread
from deep_translator import GoogleTranslator
import os

# ---- Discord Bot基本設定 ----
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)  # prefixは使わないけど必要

# ---- Flask (Render用 keep-alive) ----
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

def run_web():
    app.run(host="0.0.0.0", port=8080)

Thread(target=run_web).start()

# ===============================
# 自動翻訳 ON/OFF & 多言語設定
# ===============================
auto_translate_channels = set()
target_languages = ["en", "ja", "ko"]
flags = {"en": "🇺🇸", "ja": "🇯🇵", "ko": "🇰🇷"}

translated_message_map = {}

# ===============================
# スラッシュコマンド登録
# ===============================
@bot.tree.command(name="auto", description="自動翻訳のON/OFFを切り替えます")
async def auto(interaction: discord.Interaction):
    channel_id = interaction.channel_id
    if channel_id in auto_translate_channels:
        auto_translate_channels.remove(channel_id)
        await interaction.response.send_message("❌ 自動翻訳をオフにしました。")
    else:
        auto_translate_channels.add(channel_id)
        await interaction.response.send_message("✅ 自動翻訳をオンにしました。")

# ===============================
# メッセージ監視 → 翻訳
# ===============================
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if message.channel.id in auto_translate_channels:
        text = message.content
        translated_messages = []
        for lang in target_languages:
            try:
                translated = GoogleTranslator(source='auto', target=lang).translate(text)
                sent_msg = await message.channel.send(f"{flags[lang]} {translated}")
                translated_messages.append(sent_msg.id)
            except Exception as e:
                await message.channel.send(f"翻訳エラー: {e}")

        translated_message_map[message.id] = translated_messages

    await bot.process_commands(message)

# ===============================
# メッセージ削除連動
# ===============================
@bot.event
async def on_message_delete(message):
    if message.id in translated_message_map:
        for msg_id in translated_message_map[message.id]:
            try:
                msg = await message.channel.fetch_message(msg_id)
                await msg.delete()
            except:
                pass
        del translated_message_map[message.id]

# ===============================
# 起動イベント
# ===============================
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    try:
        synced = await bot.tree.sync()  # ← スラッシュコマンド登録
        print(f"🟢 Synced {len(synced)} commands")
    except Exception as e:
        print(f"❌ Command sync failed: {e}")

# ---- Bot起動 ----
bot.run(os.environ["DISCORD_TOKEN"])
