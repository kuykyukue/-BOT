import os
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
intents.messages = True
bot = commands.Bot(command_prefix="/", intents=intents)

# --- 各種データ保存 ---
translate_channels = set()  # 翻訳有効チャンネル
guild_languages = {}        # {guild_id: ["en", "ja"]}
translated_map = {}         # {original_msg_id: [translated_msg_ids]}

# --- 国旗絵文字辞書 ---
flags = {
    "en": "🇺🇸", "ja": "🇯🇵", "ko": "🇰🇷", "zh": "🇨🇳",
    "fr": "🇫🇷", "de": "🇩🇪", "es": "🇪🇸", "it": "🇮🇹",
    "ru": "🇷🇺", "pt": "🇧🇷", "id": "🇮🇩", "vi": "🇻🇳", "th": "🇹🇭"
}

# ===============================
# /setchannel コマンド
# ===============================
@bot.command()
async def setchannel(ctx, channel: discord.TextChannel):
    """翻訳を有効にするチャンネルを設定／解除"""
    if channel.id in translate_channels:
        translate_channels.remove(channel.id)
        await ctx.send(f"🚫 {channel.mention} の翻訳をオフにしました。")
    else:
        translate_channels.add(channel.id)
        await ctx.send(f"✅ {channel.mention} の翻訳をオンにしました。")

# ===============================
# /setlang コマンド
# ===============================
@bot.command()
async def setlang(ctx, *, languages: str):
    """翻訳先言語を設定（例: /setlang en ja ko）"""
    langs = languages.split()
    guild_languages[ctx.guild.id] = langs
    flags_display = " ".join(flags.get(lang, f"[{lang}]") for lang in langs)
    await ctx.send(f"🌍 翻訳対象言語を {flags_display} に設定しました。")

# ===============================
# メッセージ受信時
# ===============================
@bot.event
async def on_message(message):
    # Bot自身・指定ユーザー（自分）の発言は翻訳しない
    if message.author.bot:
        return
    if message.author.id == message.guild.owner_id:  # 👈 サーバー管理者自身を除外（必要なら変更可）
        return

    # 翻訳対象チャンネル以外では無視
    if message.channel.id not in translate_channels:
        return

    # 翻訳言語設定を取得（なければ英日）
    target_langs = guild_languages.get(message.guild.id, ["en", "ja"])
    text = message.content

    translated_ids = []
    for lang in target_langs:
        try:
            translated = GoogleTranslator(source='auto', target=lang).translate(text)
            if translated and translated != text:
                flag = flags.get(lang, f"[{lang}]")
                await message.channel.send(f"{flag} {translated}")
                translated_ids.append(sent.id)
        except Exception as e:
            await message.channel.send(f"⚠️ 翻訳エラー: {e}")

    # 削除連動のために記録
    if translated_ids:
        translated_map[message.id] = translated_ids

    await bot.process_commands(message)

# ===============================
# メッセージ削除時（元メッセージ削除で翻訳も削除）
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
# 起動イベント
# ===============================
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")

# ===============================
# 実行
# ===============================
bot.run(os.environ["DISCORD_BOT_TOKEN"])
