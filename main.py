import discord
from discord import app_commands
from discord.ext import commands
from googletrans import Translator
import json
import os
from flask import Flask
import threading

# ---------- 翻訳設定保存ファイル ----------
CONFIG_FILE = "guild_settings.json"

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_config(data):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# ---------- Discord Bot 設定 ----------
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
translator = Translator()

# ---------- Flask（Render維持用） ----------
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is alive!"

def run():
    app.run(host='0.0.0.0', port=8080)

thread = threading.Thread(target=run)
thread.start()

# ---------- スラッシュコマンド ----------
@bot.event
async def on_ready():
    print(f"✅ ログイン完了: {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"🔧 スラッシュコマンド同期済み: {len(synced)}個")
    except Exception as e:
        print(f"⚠️ コマンド同期エラー: {e}")

# 言語設定コマンド
@bot.tree.command(name="setlang", description="翻訳元と翻訳先の言語を設定します。例: /setlang ja en")
@app_commands.describe(source="翻訳元の言語コード", target="翻訳先の言語コード")
async def setlang(interaction: discord.Interaction, source: str, target: str):
    config = load_config()
    config[str(interaction.guild_id)] = {"source": source, "target": target, "enabled": True}
    save_config(config)
    await interaction.response.send_message(f"✅ 翻訳設定を保存しました: {source} → {target}")

# 翻訳ON/OFF
@bot.tree.command(name="toggletranslate", description="翻訳機能をON/OFFします。")
async def toggletranslate(interaction: discord.Interaction):
    config = load_config()
    gid = str(interaction.guild_id)
    if gid not in config:
        config[gid] = {"source": "ja", "target": "en", "enabled": True}

    config[gid]["enabled"] = not config[gid]["enabled"]
    save_config(config)
    status = "ON" if config[gid]["enabled"] else "OFF"
    await interaction.response.send_message(f"🔘 翻訳機能を {status} にしました。")

# ---------- メッセージ受信 ----------
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    config = load_config()
    gid = str(message.guild.id)
    if gid not in config or not config[gid]["enabled"]:
        return

    src_lang = config[gid]["source"]
    dest_lang = config[gid]["target"]

    try:
        # 言語を自動検出
        detected = translator.detect(message.content).lang

        # 日本語→英語 or 英語→日本語 どちらでも対応
        if detected == src_lang:
            result = translator.translate(message.content, src=src_lang, dest=dest_lang)
        elif detected == dest_lang:
            result = translator.translate(message.content, src=dest_lang, dest=src_lang)
        else:
            # どちらでもない場合はデフォルト方向で翻訳
            result = translator.translate(message.content, src=detected, dest=dest_lang)

        await message.channel.send(f"{message.author.name} ({detected}→{result.dest}): {result.text}")

    except Exception as e:
        print(f"⚠️ 翻訳エラー: {e}")

# ---------- Bot起動 ----------
bot.run(os.getenv("DISCORD_TOKEN"))
