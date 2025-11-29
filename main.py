import os
import json
import asyncio
import discord
from discord.ext import commands
from deep_translator import GoogleTranslator
from flask import Flask
import threading

# ------------------------
# Flask（Render Keep-Alive用）
# ------------------------
app = Flask(__name__)
@app.route("/")
def home():
    return "Bot is running!"

# ------------------------
# Discord Bot 設定
# ------------------------
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.reactions = True
intents.guilds = True

bot = commands.Bot(command_prefix="/", intents=intents, reconnect=True)

# ------------------------
# 永続設定
# ------------------------
DATA_PATH = "data/settings.json"
os.makedirs("data", exist_ok=True)
if not os.path.exists(DATA_PATH):
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump({}, f, indent=4, ensure_ascii=False)

def load_settings():
    try:
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_settings(data):
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

settings = load_settings()  # structure: { guild_id_str: {"auto_translate": bool, "auto_lang": "ja"} }

# ------------------------
# 国旗・言語マップ（Discord emojiコード表示に使用）
# ------------------------
flag_to_lang = {
    "🇺🇸": "en",
    "🇯🇵": "ja",
    "🇰🇷": "ko",
    "🇻🇳": "vi",
    "🇪🇸": "es",
    "🇹🇼": "zh-TW",
    "🇨🇳": "zh-CN",
}
lang_to_flag = {v: k for k, v in flag_to_lang.items()}

# ------------------------
# 2: Discord 国旗コード (:flag_us:) に変換する関数
# ------------------------
def to_discord_flag(lang: str) -> str:
    """
    'en' → :flag_us:
    'ja' → :flag_jp:
    Fallback :white_flag: を返す
    """
    if "-" in lang:
        # handle zh-TW -> TW, zh-CN -> CN or 'en-US' -> US depending on mapping
        parts = lang.split("-")
        # prefer region part if present like zh-TW
        if len(parts) == 2:
            lang_code = parts[1]
        else:
            lang_code = parts[0]
    else:
        lang_code = lang

    mapping = {
        "en": "us",
        "ja": "jp",
        "ko": "kr",
        "vi": "vn",
        "es": "es",
        "zh-TW".lower(): "tw",
        "zh-TW".split("-")[-1].lower(): "tw",
        "zh-CN".split("-")[-1].lower(): "cn",
        "zh": "cn",
        "cn": "cn",
        "tw": "tw",
    }

    code = mapping.get(lang_code.lower(), None)
    if not code:
        # try 2-letter uppercase heuristics
        try:
            code = lang_code.lower()
        except:
            return ":white_flag:"
    return f":flag_{code}:"

# ------------------------
# 翻訳テキスト抽出（強化版）
# ------------------------
async def extract_text_from_message(message: discord.Message):
    """
    message から取りうるテキストを広く抽出してリストで返す（順序は原文順）
    対応:
      - message.content
      - message.embeds の title/description/fields/author.name
      - embed.type が message/message_link/article/rich/link の場合の description
      - message.reference (reply) の参照先メッセージ
      - thread starter message
    """
    texts = []

    # 1) content
    try:
        if getattr(message, "content", None):
            texts.append(message.content)
    except Exception:
        pass

    # 2) embeds
    try:
        for embed in message.embeds:
            # embed author (例えば通知のタイトル部分)
            try:
                if getattr(embed, "author", None) and getattr(embed.author, "name", None):
                    texts.append(embed.author.name)
            except Exception:
                pass

            # embed type special handling (forwarded/crosspost/message links)
            etype = getattr(embed, "type", "") or ""
            if etype in ("message", "message_link", "article", "link", "rich"):
                if getattr(embed, "description", None):
                    texts.append(embed.description)
                for f in getattr(embed, "fields", []):
                    if getattr(f, "name", None):
                        texts.append(f.name)
                    if getattr(f, "value", None):
                        texts.append(f.value)
            else:
                # generic extract
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
        pass

    # 3) thread starter (starter message)
    try:
        if message.type == discord.MessageType.thread_starter_message:
            # message.reference.resolved might be available
            if getattr(message, "reference", None) and getattr(message.reference, "resolved", None):
                starter = message.reference.resolved
                if starter and getattr(starter, "content", None):
                    texts.append(starter.content)
    except Exception:
        pass

    # 4) reply reference (普通のリプライ)
    try:
        if getattr(message, "reference", None) and getattr(message.reference, "message_id", None):
            try:
                # use channel.fetch_message — may raise if message not in same channel
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
                # fetch failed (could be in another channel/gone) — try resolved if present
                try:
                    resolved = message.reference.resolved
                    if resolved and getattr(resolved, "content", None):
                        texts.append(resolved.content)
                except Exception:
                    pass
    except Exception:
        pass

    # cleanup: strip empty and deduplicate preserving order
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

# ------------------------
# 非同期翻訳（IO-bound を別スレッドで）
# ------------------------
async def async_translate(text, target):
    return await asyncio.to_thread(
        GoogleTranslator(source="auto", target=target).translate,
        text
    )

# ------------------------
# ヘルパー: 翻訳可能かどうか（自分の翻訳メッセージか判定）
# ------------------------
TRANSLATOR_FOOTER_MARK = "Translator-BOT"  # footer にこれがあれば翻訳メッセージとして扱う

