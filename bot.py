import os
import threading
import discord
from discord.ext import commands
from flask import Flask

# 1. 建立一個簡單的 Flask 網頁伺服器（讓 Render 和 UptimeRobot 隨時可以 Ping）
app = Flask("")


@app.route("/")
def home():
  return "Bot is running!"


def run_web():
  # Render 會透過環境變數指定 Port，若沒有則預設使用 8080
  port = int(os.environ.get("PORT", 8080))
  app.run(host="0.0.0.0", port=port)


# 2. 啟動網頁伺服器的執行緒
def keep_alive():
  t = threading.Thread(target=run_web)
  t.start()


# 3. 你的 Discord 機器人設定
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
  print(f"目前登入身分 --> {bot.user}")


# 4. 主程式執行
if __name__ == "__main__":
  # 先啟動網頁伺服器
  keep_alive()

  # 啟動 Discord 機器人 (請確保你有在 Render 的 Environment 設定 DISCORD_TOKEN)
  TOKEN = os.environ.get("DISCORD_TOKEN")
  bot.run(TOKEN)
