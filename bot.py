import os
import threading
import discord
from discord import app_commands
from discord.ext import commands
from flask import Flask

# ================= 1. 保持 Render 活躍的網頁伺服器 =================
app = Flask("")


@app.route("/")
def home():
  return "Bot is running!"


def run_web():
  port = int(os.environ.get("PORT", 8080))
  app.run(host="0.0.0.0", port=port)


def keep_alive():
  t = threading.Thread(target=run_web)
  t.start()


# ================= 2. Discord 機器人設定 =================
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)


# ================= 3. 打本登記按鈕與視圖類別 =================
class EventView(discord.ui.View):

  def __init__(self):
    super().__init__(timeout=None)
    # 儲存各個分類的人員名單
    self.participants = {"出席": [], "外找": [], "請假": [], "再看看": []}

  async def update_status(
      self, interaction: discord.Interaction, target_status: str
  ):
    user = interaction.user

    # 1. 從所有清單中移除該使用者（避免重複或留在舊分類）
    for status in self.participants:
      self.participants[status] = [
          u for u in self.participants[status] if u.id != user.id
      ]

    # 2. 將使用者加入點擊的新分類清單中
    self.participants[target_status].append(user)

    # 3. 重新建立 Embed 訊息內容
    embed = discord.Embed(
        title="⚔️ 打本登記活動", color=discord.Color.from_rgb(47, 49, 54)
    )
    embed.add_field(name="活動", value="打本", inline=False)
    embed.add_field(name="日期", value="10/19 9:30", inline=False)

    # 動態產生各個欄位與人數
    for status, users in self.participants.items():
      user_list_str = (
          "\n".join([f"• {u.mention}" for u in users]) if users else "目前無人"
      )

      if status == "出席":
        prefix = "✅"
      elif status == "外找":
        prefix = "⚠️"
      elif status == "請假":
        prefix = "❌"
      else:
        prefix = "👀"

      embed.add_field(
          name=f"{prefix} {status} ({len(users)})",
          value=user_list_str,
          inline=False,
      )

    total_attend = len(self.participants["出席"])
    embed.set_footer(text=f"總計出席人數：{total_attend} 人")

    # 4. 更新 Discord 上的訊息畫面
    await interaction.response.edit_message(embed=embed, view=self)

  @discord.ui.button(
      label="出席", style=discord.ButtonStyle.success, custom_id="btn_attend"
  )
  async def attend_button(
      self, interaction: discord.Interaction, button: discord.ui.Button
  ):
    await self.update_status(interaction, "出席")

  @discord.ui.button(
      label="外找", style=discord.ButtonStyle.secondary, custom_id="btn_external"
  )
  async def external_button(
      self, interaction: discord.Interaction, button: discord.ui.Button
  ):
    await self.update_status(interaction, "外找")

  @discord.ui.button(
      label="請假", style=discord.ButtonStyle.danger, custom_id="btn_leave"
  )
  async def leave_button(
      self, interaction: discord.Interaction, button: discord.ui.Button
  ):
    await self.update_status(interaction, "請假")

  @discord.ui.button(
      label="再看看", style=discord.ButtonStyle.blurple, custom_id="btn_maybe"
  )
  async def maybe_button(
      self, interaction: discord.Interaction, button: discord.ui.Button
  ):
    await self.update_status(interaction, "再看看")


# ================= 4. 斜線指令 (/create_event) =================
@bot.tree.command(name="create_event", description="建立打本登記活動")
async def create_event(interaction: discord.Interaction):
  embed = discord.Embed(
      title="⚔️ 打本登記活動", color=discord.Color.from_rgb(47, 49, 54)
  )
  embed.add_field(name="活動", value="打本", inline=False)
  embed.add_field(name="日期", value="10/19 9:30", inline=False)
  embed.add_field(name="✅ 出席 (0)", value="目前無人", inline=False)
  embed.add_field(name="⚠️ 外找 (0)", value="目前無人", inline=False)
  embed.add_field(name="❌ 請假 (0)", value="目前無人", inline=False)
  embed.add_field(name="👀 再看看 (0)", value="目前無人", inline=False)
  embed.set_footer(text="總計出席人數：0 人")

  view = EventView()
  await interaction.response.send_message(embed=embed, view=view)


# ================= 5. 機器人啟動事件 =================
@bot.event
async def on_ready():
  print(f"目前登入身分 --> {bot.user}")
  try:
    synced = await bot.tree.sync()
    print(f"成功同步了 {len(synced)} 個斜線指令")
  except Exception as e:
    print(f"同步指令失敗: {e}")


# ================= 6. 程式主入口 =================
if __name__ == "__main__":
  # 先啟動背景網頁服務（確保 Render 不會關閉）
  keep_alive()

  # 啟動 Discord 機器人
  TOKEN = os.environ.get("DISCORD_TOKEN")
  bot.run(TOKEN)
