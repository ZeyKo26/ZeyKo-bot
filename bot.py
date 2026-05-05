import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
import random
import os
import time

TOKEN = os.getenv("TOKEN")
GUILD_ID = 123456789012345678
guild = discord.Object(id=GUILD_ID)

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

cooldowns = {}
daily = {}

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
        await db.execute("""
        CREATE TABLE IF NOT EXISTS inventory (
            user_id INTEGER,
            item TEXT,
            amount INTEGER
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

# ---------------- XP ----------------
async def add_xp(user_id, amount):
    async with aiosqlite.connect("ultrapro.db") as db:
        async with db.execute("SELECT xp, level FROM users WHERE user_id = ?", (user_id,)) as cursor:
            xp, level = await cursor.fetchone()

        xp += amount
        up = False

        if xp >= level * 100:
            level += 1
            xp = 0
            up = True

        await db.execute("UPDATE users SET xp=?, level=? WHERE user_id=?", (xp, level, user_id))
        await db.commit()

        return up, level

# ---------------- READY ----------------
@bot.event
async def on_ready():
    await init_db()
    await bot.tree.sync(guild=guild)
    print("Bot prêt")

# ---------------- AIDE ----------------
@bot.tree.command(name="aide", guild=guild)
async def aide(interaction: discord.Interaction):
    msg = """
📜 Commandes :

💰 Économie :
/balance - Voir ton argent
/travailler - Gagner de l'argent (4h)
/parier - Jouer de l'argent

🏦 Banque :
/deposer - Mettre en banque
/retirer - Retirer argent

📊 Progression :
/niveau - Voir ton niveau
/classement - Top joueurs

🛒 Boutique :
/boutique - Voir shop
/acheter - Acheter objet
/inventaire - Voir objets

🎁 Bonus :
/quotidien - Récompense toutes les 24h
"""
    await interaction.response.send_message(msg, ephemeral=True)

# ---------------- ECONOMIE ----------------
@bot.tree.command(name="balance", guild=guild)
async def balance(interaction: discord.Interaction):
    user = await get_user(interaction.user.id)
    await interaction.response.send_message(f"💰 {user[1]} | 🏦 {user[2]}")

@bot.tree.command(name="travailler", guild=guild)
async def travailler(interaction: discord.Interaction):
    uid = interaction.user.id

    if uid in cooldowns and time.time() - cooldowns[uid] < 14400:
        return await interaction.response.send_message("⏳ Reviens dans 4h.")

    cooldowns[uid] = time.time()

    gain = random.randint(100, 400)

    async with aiosqlite.connect("ultrapro.db") as db:
        await db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (gain, uid))
        await db.commit()

    up, level = await add_xp(uid, 25)

    msg = f"💼 Tu gagnes {gain} 💰"

    if up:
        msg += f"\n🎉 Niveau {level} !"

    await interaction.response.send_message(msg)

@bot.tree.command(name="parier", guild=guild)
async def parier(interaction: discord.Interaction, montant: int):
    user = await get_user(interaction.user.id)

    if montant > user[1]:
        return await interaction.response.send_message("❌ Pas assez d'argent.")

    win = random.choice([True, False])

    async with aiosqlite.connect("ultrapro.db") as db:
        if win:
            await db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (montant, interaction.user.id))
            msg = f"🎉 +{montant}"
        else:
            await db.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (montant, interaction.user.id))
            msg = f"💀 -{montant}"
        await db.commit()

    await interaction.response.send_message(msg)

# ---------------- BANQUE ----------------
@bot.tree.command(name="deposer", guild=guild)
async def deposer(interaction: discord.Interaction, montant: int):
    user = await get_user(interaction.user.id)

    if montant > user[1]:
        return await interaction.response.send_message("❌ Pas assez.")

    async with aiosqlite.connect("ultrapro.db") as db:
        await db.execute("UPDATE users SET balance = balance - ?, bank = bank + ? WHERE user_id = ?", (montant, montant, interaction.user.id))
        await db.commit()

    await interaction.response.send_message("🏦 Déposé")

@bot.tree.command(name="retirer", guild=guild)
async def retirer(interaction: discord.Interaction, montant: int):
    user = await get_user(interaction.user.id)

    if montant > user[2]:
        return await interaction.response.send_message("❌ Pas assez en banque.")

    async with aiosqlite.connect("ultrapro.db") as db:
        await db.execute("UPDATE users SET balance = balance + ?, bank = bank - ? WHERE user_id = ?", (montant, montant, interaction.user.id))
        await db.commit()

    await interaction.response.send_message("💰 Retiré")

# ---------------- XP ----------------
@bot.tree.command(name="niveau", guild=guild)
async def niveau(interaction: discord.Interaction):
    user = await get_user(interaction.user.id)
    await interaction.response.send_message(f"Niveau {user[4]} | XP {user[3]}")

@bot.tree.command(name="classement", guild=guild)
async def classement(interaction: discord.Interaction):
    async with aiosqlite.connect("ultrapro.db") as db:
        async with db.execute("SELECT user_id, level FROM users ORDER BY level DESC LIMIT 10") as cursor:
            data = await cursor.fetchall()

    msg = "🏆 Classement :\n"
    for i, u in enumerate(data):
        msg += f"{i+1}. <@{u[0]}> - Niveau {u[1]}\n"

    await interaction.response.send_message(msg)

# ---------------- SHOP ----------------
shop = {"pizza":100, "pc":1000, "voiture":5000}

@bot.tree.command(name="boutique", guild=guild)
async def boutique(interaction: discord.Interaction):
    msg = "🛒 Boutique :\n"
    for i, p in shop.items():
        msg += f"{i} - {p} 💰\n"
    await interaction.response.send_message(msg)

@bot.tree.command(name="acheter", guild=guild)
async def acheter(interaction: discord.Interaction, objet: str):
    user = await get_user(interaction.user.id)

    if objet not in shop:
        return await interaction.response.send_message("❌ Objet inconnu.")

    prix = shop[objet]

    if user[1] < prix:
        return await interaction.response.send_message("❌ Pas assez.")

    async with aiosqlite.connect("ultrapro.db") as db:
        await db.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (prix, interaction.user.id))
        await db.execute("INSERT INTO inventory VALUES (?, ?, 1)", (interaction.user.id, objet))
        await db.commit()

    await interaction.response.send_message(f"✅ Acheté : {objet}")

@bot.tree.command(name="inventaire", guild=guild)
async def inventaire(interaction: discord.Interaction):
    async with aiosqlite.connect("ultrapro.db") as db:
        async with db.execute("SELECT item, amount FROM inventory WHERE user_id = ?", (interaction.user.id,)) as cursor:
            items = await cursor.fetchall()

    if not items:
        return await interaction.response.send_message("Vide.")

    msg = "📦 Inventaire :\n"
    for i in items:
        msg += f"{i[0]} x{i[1]}\n"

    await interaction.response.send_message(msg)

# ---------------- DAILY ----------------
@bot.tree.command(name="quotidien", guild=guild)
async def quotidien(interaction: discord.Interaction):
    uid = interaction.user.id

    if uid in daily and time.time() - daily[uid] < 86400:
        return await interaction.response.send_message("⏳ Déjà récupéré aujourd'hui.")

    daily[uid] = time.time()
    gain = random.randint(200, 600)

    async with aiosqlite.connect("ultrapro.db") as db:
        await db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (gain, uid))
        await db.commit()

    await interaction.response.send_message(f"🎁 +{gain} 💰")

# ---------------- MESSAGE XP ----------------
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    up, level = await add_xp(message.author.id, 5)

    if up:
        await message.channel.send(f"🎉 {message.author.mention} niveau {level} !")

    await bot.process_commands(message)

bot.run(TOKEN)
