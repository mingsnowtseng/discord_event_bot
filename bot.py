import os
import sqlite3
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
DB_PATH = "events.db"

# 初始化資料庫
def init_db():
    with sqlite3.connect(DB_PATH) as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS events (
                message_id INTEGER PRIMARY KEY,
                channel_id INTEGER NOT NULL,
                activity TEXT NOT NULL,
                datetime_text TEXT NOT NULL,
                category TEXT NOT NULL
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS members (
                message_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                status TEXT NOT NULL,
                PRIMARY KEY (message_id, user_id)
            )
        """)

init_db()

intents = discord.Intents.default()
client = commands.Bot(command_prefix="!", intents=intents)

class EventView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="出席", style=discord.ButtonStyle.green, emoji="✅", custom_id="attend_btn")
    async def attend(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_action(interaction, "出席")

    @discord.ui.button(label="請假", style=discord.ButtonStyle.red, emoji="❌", custom_id="leave_btn")
    async def leave(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_action(interaction, "請假")

    @discord.ui.button(label="再看看", style=discord.ButtonStyle.blurple, emoji="👀", custom_id="maybe_btn")
    async def maybe(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_action(interaction, "再看看")

    async def handle_action(self, interaction: discord.Interaction, action_type: str):
        msg_id = interaction.message.id
        user_id = interaction.user.id

        with sqlite3.connect(DB_PATH) as con:
            cur = con.cursor()
            cur.execute("SELECT status FROM members WHERE message_id = ? AND user_id = ?", (msg_id, user_id))
            row = cur.fetchone()

            if row:
                current_status = row[0]
                if current_status == action_type:
                    # 再次點擊相同按鈕即取消
                    cur.execute("DELETE FROM members WHERE message_id = ? AND user_id = ?", (msg_id, user_id))
                    msg = f"已取消您的「{action_type}」狀態。"
                else:
                    # 切換狀態
                    cur.execute("UPDATE members SET status = ? WHERE message_id = ? AND user_id = ?", (action_type, msg_id, user_id))
                    msg = f"已將您的狀態切換為：「{action_type}」。"
            else:
                cur.execute("INSERT INTO members (message_id, user_id, status) VALUES (?, ?, ?)", (msg_id, user_id, action_type))
                msg = f"登記成功：{action_type}！"
            con.commit()

        await update_event_message(interaction.message)
        await interaction.response.send_message(msg, ephemeral=True)

async def update_event_message(message: discord.Message):
    msg_id = message.id
    with sqlite3.connect(DB_PATH) as con:
        cur = con.cursor()
        cur.execute("SELECT activity, datetime_text, category FROM events WHERE message_id = ?", (msg_id,))
        event = cur.fetchone()
        if not event:
            return

        activity, dt, category = event
        cur.execute("SELECT user_id, status FROM members WHERE message_id = ?", (msg_id,))
        members = cur.fetchall()

    attend_list = [f"• <@{uid}>" for uid, status in members if status == "出席"]
    leave_list = [f"• <@{uid}>" for uid, status in members if status == "請假"]
    maybe_list = [f"• <@{uid}>" for uid, status in members if status == "再看看"]

    embed = discord.Embed(title=f"⚔️ 約戰登記活動", color=discord.Color.blue())
    embed.add_field(name="活動", value=activity, inline=False)
    embed.add_field(name="日期", value=dt, inline=False)
    embed.add_field(name="分類", value=category, inline=False)
    embed.add_field(name=f"✅ 出席 ({len(attend_list)})", value="\n".join(attend_list) if attend_list else "目前無人登記", inline=False)
    embed.add_field(name=f"❌ 請假 ({len(leave_list)})", value="\n".join(leave_list) if leave_list else "目前無人請假", inline=False)
    embed.add_field(name=f"👀 再看看 ({len(maybe_list)})", value="\n".join(maybe_list) if maybe_list else "目前無人", inline=False)

    await message.edit(embed=embed, view=EventView())

@client.event
async def on_ready():
    client.add_view(EventView())
    try:
        await client.tree.sync()
    except Exception as e:
        print(e)
    print(f"機器人已登入：{client.user}")

@client.tree.command(name="create_event", description="建立新的公告")
@app_commands.describe(activity="活動名稱", datetime_text="日期與時間 (例如 2026-10-25 20:00)", category="分類")
@app_commands.choices(category=[
    app_commands.Choice(name="拓荒", value="拓荒"),
    app_commands.Choice(name="一般打本", value="一般打本")
])
async def create_event(interaction: discord.Interaction, activity: str, datetime_text: str, category: str):
    await interaction.response.defer(ephemeral=True)
    
    embed = discord.Embed(title=f"⚔️ 約戰登記活動", color=discord.Color.blue())
    embed.add_field(name="活動", value=activity, inline=False)
    embed.add_field(name="日期", value=datetime_text, inline=False)
    embed.add_field(name="分類", value=category, inline=False)
    embed.add_field(name="✅ 出席 (0)", value="目前無人登記", inline=False)
    embed.add_field(name="❌ 請假 (0)", value="目前無人請假", inline=False)
    embed.add_field(name="👀 再看看 (0)", value="目前無人", inline=False)

    message = await interaction.channel.send(embed=embed, view=EventView())
    
    with sqlite3.connect(DB_PATH) as con:
        con.execute("INSERT INTO events VALUES (?, ?, ?, ?, ?)", 
                    (message.id, interaction.channel_id, activity, datetime_text, category))
        con.commit()

    await interaction.followup.send("約戰公告建立成功！", ephemeral=True)

client.run(TOKEN)