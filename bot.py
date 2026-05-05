import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
import random
import os

TOKEN = os.getenv("TOKEN")

# 🔥 MET TON ID DE SERVEUR ICI (important)
GUILD_ID = 1449102273262391409
guild = discord.Object(id=GUILD_ID)

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ---------------- DATABASE ----------------

async def init_db():
    async with aiosqlite.connect("ultrapro.db") as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            balance INTEGER DEFAULT 500,
            bank INTEGER DEFAULT 0,
            xp INTEGER DEFAULT 0,
            level INTEGER DEFAULT 1
        )
        """)
        await db.commit()

# ---------------- USER ----------------

async def get_user(user_id):
    async with aiosqlite.connect("ultrapro.db") as db:
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
            user = await cursor.fetchone()

        if not user:
            await db.execute("INSERT INTO users (user_id) VALUES (?)", (user_id,))
            await db.commit()
            return (user_id, 500, 0, 0, 1)

        return user

# ---------------- READY ----------------

@bot.event
async def on_ready():
    await init_db()

    synced = await bot.tree.sync(guild=guild)

    print(f"Connecté en tant que {bot.user}")
    print(f"{len(synced)} commandes sync (guild)")
    print("Bot prêt.")

# ---------------- XP ----------------

async def add_xp(user_id, amount):
    async with aiosqlite.connect("ultrapro.db") as db:
        async with db.execute("SELECT xp, level FROM users WHERE user_id = ?", (user_id,)) as cursor:
            data = await cursor.fetchone()

        xp, level = data
        xp += amount

        if xp >= level * 100:
            level += 1
            xp = 0

        await db.execute("UPDATE users SET xp=?, level=? WHERE user_id=?",
                         (xp, level, user_id))
        await db.commit()

# ---------------- COMMANDES ----------------

@bot.tree.command(name="aide", description="Liste des commandes", guild=guild)
async def aide(interaction: discord.Interaction):
    embed = discord.Embed(title="Commandes", color=0x5865F2)
    embed.add_field(name="💰 Économie", value="/balance /work /gamble", inline=False)
    embed.add_field(name="🏦 Banque", value="/deposit /withdraw", inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ---------------- BALANCE ----------------

@bot.tree.command(name="balance", guild=guild)
async def balance(interaction: discord.Interaction):
    user = await get_user(interaction.user.id)

    embed = discord.Embed(
        title="Ton argent",
        description=f"Cash: {user[1]} 💰\nBanque: {user[2]} 🏦",
        color=0x2ecc71
    )

    await interaction.response.send_message(embed=embed)

# ---------------- WORK ----------------

@bot.tree.command(name="work", guild=guild)
async def work(interaction: discord.Interaction):
    gain = random.randint(80, 300)

    async with aiosqlite.connect("ultrapro.db") as db:
        await db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?",
                         (gain, interaction.user.id))
        await db.commit()

    await add_xp(interaction.user.id, 20)

    await interaction.response.send_message(f"Tu as gagné {gain} 💰 + 20 XP")

# ---------------- GAMBLE ----------------

@bot.tree.command(name="gamble", guild=guild)
async def gamble(interaction: discord.Interaction, amount: int):
    user = await get_user(interaction.user.id)

    if amount > user[1]:
        return await interaction.response.send_message("Pas assez d'argent.")

    win = random.choice([True, False])

    async with aiosqlite.connect("ultrapro.db") as db:
        if win:
            await db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?",
                             (amount, interaction.user.id))
            msg = f"Tu gagnes {amount} 💰"
        else:
            await db.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?",
                             (amount, interaction.user.id))
            msg = f"Tu perds {amount} 💀"

        await db.commit()

    await interaction.response.send_message(msg)

# ---------------- BANQUE ----------------

@bot.tree.command(name="deposit", guild=guild)
async def deposit(interaction: discord.Interaction, amount: int):
    user = await get_user(interaction.user.id)

    if amount > user[1]:
        return await interaction.response.send_message("Pas assez d'argent.")

    async with aiosqlite.connect("ultrapro.db") as db:
        await db.execute("""
        UPDATE users
        SET balance = balance - ?, bank = bank + ?
        WHERE user_id = ?
        """, (amount, amount, interaction.user.id))
        await db.commit()

    await interaction.response.send_message("Argent déposé.")

@bot.tree.command(name="withdraw", guild=guild)
async def withdraw(interaction: discord.Interaction, amount: int):
    user = await get_user(interaction.user.id)

    if amount > user[2]:
        return await interaction.response.send_message("Pas assez en banque.")

    async with aiosqlite.connect("ultrapro.db") as db:
        await db.execute("""
        UPDATE users
        SET balance = balance + ?, bank = bank - ?
        WHERE user_id = ?
        """, (amount, amount, interaction.user.id))
        await db.commit()

    await interaction.response.send_message("Argent retiré.")

# ---------------- XP CHAT ----------------

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    await add_xp(message.author.id, 5)
    await bot.process_commands(message)

# ---------------- RUN ----------------

bot.run(TOKEN)
