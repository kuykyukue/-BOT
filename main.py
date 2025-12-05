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

settings = safe_load_settings(SETTINGS_FILE)

# -----------------------------
# Flask keep-alive (Render用)
# -----------------------------
app = Flask(__name__)

@app.route("/")
def home():
    return "✅ Discord翻訳BOT is alive!"

def run_flask(port: int = DEFAULT_PORT):
    app.run(host="0.0.0.0", port=port)

flask_thread = threading.Thread(target=run_flask, daemon=True)
flask_thread.start()

# -----------------------------
# Discord BOT 設定
# -----------------------------
intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True
intents.guilds = True
intents.members = False

bot = commands.Bot(command_prefix="/", intents=intents, reconnect=True)

# original_message_id + lang → translated message list
translated_messages: Dict[Tuple[int, str], List[int]] = {}

# -----------------------------
# Flag → Language mapping
# -----------------------------
LANG_TO_EMOJI = {
    "en": "🇺🇸", "ja": "🇯🇵", "ko": "🇰🇷", "zh": "🇨🇳",
    "zh-CN": "🇨🇳", "zh-TW": "🇹🇼", "fr": "🇫🇷", "de": "🇩🇪",
    "es": "🇪🇸", "it": "🇮🇹", "ru": "🇷🇺", "pt": "🇧🇷",
    "id": "🇮🇩", "vi": "🇻🇳", "th": "🇹🇭"
}

EMOJI_TO_LANG = {v: k for k, v in LANG_TO_EMOJI.items()}

# -----------------------------
# Emoji 正規化
# -----------------------------
def emoji_to_lang_from_partial_name(name: str) -> Optional[str]:
    m = re.search(r"flag[_\-]?([a-z]{2})", name, flags=re.I)
    if m:
        cc = m.group(1).lower()
        mapping = {
            "jp": "ja", "us": "en", "gb": "en", "kr": "ko",
            "cn": "zh-CN", "tw": "zh-TW", "fr": "fr", "de": "de",
            "es": "es", "it": "it", "ru": "ru", "br": "pt",
            "id": "id", "vn": "vi", "th": "th"
        }
        return mapping.get(cc)
    if len(name) == 2 and name.isalpha():
        mapping = {"ja": "ja", "jp": "ja", "en": "en", "ko": "ko", "cn": "zh-CN", "tw": "zh-TW"}
        return mapping.get(name.lower())
    return None

def unicode_flag_to_lang(flag_str: str) -> Optional[str]:
    try:
        if len(flag_str) < 2:
            return None
        cp = [ord(ch) for ch in flag_str]
        if all(0x1F1E6 <= x <= 0x1F1FF for x in cp[:2]):
            cc = ''.join(chr(x - 0x1F1E6 + ord('a')) for x in cp[:2])
            return emoji_to_lang_from_partial_name(f"flag_{cc}")
    except:
        pass
    return None

def normalize_emoji(payload_emoji) -> Optional[str]:
    try:
        # PartialEmoji
        if hasattr(payload_emoji, "name") and payload_emoji.name:
            lang = emoji_to_lang_from_partial_name(payload_emoji.name)
            if lang:
                return lang

        # unicode emoji
        s = str(payload_emoji)
        lang = unicode_flag_to_lang(s)
        if lang:
            return lang

        # fallback
        if s in EMOJI_TO_LANG:
            return EMOJI_TO_LANG[s]
    except:
        pass
    return None
    # --- Reaction Translation Helpers ---

# メモリ上に翻訳メッセージの関連を保存
# { original_message_id: {emoji: translated_message_id} }
reaction_map = {}


async def translate_text(text: str, src: str, dest: str):
    try:
        result = await translator.translate(text, src=src, dest=dest)
        return result.text
    except Exception as e:
        print(f"[Error] Translation failed: {e}")
        return None
# 絵文字 → 言語マッピング
emoji_lang = {
    "🇯🇵": "ja",
    "🇺🇸": "en",
    "🇨🇳": "zh-cn",
    "🇹🇼": "zh-tw",
    "🇰🇷": "ko",
    "🇫🇷": "fr"
}
@bot.event
async def on_reaction_add(reaction, user):
    if user.bot:
        return

    emoji = str(reaction.emoji)
    if emoji not in emoji_lang:
        return

    lang = emoji_lang[emoji]
    message = reaction.message

    # 既に翻訳済みなら何もしない
    if message.id in reaction_map and emoji in reaction_map[message.id]:
        return

    # メッセージ本文を取得
    content = message.content
    if not content:
        return

    translated = await translate_text(content, "auto", lang)
    if not translated:
        return

    # 転送メッセージ / 引用メッセージも翻訳
    ref_text = ""
    if message.reference and message.reference.resolved:
        ref_src = message.reference.resolved
        ref_text = f"\n> **引用:** {ref_src.content}"

    sent = await message.channel.send(f"**🔁 {emoji} 翻訳:**\n{translated}{ref_text}")

    # 保存
    if message.id not in reaction_map:
        reaction_map[message.id] = {}

    reaction_map[message.id][emoji] = sent.id
    @bot.event
async def on_reaction_remove(reaction, user):
    if user.bot:
        return

    emoji = str(reaction.emoji)
    if emoji not in emoji_lang:
        return

    message = reaction.message

    # 登録されていないなら終了
    if message.id not in reaction_map:
        return
    if emoji not in reaction_map[message.id]:
        return

    translated_msg_id = reaction_map[message.id][emoji]

    # 削除を試みる
    try:
        translated_msg = await message.channel.fetch_message(translated_msg_id)
        await translated_msg.delete()
    except:
        pass

    # マップから消す
    del reaction_map[message.id][emoji]

    # もし全部消えたらエントリ削除
    if len(reaction_map[message.id]) == 0:
        del reaction_map[message.id]
        bot.run(DISCORD_BOT_TOKEN)
