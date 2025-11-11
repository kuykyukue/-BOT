import os
import json
import discord
from discord import app_commands
from discord.ext import commands
from deep_translator import GoogleTranslator
from flask import Flask
from threading import Thread
from dotenv import load_dotenv

# --- 環境変数読み込み (.envから) ---
load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")

# --- Flask サーバー（Renderのスリープ防止用） ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

Thread(target=run_web).start()

# --- Discord Bot 設定 ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="/", intents=intents)
tree = bot.tree

# --- データ保存ファイル ---
SETTINGS_FILE = "data/settings.json"
os.makedirs("data", exist_ok=True)

# --- 国旗マッピング ---
FLAGS = {
    "en": "🇺🇸", "ja": "🇯🇵", "ko": "🇰🇷", "zh": "🇨🇳",
    "fr": "🇫🇷", "de": "🇩🇪", "es": "🇪🇸", "it": "🇮🇹",
    "ru": "🇷🇺", "pt": "🇧🇷", "id": "🇮🇩", "vi": "🇻🇳", "th": "🇹🇭"
}

SUPPORTED_LANGUAGES = list(FLAGS.keys())

# --- 永続データ読み込み ---
def load_settings():
    if not os.path.exists(SETTINGS_FILE):
        return {}
    with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_settings():
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=4)

settings = load_settings()
translated_map = {}  # 元メッセージIDと翻訳メッセージIDの対応表

# --- /auto 翻訳ON/OFF ---
@tree.command(name="auto", description="現在のチャンネルで自動翻訳をオン／オフします")
async def auto(interaction: discord.Interaction):
    guild_id = str(interaction.guild.id)
    channel_id = str(interaction.channel.id)

    if guild_id not in settings:
        settings[guild_id] = {}

    if "channels" not in settings[guild_id]:
        settings[guild_id]["channels"] = {}

    channels = settings[guild_id]["channels"]

    if channel_id in channels:
        del channels[channel_id]
        await interaction.response.send_message("❌ このチャンネルの自動翻訳をオフにしました。")
    else:
        channels[channel_id] = {"langs": ["en", "ja"]}
        await interaction.response.send_message("✅ このチャンネルの自動翻訳をオンにしました。")

    save_settings()

# --- /setlang 翻訳言語設定 ---
@tree.command(name="setlang", description="翻訳先言語を設定します（複数選択可）")
@app_commands.describe(languages="翻訳先言語を選択してください")
@app_commands.choices(
    languages=[
        app_commands.Choice(name=f"{FLAGS[l]} {l}", value=l)
        for l in SUPPORTED_LANGUAGES
    ]
)
async def setlang(interaction: discord.Interaction, languages: app_commands.Choice[str]):
    guild_id = str(interaction.guild.id)
    channel_id = str(interaction.channel.id)

    if guild_id not in settings:
        settings[guild_id] = {"channels": {}}

    if channel_id not in settings[guild_id]["channels"]:
        settings[guild_id]["channels"][channel_id] = {"langs": []}

    # 翻訳対象言語を更新
    selected_lang = languages.value
    current_langs = settings[guild_id]["channels"][channel_id]["langs"]

    if selected_lang in current_langs:
        current_langs.remove(selected_lang)
        msg = f"🗑️ {FLAGS[selected_lang]} を削除しました。"
    else:
        current_langs.append(selected_lang)
        msg = f"✅ {FLAGS[selected_lang]} を追加しました。"

    save_settings()
    flags_display = " ".join(FLAGS.get(l, f"[{l}]") for l in current_langs)
    await interaction.response.send_message(f"{msg}\n📘 現在の設定: {flags_display or 'なし'}")

# --- /help コマンド ---
@tree.command(name="help", description="Botの使い方を表示します")
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(title="🌐 翻訳Bot ヘルプ", color=0x1abc9c)
    embed.add_field(name="/auto", value="このチャンネルの自動翻訳をON/OFFします。", inline=False)
    embed.add_field(name="/setlang", value="翻訳先言語を国旗リストから選択できます。複数可。", inline=False)
    embed.add_field(name="🗑️ メッセージ削除連動", value="元のメッセージを削除すると翻訳メッセージも削除されます。", inline=False)
    await interaction.response.send_message(embed=embed)

# --- 翻訳処理 ---
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    guild_id = str(message.guild.id)
    channel_id = str(message.channel.id)

    if guild_id not in settings or channel_id not in settings[guild_id].get("channels", {}):
        return  # 自動翻訳が有効でないチャンネル

    langs = settings[guild_id]["channels"][channel_id].get("langs", [])
    if not langs:
        return

    # 自分の発言は翻訳しない
    if message.author == bot.user:
        return

    translated_messages = []
    for lang in langs:
        try:
            translated = GoogleTranslator(source="auto", target=lang).translate(message.content)
            if translated and translated != message.content:
                flag = FLAGS.get(lang, f"[{lang}]")
                reply = await message.channel.send(f"{flag} {translated}")
                translated_messages.append(reply.id)
        except Exception as e:
            print(f"翻訳エラー: {e}")

    if translated_messages:
        translated_map[message.id] = translated_messages

# --- 元メッセージ削除時に翻訳メッセージも削除 ---
@bot.event
async def on_message_delete(message):
    if message.id in translated_map:
        for msg_id in translated_map[message.id]:
            try:
                msg = await message.channel.fetch_message(msg_id)
                await msg.delete()
            except:
                pass
        del translated_map[message.id]

# --- 起動 ---
@bot.event
async def on_ready():
    await tree.sync()
    print(f"✅ Logged in as {bot.user}")
    print("🌍 Ready and running on Render!")

if __name__ == "__main__":
    bot.run(TOKEN)
