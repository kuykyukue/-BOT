import os
import json
import asyncio
import discord
from discord.ext import commands
from discord import app_commands
from deep_translator import GoogleTranslator
from flask import Flask
import threading

# ===========================
# Flask（Render Keep-Alive）
# ===========================
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running!"

# ===========================
# Discord Bot 設定
# ===========================
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.reactions = True

bot = commands.Bot(
    command_prefix="/",
    intents=intents,
    reconnect=True
)

# ===========================
# 永続設定
# ===========================
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

# ===========================
# 翻訳サポート言語
# ===========================
supported_langs = {
    "en": "🇺🇸 English",
    "ja": "🇯🇵 Japanese",
    "ko": "🇰🇷 Korean",
    "vi": "🇻🇳 Vietnamese",
    "es": "🇪🇸 Spanish",
    "zh-TW": "🇹🇼 Traditional Chinese",
    "zh-CN": "🇨🇳 Simplified Chinese",
}

flags = {
    "en": "🇺🇸",
    "ja": "🇯🇵",
    "ko": "🇰🇷",
    "vi": "🇻🇳",
    "es": "🇪🇸",
    "zh-TW": "🇹🇼",
    "zh-CN": "🇨🇳",
}

# 元→翻訳IDマップ
translated_message_map = {}

# ===========================
# 翻訳ヘルパー（非同期化）
# ===========================
async def async_translate(text, target):
    return await asyncio.to_thread(
        GoogleTranslator(source="auto", target=target).translate,
        text
    )

# ===========================
# /auto（翻訳ON/OFF）
# ===========================
@bot.tree.command(name="auto", description="自動翻訳をON/OFFします")
@app_commands.choices(
    mode=[
        app_commands.Choice(name="ON（有効）", value="on"),
        app_commands.Choice(name="OFF（無効）", value="off")
    ]
)
async def auto(interaction: discord.Interaction, mode: app_commands.Choice[str]):
    guild_id = str(interaction.guild_id)
    ch_id = str(interaction.channel_id)

    guild_settings = settings.get(guild_id, {})
    channels = guild_settings.get("channels", {})
    ch_settings = channels.get(ch_id, {"auto": False, "langs": ["en"]})

    ch_settings["auto"] = (mode.value == "on")
    channels[ch_id] = ch_settings
    guild_settings["channels"] = channels
    settings[guild_id] = guild_settings
    save_settings(settings)

    await interaction.response.send_message(
        "✅ 自動翻訳をONにしました。" if mode.value == "on" else "🚫 自動翻訳をOFFにしました。",
        ephemeral=True
    )

# ===========================
# /setlang
# ===========================
class LangSelect(discord.ui.Select):
    def __init__(self, interaction):
        options = [
            discord.SelectOption(label=name, value=code)
            for code, name in supported_langs.items()
        ]
        super().__init__(
            placeholder="翻訳する言語を選択（複数可）",
            min_values=1,
            max_values=len(options),
            options=options
        )
        self.interaction = interaction

    async def callback(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild_id)
        ch_id = str(interaction.channel_id)

        guild_settings = settings.get(guild_id, {})
        channels = guild_settings.get("channels", {})
        ch_settings = channels.get(ch_id, {"auto": False, "langs": ["en"]})

        ch_settings["langs"] = self.values
        channels[ch_id] = ch_settings
        guild_settings["channels"] = channels
        settings[guild_id] = guild_settings
        save_settings(settings)

        flags_display = " ".join(flags.get(l, l) for l in self.values)

        await interaction.response.edit_message(
            content=f"✅ 翻訳言語を {flags_display} に設定しました。",
            view=None
        )

class LangView(discord.ui.View):
    def __init__(self, interaction):
        super().__init__(timeout=120)
        self.add_item(LangSelect(interaction))

@bot.tree.command(name="setlang", description="翻訳先言語を複数選択で設定")
async def setlang(interaction: discord.Interaction):
    await interaction.response.send_message(
        "🌐 翻訳先言語を選択してください：",
        view=LangView(interaction),
        ephemeral=True
    )

