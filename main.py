import os
import time
import discord
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
    return "✅ Bot is running!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# Flaskをバックグラウンドで起動
Thread(target=run_flask, daemon=True).start()


# ===============================
# Discord Bot設定
# ===============================
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="/", intents=intents, reconnect=True)

# 翻訳関連データ
translate_channels = set()   # 翻訳ONのチャンネルID
guild_languages = {}         # サーバーごとの翻訳対象言語
translated_map = {}          # {元メッセージID: [翻訳メッセージID]}

# 国旗絵文字マッピング
flags = {
    "en": "🇺🇸", "ja": "🇯🇵", "ko": "🇰🇷", "zh": "🇨🇳",
    "fr": "🇫🇷", "de": "🇩🇪", "es": "🇪🇸", "it": "🇮🇹",
    "ru": "🇷🇺", "pt": "🇧🇷", "id": "🇮🇩", "vi": "🇻🇳", "th": "🇹🇭"
}


# ===============================
# /auto コマンド（チャンネル翻訳ON/OFF）
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
# /setlang コマンド（翻訳先言語設定）
# ===============================
@bot.tree.command(name="setlang", description="翻訳先言語を設定します（例: /setlang en ja）")
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
    if message.author.bot:
        return
    if message.channel.id not in translate_channels:
        return

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
                time.sleep(0.5)  # 429エラー対策
        except Exception as e:
            print(f"⚠️ 翻訳エラー: {e}")
            await message.channel.send(f"⚠️ 翻訳エラーが発生しました（{lang}）")

    if translated_ids:
        translated_map[message.id] = translated_ids

    await bot.process_commands(message)


# ===============================
# メッセージ削除時：翻訳文も削除
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
# 接続状態イベント
# ===============================
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"✅ Logged in as {bot.user} | Bot is online and synced!")

@bot.event
async def on_disconnect():
    print("⚠️ Discordから切断されました。再接続を試みます...")

@bot.event
async def on_resumed():
    print("🔁 接続が復旧しました。")


# ===============================
# 実行
# ===============================
if __name__ == "__main__":
    token = os.environ.get("DISCORD_BOT_TOKEN")
    if not token:
        print("❌ 環境変数 DISCORD_BOT_TOKEN が設定されていません。")
    else:
        bot.run(token)
