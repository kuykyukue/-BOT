import os
import discord
from discord.ext import commands
from flask import Flask
from threading import Thread
from deep_translator import GoogleTranslator

# ===============================
# Discord Bot 基本設定
# ===============================
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True  # メッセージ内容取得許可
bot = commands.Bot(command_prefix="/", intents=intents)

# ===============================
# Flask（Render keep-alive用）
# ===============================
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

Thread(target=run_web).start()

# ===============================
# 自動翻訳設定
# ===============================
auto_translate_channels = set()  # ONになっているチャンネル
target_languages = ["en", "ja", "ko"]  # 翻訳先言語
flags = {"en": "🇺🇸", "ja": "🇯🇵", "ko": "🇰🇷"}  # 国旗マーク

# 翻訳メッセージの対応マップ（削除連動用）
translated_message_map = {}  # {元メッセージID: [翻訳メッセージID, ...]}

# ===============================
# /auto コマンド（翻訳ON/OFF）
# ===============================
@bot.command()
async def auto(ctx):
    """自動翻訳ON/OFF切替"""
    if ctx.channel.id in auto_translate_channels:
        auto_translate_channels.remove(ctx.channel.id)
        await ctx.send("❌ 自動翻訳をオフにしました。")
    else:
        auto_translate_channels.add(ctx.channel.id)
        await ctx.send("✅ 自動翻訳をオンにしました。")

# ===============================
# メッセージ受信時 → 翻訳処理
# ===============================
@bot.event
async def on_message(message):
    if message.author.bot:
        return  # Bot自身や他のBotを無視（重複翻訳防止）

    if message.channel.id in auto_translate_channels:
        text = message.content
        translated_messages = []

        for lang in target_languages:
            try:
                translated = GoogleTranslator(source='auto', target=lang).translate(text)
                if translated and translated != text:
                    flag = flags.get(lang, f"[{lang}]")
                    sent = await message.channel.send(f"{flag} {translated}")
                    translated_messages.append(sent.id)
            except Exception as e:
                await message.channel.send(f"⚠️ 翻訳エラー: {e}")

        # 削除連動用にマッピング
        if translated_messages:
            translated_message_map[message.id] = translated_messages

    await bot.process_commands(message)

# ===============================
# 元メッセージ削除 → 翻訳も削除
# ===============================
@bot.event
async def on_message_delete(message):
    if message.id in translated_message_map:
        for msg_id in translated_message_map[message.id]:
            try:
                msg = await message.channel.fetch_message(msg_id)
                await msg.delete()
            except discord.NotFound:
                pass
        del translated_message_map[message.id]

# ===============================
# 起動処理
# ===============================
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")

# ===============================
# 実行
# ===============================
bot.run(os.environ["DISCORD_BOT_TOKEN"])

