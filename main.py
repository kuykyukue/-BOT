import discord
from discord.ext import commands
from googletrans import Translator
import os

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="/", intents=intents)

translator = Translator()

# デフォルト言語設定
source_lang = "ja"
target_lang = "en"
translation_enabled = True

@bot.event
async def on_ready():
    print(f"✅ ログイン完了: {bot.user}")
    print("翻訳BOTが起動しました！")

@bot.command()
async def setlang(ctx, source, target):
    """翻訳元と翻訳先を設定します。例: /setlang ja en"""
    global source_lang, target_lang
    source_lang = source.lower()
    target_lang = target.lower()
    await ctx.send(f"🌐 翻訳設定を保存しました: {source_lang} → {target_lang}")

@bot.command()
async def toggletranslate(ctx):
    """翻訳のON/OFFを切り替えます"""
    global translation_enabled
    translation_enabled = not translation_enabled
    state = "ON" if translation_enabled else "OFF"
    await ctx.send(f"🔁 翻訳機能を {state} にしました。")

@bot.event
async def on_message(message):
    global source_lang, target_lang, translation_enabled

    if message.author.bot:
        return  # BOT自身のメッセージは無視

    await bot.process_commands(message)  # コマンド処理

    if translation_enabled:
        text = message.content.strip()
        if not text:
            return

        try:
            # 言語自動判定
            detected = translator.detect(text).lang

            # ja→en / en→ja の双方向判定
            if detected == "ja" and target_lang == "en":
                translated = translator.translate(text, src="ja", dest="en").text
                await message.channel.send(f"{message.author.name} 🇯🇵→🇺🇸: {translated}")

            elif detected == "en" and target_lang == "ja":
                translated = translator.translate(text, src="en", dest="ja").text
                await message.channel.send(f"{message.author.name} 🇺🇸→🇯🇵: {translated}")

        except Exception as e:
            print("翻訳エラー:", e)

# Render用（Webサーバープロセス防止）
from flask import Flask
from threading import Thread

app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!"

def run():
    app.run(host='0.0.0.0', port=8080)

Thread(target=run).start()

# Discordトークン
bot.run(os.getenv("DISCORD_TOKEN"))
