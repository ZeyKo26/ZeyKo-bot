import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
import random
import datetime
import os

TOKEN = os.getenv("TOKEN")

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
            level INTEGER DEFAULT 1,
            job TEXT DEFAULT 'chomeur',
            last_work TEXT
        )
        """)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS config (
            guild_id INTEGER PRIMARY KEY,
            log_channel INTEGER
        )
        """)
        await db.commit()

@bot.event
async def on_ready():
    await init_db()
    await bot.tree.sync()
    print(f"{bot.user} est prêt.")

# ---------------- UTIL ----------------

async def get_user(user_id):
    async with aiosqlite.connect("ultrapro.db") as db:
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
            user = await cursor.fetchone()
            if not user:
                await db.execute("INSERT INTO users (user_id) VALUES (?)", (user_id,))
                await db.commit()
                return (user_id, 500, 0, 0, 1, "chomeur", None)
            return user

async def add_xp(user_id, amount):
    async with aiosqlite.connect("ultrapro.db") as db:
        async with db.execute("SELECT xp, level FROM users WHERE user_id = ?", (user_id,)) as cursor:
            xp, level = await cursor.fetchone()

        xp += amount
        needed = level * 100

        if xp >= needed:
            level += 1
            xp = 0

        await db.execute("UPDATE users SET xp=?, level=? WHERE user_id=?",
                         (xp, level, user_id))
        await db.commit()

# ---------------- /AIDE ----------------

@bot.tree.command(name="aide", description="Voir toutes les commandes")
async def aide(interaction: discord.Interaction):
    embed = discord.Embed(title="📖 Commandes disponibles", color=0x5865F2)
    embed.add_field(name="💰 Économie", value="/balance /work /gamble /shop", inline=False)
    embed.add_field(name="🏦 Banque", value="/deposit /withdraw", inline=False)
    embed.add_field(name="⭐ XP", value="XP automatique en parlant", inline=False)
    embed.add_field(name="📅 Event", value="/create_event", inline=False)
    embed.add_field(name="⚙️ Admin", value="/config", inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ---------------- ECONOMIE ----------------

@bot.tree.command(name="balance")
async def balance(interaction: discord.Interaction):
    user = await get_user(interaction.user.id)
    embed = discord.Embed(title="💰 Votre solde",
                          description=f"Portefeuille: {user[1]} ZeyCoins\nBanque: {user[2]} ZeyCoins",
                          color=0x2ecc71)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="deposit")
async def deposit(interaction: discord.Interaction, amount: int):
    user = await get_user(interaction.user.id)
    if amount > user[1]:
        return await interaction.response.send_message("❌ Fonds insuffisants.")

    async with aiosqlite.connect("ultrapro.db") as db:
        await db.execute("UPDATE users SET balance=balance-?, bank=bank+? WHERE user_id=?",
                         (amount, amount, interaction.user.id))
        await db.commit()

    await interaction.response.send_message(f"🏦 {amount} déposés en banque.")

@bot.tree.command(name="withdraw")
async def withdraw(interaction: discord.Interaction, amount: int):
    user = await get_user(interaction.user.id)
    if amount > user[2]:
        return await interaction.response.send_message("❌ Banque insuffisante.")

    async with aiosqlite.connect("ultrapro.db") as db:
        await db.execute("UPDATE users SET balance=balance+?, bank=bank-? WHERE user_id=?",
                         (amount, amount, interaction.user.id))
        await db.commit()

    await interaction.response.send_message(f"💵 {amount} retirés.")

# ---------------- WORK ----------------

jobs = {"developpeur": (100,300), "streamer": (50,200)}

@bot.tree.command(name="work")
async def work(interaction: discord.Interaction):
    user = await get_user(interaction.user.id)
    gain = random.randint(100, 300)

    async with aiosqlite.connect("ultrapro.db") as db:
        await db.execute("UPDATE users SET balance=balance+? WHERE user_id=?",
                         (gain, interaction.user.id))
        await db.commit()

    await add_xp(interaction.user.id, 20)

    await interaction.response.send_message(f"💼 Vous avez gagné {gain} ZeyCoins + 20 XP")

# ---------------- GAMBLE ----------------

@bot.tree.command(name="gamble")
async def gamble(interaction: discord.Interaction, amount: int):
    user = await get_user(interaction.user.id)
    if amount > user[1]:
        return await interaction.response.send_message("❌ Pas assez d'argent.")

    win = random.choice([True, False])

    async with aiosqlite.connect("ultrapro.db") as db:
        if win:
            await db.execute("UPDATE users SET balance=balance+? WHERE user_id=?",
                             (amount, interaction.user.id))
            msg = f"🎉 Vous avez gagné {amount}!"
        else:
            await db.execute("UPDATE users SET balance=balance-? WHERE user_id=?",
                             (amount, interaction.user.id))
            msg = f"💀 Vous avez perdu {amount}."
        await db.commit()

    await interaction.response.send_message(msg)

# ---------------- XP AUTOMATIQUE ----------------

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    await add_xp(message.author.id, 5)
    await bot.process_commands(message)

# ---------------- CONFIG LOGS ----------------

@bot.tree.command(name="config")
@app_commands.checks.has_permissions(administrator=True)
async def config(interaction: discord.Interaction, log_channel: discord.TextChannel):
    async with aiosqlite.connect("ultrapro.db") as db:
        await db.execute("INSERT OR REPLACE INTO config (guild_id, log_channel) VALUES (?,?)",
                         (interaction.guild.id, log_channel.id))
        await db.commit()

    await interaction.response.send_message("⚙️ Configuration mise à jour.")

bot.run(TOKEN)
