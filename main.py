import discord
from discord.ext import commands
from discord import app_commands
import os
import json
from googletrans import Translator

# =====================================================
# 基本設定
# =====================================================
TOKEN = os.environ['DISCORD_BOT_TOKEN']
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
bot = commands.Bot(command_prefix="/", intents=intents)

translator = Translator()

# =====================================================
# 永続保存ファイル設定
# =====================================================
SETTINGS_FILE = "data/settings.json"
os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)

def load_settings():
    """JSONファイルからチャンネル設定を読み込み"""
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            print("⚠ settings.json が壊れていました。初期化します。")
            return {}
    return {}

def save_settings():
    """現在の設定をJSONに保存"""
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(channel_lang_settings, f, ensure_ascii=False, indent=2)

# 起動時に読み込み
channel_lang_settings = load_settings()

# =====================================================
# サポート言語（国旗付き）
# =====================================================
supported_languages = {
    "ja": "🇯🇵 日本語",
    "en": "🇺🇸 英語",
    "zh-cn": "🇨🇳 中国語（簡体）",
    "zh-tw": "🇹🇼 中国語（繁体）",
    "ko": "🇰🇷 韓国語",
    "fr": "🇫🇷 フランス語",
    "de": "🇩🇪 ドイツ語",
    "es": "🇪🇸 スペイン語",
    "vi": "🇻🇳 ベトナム語"
}

# =====================================================
# 起動時の処理
# =====================================================
@bot.event
async def on_ready():
    print(f"✅ ログイン完了: {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"✅ スラッシュコマンド同期完了: {len(synced)}件")
    except Exception as e:
        print(f"❌ コマンド同期エラー: {e}")

# =====================================================
# /setlang コマンド（翻訳先の言語を設定・複数選択可）
# =====================================================
@bot.tree.command(name="setlang", description="翻訳先の言語を設定します（複数選択可）")
async def setlang(interaction: discord.Interaction):
    options = [
        discord.SelectOption(label=f"{supported_languages[code]}", value=code)
        for code in supported_languages.keys()
    ]

    select = discord.ui.Select(placeholder="翻訳先の言語を選んでください（複数選択可）",
                               min_values=1,
                               max_values=len(options),
                               options=options)

    async def select_callback(interaction2: discord.Interaction):
        selected_langs = select.values
        channel_lang_settings[str(interaction.channel.id)] = selected_langs
        save_settings()  # 💾 永続保存
        selected_flags = " ".join([supported_languages[l].split()[0] for l in selected_langs])
        await interaction2.response.edit_message(
            content=f"✅ 翻訳先を設定しました：{selected_flags}",
            view=None
        )

    select.callback = select_callback
    view = discord.ui.View()
    view.add_item(select)
    await interaction.response.send_message("翻訳先を選択してください：", view=view, ephemeral=True)

# =====================================================
# /help コマンド（使い方表示）
# =====================================================
@bot.tree.command(name="help", description="翻訳BOTの使い方を表示します")
async def help_command(interaction: discord.Interaction):
    help_text = (
        "🌐 **翻訳BOTの使い方**\n\n"
        "🗣️ **メッセージ翻訳**\n"
        "　指定チャンネルに投稿されたメッセージを自動で翻訳します。\n"
        "　自分の発言は翻訳されません。\n\n"
        "⚙️ **コマンド一覧**\n"
        "　`/setlang`：翻訳先言語を設定（複数選択可）\n"
        "　`/help`：この説明を表示\n\n"
        "💾 設定はチャンネルごとに保存され、Render再起動後も維持されます。"
    )
    await interaction.response.send_message(help_text, ephemeral=True)

# =====================================================
# メッセージ受信 → 翻訳処理
# =====================================================
@bot.event
async def on_message(message):
    if message.author.bot:
        return  # BOT自身の発言は無視
    if str(message.channel.id) not in channel_lang_settings:
        return  # 言語設定がないチャンネルでは翻訳しない

    target_langs = channel_lang_settings[str(message.channel.id)]
    for lang in target_langs:
        translated = translator.translate(message.content, dest=lang)
        flag = supported_languages[lang].split()[0]
        await message.channel.send(f"{flag} {translated.text}")

# =====================================================
# 実行
# =====================================================
bot.run(TOKEN)
