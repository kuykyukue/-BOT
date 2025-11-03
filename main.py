import discord
from discord.ext import commands
from googletrans import Translator
import os

# ---- 基本設定 ----
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="/", intents=intents)

translator = Translator()

# デフォルト設定
source_lang = "ja"
target_lang = "en"
translation_enabled = True


# ---- 起動メッセージ ----
@bot.event
async def on_ready():
    print(f"✅ ログイン完了: {bot.user}")
    print("翻訳BOTが起動しました！")


# ---- 言語設定コマンド ----
@bot.command()
async def setlang(ctx, source: str = "ja", target: str = "en"):
    """翻訳元と翻訳先を設定します。例: /setlang ja en"""
    global source_lang, target_lang
    source_lang = source.lower()
    target_lang = target.lower()
    await ctx.send(f"🌐 翻訳設定を保存しました: {source_lang} → {target_lang}")


# ---- 翻訳ON/OFF切替 ----
@bot.command()
async def toggletranslate(ctx):
    """翻訳のON/OFFを切り替えます"""
    global translation_enabled
    translation_enabled = not translation_enabled
    state = "ON" if translation_enabled else "OFF"
    await ctx.send(f"🔁 翻訳機能を {state} にしました。")


# ---- メッセージ監視 ----
@bot.event
async def on_message(message):
    global source_lang, target_lang, translation_enabled

    if message.author.bot:
        return  # BOT自身のメッセージは無視

    await bot.process_commands(message)  # コマンド処理も忘れずに

    if not translation_enabled:
        return

    text = message.content.strip()
    if not text:
        return

    try:
        # 言語を自動判定
        detected = translator.detect(text).lang

        # 🔄 自動判定で翻訳方向を決定
        if detected == source_lang and target_lang != source_lang:
            translated = translator.translate(text, src=source_lang, dest=target_lang).text
            await message.channel.send(f"{message.author.name} 🌏 {source_lang}→{target_lang}: {translated}")

        elif detected == target_lang and source_lang != target_lang:
            translated = translator.translate(text, src=target_lang, dest=source_lang).text
            await message.channel.send(f"{message.author.name} 🌏 {target_lang}→{source_lang}: {translated}")

    except Exception as e:
        print("翻訳エラー:", e)


# ---- Render動作用 (Flaskサーバー) ----
from flask import Flask
from threading import Thread

app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!"

def run():
    app.run(host='0.0.0.0', port=8080)

Thread(target=run).start()


# ---- Discordトークン ----
bot.run(os.getenv("DISCORD_TOKEN"))
