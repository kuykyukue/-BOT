# main.py
# -*- coding: utf-8 -*-
import os
import sys
import json
import re
import asyncio
import threading
from typing import List, Optional, Tuple, Dict

import aiohttp
import discord
from discord.ext import commands, tasks
from deep_translator import GoogleTranslator
from flask import Flask

# -----------------------------
# Configuration
# -----------------------------
SETTINGS_FILE = "data/settings.json"
TRANSLATOR_FOOTER_MARK = "Translator-BOT"
KEEPALIVE_TARGET = os.environ.get("KEEPALIVE_URL")  # optional, fallback to render url if set
DEFAULT_PORT = int(os.environ.get("PORT", 10000))
DISCORD_TOKEN_ENV = "DISCORD_BOT_TOKEN"

# -----------------------------
# Ensure data folder & load settings
# -----------------------------
os.makedirs("data", exist_ok=True)

def safe_load_settings(path: str) -> dict:
    try:
        if not os.path.exists(path):
            with open(path, "w", encoding="utf-8") as f:
                json.dump({}, f, ensure_ascii=False, indent=4)
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception as e:
        print(f"[settings] load error: {e}")
        return {}

def safe_save_settings(path: str, data: dict):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"[settings] save error: {e}")

settings = safe_load_settings(SETTINGS_FILE)  # structure: { guild_id_str: {"auto_translate": bool, "auto_lang": "ja", "langs":[...]} }

# -----------------------------
# Flask keep-alive (Render)
# -----------------------------
app = Flask(__name__)

@app.route("/")
def home():
    return "✅ Discord翻訳BOT is alive!"

def run_flask(port: int = DEFAULT_PORT):
    # Use daemon thread when starting
    app.run(host="0.0.0.0", port=port)

flask_thread = threading.Thread(target=run_flask, daemon=True)
flask_thread.start()

# -----------------------------
# Bot setup
# -----------------------------
intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True
intents.guilds = True
intents.members = False

bot = commands.Bot(command_prefix="/", intents=intents, reconnect=True)

# translated_messages mapping:
# key: (original_message_id, lang) -> [translated_message_ids]
translated_messages: Dict[Tuple[int, str], List[int]] = {}

# -----------------------------
# Flags mapping (emoji unicode strings to language codes)
# Keep both unicode and alias mapping in mind.
# -----------------------------
# Primary language -> unicode emoji (common)
LANG_TO_EMOJI = {
    "en": "🇺🇸", "ja": "🇯🇵", "ko": "🇰🇷", "zh": "🇨🇳",
    "zh-CN": "🇨🇳", "zh-TW": "🇹🇼", "fr": "🇫🇷", "de": "🇩🇪",
    "es": "🇪🇸", "it": "🇮🇹", "ru": "🇷🇺", "pt": "🇧🇷",
    "id": "🇮🇩", "vi": "🇻🇳", "th": "🇹🇭"
}
# Build reverse map for quick match: unicode -> lang
EMOJI_TO_LANG = {v: k for k, v in LANG_TO_EMOJI.items()}

# -----------------------------
# Helpers: normalize emoji payloads to 2-letter region code or unicode flag
# - Handles:
#   * Unicode flag emoji (e.g. '🇯🇵')
#   * PartialEmoji with name like 'flag_jp' or 'jp'
#   * :flag_jp: style names
# Returns canonical language code (e.g. 'ja' or 'zh-TW') if possible, else None
# -----------------------------
def emoji_to_lang_from_partial_name(name: str) -> Optional[str]:
    # common patterns: "flag_jp", "jp", "flag_jp:jp" etc.
    m = re.search(r"flag[_\-]?([a-z]{2})", name, flags=re.I)
    if m:
        cc = m.group(1).lower()
        # map 2-letter country code to language heuristics
        mapping_cc_to_lang = {
            "jp": "ja", "us": "en", "gb": "en", "kr": "ko",
            "cn": "zh-CN", "tw": "zh-TW", "fr": "fr", "de": "de",
            "es": "es", "it": "it", "ru": "ru", "br": "pt",
            "id": "id", "vn": "vi", "th": "th"
        }
        return mapping_cc_to_lang.get(cc)
    # try raw two-letter language
    if len(name) == 2 and name.isalpha():
        two = name.lower()
        code_map = {"ja":"ja","jp":"ja","en":"en","ko":"ko","cn":"zh-CN","tw":"zh-TW"}
        return code_map.get(two)
    return None

