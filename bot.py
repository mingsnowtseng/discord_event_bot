import discord

class EventView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        
        # 假設用一個字典來儲存各個狀態的人員名單
        # 格式範例: {"出席": [], "外找": [], "請假": [], "再看看": []}
        self.participants = {
            "出席": [],
            "外找": [],
            "請假": [],
            "再看看": []
        }

    # 共用的更新狀態邏輯
    async def update_status(self, interaction: discord.Interaction, target_status: str):
        user = interaction.user
        # 取得使用者的顯示名稱或 Mention (看你原本是用哪一種，這裡用 mention)
        user_mention = user.mention 

        # 1. 先從所有清單中移除該使用者（避免重複或留在舊分類）
        for status in self.participants:
            # 移除包含該使用者的項目（注意：如果清單內存的是物件或字串，要對應修改）
            self.participants[status] = [u for u in self.participants[status] if u.id != user.id]

        # 2. 將使用者加入到點擊的新分類清單中
        self.participants[target_status].append(user)

        # 3. 重新建立你的 Embed 內容
        embed = discord.Embed(title="⚔️ 打本登記活動", color=discord.Color.blue())
        embed.add_field(name="活動", value="打本", inline=False)
        embed.add_field(name="日期", value="10/19 9:30", inline=False)
        
        # 產生各個欄位的顯示文字
        for status, users in self.participants.items():
            user_list_str = "\n".join([f"• {u.mention}" for u in users]) if users else "目前無人"
            
            # 加上對應的符號
            prefix = "✅" if status == "出席" else "⚠️" if status == "外找" else "❌" if status == "請假" else "👀"
            
            embed.add_field(
                name=f"{prefix} {status} ({len(users)})", 
                value=user_list_str, 
                inline=False
            )

        # 4. 更新原本的 Discord 訊息
        await interaction.response.edit_message(embed=embed, view=self)

    # 各個按鈕的互動觸發
    @discord.ui.button(label="出席", style=discord.ButtonStyle.success, custom_id="btn_attend")
    async def attend_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.update_status(interaction, "出席")

    @discord.ui.button(label="外找", style=discord.ButtonStyle.secondary, custom_id="btn_external")
    async def external_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.update_status(interaction, "外找")

    @discord.ui.button(label="請假", style=discord.ButtonStyle.danger, custom_id="btn_leave")
    async def leave_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.update_status(interaction, "請假")

    @discord.ui.button(label="再看看", style=discord.ButtonStyle.blurple, custom_id="btn_maybe")
    async def maybe_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.update_status(interaction, "再看看")
