# refactor_translate_bot.py
import os
import json
import asyncio
import logging
from threading import Thread
from typing import Optional, List

import discord
from discord.ext import commands, tasks
from discord import app_commands
from deep_translator import GoogleTranslator
from flask import Flask
import aiohttp

# -----------------------
# Basic logging
# -----------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("translate-bot")

# -----------------------
# Flask KeepAlive
# -----------------------
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is alive!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

Thread(target=run_flask, daemon=True).start()

# -----------------------
# Config files
# -----------------------
GUILD_SETTINGS_FILE = "settings.json"

# settings structure: {guild_id: {"auto": False, "langs": ["en","ja"]}}
guild_settings = {}

# translated_messages: {original_message_id (int): [translated_message_id (int), ...], ...}
translated_messages = {}

# -----------------------
# Flags (language -> emoji)
# -----------------------
flags = {
    "en": "🇺🇸", "ja": "🇯🇵", "ko": "🇰🇷", "zh": "🇨🇳",
    "fr": "🇫🇷", "de": "🇩🇪", "es": "🇪🇸", "it": "🇮🇹",
    "ru": "🇷🇺", "pt": "🇧🇷", "id": "🇮🇩", "vi": "🇻🇳",
    "th": "🇹🇭"
}

# -----------------------
# Helper: load/save settings
# -----------------------
def load_settings():
    global guild_settings
    try:
        if not os.path.exists(GUILD_SETTINGS_FILE):
            with open(GUILD_SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump({}, f, ensure_ascii=False, indent=4)
        with open(GUILD_SETTINGS_FILE, "r", encoding="utf-8") as f:
            guild_settings = json.load(f)
        logger.info("Settings loaded.")
    except Exception as e:
        logger.exception("Failed to load settings: %s", e)
        guild_settings = {}

def save_settings():
    try:
        with open(GUILD_SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(guild_settings, f, ensure_ascii=False, indent=4)
        logger.info("Settings saved.")
    except Exception as e:
        logger.exception("Failed to save settings: %s", e)

load_settings()

# -----------------------
# Bot setup: intents + partials
# -----------------------
intents = discord.Intents.default()
intents.message_content = True
intents.messages = True
intents.reactions = True
intents.guilds = True
intents.members = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents,
    heartbeat_timeout=60,
    # Partials required for raw reaction events and messages that may be uncached
    partials=[discord.PartialMessage, discord.PartialReaction, discord.PartialUser, discord.PartialChannel]
)

# -----------------------
# Utilities
# -----------------------
def _emoji_to_lang(emoji_str: str, payload_emoji: Optional[discord.PartialEmoji] = None) -> Optional[str]:
    """
    Try multiple strategies to map an emoji to a language code in `flags`.
    - direct unicode match
    - emoji name (payload_emoji.name) if available
    - regional indicator fallback (e.g., :flag_jp: -> 'ja')
    """
    # direct unicode match
    for lang, flag in flags.items():
        if emoji_str == flag:
            return lang

    # if we have a PartialEmoji or name, check for known patterns
    if payload_emoji is not None:
        # some clients give 'jp' or 'flag_jp' style names for custom/converted emojis
        name = getattr(payload_emoji, "name", "") or ""
        name_lower = name.lower()
        # exactly language code
        if name_lower in flags:
            return name_lower
        # patterns like 'flag_jp' or 'regional_indicator_jp'
        for lang in flags.keys():
            if lang in name_lower:
                return lang

    # fallback: try to parse regional indicators from unicode (rare)
    # e.g. 🇯🇵 is two regional indicator symbols; not always necessary but keep a fallback
    try:
        # map known emoji to lang if possible (redundant with dict above, but safe)
        for lang, flag in flags.items():
            if flag in emoji_str:
                return lang
    except Exception:
        pass

    return None

def extract_text(message: discord.Message) -> str:
    """
    Extract as much textual content as possible from a message, including:
    - message.content
    - embeds: title, description, fields, author.name, footer.text, image.url, thumbnail.url
    - attachments: filenames or URLs
    """
    parts: List[str] = []

    # message content
    try:
        if getattr(message, "content", None):
            parts.append(message.content)
    except Exception:
        pass

    # embeds
    try:
        for embed in message.embeds:
            if not embed:
                continue
            if getattr(embed, "title", None):
                parts.append(embed.title)
            if getattr(embed, "description", None):
                parts.append(embed.description)

            # fields
            try:
                for field in getattr(embed, "fields", []) or []:
                    if getattr(field, "name", None):
                        parts.append(field.name)
                    if getattr(field, "value", None):
                        parts.append(field.value)
            except Exception:
                pass

            # author
            try:
                if getattr(embed, "author", None) and getattr(embed.author, "name", None):
                    parts.append(embed.author.name)
            except Exception:
                pass

            # footer
            try:
                if getattr(embed, "footer", None) and getattr(embed.footer, "text", None):
                    parts.append(embed.footer.text)
            except Exception:
                pass

            # images / thumbnails (include URLs in case text is only in image alt or link)
            try:
                if getattr(embed, "image", None) and getattr(embed.image, "url", None):
                    parts.append(embed.image.url)
            except Exception:
                pass
            try:
                if getattr(embed, "thumbnail", None) and getattr(embed.thumbnail, "url", None):
                    parts.append(embed.thumbnail.url)
            except Exception:
                pass
    except Exception:
        logger.exception("Error while extracting embeds")

    # attachments
    try:
        for att in getattr(message, "attachments", []) or []:
            if getattr(att, "url", None):
                parts.append(att.url)
            elif getattr(att, "filename", None):
                parts.append(att.filename)
    except Exception:
        pass

    text = "\n".join([p for p in parts if p]).strip()
    return text

# -----------------------
# Translation (non-blocking wrapper for deep_translator)
# -----------------------
async def translate_message(text: str, target_lang: str, timeout: float = 15.0) -> str:
    """
    Translate using deep_translator.GoogleTranslator but run in a thread to avoid blocking the event loop.
    Returns the translated text or a helpful error string.
    """
    if not text or not text.strip():
        return "[翻訳エラー: 翻訳対象のテキストが見つかりませんでした]"

    async def _translate_blocking():
        # This function runs in a thread
        try:
            translator = GoogleTranslator(source="auto", target=target_lang)
            return translator.translate(text)
        except Exception as e:
            # propagate as string so outer code can format a message
            return f"[翻訳エラー: {e}]"

    try:
        translated = await asyncio.wait_for(asyncio.to_thread(_translate_blocking), timeout=timeout)
        return translated
    except asyncio.TimeoutError:
        logger.exception("Translation timed out for lang=%s", target_lang)
        return "[翻訳エラー: 翻訳がタイムアウトしました]"
    except Exception as e:
        logger.exception("Unexpected translation error: %s", e)
        return f"[翻訳エラー: {e}]"

# -----------------------
# Slash commands
# -----------------------
@bot.tree.command(name="auto", description="サーバーの自動翻訳を ON/OFF します")
async def auto(interaction: discord.Interaction):
    guild_id = str(interaction.guild_id)
    guild_settings.setdefault(guild_id, {"auto": False, "langs": ["en", "ja"]})
    guild_settings[guild_id]["auto"] = not guild_settings[guild_id]["auto"]
    save_settings()
    status = "ON" if guild_settings[guild_id]["auto"] else "OFF"
    await interaction.response.send_message(f"自動翻訳を **{status}** にしました。")

@bot.tree.command(name="setlang", description="翻訳対象言語を設定（例: /setlang en ja）")
@app_commands.describe(langs="スペース区切りの言語コード (例: en ja)")
async def setlang(interaction: discord.Interaction, langs: str):
    guild_id = str(interaction.guild_id)
    lang_list = langs.split()
    if not lang_list:
        await interaction.response.send_message("言語を指定してください。例: `/setlang en ja`")
        return
    guild_settings.setdefault(guild_id, {})
    guild_settings[guild_id]["langs"] = lang_list
    save_settings()
    flags_display = " ".join(flags.get(lang, lang) for lang in lang_list)
    await interaction.response.send_message(f"翻訳対象言語を {flags_display} に設定しました。")

# -----------------------
# Reaction add/remove handling (raw events)
# -----------------------
@bot.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    # ignore bot's own reactions
    if payload.user_id == bot.user.id:
        return

    # map emoji -> language
    emoji_str = str(payload.emoji)
    lang = _emoji_to_lang(emoji_str, payload_emoji=payload.emoji)

    if not lang:
        # not a configured language reaction
        return

    # fetch channel (robust)
    channel = bot.get_channel(payload.channel_id)
    if channel is None:
        try:
            channel = await bot.fetch_channel(payload.channel_id)
        except Exception:
            logger.exception("Failed to fetch channel %s", payload.channel_id)
            return

    # fetch message
    try:
        message = await channel.fetch_message(payload.message_id)
    except Exception:
        # sometimes message might be partial; try to get via bot.http if needed (fetch_message above is best)
        logger.exception("Failed to fetch message %s in channel %s", payload.message_id, channel)
        return

    # extract text and translate
    text = extract_text(message)
    logger.info("Reaction add: guild=%s user=%s lang=%s message_id=%s text_len=%s",
                payload.guild_id, payload.user_id, lang, message.id, len(text))
    translated = await translate_message(text, lang)

    # Build embed
    emoji_display = flags.get(lang, emoji_str)
    embed = discord.Embed(
        title=f"{emoji_display} 翻訳 ({lang})",
        description=translated,
        color=0x00BFFF
    )
    try:
        sent = await channel.send(embed=embed)
    except Exception:
        logger.exception("Failed to send translation message")
        return

    # record translated message IDs
    translated_messages.setdefault(message.id, []).append(sent.id)

@bot.event
async def on_raw_reaction_remove(payload: discord.RawReactionActionEvent):
    emoji_str = str(payload.emoji)
    if emoji_str not in flags.values() and _emoji_to_lang(emoji_str, payload_emoji=payload.emoji) is None:
        return

    channel = bot.get_channel(payload.channel_id)
    if channel is None:
        try:
            channel = await bot.fetch_channel(payload.channel_id)
        except Exception:
            return

    if payload.message_id not in translated_messages:
        return

    for msg_id in translated_messages.get(payload.message_id, []):
        try:
            msg = await channel.fetch_message(msg_id)
            await msg.delete()
        except Exception:
            pass

    translated_messages.pop(payload.message_id, None)

# -----------------------
# Auto translate on message (when enabled)
# -----------------------
@bot.event
async def on_message(message: discord.Message):
    # avoid reacting to bots
    if message.author and message.author.bot:
        await bot.process_commands(message)
        return

    # guild check
    if not message.guild:
        await bot.process_commands(message)
        return

    guild_id = str(message.guild.id)
    if guild_id not in guild_settings:
        await bot.process_commands(message)
        return

    if not guild_settings[guild_id].get("auto", False):
        await bot.process_commands(message)
        return

    langs = guild_settings[guild_id].get("langs", ["en", "ja"])
    text = extract_text(message)
    logger.info("Auto translate: guild=%s message_id=%s text_len=%s langs=%s",
                guild_id, message.id, len(text), langs)

    for lang in langs:
        translated = await translate_message(text, lang)
        emoji_display = flags.get(lang, lang)
        embed = discord.Embed(
            title=f"{emoji_display} 翻訳 ({lang})",
            description=translated,
            color=0x00BFFF
        )
        try:
            sent = await message.channel.send(embed=embed)
            translated_messages.setdefault(message.id, []).append(sent.id)
        except Exception:
            logger.exception("Failed to send auto-translation for message %s", message.id)

    # ensure commands still processed
    await bot.process_commands(message)

# -----------------------
# When original message deleted -> delete translations
# -----------------------
@bot.event
async def on_message_delete(message: discord.Message):
    if message.id not in translated_messages:
        return
    channel = message.channel
    for msg_id in translated_messages.get(message.id, []):
        try:
            msg = await channel.fetch_message(msg_id)
            await msg.delete()
        except Exception:
            pass
    translated_messages.pop(message.id, None)

# -----------------------
# Keepalive ping (to Render or uptime monitors)
# -----------------------
@tasks.loop(seconds=60)
async def keepalive_ping():
    url = os.environ.get("KEEPALIVE_URL", "https://fan-yi-bot.onrender.com")
    try:
        async with aiohttp.ClientSession() as session:
            await session.get(url, timeout=10)
    except Exception:
        # ignore network errors but log them occasionally
        logger.debug("Keepalive ping failed")

@bot.event
async def on_ready():
    try:
        keepalive_ping.start()
    except RuntimeError:
        # already started
        pass
    # sync application commands
    await bot.tree.sync()
    logger.info("Logged in as %s (id=%s)", bot.user, bot.user.id)

# -----------------------
# Run the bot
# -----------------------
if __name__ == "__main__":
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        logger.error("DISCORD_BOT_TOKEN is not set in environment variables.")
        raise SystemExit("Missing DISCORD_BOT_TOKEN")
    bot.run(token, reconnect=True)