def unicode_flag_to_lang(flag_str: str) -> Optional[str]:
    # Unicode flag are composed of two regional indicator symbols.
    # Convert to country code then map to lang.
    try:
        if not flag_str or len(flag_str) < 2:
            return None
        # detect regional indicators
        codepoints = [ord(ch) for ch in flag_str]
        # regional indicator A starts at U+1F1E6
        if all(0x1F1E6 <= cp <= 0x1F1FF for cp in codepoints[:2]):
            cc = ''.join(chr(cp - 0x1F1E6 + ord('a')) for cp in codepoints[:2])
            return emoji_to_lang_from_partial_name(f"flag_{cc}")
    except Exception:
        pass
    return None

def normalize_emoji(payload_emoji) -> Optional[str]:
    """
    Accepts payload.emoji which might be:
      - discord.PartialEmoji (has .name)
      - string like '🇯🇵'
      - discord.Emoji (custom emoji)
    Returns language code like 'ja', 'en', 'zh-CN' or None.
    """
    try:
        # If it's an object with name attribute (PartialEmoji)
        if hasattr(payload_emoji, "name") and payload_emoji.name:
            name = payload_emoji.name
            lang = emoji_to_lang_from_partial_name(name)
            if lang:
                return lang
            # sometimes name is like 'jp' or 'flag_jp'
            # fallback: try direct
            if name.lower() in ("jp", "ja", "en", "ko", "cn", "tw"):
                return {"jp":"ja","ja":"ja","en":"en","ko":"ko","cn":"zh-CN","tw":"zh-TW"}.get(name.lower())
        # If it's a string unicode emoji
        s = str(payload_emoji)
        lang = unicode_flag_to_lang(s)
        if lang:
            return lang
        # As last resort, check if s equals our emoji mapping
        if s in EMOJI_TO_LANG:
            return EMOJI_TO_LANG[s]
    except Exception:
        pass
    return None

# -----------------------------
# Extract text from message (robust)
# - content
# - embeds: author name, title, description, fields
# - referenced message (reply)
# - attachments: don't attempt OCR; skip
# Returns cleaned joined text or empty string
# -----------------------------
async def extract_text_from_message(message: discord.Message) -> List[str]:
    texts = []
    try:
        if getattr(message, "content", None):
            texts.append(message.content)
    except Exception:
        pass

    # embeds
    try:
        for embed in getattr(message, "embeds", []):
            # author name
            if getattr(embed, "author", None) and getattr(embed.author, "name", None):
                texts.append(embed.author.name)
            # title / description
            if getattr(embed, "title", None):
                texts.append(embed.title)
            if getattr(embed, "description", None):
                texts.append(embed.description)
            # fields
            for f in getattr(embed, "fields", []):
                if getattr(f, "name", None):
                    texts.append(f.name)
                if getattr(f, "value", None):
                    texts.append(f.value)
    except Exception:
        pass

    # referenced message (reply)
    try:
        if getattr(message, "reference", None) and getattr(message.reference, "message_id", None):
            try:
                ref_msg = await message.channel.fetch_message(message.reference.message_id)
                if getattr(ref_msg, "content", None):
                    texts.append(ref_msg.content)
                for embed in getattr(ref_msg, "embeds", []):
                    if getattr(embed, "title", None):
                        texts.append(embed.title)
                    if getattr(embed, "description", None):
                        texts.append(embed.description)
                    for f in getattr(embed, "fields", []):
                        if getattr(f, "name", None):
                            texts.append(f.name)
                        if getattr(f, "value", None):
                            texts.append(f.value)
            except Exception:
                # sometimes resolved exists
                try:
                    resolved = message.reference.resolved
                    if resolved and getattr(resolved, "content", None):
                        texts.append(resolved.content)
                except Exception:
                    pass
    except Exception:
        pass

    # dedupe & strip
    out = []
    seen = set()
    for t in texts:
        try:
            s = t.strip()
        except Exception:
            s = str(t).strip()
        if not s:
            continue
        if s in seen:
            continue
        seen.add(s)
        out.append(s)
    return out

# -----------------------------
# Async translate wrapper (run blocking deep_translator in thread)
# -----------------------------
async def async_translate(text: str, target: str) -> str:
    try:
        # deep_translator's translate is synchronous; run in thread
        return await asyncio.to_thread(GoogleTranslator(source="auto", target=target).translate, text)
    except Exception as e:
        return f"⚠️ 翻訳エラー: {e}"

# -----------------------------
# Determine if message is our own translation message
# by checking embeds' footer for marker
# -----------------------------
def is_own_translation_message(message: discord.Message) -> bool:
    try:
        for embed in getattr(message, "embeds", []):
            footer = getattr(embed, "footer", None)
            if footer and getattr(footer, "text", None):
                if TRANSLATOR_FOOTER_MARK in footer.text:
                    return True
    except Exception:
        pass
    return False

