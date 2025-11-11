import os
import json
import discord
from discord import app_commands
from discord.ext import commands
from googletrans import Translator

# ==========================
# 🌍 設定ファイル
# ==========================
LANG_FILE = "languages.json"
translator = Translator()

# ==========================
# 🏳️‍🌈 国旗＋言語名辞書
# ==========================
LANG_FLAGS = {
    "en": "🇺🇸 英語",
    "ja": "🇯🇵 日本語",
    "zh-cn": "🇨🇳 中国語（簡体字）",
    "ko": "🇰🇷 韓国語",
    "fr": "🇫🇷 フランス語",
    "es": "🇪🇸 スペイン語",
    "de": "🇩🇪 ドイツ語",
}

# ==========================
# 🎌 言語選択肢
# ==========================
LANG_CHOICES = [
    app_commands.Choice(name="🇺🇸 英語 (English)", value="en"),
    app_commands.Choice(name="🇯🇵 日本語 (Japanese)", value="ja"),
    app_commands.Choice(name="🇨🇳 中国語 (Chinese Simplified)", value="zh-cn"),
    app_commands.Choice(name="🇰🇷 韓国語 (Korean)", value="ko"),
    app_commands.Choice(name="🇫🇷 フランス語 (French)", value="fr"),
    app_commands.Choice(name="🇪🇸 スペイン語 (Spanish)", value="es"),
    app_commands.Choice(name="🇩🇪 ドイツ語 (German)", value="de"),
    app_commands.Choice(name="🛑 翻訳オフ (Off)", value="off"),
]

# ==========================
# 📁 言語設定の読み込み
# ==========================
if os.path.exists(LANG_FILE):
    with open(LANG_FILE, "r", encoding="utf-8") as f:
        channel_languages = json.load(f)
else:
    channel_languages = {}

def save_languages():
    """JSONファイルに保存"""
    with open(LANG_FILE, "w", encoding="utf-8") as f:
        json.dump(channel_languages, f, ensure_ascii=False, indent=2)

# ==========================
# 🤖 Bot初期化
# ==========================
intents = discord.Intents.all()
client = commands.Bot(command_prefix="!", intents=intents)

@client.event
async def on_ready():
    print(f"✅ ログイン成功: {client.user}")
    try:
        await client.tree.sync()
        print("🔁 スラッシュコマンドを同期しました。")
    except Exception as e:
        print(f"⚠️ コマンド同期エラー: {e}")

# ==========================
# 💡 /setlang コマンド
# ==========================
@client.tree.command(name="setlang", description="このチャンネルの翻訳先を設定します")
@app_commands.choices(language=LANG_CHOICES)
async def setlang(interaction: discord.Interaction, language: app_commands.Choice[str]):
    channel_id = str(interaction.channel.id)
    lang = language.value

    try:
        if lang == "off":
            if channel_id in channel_languages:
                del channel_languages[channel_id]
                save_languages()
                await interaction.response.send_message("🛑 このチャンネルの自動翻訳を無効化しました。")
            else:
                await interaction.response.send_message("⚠️ すでに翻訳は無効です。")
        else:
            channel_languages[channel_id] = lang
            save_languages()
            lang_label = LANG_FLAGS.get(lang, lang)
            await interaction.response.send_message(f"✅ 翻訳先を **{lang_label}** に設定しました。")

    except Exception as e:
        await interaction.response.send_message(f"⚠️ 設定中にエラーが発生しました: {e}")

# ==========================
# 🔍 /showlang コマンド
# ==========================
@client.tree.command(name="showlang", description="現在の翻訳先を表示します")
async def showlang(interaction: discord.Interaction):
    try:
        channel_id = str(interaction.channel.id)
        if channel_id in channel_languages:
            lang = channel_languages[channel_id]
            lang_label = LANG_FLAGS.get(lang, lang)
            await interaction.response.send_message(f"🌍 現在の翻訳先は **{lang_label}** です。")
        else:
            await interaction.response.send_message("ℹ️ このチャンネルでは翻訳が無効です。")
    except Exception as e:
        await interaction.response.send_message(f"⚠️ エラー: {e}")

# ==========================
# 💬 メッセージ自動翻訳
# ==========================
@client.event
async def on_message(message):
    if message.author.bot:
        return

    channel_id = str(message.channel.id)
    if channel_id in channel_languages:
        lang = channel_languages[channel_id]
        try:
            translated = translator.translate(message.content, dest=lang)
            if translated.text != message.content:
                lang_label = LANG_FLAGS.get(lang, lang)
                embed = discord.Embed(
                    title=f"🌐 翻訳結果 [{lang_label}]",
                    description=translated.text,
                    color=0x1E90FF
                )
                embed.set_footer(text=f"翻訳元: {translated.src}")
                await message.channel.send(embed=embed)
        except Exception as e:
            print(f"⚠️ 翻訳エラー: {e}")

    # commands.Botの場合、明示的に必要
    await client.process_commands(message)

# ==========================
# 🧱 エラーハンドリング
# ==========================
@client.event
async def on_error(event, *args, **kwargs):
    print(f"⚠️ イベントエラー発生: {event}")

@client.event
async def on_command_error(ctx, error):
    try:
        await ctx.send("⚠️ コマンド実行中にエラーが発生しました。")
    except:
        pass
    print(f"詳細: {error}")

# ==========================
# 🚀 起動
# ==========================
client.run(os.getenv("DISCORD_BOT_TOKEN"))
