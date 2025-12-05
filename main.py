import os
import logging
from dotenv import load_dotenv

import discord
from discord.ext import commands
from deep_translator import GoogleTranslator

# ----------------------------
#    設定読み込み & ログ設定
# ----------------------------
load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("translate-bot")

TOKEN = os.getenv("DISCORD_BOT_TOKEN")  # ← 固定！

if not TOKEN:
    raise ValueError("環境変数 DISCORD_BOT_TOKEN が設定されていません。")


# ----------------------------
#    Discord Intents
# ----------------------------
intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True
intents.messages = True

bot = commands.Bot(command_prefix="!", intents=intents)


# ----------------------------
#   Embed / 本文 抽出関数
# ----------------------------
async def extract_text_from_message(message):
    """
    Discord 仕様変更対策版：
    fetch_message で再取得し、Embed の内容まで可能な限り抽出する
    """

    try:
        channel = message.channel
        message = await channel.fetch_message(message.id)
    except Exception:
        pass

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

        if embed.author and embed.author.name:
            parts.append(embed.author.name)

        if embed.footer and embed.footer.text:
            parts.append(embed.footer.text)

    joined = "\n".join(parts).strip()
    return joined if joined else None


# ----------------------------
#           翻訳
# ----------------------------
def translate_text(text, target_lang):
    try:
        return GoogleTranslator(source="auto", target=target_lang).translate(text)
    except Exception as e:
        return f"翻訳エラー: {e}"


# ----------------------------
#   国旗リアクション → 翻訳
# ----------------------------
FLAG_TO_LANG = {
    "🇯🇵": "ja",
    "🇺🇸": "en",
    "🇬🇧": "en",
}


@bot.event
async def on_raw_reaction_add(payload):
    if payload.user_id == bot.user.id:
        return

    emoji = str(payload.emoji)

    if emoji not in FLAG_TO_LANG:
        return

    guild = bot.get_guild(payload.guild_id)
    channel = guild.get_channel(payload.channel_id)
    message = await channel.fetch_message(payload.message_id)

    text = await extract_text_from_message(message)

    if not text:
        await channel.send(
            embed=discord.Embed(
                title=f"{emoji} 翻訳（{FLAG_TO_LANG[emoji]}）",
                description="（翻訳する内容がありません）",
                color=0x3498db,
            )
        )
        return

    target_lang = FLAG_TO_LANG[emoji]
    translated = translate_text(text, target_lang)

    embed = discord.Embed(
        title=f"{emoji} 翻訳（{target_lang}）",
        description=translated,
        color=0x3498db,
    )
    await channel.send(embed=embed)


# ----------------------------
#          起動
# ----------------------------
@bot.event
async def on_ready():
    logger.info("Bot が online になりました！")


bot.run(TOKEN)