# -----------------------------
# Send translation embed and register mapping
# -----------------------------
async def send_translation(channel: discord.TextChannel, original_message: discord.Message, lang: str, translated_text: str) -> Optional[discord.Message]:
    emoji = LANG_TO_EMOJI.get(lang, "")
    title = f"{emoji} 翻訳 ({lang})" if emoji else f"翻訳 ({lang})"
    embed = discord.Embed(title=title, description=translated_text, color=0x00C19F)
    embed.set_footer(text=f"{TRANSLATOR_FOOTER_MARK} | original:{original_message.id}")
    try:
        sent = await channel.send(embed=embed)
        # register mapping
        key = (original_message.id, lang)
        translated_messages.setdefault(key, []).append(sent.id)
        return sent
    except Exception as e:
        print(f"[send_translation] send failed: {e}")
        return None

# -----------------------------
# Remove translations for (orig_id, lang)
# -----------------------------
async def remove_translations_for(original_message_id: int, lang: Optional[str] = None, channel: Optional[discord.TextChannel] = None):
    # if lang is None => remove all langs for that original
    keys = []
    if lang:
        keys = [(original_message_id, lang)]
    else:
        keys = [k for k in translated_messages.keys() if k[0] == original_message_id]

    for key in keys:
        sent_ids = translated_messages.get(key, [])
        for mid in sent_ids:
            try:
                if channel:
                    msg = await channel.fetch_message(mid)
                else:
                    # we need to find channel: can't if not provided -> skip
                    continue
                await msg.delete()
            except Exception:
                pass
        translated_messages.pop(key, None)

# -----------------------------
# Event: Reaction add -> translate
# Uses normalize_emoji to support many payload forms
# -----------------------------
@bot.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    try:
        # Ignore bot's own reactions
        if payload.user_id == bot.user.id:
            return

        lang = normalize_emoji(payload.emoji)
        if not lang:
            return

        # fetch guild/channel/message safely
        guild = bot.get_guild(payload.guild_id)
        if guild is None:
            return
        channel = guild.get_channel(payload.channel_id)
        if channel is None:
            return
        try:
            message = await channel.fetch_message(payload.message_id)
        except Exception as e:
            print(f"[on_raw_reaction_add] fetch_message failed: {e}")
            return

        # don't translate our own translation messages
        if is_own_translation_message(message):
            return

        texts = await extract_text_from_message(message)
        if not texts:
            # nothing to translate
            # but to avoid user confusion, optionally send a small ephemeral message? skip for now
            return
        original = "\n".join(texts)

        # translate (async)
        translated = await async_translate(original, lang)
        if not translated:
            return

        await send_translation(channel, message, lang, translated)

    except Exception as e:
        print(f"[on_raw_reaction_add] error: {e}")

# -----------------------------
# Event: Reaction remove -> delete translations (for that lang)
# -----------------------------
@bot.event
async def on_raw_reaction_remove(payload: discord.RawReactionActionEvent):
    try:
        lang = normalize_emoji(payload.emoji)
        if not lang:
            return

        # If mapping exists for given original and lang, delete translated messages
        key = (payload.message_id, lang)
        if key not in translated_messages:
            return

        guild = bot.get_guild(payload.guild_id)
        if guild is None:
            return
        channel = guild.get_channel(payload.channel_id)
        if channel is None:
            return

        # delete the mapped translated messages in that channel
        sent_ids = translated_messages.get(key, [])
        for mid in sent_ids:
            try:
                msg = await channel.fetch_message(mid)
                await msg.delete()
            except Exception:
                pass
        translated_messages.pop(key, None)

    except Exception as e:
        print(f"[on_raw_reaction_remove] error: {e}")

# -----------------------------
# Event: on_message for auto-translate and command processing
# - Process commands first to allow commands to be used inline
# - Skip if bot msg or translation footer present
# -----------------------------
@bot.event
async def on_message(message: discord.Message):
    # allow commands to work
    await bot.process_commands(message)

    # ignore bot messages
    if message.author.bot:
        return
    # ignore translation messages
    if is_own_translation_message(message):
        return
    # only in guilds
    if not message.guild:
        return

    gid = str(message.guild.id)
    guild_conf = settings.get(gid, None) or settings.get(gid)
    if not guild_conf:
        return
    if not guild_conf.get("auto_translate", False):
        return

    auto_lang = guild_conf.get("auto_lang") or guild_conf.get("auto") or guild_conf.get("langs")
    # accept multiple forms: string (single lang) or list
    if isinstance(auto_lang, list):
        target_langs = auto_lang
    elif isinstance(auto_lang, str):
        target_langs = [auto_lang]
    else:
        # default fallback
        target_langs = ["ja"]

    texts = await extract_text_from_message(message)
    if not texts:
        return
    original = "\n".join(texts)

    for lang in target_langs:
        translated = await async_translate(original, lang)
        await send_translation(message.channel, message, lang, translated)

