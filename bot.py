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

threading.Thread(target=run_web, daemon=True).start()
# -------------------------------------------------------------

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
                identifier TEXT NOT NULL,
                status TEXT NOT NULL,
                class_name TEXT,
                PRIMARY KEY (message_id, identifier)
            )
        """)

init_db()

intents = discord.Intents.default()
client = commands.Bot(command_prefix="!", intents=intents)

# 點擊出席後跳出的「職業選擇私密介面」
class ClassSelectModalView(discord.ui.View):
    def __init__(self, original_message: discord.Message):
        super().__init__(timeout=60)
        self.original_message = original_message

    async def save_class(self, interaction: discord.Interaction, class_name: str):
        msg_id = self.original_message.id
        identifier = str(interaction.user.id)

        with sqlite3.connect(DB_PATH) as con:
            cur = con.cursor()
            # 確保玩家已經是出席狀態
            cur.execute("SELECT status FROM members WHERE message_id = ? AND identifier = ?", (msg_id, identifier))
            row = cur.fetchone()

            if not row or row[0] != "出席":
                await interaction.response.send_message("❌ 請先點擊主選單的「出席」後，才能選擇職業！", ephemeral=True)
                return

            # 更新職業
            cur.execute("""
                UPDATE members SET class_name = ? WHERE message_id = ? AND identifier = ?
            """, (class_name, msg_id, identifier))
            con.commit()

        await update_event_message(self.original_message)
        await interaction.response.send_message(f"✅ 成功選擇職業：【{class_name}】", ephemeral=True)

    @discord.ui.button(label="九靈 💜", style=discord.ButtonStyle.secondary, custom_id="cls_jiuling", row=0)
    async def jiuling(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.save_class(interaction, "九靈")

    @discord.ui.button(label="龍吟 💚", style=discord.ButtonStyle.secondary, custom_id="cls_longyin", row=0)
    async def longyin(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.save_class(interaction, "龍吟")

    @discord.ui.button(label="血河 💖", style=discord.ButtonStyle.secondary, custom_id="cls_xuehe", row=0)
    async def xuehe(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.save_class(interaction, "血河")

    @discord.ui.button(label="鐵衣 🧡", style=discord.ButtonStyle.secondary, custom_id="cls_tieyi", row=0)
    async def tieyi(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.save_class(interaction, "鐵衣")

    @discord.ui.button(label="素問 🩷", style=discord.ButtonStyle.secondary, custom_id="cls_suwen", row=1)
    async def suwen(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.save_class(interaction, "素問")

    @discord.ui.button(label="碎夢 🩶", style=discord.ButtonStyle.secondary, custom_id="cls_suimeng", row=1)
    async def suimeng(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.save_class(interaction, "碎夢")

    @discord.ui.button(label="潮光 💙", style=discord.ButtonStyle.secondary, custom_id="cls_chaoguang", row=1)
    async def chaoguang(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.save_class(interaction, "潮光")

    @discord.ui.button(label="神相 🩵", style=discord.ButtonStyle.secondary, custom_id="cls_shenxiang", row=2)
    async def shenxiang(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.save_class(interaction, "神相")

    @discord.ui.button(label="玄機 💛", style=discord.ButtonStyle.secondary, custom_id="cls_xuanji", row=2)
    async def xuanji(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.save_class(interaction, "玄機")

# 公告下方的常駐主選單（只保留：出席、請假、再看看）
class EventView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def handle_main_action(self, interaction: discord.Interaction, status: str):
        msg_id = interaction.message.id
        identifier = str(interaction.user.id)

        with sqlite3.connect(DB_PATH) as con:
            cur = con.cursor()
            cur.execute("SELECT status FROM members WHERE message_id = ? AND identifier = ?", (msg_id, identifier))
            row = cur.fetchone()

            # 如果重複點擊相同的狀態，則取消
            if row and row[0] == status:
                cur.execute("DELETE FROM members WHERE message_id = ? AND identifier = ?", (msg_id, identifier))
                msg = f"已取消您的登記狀態。"
                con.commit()
                await update_event_message(interaction.message)
                await interaction.response.send_message(msg, ephemeral=True)
                return
            else:
                # 登記狀態（如果是出席，預設不帶職業或清空職業，等待玩家點選職業）
                cur.execute("""
                    INSERT INTO members (message_id, identifier, status, class_name) 
                    VALUES (?, ?, ?, NULL)
                    ON CONFLICT(message_id, identifier) 
                    DO UPDATE SET status = ?, class_name = NULL
                """, (msg_id, identifier, status, status))
                con.commit()

        await update_event_message(interaction.message)

        # 如果點擊的是「出席」，則跳出私密視窗讓玩家選擇職業
        if status == "出席":
            view = ClassSelectModalView(interaction.message)
            await interaction.response.send_message("✅ 已登記出席！請點擊下方按鈕選擇你的職業：", view=view, ephemeral=True)
        else:
            await interaction.response.send_message(f"成功切換至：【{status}】", ephemeral=True)

    @discord.ui.button(label="出席", style=discord.ButtonStyle.secondary, emoji="✅", custom_id="attend_btn")
    async def attend(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_main_action(interaction, "出席")

    @discord.ui.button(label="請假", style=discord.ButtonStyle.secondary, emoji="❌", custom_id="leave_btn")
    async def leave(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_main_action(interaction, "請假")

    @discord.ui.button(label="再看看", style=discord.ButtonStyle.secondary, emoji="👀", custom_id="maybe_btn")
    async def maybe(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_main_action(interaction, "再看看")

async def update_event_message(message: discord.Message):
    msg_id = message.id
    with sqlite3.connect(DB_PATH) as con:
        cur = con.cursor()
        cur.execute("SELECT activity, datetime_text, category FROM events WHERE message_id = ?", (msg_id,))
        event = cur.fetchone()
        if not event:
            return

        activity, dt, category = event
        cur.execute("SELECT identifier, status, class_name FROM members WHERE message_id = ?", (msg_id,))
        members = cur.fetchall()

    attend_list = []
    leave_list = []
    maybe_list = []

    for identifier, status, cname in members:
        if identifier.isdigit():
            user_display = f"<@{identifier}>"
        else:
            user_display = f"**{identifier}** (手動)"

        if status == "出席":
            if cname:
                attend_list.append(f"• 【{cname}】 {user_display}")
            else:
                attend_list.append(f"• {user_display} (尚未選擇職業)")
        elif status == "請假":
            leave_list.append(f"• {user_display}")
        elif status == "再看看":
            maybe_list.append(f"• {user_display}")

    embed = discord.Embed(title=f"⚔️ 打本登記活動", color=discord.Color.blue())
    embed.add_field(name="活動", value=activity, inline=False)
    embed.add_field(name="日期", value=dt, inline=False)
    embed.add_field(name="分類", value=category, inline=False)
    
    if attend_list:
        attend_text = "\n".join(attend_list) + f"\n\n**總計出席人數：{len(attend_list)} 人**"
    else:
        attend_text = "目前無人登記\n\n**總計出席人數：0 人**"

    leave_text = "\n".join(leave_list) if leave_list else "目前無人請假"
    maybe_text = "\n".join(maybe_list) if maybe_list else "目前無人"

    embed.add_field(name=f"✅ 出席 ({len(attend_list)})", value=attend_text, inline=False)
    embed.add_field(name=f"❌ 請假 ({len(leave_list)})", value=leave_text, inline=False)
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
    embed.add_field(name="✅ 出席 (0)", value="目前無人登記\n\n**總計出席人數：0 人**", inline=False)
    embed.add_field(name="❌ 請假 (0)", value="目前無人請假", inline=False)
    embed.add_field(name="👀 再看看 (0)", value="目前無人", inline=False)

    message = await interaction.channel.send(embed=embed, view=EventView())
    
    with sqlite3.connect(DB_PATH) as con:
        con.execute("INSERT INTO events VALUES (?, ?, ?, ?, ?)", 
                    (message.id, interaction.channel_id, activity, datetime_text, category))
        con.commit()

    await interaction.followup.send("打本公告建立成功！", ephemeral=True)

@client.tree.command(name="add_member", description="手動幫未在伺服器內的人員登記出席")
@app_commands.describe(message_id="公告訊息ID", name="人員遊戲名稱", class_name="職業")
@app_commands.choices(class_name=[
    app_commands.Choice(name="九靈", value="九靈"),
    app_commands.Choice(name="龍吟", value="龍吟"),
    app_commands.Choice(name="血河", value="血河"),
    app_commands.Choice(name="鐵衣", value="鐵衣"),
    app_commands.Choice(name="素問", value="素問"),
    app_commands.Choice(name="碎夢", value="碎夢"),
    app_commands.Choice(name="潮光", value="潮光"),
    app_commands.Choice(name="神相", value="神相"),
    app_commands.Choice(name="玄機", value="玄機"),
])
async def add_member(interaction: discord.Interaction, message_id: str, name: str, class_name: str):
    await interaction.response.defer(ephemeral=True)
    
    try:
        msg_id = int(message_id)
        target_message = await interaction.channel.fetch_message(msg_id)
    except Exception:
        await interaction.followup.send("找不到該則訊息 ID，請確認是否在同一個頻道中！", ephemeral=True)
        return

    with sqlite3.connect(DB_PATH) as con:
        cur = con.cursor()
        cur.execute("SELECT activity FROM events WHERE message_id = ?", (msg_id,))
        if not cur.fetchone():
            await interaction.followup.send("此訊息不是約戰公告，無法登記！", ephemeral=True)
            return

        cur.execute("""
            INSERT INTO members (message_id, identifier, status, class_name) 
            VALUES (?, ?, '出席', ?)
            ON CONFLICT(message_id, identifier) 
            DO UPDATE SET status = '出席', class_name = ?
        """, (msg_id, name, class_name, class_name))
        con.commit()

    await update_event_message(target_message)
    await interaction.followup.send(f"已成功幫【{name} ({class_name})】手動登記出席！", ephemeral=True)

client.run(TOKEN)
