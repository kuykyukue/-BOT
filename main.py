import discord
from discord import app_commands
from discord.ext import commands
from googletrans import Translator
import json
import os

# 翻訳設定ファイル
SETTINGS_FILE = "translation_settings.json"

# 設定を読み込み
if os.path.exists(SETTINGS_FILE):
    with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
        settings = json.load(f)
else:
    settings = {}

# Bot設定
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
translator = Translator()

# 翻訳ON/OFF 切り替えコマンド
@bot.tree.command(name="toggletranslate", description="翻訳機能をON/OFFします。")
async def toggle_translate(interaction: discord.Interaction):
    guild_id = str(interaction.guild_id)
    settings.setdefault(guild_id, {"enabled": True, "from": "ja", "to": "en"})

    settings[guild_id]["enabled"] = not settings[guild_id]["enabled"]

    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)

    status = "✅ ON（翻訳有効）" if settings[guild_id]["enabled"] else "❌ OFF（翻訳停止）"
    await interaction.response.send_message(f"翻訳機能を切り替えました: {status}", ephemeral=True)

# 言語設定コマンド
@bot.tree.command(name="setlang", description="翻訳元言語と翻訳先言語を設定します。例: /setlang ja en")
@app_commands.describe(from_lang="翻訳元の言語コード", to_lang="翻訳先の言語コード")
async def set_language(interaction: discord.Interaction, from_lang: str, to_lang: str):
    guild_id = str(interaction.guild_id)
    settings.setdefault(guild_id, {"enabled": True})
    settings[guild_id]["from"] = from_lang
    settings[guild_id]["to"] = to_lang

    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)

    await interaction.response.send_message(
        f"🌍 翻訳言語を設定しました。\n　入力言語: `{from_lang}` → 出力言語: `{to_lang}`", ephemeral=True
    )

# メッセージ監視・翻訳処理
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    guild_id = str(message.guild.id)
    guild_settings = settings.get(guild_id)

    if guild_settings and guild_settings.get("enabled", True):
        src = guild_settings.get("from", "ja")
        dest = guild_settings.get("to", "en")

        try:
            result = translator.translate(message.content, src=src, dest=dest)
            # 絵文字を保持したまま翻訳文を表示
            await message.channel.send(
                f"💬 **翻訳 ({src} → {dest})**\n{result.text}"
            )
        except Exception as e:
            await message.channel.send(f"⚠️ 翻訳エラー: {e}")

# 起動時
@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
        print(f"✅ スラッシュコマンドを同期しました ({len(synced)} 個)")
    except Exception as e:
        print(f"❌ スラッシュコマンド同期エラー: {e}")
    print(f"🤖 ログイン完了: {bot.user}")

# Bot起動
bot.run(os.environ["DISCORD_TOKEN"])