# -----------------------------
# on_message_delete : when original is deleted, delete translations
# -----------------------------
@bot.event
async def on_message_delete(message: discord.Message):
    try:
        # delete all translations for this original
        keys = [k for k in translated_messages.keys() if k[0] == message.id]
        if not keys:
            return
        for key in keys:
            # attempt delete in same channel
            sent_ids = translated_messages.get(key, [])
            for mid in sent_ids:
                try:
                    # We don't always know channel; try message.channel
                    # Note: if translations sent to same channel, this works
                    ch = message.channel
                    msg = await ch.fetch_message(mid)
                    await msg.delete()
                except Exception:
                    pass
            translated_messages.pop(key, None)
    except Exception as e:
        print(f"[on_message_delete] error: {e}")

# -----------------------------
# Admin commands: /autotranslate on|off and /autolang <lang>
# Using simple text commands (slash commands can be added similarly)
# -----------------------------
@bot.command(name="autotranslate")
@commands.has_guild_permissions(administrator=True)
async def autotranslate_cmd(ctx: commands.Context, mode: str):
    """
    Usage: /autotranslate on|off
    """
    try:
        mode = mode.lower()
        if mode not in ("on", "off"):
            await ctx.send("使い方: /autotranslate on か /autotranslate off")
            return
        gid = str(ctx.guild.id)
        conf = settings.get(gid, {})
        conf["auto_translate"] = (mode == "on")
        # keep existing auto_lang or set default
        conf.setdefault("auto_lang", "ja")
        settings[gid] = conf
        safe_save_settings(SETTINGS_FILE, settings)
        await ctx.send(f"自動翻訳を **{mode}** に設定しました。自動翻訳先言語: `{conf['auto_lang']}`")
    except Exception as e:
        await ctx.send(f"エラー: {e}")

@bot.command(name="autolang")
@commands.has_guild_permissions(administrator=True)
async def autolang_cmd(ctx: commands.Context, lang: str):
    """
    Usage: /autolang ja|en|ko|zh-TW ...
    """
    try:
        gid = str(ctx.guild.id)
        conf = settings.get(gid, {})
        conf.setdefault("auto_translate", False)
        conf["auto_lang"] = lang
        settings[gid] = conf
        safe_save_settings(SETTINGS_FILE, settings)
        await ctx.send(f"自動翻訳先言語を `{lang}` に設定しました。自動翻訳は `{conf['auto_translate']}` の状態です。")
    except Exception as e:
        await ctx.send(f"エラー: {e}")

# -----------------------------
# Keepalive ping task (optionally hits KEEPALIVE_TARGET or default Render url)
# -----------------------------
@tasks.loop(seconds=60)
async def keepalive_ping():
    url = KEEPALIVE_TARGET or os.environ.get("KEEPALIVE_URL") or os.environ.get("RENDER_EXTERNAL_URL")
    # if none, try to construct from environment (Render usually sets RENDER_EXTERNAL_URL)
    if not url:
        # Fallback: try to build from host env var (user may set KEEPALIVE_URL manually)
        url = None
    if not url:
        return
    try:
        async with aiohttp.ClientSession() as sess:
            async with sess.get(url, timeout=10) as resp:
                # optionally log
                # print(f"[keepalive] {resp.status}")
                pass
    except Exception:
        pass

# -----------------------------
# on_ready: sync commands & start keepalive
# -----------------------------
@bot.event
async def on_ready():
    try:
        # load settings fresh on ready
        global settings
        settings = safe_load_settings(SETTINGS_FILE)
    except Exception:
        pass
    print(f"✅ Logged in as {bot.user} (id: {bot.user.id})")
    # start keepalive ping if target provided
    if (KEEPALIVE_TARGET or os.environ.get("KEEPALIVE_URL") or os.environ.get("RENDER_EXTERNAL_URL")) and not keepalive_ping.is_running():
        keepalive_ping.start()
    # sync app commands (if you add slash commands later)
    try:
        # await bot.tree.sync()
        pass
    except Exception:
        pass

# -----------------------------
# Safe run
# -----------------------------
def main():
    token = os.environ.get(DISCORD_TOKEN_ENV)
    if not token:
        print(f"❌ 環境変数 {DISCORD_TOKEN_ENV} が見つかりません。Render の Dashboard で設定してください。")
        sys.exit(1)
    # Optionally set KEEPALIVE_TARGET to Render URL if not set by user
    # On Render, you can set KEEPALIVE_URL env var to https://<app>.onrender.com
    print("🚀 Starting bot...")
    bot.run(token, reconnect=True)

if __name__ == "__main__":
    main()
