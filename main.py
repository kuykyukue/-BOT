import os
import json
import discord
from discord.ext import commands
from discord import app_commands
from deep_translator import GoogleTranslator
from flask import Flask
from threading import Thread

# ====== Flask (Render Keep-Alive) ======
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

def run_web():
    app.run(host="0.0.0.0", port=8080)

Thread(target=run_web, daemon=True).start()

# ====== Discord Bot設定 ======
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
bot = commands.Bot(command_prefix="/", intents=intents)

# ====== 永続設定ファイル ======
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

# ====== 翻訳サポート言語（国旗＋言語名） ======
supported_langs = {
    "en": "🇺🇸 English",
    "ja": "🇯🇵 Japanese",
    "ko": "🇰🇷 Korean",
    "vi": "🇻🇳 Vietnamese",
    "es": "🇪🇸 Spanish",
    "zh-TW": "🇹🇼 Traditional Chinese (Taiwan)",
    "zh-CN": "🇨🇳 Simplified Chinese (China)"
}

flags = {
    "en": "🇺🇸",
    "ja": "🇯🇵",
    "ko": "🇰🇷",
    "vi": "🇻🇳",
    "es": "🇪🇸",
    "zh-TW": "🇹🇼",
    "zh-CN": "🇨🇳"
}

# 翻訳削除連動
translated_message_map = {}  # {元メッセージID: [翻訳メッセージID,...]}


# ====== /autoコマンド ======
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
    ch_settings = channels.get(ch_id, {"auto": False, "langs": ["en", "ja"]})

    ch_settings["auto"] = (mode.value == "on")
    channels[ch_id] = ch_settings
    guild_settings["channels"] = channels
    settings[guild_id] = guild_settings
    save_settings(settings)

    await interaction.response.send_message(
        f"{'✅ 自動翻訳をONにしました。' if mode.value == 'on' else '🚫 自動翻訳をOFFにしました。'}",
        ephemeral=True
    )


# ====== /setlang（国旗付き・複数選択） ======
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
        ch_settings = channels.get(ch_id, {"auto": False, "langs": ["en", "ja"]})

        ch_settings["langs"] = self.values
        channels[ch_id] = ch_settings
        guild_settings["channels"] = channels
        settings[guild_id] = guild_settings
        save_settings(settings)

        flags_display = " ".join(flags.get(l, l) for l in self.values)
        await interaction.response.edit_message(content=f"✅ 翻訳言語を {flags_display} に設定しました。", view=None)


class LangView(discord.ui.View):
    def __init__(self, interaction):
        super().__init__(timeout=60)
        self.add_item(LangSelect(interaction))


@bot.tree.command(name="setlang", description="翻訳先言語を設定（複数選択）")
async def setlang(interaction: discord.Interaction):
    await interaction.response.send_message("🌐 翻訳先言語を選択してください：", view=LangView(interaction), ephemeral=True)


# ====== /status ======
@bot.tree.command(name="status", description="現在の設定を表示します")
async def status(interaction: discord.Interaction):
    guild_id = str(interaction.guild_id)
    ch_id = str(interaction.channel_id)

    guild_settings = settings.get(guild_id, {})
    ch_settings = guild_settings.get("channels", {}).get(ch_id, {"auto": False, "langs": ["en", "ja"]})
    langs_display = " ".join(flags.get(l, l) for l in ch_settings["langs"])
    auto_status = "✅ ON" if ch_settings["auto"] else "🚫 OFF"

    embed = discord.Embed(title="🌐 翻訳BOT ステータス", color=0x00a2ff)
    embed.add_field(name="自動翻訳", value=auto_status, inline=False)
    embed.add_field(name="翻訳言語", value=langs_display, inline=False)
    embed.set_footer(text="※チャンネルごとに設定されます")

    await interaction.response.send_message(embed=embed, ephemeral=True)


# ====== /help ======
@bot.tree.command(name="help", description="使い方を表示します")
async def help(interaction: discord.Interaction):
    embed = discord.Embed(title="📝 翻訳BOT コマンド一覧", color=0x58b9ff)
    embed.add_field(name="/auto", value="自動翻訳のON/OFFを切り替えます（選択式）", inline=False)
    embed.add_field(name="/setlang", value="翻訳先の言語を複数選択します（国旗付きリスト）", inline=False)
    embed.add_field(name="/status", value="現在のチャンネル設定を確認します", inline=False)
    embed.add_field(name="/help", value="このヘルプを表示します", inline=False)
    embed.set_footer(text="開発：miku専用 翻訳BOT")
    await interaction.response.send_message(embed=embed, ephemeral=True)


# ====== メッセージ受信・翻訳（削除ボタンなし） ======
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    guild_id = str(message.guild.id)
    ch_id = str(message.channel.id)
    guild_settings = settings.get(guild_id, {})
    channels = guild_settings.get("channels", {})
    ch_settings = channels.get(ch_id, {"auto": False, "langs": ["en", "ja"]})

    if not ch_settings["auto"]:
        return

    if message.author == bot.user:
        return

    translated_msgs = []
    for lang in ch_settings["langs"]:
        try:
            translated = GoogleTranslator(source="auto", target=lang).translate(message.content)
            if translated and translated != message.content:
                sent = await message.channel.send(
                    f"{flags.get(lang, lang)} {translated}"
                )
                translated_msgs.append(sent.id)
        except Exception as e:
            print(f"翻訳エラー: {e}")

    if translated_msgs:
        translated_message_map[message.id] = translated_msgs


# ====== 元メッセージ削除で翻訳も削除 ======
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


# ====== 起動 ======
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"✅ Logged in as {bot.user}")


# ====== 実行 ======
bot.run(os.environ["DISCORD_BOT_TOKEN"])
