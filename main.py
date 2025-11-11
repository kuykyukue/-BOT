import os
import json
import discord
from discord import app_commands
from discord.ext import commands
from deep_translator import GoogleTranslator
from flask import Flask
from threading import Thread

# ---- Flask (Render keep-alive) ----
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

def run_web():
    app.run(host="0.0.0.0", port=8080)

Thread(target=run_web).start()

# ---- Discord Bot 設定 ----
TOKEN = os.environ.get("DISCORD_BOT_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# ---- 設定ファイル ----
SETTINGS_FILE = "channel_settings.json"

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_settings():
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(channel_settings, f, ensure_ascii=False, indent=2)

channel_settings = load_settings()

# ---- サポート言語（国旗つき）----
supported_languages = {
    "en": "🇺🇸 English",
    "ja": "🇯🇵 Japanese",
    "ko": "🇰🇷 Korean",
    "vi": "🇻🇳 Vietnamese",
    "es": "🇪🇸 Spanish",
    "fr": "🇫🇷 French",
    "de": "🇩🇪 German",
    "zh": "🇨🇳 Chinese"
}

flag_only = {k: v.split()[0] for k, v in supported_languages.items()}

# ===============================
# /setlang コマンド（複数選択リスト対応）
# ===============================
@tree.command(name="setlang", description="翻訳先の言語を設定します（複数選択可）")
async def setlang(interaction: discord.Interaction):
    options = [
        discord.SelectOption(label=v, value=k)
        for k, v in supported_languages.items()
    ]

    select = discord.ui.Select(
        placeholder="翻訳したい言語を選んでください（複数可）",
        min_values=1,
        max_values=len(options),
        options=options
    )

    async def select_callback(interaction2: discord.Interaction):
        selected_langs = select.values
        channel_id = str(interaction.channel_id)

        # 保存
        channel_settings[channel_id] = {
            "langs": selected_langs,
            "auto": channel_settings.get(channel_id, {}).get("auto", False)
        }
        save_settings()

        flags = " ".join(flag_only[l] for l in selected_langs)
        await interaction2.response.edit_message(
            content=f"✅ 翻訳先を {flags} に設定しました！",
            view=None
        )

    select.callback = select_callback
    view = discord.ui.View()
    view.add_item(select)
    await interaction.response.send_message("🌐 翻訳したい言語を選んでください👇", view=view)

# ===============================
# /auto コマンド（ON/OFF切替）
# ===============================
@tree.command(name="auto", description="このチャンネルの自動翻訳をオン／オフします")
async def auto(interaction: discord.Interaction):
    channel_id = str(interaction.channel_id)

    if channel_id not in channel_settings:
        channel_settings[channel_id] = {"langs": ["en"], "auto": False}

    current = channel_settings[channel_id]["auto"]
    channel_settings[channel_id]["auto"] = not current
    save_settings()

    status = "✅ オン" if not current else "❌ オフ"
    await interaction.response.send_message(f"🌍 自動翻訳を {status} にしました！")

# ===============================
# /help コマンド（使い方）
# ===============================
@tree.command(name="help", description="このBotの使い方を表示します")
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🌐 翻訳Bot 使い方ガイド",
        color=0x1E90FF
    )
    embed.add_field(
        name="🗣️ `/setlang`",
        value="翻訳したい言語を**複数選択リスト**から選べます。\n例：🇯🇵🇺🇸🇻🇳🇪🇸",
        inline=False
    )
    embed.add_field(
        name="🌍 `/auto`",
        value="現在のチャンネルの自動翻訳を**オン／オフ**切り替えます。",
        inline=False
    )
    embed.add_field(
        name="💬 翻訳動作",
        value="・自分の発言は翻訳されません。\n・他のユーザーの発言が選択した言語に翻訳されます。\n・翻訳文には国旗が付きます。",
        inline=False
    )
    embed.add_field(
        name="💾 設定保存",
        value="設定は自動的に保存され、再起動後も保持されます。",
        inline=False
    )
    embed.set_footer(text="開発: ChatGPT翻訳Bot（Render対応版）")
    await interaction.response.send_message(embed=embed)

# ===============================
# メッセージ受信 → 翻訳処理
# ===============================
@bot.event
async def on_message(message):
    if message.author.bot:
        return  # 自分・他のBotは無視

    channel_id = str(message.channel.id)
    settings = channel_settings.get(channel_id, {"langs": ["en"], "auto": False})

    if not settings["auto"]:
        return

    langs = settings.get("langs", ["en"])

    for lang in langs:
        try:
            translated = GoogleTranslator(source='auto', target=lang).translate(message.content)
            if translated and translated != message.content:
                await message.channel.send(f"{flag_only.get(lang, lang)} {translated}")
        except Exception as e:
            print(f"⚠️ 翻訳エラー: {e}")

# ===============================
# 起動イベント
# ===============================
@bot.event
async def on_ready():
    await tree.sync()
    print(f"✅ Logged in as {bot.user}")
    print("📂 設定読み込み:", channel_settings)

if __name__ == "__main__":
    bot.run(TOKEN)
