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
# 国旗 → 言語コード（リアクション用）
# ===========================
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

# 元→翻訳IDマップ
translated_message_map = {}

# ===========================
# 翻訳ヘルパー（非同期）
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
# /setlang（自動翻訳用）
# ===========================
class LangSelect(discord.ui.Select):
    def __init__(self, interaction):
        options = [
            discord.SelectOption(label=f"{flag} {lang}", value=code)
            for flag, code, lang in zip(
                flag_to_lang.keys(),
                flag_to_lang.values(),
                ["English", "Japanese", "Korean", "Vietnamese", "Spanish", "Traditional Chinese", "Simplified Chinese"]
            )
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

        flags_display = " ".join(flags[l] for l in self.values)

        await interaction.response.edit_message(
            content=f"✅ 自動翻訳の言語を {flags_display} に設定しました。",
            view=None
        )

class LangView(discord.ui.View):
    def __init__(self, interaction):
        super().__init__(timeout=120)
        self.add_item(LangSelect(interaction))

@bot.tree.command(name="setlang", description="自動翻訳時の翻訳先言語を設定")
async def setlang(interaction: discord.Interaction):
    await interaction.response.send_message(
        "🌐 自動翻訳で使用する言語を選択してください：",
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
    langs_display = " ".join(flags[l] for l in langs)

    embed = discord.Embed(title="🌐 翻訳BOT ステータス", color=0x00a2ff)
    embed.add_field(name="自動翻訳", value=auto_status, inline=False)
    embed.add_field(name="自動翻訳の言語", value=langs_display, inline=False)
    embed.set_footer(text="※チャンネルごとに設定")

    await interaction.response.send_message(embed=embed, ephemeral=True)

# ===========================
# メッセージ受信 → 自動翻訳
# ===========================
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    guild_id = str(message.guild.id)
    ch_id = str(message.channel.id)

    guild_settings = settings.get(guild_id, {})
    ch_settings = guild_settings.get("channels", {}).get(ch_id, {})

    if not ch_settings.get("auto"):
        return

    targets = []

    if message.content:
        targets.append(message.content)

    # 引用メッセージも翻訳対象
    if message.reference and message.reference.resolved:
        ref = message.reference.resolved
        if ref.content:
            targets.append(ref.content)

    translated_ids = []

    for text in targets:
        for lang in ch_settings.get("langs", ["en"]):
            try:
                t = await async_translate(text, lang)
                if t and t != text:
                    sent = await message.channel.send(f"{flags[lang]} {t}")
                    translated_ids.append(sent.id)
            except:
                pass

    if translated_ids:
        translated_message_map[message.id] = translated_ids

# ===========================
# 任意翻訳（国旗リアクション）
# ===========================
@bot.event
async def on_raw_reaction_add(payload):
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

    text = message.content
    if not text:
        return

    try:
        translated = await async_translate(text, lang)
        if translated:
            await channel.send(f"{emoji} {translated}")
    except Exception as e:
        print("国旗翻訳エラー:", e)

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
