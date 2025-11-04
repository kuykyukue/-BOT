import os
import discord
from discord import app_commands
from discord.ext import commands
from deep_translator import GoogleTranslator
from flask import Flask
from threading import Thread

# --- Flask サーバー（Render維持用） ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

def keep_alive():
    t = Thread(target=run_flask)
    t.daemon = True
    t.start()

# --- Discord Bot 設定 ---
TOKEN = os.environ.get("DISCORD_TOKEN")  # ← Renderの環境変数名に合わせました

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# --- データ保存用辞書 ---
auto_translate_guilds = {}     # サーバーごとの自動翻訳設定（ON/OFF）
user_languages = {}            # サーバーごとの翻訳言語設定
channel_whitelist = {}         # サーバーごとの対象チャンネル設定

# --- 国旗絵文字マッピング ---
flags = {
    "en": "🇺🇸", "ja": "🇯🇵", "ko": "🇰🇷", "zh": "🇨🇳",
    "fr": "🇫🇷", "de": "🇩🇪", "es": "🇪🇸", "it": "🇮🇹",
    "ru": "🇷🇺", "pt": "🇧🇷", "id": "🇮🇩", "vi": "🇻🇳", "th": "🇹🇭"
}

# --- /autoコマンド（翻訳ON/OFF） ---
@tree.command(name="auto", description="自動翻訳をオン／オフします")
@app_commands.describe(mode="on または off")
async def auto(interaction: discord.Interaction, mode: str):
    guild_id = interaction.guild.id
    if mode.lower() == "on":
        auto_translate_guilds[guild_id] = True
        await interaction.response.send_message("🌍 自動翻訳を **オン** にしました！")
    elif mode.lower() == "off":
        auto_translate_guilds[guild_id] = False
        await interaction.response.send_message("🚫 自動翻訳を **オフ** にしました！")
    else:
        await interaction.response.send_message("⚠️ `on` または `off` を指定してください。")

# --- /langコマンド（翻訳先言語の設定） ---
@tree.command(name="lang", description="翻訳対象言語を設定します（例: en ja ko）")
@app_commands.describe(languages="翻訳先の言語をスペース区切りで入力")
async def lang(interaction: discord.Interaction, languages: str):
    guild_id = interaction.guild.id
    user_languages[guild_id] = languages.split()
    await interaction.response.send_message(f"✅ 翻訳対象言語を `{languages}` に設定しました！")

# --- /channelコマンド（翻訳対象チャンネルを選択） ---
@tree.command(name="channel", description="翻訳を有効にするチャンネルを設定します")
@app_commands.describe(channel="翻訳を有効にしたいチャンネル")
async def channel(interaction: discord.Interaction, channel: discord.TextChannel):
    guild_id = interaction.guild.id
    if guild_id not in channel_whitelist:
        channel_whitelist[guild_id] = set()
    if channel.id in channel_whitelist[guild_id]:
        channel_whitelist[guild_id].remove(channel.id)
        await interaction.response.send_message(f"🚫 {channel.mention} の翻訳をオフにしました。")
    else:
        channel_whitelist[guild_id].add(channel.id)
        await interaction.response.send_message(f"✅ {channel.mention} で翻訳をオンにしました。")

# --- /statusコマンド（現在の設定確認） ---
@tree.command(name="status", description="現在の翻訳設定を確認します")
async def status(interaction: discord.Interaction):
    guild_id = interaction.guild.id
    auto_status = "オン ✅" if auto_translate_guilds.get(guild_id, False) else "オフ ❌"
    langs = " ".join(user_languages.get(guild_id, ["en", "ja"]))
    channels = channel_whitelist.get(guild_id, set())
    ch_list = ", ".join(f"<#{ch_id}>" for ch_id in channels) if channels else "（未設定）"

    embed = discord.Embed(title="🌐 翻訳Bot ステータス", color=0x3498db)
    embed.add_field(name="自動翻訳", value=auto_status, inline=False)
    embed.add_field(name="翻訳対象言語", value=langs, inline=False)
    embed.add_field(name="対象チャンネル", value=ch_list, inline=False)
    await interaction.response.send_message(embed=embed)

# --- メッセージ監視・翻訳処理 ---
@bot.event
async def on_message(message):
    if message.author.bot:
        return  # ✅ Bot自身の発言を無視（翻訳の重複防止）

    guild_id = message.guild.id

    # 自動翻訳ONでない場合
    if not auto_translate_guilds.get(guild_id, False):
        await bot.process_commands(message)
        return

    # チャンネル制限ありの場合
    allowed_channels = channel_whitelist.get(guild_id, set())
    if allowed_channels and message.channel.id not in allowed_channels:
        await bot.process_commands(message)
        return

    target_langs = user_languages.get(guild_id, ["en", "ja"])
    text = message.content

    try:
        for lang in target_langs:
            translated = GoogleTranslator(source='auto', target=lang).translate(text)
            if translated and translated != text:
                flag = flags.get(lang, f"[{lang}]")
                await message.channel.send(f"{flag} {translated}")
    except Exception as e:
        await message.channel.send(f"⚠️ 翻訳エラー: {e}")

    # ✅ スラッシュコマンドが動作するようにする
    await bot.process_commands(message)

# --- 起動イベント ---
@bot.event
async def on_ready():
    await tree.sync()
    print(f"✅ Logged in as {bot.user}")

# --- メイン実行 ---
if __name__ == "__main__":
    keep_alive()
    bot.run(TOKEN)
