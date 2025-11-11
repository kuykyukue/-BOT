import discord
from discord.ext import commands
from flask import Flask
from threading import Thread
from deep_translator import GoogleTranslator
import os

# ---- Flask (Render用 keep-alive) ----
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

def run_web():
    app.run(host="0.0.0.0", port=8080)

Thread(target=run_web).start()

# ---- Discord Bot設定 ----
intents = discord.Intents.default()
intents.message_content = True
intents.messages = True
bot = commands.Bot(command_prefix="/", intents=intents)

# ---- データ管理 ----
auto_translate_channels = set()  # 自動翻訳ONチャンネル
channel_lang_settings = {}       # {channel_id: [翻訳先言語]}
translated_message_map = {}      # {元メッセージID: [翻訳メッセージID,...]}

supported_languages = {
    "en": "🇺🇸 English",
    "ja": "🇯🇵 Japanese",
    "ko": "🇰🇷 Korean",
    "vi": "🇻🇳 Vietnamese",
    "es": "🇪🇸 Spanish"
}

# ---- メッセージ翻訳 ----
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if message.channel.id in auto_translate_channels and message.channel.id in channel_lang_settings:
        langs = channel_lang_settings[message.channel.id]
        translated_ids = []

        for lang in langs:
            try:
                translated = GoogleTranslator(source='auto', target=lang).translate(message.content)
                sent_msg = await message.channel.send(f"{supported_languages[lang].split()[0]} {translated}")
                translated_ids.append(sent_msg.id)
            except Exception as e:
                await message.channel.send(f"⚠️ 翻訳エラー: {e}")

        # 翻訳されたメッセージのIDを保存（削除連動用）
        if translated_ids:
            translated_message_map[message.id] = translated_ids

    await bot.process_commands(message)

# ---- 元メッセージ削除時の連動削除 ----
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

# ---- /auto ----
@bot.tree.command(name="auto", description="このチャンネルの自動翻訳をON/OFFします")
async def auto(interaction: discord.Interaction):
    channel_id = interaction.channel.id
    if channel_id in auto_translate_channels:
        auto_translate_channels.remove(channel_id)
        await interaction.response.send_message("❌ このチャンネルの自動翻訳をオフにしました。", ephemeral=True)
    else:
        auto_translate_channels.add(channel_id)
        await interaction.response.send_message("✅ このチャンネルの自動翻訳をオンにしました。", ephemeral=True)

# ---- /setlang ----
@bot.tree.command(name="setlang", description="翻訳先の言語を設定します（複数選択可）")
async def setlang(interaction: discord.Interaction):
    options = [
        discord.SelectOption(label=name, value=code, emoji=flag.split()[0])
        for code, flag in supported_languages.items()
    ]

    select = discord.ui.Select(
        placeholder="翻訳先の言語を選択してください（複数選択可）",
        min_values=1,
        max_values=len(options),
        options=options
    )

    async def select_callback(interaction2: discord.Interaction):
        selected_langs = select.values
        channel_lang_settings[interaction.channel.id] = selected_langs
        selected_flags = " ".join([supported_languages[l].split()[0] for l in selected_langs])
        await interaction2.response.edit_message(
            content=f"✅ 翻訳先を設定しました：{selected_flags}",
            view=None
        )

    select.callback = select_callback
    view = discord.ui.View()
    view.add_item(select)
    await interaction.response.send_message("🌐 翻訳先を選んでください：", view=view, ephemeral=True)

# ---- /help ----
@bot.tree.command(name="help", description="Botの使い方を表示します")
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🌍 翻訳Bot 操作ガイド",
        description="このBotはチャンネル内の発言を自動で翻訳します。",
        color=0x00BFFF
    )
    embed.add_field(
        name="/auto",
        value="チャンネルごとに自動翻訳をON/OFFします。",
        inline=False
    )
    embed.add_field(
        name="/setlang",
        value="翻訳先の言語を選択します。（複数選択可能）",
        inline=False
    )
    embed.add_field(
        name="/help",
        value="この説明を表示します。",
        inline=False
    )
    embed.set_footer(text="💡 自分の発言は翻訳されません。元メッセージ削除時に翻訳文も消えます。")

    await interaction.response.send_message(embed=embed, ephemeral=True)

# ---- 起動 ----
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"✅ Logged in as {bot.user}")

bot.run(os.environ["DISCORD_BOT_TOKEN"])
