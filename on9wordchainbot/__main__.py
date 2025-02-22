import asyncio
import random
import time
from decimal import ROUND_HALF_UP, getcontext
from flask import Flask
from threading import Thread

from aiogram import executor
from periodic import Periodic

from on9wordchainbot import dp, loop, pool, session
from on9wordchainbot.utils import send_admin_group
from on9wordchainbot.words import Words
from on9wordchainbot.constants import load_authorized_ids

random.seed(time.time())
getcontext().rounding = ROUND_HALF_UP

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running!", 200

def run_flask():
    app.run(host="0.0.0.0", port=8000)

async def on_startup(_) -> None:

    await load_authorized_ids()

    await Words.update()

    # Notify admin group
    await send_admin_group("🚀 Bot is up and running!")

    # Update word list every 3 hours
    task = Periodic(3 * 60 * 60, Words.update)
    await task.start()


async def on_shutdown(_) -> None:
    await asyncio.gather(session.close(), pool.close())


def main() -> None:
    executor.start_polling(
        dp, loop=loop, on_startup=on_startup, on_shutdown=on_shutdown, skip_updates=True
    )


if __name__ == "__main__":
    Thread(target=run_flask, daemon=True).start()
    main()