# ===========================
# /status
# ===========================
@bot.tree.command(name="status", description="現在の設定を表示します")
async def status(interaction: discord.Interaction):
    guild_id = str(interaction.guild_id)
    ch_id = str(interaction.channel_id)

    guild_settings = settings.get(guild_id, {})
    ch_settings = guild_settings.get("channels", {}).get(ch_id, {})

    auto_status = "✅ ON" if ch_settings.get("auto") else "🚫 OFF"
    langs = ch_settings.get("langs", ["en"])
    langs_display = " ".join(flags.get(l, l) for l in langs)

    embed = discord.Embed(title="🌐 翻訳BOT ステータス", color=0x00a2ff)
    embed.add_field(name="自動翻訳", value=auto_status, inline=False)
    embed.add_field(name="翻訳言語", value=langs_display, inline=False)
    embed.set_footer(text="※チャンネルごとに設定されます")

    await interaction.response.send_message(embed=embed, ephemeral=True)

# ===========================
# /help
# ===========================
@bot.tree.command(name="help", description="使い方を表示します")
async def help_cmd(interaction: discord.Interaction):
    embed = discord.Embed(title="📝 翻訳BOT コマンド一覧", color=0x58b9ff)
    embed.add_field(name="/auto", value="翻訳のON/OFF（選択式）", inline=False)
    embed.add_field(name="/setlang", value="翻訳先言語を複数選択", inline=False)
    embed.add_field(name="/status", value="現在の設定を確認", inline=False)
    embed.add_field(name="/help", value="このヘルプを表示", inline=False)
    embed.set_footer(text="開発：kuyBOT")

    await interaction.response.send_message(embed=embed, ephemeral=True)

# ===========================
# メッセージ受信 → 自動翻訳
# ===========================
@bot.event
async def on_message(message):
    # 🔥 Bot のメッセージは常に翻訳しない
    if message.author.bot:
        return

    guild_id = str(message.guild.id)
    ch_id = str(message.channel.id)

    guild_settings = settings.get(guild_id, {})
    ch_settings = guild_settings.get("channels", {}).get(ch_id, {})

    # 自動翻訳OFFならスキップ
    if not ch_settings.get("auto"):
        return

    translated_ids = []

    for lang in ch_settings.get("langs", ["en"]):
        try:
            t = await async_translate(message.content, lang)
            if t and t != message.content:
                sent = await message.channel.send(f"{flags.get(lang, lang)} {t}")
                translated_ids.append(sent.id)
        except Exception as e:
            print("翻訳エラー:", e)

    if translated_ids:
        translated_message_map[message.id] = translated_ids

# ===========================
# 任意翻訳（🌐リアクション）
# ===========================
TRANSLATE_EMOJI = "🌐"

@bot.event
async def on_raw_reaction_add(payload):
    # 自分の BOT のリアクションは無視
    if payload.user_id == bot.user.id:
        return

    if str(payload.emoji) != TRANSLATE_EMOJI:
        return

    guild = bot.get_guild(payload.guild_id)
    if guild is None:
        return

    channel = guild.get_channel(payload.channel_id)
    if channel is None:
        return

    message = await channel.fetch_message(payload.message_id)

    # Bot のメッセージは翻訳しない
    if message.author.bot:
        return

    guild_id = str(payload.guild_id)
    ch_id = str(payload.channel_id)

    guild_settings = settings.get(guild_id, {})
    ch_settings = guild_settings.get("channels", {}).get(ch_id, {"langs": ["en"]})

    langs = ch_settings.get("langs", ["en"])

    for lang in langs:
        try:
            t = await async_translate(message.content, lang)
            await channel.send(f"{flags.get(lang, lang)} {t}")
        except Exception as e:
            print("任意翻訳エラー:", e)

# ===========================
# 元メッセージ削除 → 翻訳も削除
# ===========================
@bot.event
async def on_message_delete(message):
    if message.id in translated_message_map:
        for tid in translated_message_map[message.id]:
            try:
                msg = await message.channel.fetch_message(tid)
                await msg.delete()
            except:
                pass
        del translated_message_map[message.id]

# ===========================
# on_ready
# ===========================
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"✅ Logged in as {bot.user}")

# ===========================
# Flask + Discord Bot 同時実行
# ===========================
def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    thread = threading.Thread(target=run_flask)
    thread.start()
    bot.run(os.environ["DISCORD_BOT_TOKEN"])
