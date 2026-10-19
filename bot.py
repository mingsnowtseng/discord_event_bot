import os
import sqlite3
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
DB_PATH = "events.db"

# --- 假網頁伺服器（用來應付 Render 的 Port 檢查，避免報錯） ---
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive!")

def run_web():
    server = HTTPServer(('0.0.0.0', 10000), SimpleHandler)
    server.serve_forever()

# 讓網頁伺服器在背景獨立運作，不影響 Discord 機器人
threading.Thread(target=run_web, daemon=True).start()
# -------------------------------------------------------------

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
                class_name TEXT,
                PRIMARY KEY (message_id, user_id)
            )
        """)

init_db()

intents = discord.Intents.default()
client = commands.Bot(command_prefix="!", intents=intents)

# 職業選擇介面 (點擊出席後跳出)
class ClassSelectView(discord.ui.View):
    def __init__(self, original_message: discord.Message):
        super().__init__(timeout=60)
        self.original_message = original_message

    async def save_attendance(self, interaction: discord.Interaction, class_name: str):
        msg_id = self.original_message.id
        user_id = interaction.user.id
        status = "出席"

        with sqlite3.connect(DB_PATH) as con:
            cur = con.cursor()
            cur.execute("SELECT status, class_name FROM members WHERE message_id = ? AND user_id = ?", (msg_id, user_id))
            row = cur.fetchone()

            if row and row[0] == status and row[1] == class_name:
                cur.execute("DELETE FROM members WHERE message_id = ? AND user_id = ?", (msg_id, user_id))
                msg = f"已取消您的「出席」狀態。"
            else:
                cur.execute("""
                    INSERT INTO members (message_id, user_id, status, class_name) 
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(message_id, user_id) 
                    DO UPDATE SET status = ?, class_name = ?
                """, (msg_id, user_id, status, class_name, status, class_name))
                msg = f"成功登記出席！職業：{class_name}"
            con.commit()

        await update_event_message(self.original_message)
        await interaction.response.send_message(msg, ephemeral=True)

    # 各職業按鈕 (保留你原本設定的愛心與顏色)
    @discord.ui.button(label="九靈 💜", style=discord.ButtonStyle.secondary, custom_id="cls_jiuling")
    async def jiuling(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.save_attendance(interaction, "九靈")

    @discord.ui.button(label="龍吟 💚", style=discord.ButtonStyle.success, custom_id="cls_longyin")
    async def longyin(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.save_attendance(interaction, "龍吟")

    @discord.ui.button(label="血河 💖", style=discord.ButtonStyle.danger, custom_id="cls_xuehe")
    async def xuehe(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.save_attendance(interaction, "血河")

    @discord.ui.button(label="鐵衣 🧡", style=discord.ButtonStyle.secondary, custom_id="cls_tieyi")
    async def tieyi(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.save_attendance(interaction, "鐵衣")

    @discord.ui.button(label="素問 🩷", style=discord.ButtonStyle.secondary, custom_id="cls_suwen")
    async def suwen(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.save_attendance(interaction, "素問")

    @discord.ui.button(label="碎夢 🩶", style=discord.ButtonStyle.primary, custom_id="cls_suimeng")
    async def suimeng(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.save_attendance(interaction, "碎夢")

    @discord.ui.button(label="潮光 💙", style=discord.ButtonStyle.primary, custom_id="cls_chaoguang")
    async def chaoguang(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.save_attendance(interaction, "潮光")

    @discord.ui.button(label="神相 🩵", style=discord.ButtonStyle.primary, custom_id="cls_shenxiang")
    async def shenxiang(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.save_attendance(interaction, "神相")

    @discord.ui.button(label="玄機 💛", style=discord.ButtonStyle.secondary, custom_id="cls_xuanji")
    async def xuanji(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.save_attendance(interaction, "玄機")

# 主頁面按鈕 (出席、請假、再看看)
class EventView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="出席", style=discord.ButtonStyle.green, emoji="✅", custom_id="attend_btn")
    async def attend(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = ClassSelectView(interaction.message)
        await interaction.response.send_message("請選擇你的職業：", view=view, ephemeral=True)

    @discord.ui.button(label="請假", style=discord.ButtonStyle.red, emoji="❌", custom_id="leave_btn")
    async def leave(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_simple_action(interaction, "請假")

    @discord.ui.button(label="再看看", style=discord.ButtonStyle.blurple, emoji="👀", custom_id="maybe_btn")
    async def maybe(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_simple_action(interaction, "再看看")

    async def handle_simple_action(self, interaction: discord.Interaction, action_type: str):
        msg_id = interaction.message.id
        user_id = interaction.user.id

        with sqlite3.connect(DB_PATH) as con:
            cur = con.cursor()
            cur.execute("SELECT status FROM members WHERE message_id = ? AND user_id = ?", (msg_id, user_id))
            row = cur.fetchone()

            if row and row[0] == action_type:
                cur.execute("DELETE FROM members WHERE message_id = ? AND user_id = ?", (msg_id, user_id))
                msg = f"已取消您的「{action_type}」狀態。"
            else:
                cur.execute("""
                    INSERT INTO members (message_id, user_id, status, class_name) 
                    VALUES (?, ?, ?, NULL)
                    ON CONFLICT(message_id, user_id) 
                    DO UPDATE SET status = ?, class_name = NULL
                """, (msg_id, user_id, action_type, action_type))
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
        cur.execute("SELECT user_id, status, class_name FROM members WHERE message_id = ?", (msg_id,))
        members = cur.fetchall()

    attend_list = [f"• <@{uid}>【{cname}】" for uid, status, cname in members if status == "出席"]
    leave_list = [f"• <@{uid}>" for uid, status, cname in members if status == "請假"]
    maybe_list = [f"• <@{uid}>" for uid, status, cname in members if status == "再看看"]

    embed = discord.Embed(title=f"⚔️ 打本登記活動", color=discord.Color.blue())
    embed.add_field(name="活動", value=activity, inline=False)
    embed.add_field(name="日期", value=dt, inline=False)
    embed.add_field(name="分類", value=category, inline=False)
    
    attend_text = "\n".join(attend_list) if attend_list else "目前無人登記"
    leave_text = "\n".join(leave_list) if leave_list else "目前無人請假"
    maybe_text = "\n".join(maybe_list) if maybe_list else "目前無人"

    embed.add_field(name=f"✅ 出席 ({len(attend_list)})", value=attend_text, inline=True)
    embed.add_field(name=f"❌ 請假 ({len(leave_list)})", value=leave_text, inline=True)
    embed.add_field(name=f"👀 再看看 ({len(maybe_list)})", value=maybe_text, inline=False)

    await message.edit(embed=embed, view=EventView())

@client.event
async def on_ready():
    client.add_view(EventView())
    try:
        await client.tree.sync()
    except Exception as e:
        print(e)
    print(f"機器人已登入：{client.user}")

@client.tree.command(name="create_event", description="建立新的打本公告")
@app_commands.describe(activity="活動名稱", datetime_text="日期與時間 (例如 2026-10-25 20:00)", category="分類")
@app_commands.choices(category=[
    app_commands.Choice(name="拓荒", value="拓荒"),
    app_commands.Choice(name="一般打本", value="一般打本")
])
async def create_event(interaction: discord.Interaction, activity: str, datetime_text: str, category: str):
    await interaction.response.defer(ephemeral=True)
    
    embed = discord.Embed(title=f"⚔️ 打本登記活動", color=discord.Color.blue())
    embed.add_field(name="活動", value=activity, inline=False)
    embed.add_field(name="日期", value=datetime_text, inline=False)
    embed.add_field(name="分類", value=category, inline=False)
    embed.add_field(name="✅ 出席 (0)", value="目前無人登記", inline=True)
    embed.add_field(name="❌ 請假 (0)", value="目前無人請假", inline=True)
    embed.add_field(name="👀 再看看 (0)", value="目前無人", inline=False)

    message = await interaction.channel.send(embed=embed, view=EventView())
    
    with sqlite3.connect(DB_PATH) as con:
        con.execute("INSERT INTO events VALUES (?, ?, ?, ?, ?)", 
                    (message.id, interaction.channel_id, activity, datetime_text, category))
        con.commit()

    await interaction.followup.send("打本公告建立成功！", ephemeral=True)

client.run(TOKEN)
