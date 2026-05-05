import discord
from discord.ext import commands
import aiosqlite
import random
import datetime

TOKEN = "TON_TOKEN_ICI"
PREFIX = "!"

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents)

# -----------------------------
# INITIALISATION BASE DE DONNÉES
# -----------------------------

async def init_db():
    async with aiosqlite.connect("zeycoins.db") as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            balance INTEGER DEFAULT 0,
            job TEXT DEFAULT 'chomeur',
            last_work TEXT,
            last_daily TEXT
        )
        """)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            date TEXT,
            description TEXT
        )
        """)
        await db.commit()

@bot.event
async def on_ready():
    await init_db()
    print(f"Bot connecté en tant que {bot.user}")

# -----------------------------
# FONCTION UTILITAIRE
# -----------------------------

async def get_user(user_id):
    async with aiosqlite.connect("zeycoins.db") as db:
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
            user = await cursor.fetchone()
            if user is None:
                await db.execute("INSERT INTO users (user_id, balance) VALUES (?, ?)", (user_id, 100))
                await db.commit()
                return (user_id, 100, "chomeur", None, None)
            return user

# -----------------------------
# COMMANDE SOLDE
# -----------------------------

@bot.command()
async def balance(ctx):
    user = await get_user(ctx.author.id)
    await ctx.send(f"💰 {ctx.author.mention}, tu as **{user[1]} ZeyCoins**.")

# -----------------------------
# DAILY REWARD
# -----------------------------

@bot.command()
async def daily(ctx):
    user = await get_user(ctx.author.id)
    today = datetime.date.today().isoformat()

    if user[4] == today:
        return await ctx.send("❌ Tu as déjà récupéré ton daily aujourd'hui.")

    reward = random.randint(50, 150)

    async with aiosqlite.connect("zeycoins.db") as db:
        await db.execute("UPDATE users SET balance = balance + ?, last_daily = ? WHERE user_id = ?", (reward, today, ctx.author.id))
        await db.commit()

    await ctx.send(f"🎁 Tu as gagné **{reward} ZeyCoins** !")

# -----------------------------
# MÉTIERS
# -----------------------------

jobs = {
    "developpeur": (100, 300),
    "streamer": (50, 200),
    "moderateur": (80, 250),
    "graphiste": (70, 220)
}

@bot.command()
async def jobs_list(ctx):
    msg = "🧑‍💼 Métiers disponibles :\n"
    for job in jobs:
        msg += f"- {job}\n"
    await ctx.send(msg)

@bot.command()
async def setjob(ctx, job_name):
    if job_name not in jobs:
        return await ctx.send("❌ Métier invalide.")

    async with aiosqlite.connect("zeycoins.db") as db:
        await db.execute("UPDATE users SET job = ? WHERE user_id = ?", (job_name, ctx.author.id))
        await db.commit()

    await ctx.send(f"✅ Tu es maintenant **{job_name}**.")

@bot.command()
async def work(ctx):
    user = await get_user(ctx.author.id)
    job = user[2]

    if job == "chomeur":
        return await ctx.send("❌ Tu n'as pas de métier.")

    today = datetime.date.today().isoformat()
    if user[3] == today:
        return await ctx.send("❌ Tu as déjà travaillé aujourd'hui.")

    gain = random.randint(jobs[job][0], jobs[job][1])

    async with aiosqlite.connect("zeycoins.db") as db:
        await db.execute("UPDATE users SET balance = balance + ?, last_work = ? WHERE user_id = ?", (gain, today, ctx.author.id))
        await db.commit()

    await ctx.send(f"💼 Tu as travaillé en tant que **{job}** et gagné **{gain} ZeyCoins**.")

# -----------------------------
# BOUTIQUE
# -----------------------------

shop = {
    "vip": 1000,
    "role_gold": 500,
    "ticket_event": 200
}

@bot.command()
async def shop_list(ctx):
    msg = "🛒 Boutique :\n"
    for item, price in shop.items():
        msg += f"- {item} : {price} ZeyCoins\n"
    await ctx.send(msg)

@bot.command()
async def buy(ctx, item):
    if item not in shop:
        return await ctx.send("❌ Objet invalide.")

    user = await get_user(ctx.author.id)

    if user[1] < shop[item]:
        return await ctx.send("❌ Pas assez d'argent.")

    async with aiosqlite.connect("zeycoins.db") as db:
        await db.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (shop[item], ctx.author.id))
        await db.commit()

    await ctx.send(f"✅ Tu as acheté **{item}**.")

# -----------------------------
# CLASSEMENT
# -----------------------------

@bot.command()
async def leaderboard(ctx):
    async with aiosqlite.connect("zeycoins.db") as db:
        async with db.execute("SELECT user_id, balance FROM users ORDER BY balance DESC LIMIT 10") as cursor:
            top = await cursor.fetchall()

    msg = "🏆 Top 10 ZeyCoins :\n"
    for i, user in enumerate(top, 1):
        member = ctx.guild.get_member(user[0])
        name = member.name if member else "Inconnu"
        msg += f"{i}. {name} - {user[1]} ZeyCoins\n"

    await ctx.send(msg)

# -----------------------------
# PARI
# -----------------------------

@bot.command()
async def gamble(ctx, amount: int):
    user = await get_user(ctx.author.id)

    if amount <= 0:
        return await ctx.send("❌ Montant invalide.")
    if user[1] < amount:
        return await ctx.send("❌ Pas assez d'argent.")

    win = random.choice([True, False])

    async with aiosqlite.connect("zeycoins.db") as db:
        if win:
            await db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, ctx.author.id))
            await ctx.send(f"🎉 Tu as gagné {amount} ZeyCoins !")
        else:
            await db.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (amount, ctx.author.id))
            await ctx.send(f"💀 Tu as perdu {amount} ZeyCoins.")
        await db.commit()

# -----------------------------
# PLANNING ÉVÉNEMENTS
# -----------------------------

@bot.command()
@commands.has_permissions(administrator=True)
async def create_event(ctx, name, date, *, description):
    async with aiosqlite.connect("zeycoins.db") as db:
        await db.execute("INSERT INTO events (name, date, description) VALUES (?, ?, ?)", (name, date, description))
        await db.commit()
    await ctx.send("📅 Événement créé !")

@bot.command()
async def events(ctx):
    async with aiosqlite.connect("zeycoins.db") as db:
        async with db.execute("SELECT name, date, description FROM events") as cursor:
            events = await cursor.fetchall()

    if not events:
        return await ctx.send("Aucun événement prévu.")

    msg = "📅 Planning des événements :\n"
    for e in events:
        msg += f"\n📌 {e[0]} - {e[1]}\n{e[2]}\n"

    await ctx.send(msg)

# -----------------------------

bot.run(TOKEN)
