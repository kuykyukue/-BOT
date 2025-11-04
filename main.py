import discord
from discord.ext import commands
from flask import Flask
from threading import Thread
from deep_translator import GoogleTranslator
import os

intents = discord.Intents.default()
intents.messages = True
bot = commands.Bot(command_prefix="/", intents=intents)

# ---- Flask (Render用 keep-alive) ----
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

def run_web():
    app.run(host="0.0.0.0", port=8080)

Thread(target=run_web).start()

# ---- 翻訳ON/OFF管理 ----
auto_translate_channels = set()

@bot.command()
async def auto(ctx):
    """自動翻訳ON/OFF切り替え"""
    if ctx.channel.id in auto_translate_channels:
        auto_translate_channels.remove(ctx.channel.id)
        await ctx.send("❌ 自動翻訳をオフにしました。")
    else:
        auto_translate_channels.add(ctx.channel.id)
        await ctx.send("✅ 自動翻訳をオンにしました。")

@bot.event
async def on_message(message):
    if message.author.bot:
        return  # ← これが重複翻訳防止の最重要ポイント！

    if message.channel.id in auto_translate_channels:
        text = message.content
        try:
            translated = GoogleTranslator(source='auto', target='en').translate(text)
            flag = "🇺🇸"
            await message.channel.send(f"{flag} {translated}")
        except Exception as e:
            await message.channel.send(f"翻訳エラー: {e}")

    await bot.process_commands(message)

# ---- Bot起動 ----
bot.run(os.environ["DISCORD_TOKEN"])
