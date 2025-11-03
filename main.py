# ================================
# 🌐 Discord翻訳BOT 完全版 (Render対応)
# ================================
import discord
from discord import app_commands
from discord.ext import commands
from googletrans import Translator
import json
import os
from flask import Flask
from threading import Thread

# ======================
# 🔧 Flask (Render対応)
# ======================
app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!"

def run():
    app.run(host='0.0.0.0', port=8080)

Thread(target=run).start()

# ======================
# ⚙️ Discord Bot設定
# ======================
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

translator = Translator()
SETTINGS_FILE = "settings.json"

# ======================
# 💾 設定の保存・読込
# ======================
def load_settings():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_settings(data):
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

settings = load_settings()

# ======================
# 🚀 起動イベント
# ======================
@bot.event
async def on_ready():
    print(f"✅ ログイン完了: {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"🧩 スラッシュコマンド {len(synced)} 件を同期しました。")
    except Exception as e:
        print(f"⚠️ コマンド同期エラー: {e}")

# ======================
# 🌍 /setlang コマンド
# ======================
@bot.tree.command(name="setlang", description="翻訳先の言語を設定します（例: /setlang ja en）")
@app_commands.describe(source="元の言語コード", target="翻訳先の言語コード")
async def setlang(interaction: discord.Interaction, source: str, target: str):
    guild_id = str(interaction.guild_id)
    settings[guild_id] = settings.get(guild_id, {})
    settings[guild_id]["source"] = source
    settings[guild_id]["target"] = target
    save_settings(settings)
    await interaction.response.send_message(
        f"✅ 翻訳言語を設定しました。\n"
        f"🌐 {source} → {target}"
    )

# ======================
# 🔘 /toggletranslate コマンド
# ======================
@bot.tree.command(name="toggletranslate", description="翻訳機能のON/OFFを切り替えます。")
async def toggletranslate(interaction: discord.Interaction):
    guild_id = str(interaction.guild_id)
    settings[guild_id] = settings.get(guild_id, {})
    current = settings[guild_id].get("enabled", True)
    settings[guild_id]["enabled"] = not current
    save_settings(settings)
    status = "ON 🔊" if not current else "OFF 🔇"
    await interaction.response.send_message(f"翻訳機能を {status} にしました。")

# ======================
# 💬 メッセージ翻訳
# ======================
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    guild_id = str(message.guild.id)
    config = settings.get(guild_id, {})

    # 翻訳がOFFならスキップ
    if not config.get("enabled", True):
        return

    source = config.get("source", "auto")
    target = config.get("target", "en")

    try:
        translated = translator.translate(message.content, src=source, dest=target)
        if translated.text != message.content:
            await message.channel.send(
                f"💬 **{message.author.display_name}** ({source}→{target}):\n{translated.text}"
            )
    except Exception as e:
        print(f"⚠️ 翻訳エラー: {e}")

# ======================
# 🚀 Bot起動
# ======================
TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    print("❌ 環境変数 DISCORD_TOKEN が設定されていません。RenderのEnvironmentに追加してください。")
else:
    bot.run(TOKEN)
