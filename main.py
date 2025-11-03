import discord
from discord import app_commands
from discord.ext import commands
from googletrans import Translator
import json
import os
from flask import Flask
from threading import Thread

# ===== 設定ファイル =====
CONFIG_FILE = "guild_settings.json"

# ===== デフォルト設定 =====
def load_settings():
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f)
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_settings(settings):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=4, ensure_ascii=False)

settings = load_settings()

# ===== Discord Bot =====
TOKEN = os.getenv("DISCORD_TOKEN")  # Renderに環境変数で設定しておく
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="/", intents=intents)
translator = Translator()

# ===== スラッシュコマンド =====
@bot.event
async def on_ready():
    print(f"✅ ログイン完了: {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"🔧 スラッシュコマンド同期済み: {len(synced)}個")
    except Exception as e:
        print(f"⚠️ コマンド同期エラー: {e}")

@bot.tree.command(name="setlang", description="翻訳先の言語を設定します（例: ja, en, zh-tw, th, vi）")
@app_commands.describe(code="翻訳先の言語コード")
async def setlang(interaction: discord.Interaction, code: str):
    gid = str(interaction.guild.id)
    if gid not in settings:
        settings[gid] = {"lang": "en", "translate": True}
    settings[gid]["lang"] = code.lower()
    save_settings(settings)
    await interaction.response.send_message(f"🌐 翻訳先を `{code}` に設定しました！")

@bot.tree.command(name="toggletranslate", description="翻訳機能をオン/オフ切替します")
async def toggletranslate(interaction: discord.Interaction):
    gid = str(interaction.guild.id)
    if gid not in settings:
        settings[gid] = {"lang": "en", "translate": True}
    settings[gid]["translate"] = not settings[gid]["translate"]
    save_settings(settings)
    state = "🟢 翻訳ON" if settings[gid]["translate"] else "🔴 翻訳OFF"
    await interaction.response.send_message(f"{state} に変更しました！")

# ===== メッセージ翻訳 =====
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    gid = str(message.guild.id)
    if gid not in settings or not settings[gid].get("translate", True):
        return

    lang = settings[gid].get("lang", "en")

    try:
        # 入力文の言語を自動検出
        detected = translator.detect(message.content).lang
        if detected == lang:
            # 翻訳先と同じならスキップ
            return

        result = translator.translate(message.content, dest=lang)
        text = result.text

        # 絵文字・記号を壊さず返信
        await message.channel.send(f"💬 **{message.author.display_name}** ({detected}→{lang}): {text}")

    except Exception as e:
        print(f"翻訳エラー: {e}")

# ===== Flaskサーバー（Render維持用）=====
app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!"

def run():
    app.run(host='0.0.0.0', port=8080)

# ===== 実行 =====
if __name__ == "__main__":
    Thread(target=run).start()
    bot.run(TOKEN)
