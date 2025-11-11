import os
import json
import discord
from discord import app_commands
from discord.ext import commands
from googletrans import Translator
from dotenv import load_dotenv

# -----------------------------
# 環境変数からトークン取得
# -----------------------------
load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")

# -----------------------------
# Bot初期化
# -----------------------------
intents = discord.Intents.default()
client = commands.Bot(command_prefix="!", intents=intents)
translator = Translator()

# -----------------------------
# 国旗＋言語名
# -----------------------------
LANG_FLAGS = {
    "en": "🇺🇸 英語",
    "ja": "🇯🇵 日本語",
    "zh-cn": "🇨🇳 中国語（簡体字）",
    "ko": "🇰🇷 韓国語",
    "es": "🇪🇸 スペイン語",
    "fr": "🇫🇷 フランス語",
    "de": "🇩🇪 ドイツ語",
    "ru": "🇷🇺 ロシア語",
    "it": "🇮🇹 イタリア語",
    "pt": "🇵🇹 ポルトガル語",
    "vi": "🇻🇳 ベトナム語",
    "id": "🇮🇩 インドネシア語",
    "th": "🇹🇭 タイ語",
    "ar": "🇸🇦 アラビア語",
}

# -----------------------------
# 翻訳設定管理
# -----------------------------
SETTINGS_FILE = "languages.json"

def load_languages():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_languages():
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(channel_languages, f, ensure_ascii=False, indent=2)

channel_languages = load_languages()

# -----------------------------
# /setlang コマンド
# -----------------------------
@client.tree.command(name="setlang", description="翻訳設定を管理します（ON/OFF/変更/確認）")
@app_commands.describe(
    mode="翻訳モード（on/off/show）を指定してください",
    language="翻訳先の言語コード（例: en, ja, zh-cn など）"
)
@app_commands.choices(
    mode=[
        app_commands.Choice(name="🟢 翻訳ON", value="on"),
        app_commands.Choice(name="🔴 翻訳OFF", value="off"),
        app_commands.Choice(name="ℹ️ 設定確認", value="show")
    ]
)
async def setlang(
    interaction: discord.Interaction,
    mode: app_commands.Choice[str],
    language: str = None
):
    channel_id = str(interaction.channel.id)

    try:
        if mode.value == "on":
            if not language:
                await interaction.response.send_message("⚠️ 言語コードを指定してください（例: `/setlang on en`）")
                return

            channel_languages[channel_id] = {"enabled": True, "lang": language.lower()}
            save_languages()
            lang_label = LANG_FLAGS.get(language.lower(), language.upper())
            await interaction.response.send_message(f"✅ 自動翻訳を有効化しました（{lang_label}）")

        elif mode.value == "off":
            if channel_id in channel_languages:
                channel_languages[channel_id]["enabled"] = False
                save_languages()
                await interaction.response.send_message("🛑 自動翻訳を無効化しました。")
            else:
                await interaction.response.send_message("⚠️ すでに翻訳は無効です。")

        elif mode.value == "show":
            if channel_id in channel_languages:
                data = channel_languages[channel_id]
                status = "🟢 有効" if data.get("enabled") else "🔴 無効"
                lang = data.get("lang", "未設定")
                lang_label = LANG_FLAGS.get(lang, lang.upper())
                await interaction.response.send_message(
                    f"📊 現在の設定：\n状態：{status}\n翻訳先：{lang_label}"
                )
            else:
                await interaction.response.send_message("ℹ️ このチャンネルでは翻訳設定がまだありません。")

    except Exception as e:
        await interaction.response.send_message(f"⚠️ エラー：\n```\n{e}\n```")

# -----------------------------
# 自動翻訳イベント
# -----------------------------
@client.event
async def on_message(message):
    if message.author.bot or message.embeds:
        return  # Bot自身や翻訳済みEmbedは無視

    channel_id = str(message.channel.id)
    if channel_id not in channel_languages:
        return

    settings = channel_languages[channel_id]
    if not settings.get("enabled"):
        return

    lang = settings.get("lang", "en")

    try:
        translated = translator.translate(message.content, dest=lang)
        # 元言語 = 翻訳先ならスキップ
        if translated.src.lower() == lang.lower():
            return

        lang_label = LANG_FLAGS.get(lang, lang)
        embed = discord.Embed(
            title=f"🌐 翻訳結果 [{lang_label}]",
            description=translated.text,
            color=0x1E90FF
        )
        embed.set_footer(text=f"翻訳元: {translated.src}")
        await message.channel.send(embed=embed)

    except Exception as e:
        await message.channel.send(f"⚠️ 翻訳中にエラーが発生しました：{e}")

# -----------------------------
# 起動
# -----------------------------
@client.event
async def on_ready():
    await client.tree.sync()
    print(f"✅ ログイン完了: {client.user}")

client.run(TOKEN)
