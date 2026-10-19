import os
import threading
import discord
from discord import app_commands
from discord.ext import commands
from flask import Flask

# ================= 1. 建立 Flask 網頁伺服器 (防止 Render 關閉網頁就斷線) =================
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


# ================= 3. 打本登記的按鈕與互動介面 =================
class EventView(discord.ui.View):

  def __init__(self):
    super().__init__(timeout=None)
    # 用字典儲存各個狀態的人員名單 (儲存 Member 物件)
    self.participants = {"出席": [], "外找": [], "請假": [], "再看看": []}

  async def update_status(
      self, interaction: discord.Interaction, target_status: str
  ):
    user = interaction.user

    # 1. 先從所有清單中移除該使用者 (確保不會同時出現在多個分類)
    for status in self.participants:
      self.participants[status] = [
          u for u in self.participants[status] if u.id != user.id
      ]

    # 2. 將使用者加入到點擊的新分類清單中
    self.participants[target_status].append(user)

    # 3. 重新建立 Embed 內容
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

      # 加上對應的符號
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

    # 4. 更新訊息介面
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
    # 自動同步斜線指令到 Discord
    synced = await bot.tree.sync()
    print(f"成功同步了 {len(synced)} 個斜線指令")
  except Exception as e:
    print(f"同步指令失敗: {e}")


# ================= 6. 執行主程式 =================
if __name__ == "__main__":
  # 先啟動背景的網頁伺服器
  keep_alive()

  # 取得環境變數中的 Token 並啟動機器人
  TOKEN = os.environ.get("DISCORD_TOKEN")
  bot.run(TOKEN)
