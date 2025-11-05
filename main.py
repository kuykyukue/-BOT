import discord
from discord.ext import commands
from discord import app_commands
from flask import Flask
from threading import Thread
from deep_translator import GoogleTranslator
import os

# ---- Discord Bot基本設定 ----
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.guilds = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ---- Flask (Render keep-alive用) ----
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

def run_web():
    app.run(host="0.0.0.0", port=8080)

Thread(target=run_web).start()

# ===============================
# 状態管理
# ===============================
auto_translate_channels = set()  # 自動翻訳ONのチャンネルID
channel_target_languages = {}    # チャンネルごとの翻訳先リスト
translated_message_map = {}      # 削除連動 {元メッセージID: [翻訳済メッセージID,...]}

# デフォルト翻訳言語
default_languages = ["en", "ja", "ko"]
flags = {"en": "🇺🇸", "ja": "🇯🇵", "ko": "🇰🇷", "zh-CN": "🇨🇳", "fr": "🇫🇷", "es": "🇪🇸"}

# ===============================
# /auto コマンド（ON/OFF）
# ===============================
@bot.tree.command(name="auto", description="自動翻訳をオン/オフ切り替えます")
async def auto(interaction: discord.Interaction):
    channel_id = interaction.channel_id
    if channel_id in auto_translate_channels:
        auto_translate_channels.remove(channel_id)
        await interaction.response.send_message("❌ 自動翻訳をオフにしました。", ephemeral=True)
    else:
        auto_translate_channels.add(channel_id)
        # デフォルト言語を設定
        channel_target_languages[channel_id] = default_languages.copy()
        await interaction.response.send_message("✅ 自動翻訳をオンにしました。", ephemeral=True)

# ===============================
# /setlang コマンド（翻訳言語設定）
# ===============================
@bot.tree.command(name="setlang", description="翻訳先の言語を設定します")
@app_commands.describe(
    lang1="翻訳先言語1",
    lang2="翻訳先言語2（任意）",
    lang3="翻訳先言語3（任意）"
)
async def setlang(interaction: discord.Interaction, lang1: str, lang2: str = None, lang3: str = None):
    valid_langs = list(flags.keys())
    selected = [lang for lang in [lang1, lang2, lang3] if lang]
    
    # 言語バリデーション
    for lang in selected:
        if lang not in valid_langs:
            await interaction.response.send_message(
                f"⚠️ `{lang}` は無効な言語コードです。\n利用可能: {', '.join(valid_langs)}",
                ephemeral=True
            )
            return
    
    # 設定を保存
    channel_target_languages[interaction.channel_id] = selected
    langs_str = " ".join(flags[lang] for lang in selected)
    await interaction.response.send_message(f"🌐 翻訳言語を設定しました: {langs_str}", ephemeral=True)

# ===============================
# メッセージ受信 → 翻訳処理
# ===============================
@bot.event
async def on_message(message):
    # Botや自分自身の発言は無視
    if message.author.bot or message.author == bot.user:
        return

    if message.channel.id in auto_translate_channels:
        # 自分の発言は翻訳しない
        app_info = await bot.application_info()
        if message.author.id == app_info.owner.id:
            return

        text = message.content
        target_langs = channel_target_languages.get(message.channel.id, default_languages)
        translated_msgs = []

        for lang in target_langs:
            try:
                translated = GoogleTranslator(source='auto', target=lang).translate(text)
                flag = flags.get(lang, "🌐")
                sent_msg = await message.channel.send(f"{flag} {translated}")
                translated_msgs.append(sent_msg.id)
            except Exception as e:
                await message.channel.send(f"⚠️ 翻訳エラー: {e}")

        # 削除連動に記録
        translated_message_map[message.id] = translated_msgs

    await bot.process_commands(message)

# ===============================
# メッセージ削除 → 翻訳メッセージも削除
# ===============================
@bot.event
async def on_message_delete(message):
    if message.id in translated_message_map:
        for msg_id in translated_message_map[message.id]:
            try:
                msg = await message.channel.fetch_message(msg_id)
                await msg.delete()
            except:
                pass
        del translated_message_map[message.id]

# ===============================
# 起動処理
# ===============================
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"🟢 Synced {len(synced)} slash commands")
    except Exception as e:
        print(f"❌ Command sync failed: {e}")

# ===============================
# Bot起動
# ===============================
bot.run(os.environ["DISCORD_BOT_TOKEN"])