def is_own_translation_message(message: discord.Message) -> bool:
    # message.author may be a webhook/system user; safe check: footer text contains marker
    try:
        for embed in message.embeds:
            footer = getattr(embed, "footer", None)
            if footer and getattr(footer, "text", None):
                if TRANSLATOR_FOOTER_MARK in footer.text:
                    return True
    except Exception:
        pass
    return False

# ------------------------
# 翻訳を送信する共通関数
# ------------------------
async def send_translation(channel: discord.TextChannel, original_message: discord.Message, lang: str, translated_text: str):
    flag_code = to_discord_flag(lang)
    embed = discord.Embed(
        title=f"翻訳結果 {flag_code}",
        description=translated_text,
        color=0x00c19f
    )
    # フッターにマーカーを入れてループを防止
    embed.set_footer(text=f"{TRANSLATOR_FOOTER_MARK} | 元メッセージID: {original_message.id}")
    sent = await channel.send(embed=embed)
    return sent

# ------------------------
# 翻訳メッセージ管理（メモリ）
# key = (orig_message_id, emoji) -> translation_message_id
# ------------------------
translated_message_map = {}

# ------------------------
# on_raw_reaction_add （国旗リアクションで翻訳）
# ------------------------
@bot.event
async def on_raw_reaction_add(payload):
    try:
        # ignore bot's own reaction events quickly
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

        try:
            message = await channel.fetch_message(payload.message_id)
        except Exception as e:
            print(f"[on_raw_reaction_add] fetch_message failed: {e}")
            return

        # 防止: Bot 自身の翻訳メッセージなら何もしない
        if is_own_translation_message(message):
            return

        # 抽出
        texts = await extract_text_from_message(message)
        if not texts:
            # nothing to translate
            return

        original = "\n".join(texts)
        translated = await async_translate(original, lang)
        if not translated:
            return

        sent = await send_translation(channel, message, lang, translated)
        translated_message_map[(message.id, emoji)] = sent.id

    except Exception as e:
        print("on_raw_reaction_add エラー:", e)

# ------------------------
# on_raw_reaction_remove （翻訳削除）
# ------------------------
@bot.event
async def on_raw_reaction_remove(payload):
    try:
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
        except Exception:
            pass
        del translated_message_map[key]

    except Exception as e:
        print("on_raw_reaction_remove エラー:", e)

# ------------------------
# 自動翻訳: メッセージ送信時に自動で翻訳を作る（guild設定で有効なら）
# - ギルドごとに settings[guild_id]["auto_translate"] (bool) と auto_lang (str) を参照
# ------------------------
@bot.event
async def on_message(message):
    # 必須: commands を動かすために先に process_commands を呼ぶ
    await bot.process_commands(message)

    # ignore if message from ourselves (bot)
    if message.author == bot.user:
        return

    # ignore if it's our translation message (by footer marker) to prevent loops
    if is_own_translation_message(message):
        return

    # guild限定（DM などは無視）
    if not message.guild:
        return

    gid = str(message.guild.id)
    guild_conf = settings.get(gid, {})
    if not guild_conf.get("auto_translate", False):
        return

    auto_lang = guild_conf.get("auto_lang", "ja")
    # Extract text
    texts = await extract_text_from_message(message)
    if not texts:
        return

    original = "\n".join(texts)
    try:
        translated = await async_translate(original, auto_lang)
    except Exception as e:
        print(f"[on_message] translate error: {e}")
        return

    try:
        await send_translation(message.channel, message, auto_lang, translated)
    except Exception as e:
        print(f"[on_message] send_translation error: {e}")

# ------------------------
# コマンド: /autotranslate on|off
# ------------------------
@bot.command(name="autotranslate")
@commands.has_guild_permissions(administrator=True)
async def autotranslate_cmd(ctx, mode: str):
    """
    管理者コマンド: /autotranslate on|off
    """
    mode = mode.lower()
    gid = str(ctx.guild.id)
    if mode not in ("on", "off"):
        await ctx.send("使い方: /autotranslate on か /autotranslate off")
        return

    conf = settings.get(gid, {})
    conf["auto_translate"] = (mode == "on")
    # preserve existing auto_lang or set default
    conf.setdefault("auto_lang", "ja")
    settings[gid] = conf
    save_settings(settings)
    await ctx.send(f"自動翻訳を **{mode}** に設定しました。自動翻訳先言語: `{conf['auto_lang']}`")

# ------------------------
# コマンド: /autolang <lang>
# ------------------------
@bot.command(name="autolang")
@commands.has_guild_permissions(administrator=True)
async def autolang_cmd(ctx, lang: str):
    """
    管理者コマンド: /autolang ja|en|ko|vi|es|zh-TW etc.
    """
    gid = str(ctx.guild.id)
    conf = settings.get(gid, {})
    conf.setdefault("auto_translate", False)
    conf["auto_lang"] = lang
    settings[gid] = conf
    save_settings(settings)
    await ctx.send(f"自動翻訳先言語を `{lang}` に設定しました。自動翻訳は `{conf['auto_translate']}` の状態です。")

# ------------------------
# Bot Ready
# ------------------------
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"✅ Logged in as {bot.user}")

# ------------------------
# Flask + Discord Bot
# ------------------------
def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    thread = threading.Thread(target=run_flask)
    thread.start()
    bot.run(os.environ["DISCORD_BOT_TOKEN"])
