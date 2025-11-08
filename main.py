import os
import discord
from discord import app_commands
from discord.ext import commands
from deep_translator import GoogleTranslator
from flask import Flask
from threading import Thread

# ===============================
# Flask（Render用 keep-alive）
# ===============================
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

Thread(target=run_flask).start()

# ===============================
# Discord Bot設定
# ===============================
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="/", intents=intents)

# --- 翻訳関連データ ---
translate_channels = set()  # 翻訳ONのチャンネルID
guild_languages = {}        # {guild_id: ["en", "ja"]}
translated_map = {}         # {original_msg_id: [translated_msg_ids]}

# --- 国旗絵文字 ---
flags = {
    "en": "🇺🇸", "ja": "🇯🇵", "ko": "🇰🇷", "zh": "🇨🇳",
    "fr": "🇫🇷", "de": "🇩🇪", "es": "🇪🇸", "it": "🇮🇹",
    "ru": "🇷🇺", "pt": "🇧🇷", "id": "🇮🇩", "vi": "🇻🇳", "th": "🇹🇭"
}

# ===============================
# /auto コマンド（チャンネルごとの翻訳ON/OFF）
# ===============================
@bot.tree.command(name="auto", description="このチャンネルの自動翻訳をON/OFFします")
async def auto(interaction: discord.Interaction):
    channel_id = interaction.channel.id
    if channel_id in translate_channels:
        translate_channels.remove(channel_id)
        await interaction.response.send_message(f"🚫 このチャンネル（{interaction.channel.mention}）の翻訳をオフにしました。")
    else:
        translate_channels.add(channel_id)
        await interaction.response.send_message(f"✅ このチャンネル（{interaction.channel.mention}）の翻訳をオンにしました。")

# ===============================
# /setlang コマンド（サーバーごとの翻訳対象言語）
# ===============================
@bot.tree.command(name="setlang", description="翻訳先言語を設定（例: /setlang en ja）")
async def setlang(interaction: discord.Interaction, languages: str):
    langs = languages.split()
    guild_languages[interaction.guild.id] = langs
    flags_display = " ".join(flags.get(lang, f"[{lang}]") for lang in langs)
    await interaction.response.send_message(f"🌍 翻訳対象言語を {flags_display} に設定しました。")

# ===============================
# メッセージ受信時の翻訳処理
# ===============================
@bot.event
async def on_message(message):
    # Bot自身の発言は無視
    if message.author.bot:
        return

    # 翻訳OFFチャンネルなら無視
    if message.channel.id not in translate_channels:
        return

    # 翻訳先言語（未設定なら英語・日本語）
    target_langs = guild_languages.get(message.guild.id, ["en", "ja"])
    text = message.content
    translated_ids = []

    for lang in target_langs:
        try:
            translated = GoogleTranslator(source='auto', target=lang).translate(text)
            if translated and translated != text:
                flag = flags.get(lang, f"[{lang}]")
                sent = await message.channel.send(f"{flag} {translated}")
                translated_ids.append(sent.id)
        except Exception as e:
            await message.channel.send(f"⚠️ 翻訳エラー: {e}")

    if translated_ids:
        translated_map[message.id] = translated_ids

    await bot.process_commands(message)

# ===============================
# メッセージ削除時（翻訳も削除）
# ===============================
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

# ===============================
# 起動時
# ===============================
@bot.event
async def on_ready():
    await bot.tree.sync()  # スラッシュコマンドを同期
    print(f"✅ Logged in as {bot.user}")

# ===============================
# 実行
# ===============================
bot.run(os.environ["DISCORD_BOT_TOKEN"])
