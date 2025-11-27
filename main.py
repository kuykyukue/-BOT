import os
import json
import asyncio
import discord
from discord.ext import commands
from discord import app_commands
from deep_translator import GoogleTranslator
from flask import Flask
import threading

# Flask（Render Keep-Alive）
app = Flask(__name__)
@app.route("/")
def home():
    return "Bot is running!"

# Discord Bot 設定
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.reactions = True
intents.guilds = True

bot = commands.Bot(command_prefix="/", intents=intents, reconnect=True)

# 永続設定
DATA_PATH = "data/settings.json"
os.makedirs("data", exist_ok=True)

if not os.path.exists(DATA_PATH):
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump({}, f, indent=4, ensure_ascii=False)

def load_settings():
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save_settings(data):
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

settings = load_settings()

# 国旗 → 言語コードマップ
flag_to_lang = {
    "🇺🇸": "en",
    "🇯🇵": "ja",
    "🇰🇷": "ko",
    "🇻🇳": "vi",
    "🇪🇸": "es",
    "🇹🇼": "zh-TW",
    "🇨🇳": "zh-CN",
}
flags = {v: k for k, v in flag_to_lang.items()}

# 翻訳メッセージ管理：
# { (元メッセージID, 絵文字) : 翻訳メッセージID }
translated_message_map = {}

# 翻訳ヘルパー（非同期）
async def async_translate(text, target):
    return await asyncio.to_thread(
        GoogleTranslator(source="auto", target=target).translate,
        text
    )

# /auto コマンドなど既存の自動翻訳関連は省略してもいいですが
# ここでは翻訳イベントのみにフォーカスします。

# --- 国旗リアクション追加で翻訳メッセージをEmbedで送信 ---
@bot.event
async def on_raw_reaction_add(payload):
    try:
        if payload.user_id == bot.user.id:
            return

        emoji = str(payload.emoji)
        if emoji not in flag_to_lang:
            return
        lang = flag_to_lang[emoji]

        guild = bot.get_guild(payload.guild_id)
        if guild is None:
            return

        channel = guild.get_channel(payload.channel_id)
        if channel is None:
            return

        message = await channel.fetch_message(payload.message_id)

        if message.author.bot:
            return

        # 翻訳対象テキスト抽出
        parts = []
        if message.content:
            parts.append(message.content)
        for embed in message.embeds:
            if embed.title:
                parts.append(embed.title)
            if embed.description:
                parts.append(embed.description)
            for field in embed.fields:
                if field.name:
                    parts.append(field.name)
                if field.value:
                    parts.append(field.value)
        if not parts:
            return

        original_text = "\n".join(parts)

        translated = await async_translate(original_text, lang)
        if not translated:
            return

        embed = discord.Embed(
            title=f"翻訳結果 ({emoji})",
            description=translated,
            color=0x1abc9c
        )
        embed.set_footer(text=f"元メッセージID: {message.id}")

        sent_msg = await channel.send(embed=embed)

        # 翻訳メッセージ管理に追加
        translated_message_map[(message.id, emoji)] = sent_msg.id
        print(f"翻訳メッセージ送信: 元={message.id}, 絵文字={emoji}, 翻訳メッセージ={sent_msg.id}")

    except Exception as e:
        print("on_raw_reaction_add エラー:", e)


# --- 国旗リアクション削除で対応翻訳メッセージを削除 ---
@bot.event
async def on_raw_reaction_remove(payload):
    try:
        if payload.user_id == bot.user.id:
            return

        emoji = str(payload.emoji)
        if emoji not in flag_to_lang:
            return

        channel = bot.get_channel(payload.channel_id)
        if channel is None:
            return

        key = (payload.message_id, emoji)
        if key not in translated_message_map:
            return

        translated_msg_id = translated_message_map[key]

        try:
            msg = await channel.fetch_message(translated_msg_id)
            await msg.delete()
            print(f"翻訳メッセージ削除: {translated_msg_id}")
        except Exception as e:
            print(f"翻訳メッセージ削除エラー: {e}")

        # 管理辞書から削除
        del translated_message_map[key]

    except Exception as e:
        print("on_raw_reaction_remove エラー:", e)


# --- 必要に応じて他のコマンドや自動翻訳処理もここに追加 ---

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"✅ Logged in as {bot.user}")


# Flask + Discord Bot 同時起動（Render対応）
def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    thread = threading.Thread(target=run_flask)
    thread.start()
    bot.run(os.environ["DISCORD_BOT_TOKEN"])
