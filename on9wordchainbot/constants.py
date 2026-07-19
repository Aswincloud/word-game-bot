import json
import logging
import os

logger = logging.getLogger(__name__)

# Load constants from config file
filename = "config_beta.json" if os.path.exists("config_beta.json") else "config.json"
logger.info("Loading constants from config file")
with open(filename) as f:
    config = json.load(f)

TOKEN: str = config["TOKEN"]
ON9BOT_TOKEN: str = config["ON9BOT_TOKEN"]
DB_URI: str = config["DB_URI"]
PROVIDER_TOKEN: str = config["PROVIDER_TOKEN"]
OWNER_ID: int = config["OWNER_ID"]
ADMIN_GROUP_ID: int = config["ADMIN_GROUP_ID"]
OFFICIAL_GROUP_ID: int = config["OFFICIAL_GROUP_ID"]
WORD_ADDITION_CHANNEL_ID: int = config["WORD_ADDITION_CHANNEL_ID"]
VIP: list[int] = config["VIP"]
VIP_GROUP: list[int] = config["VIP_GROUP"]
# Fork-specific: DB-backed admin/authorized-group access control
AUTHORIZED_ID: list[int] = config["AUTHORIZED_ID"]
ADMIN_ID: list[int] = config["ADMIN_ID"]

WORDLIST_SOURCE = "https://raw.githubusercontent.com/dwyl/english-words/master/words.txt"
# Repository root (one level above the on9wordchainbot package), used by /restart's `git pull`.
# Derived from this file's location so it works regardless of deploy path.
BOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STAR = "\u2b50\ufe0f"

async def load_authorized_ids():
    """Fetch admin and authorized IDs from the database and append them to existing lists."""
    global ADMIN_ID, AUTHORIZED_ID  # Explicitly modify global lists
    from on9wordchainbot.resources import get_pool
    pool = get_pool()
    try:
        async with pool.acquire() as conn:
            # Fetch admin IDs
            admin_records = await conn.fetch("SELECT user_id FROM admin_id;")
            new_admin_ids = {record["user_id"] for record in admin_records}

            # Fetch authorized group IDs
            authorized_records = await conn.fetch("SELECT group_id FROM authorized_id;")
            new_authorized_ids = {record["group_id"] for record in authorized_records}

            # Append only new IDs (avoid duplicates)
            ADMIN_ID.extend(id for id in new_admin_ids if id not in ADMIN_ID)
            AUTHORIZED_ID.extend(id for id in new_authorized_ids if id not in AUTHORIZED_ID)

        print("✅ Admin & Authorized IDs updated successfully!")
    except Exception as e:
        print(f"⚠️ Database Error: {e}")

class GameState:
    JOINING = 0
    RUNNING = 1
    KILLGAME = -1


class GameSettings:
    JOINING_PHASE_SECONDS = 60
    MAX_JOINING_PHASE_SECONDS = 180
    MIN_PLAYERS = 2
    MAX_PLAYERS = 50
    INCREASED_MAX_PLAYERS = 300
    MIN_TURN_SECONDS = 20
    MAX_TURN_SECONDS = 40
    TURN_SECONDS_REDUCTION_PER_LIMIT_CHANGE = 5
    MIN_WORD_LENGTH_LIMIT = 3
    MAX_WORD_LENGTH_LIMIT = 10
    WORD_LENGTH_LIMIT_INCREASE_PER_LIMIT_CHANGE = 1
    TURNS_BETWEEN_LIMITS_CHANGE = 5

    ELIM_JOINING_PHASE_SECONDS = 90
    ELIM_MIN_PLAYERS = 5
    ELIM_MAX_PLAYERS = 30
    ELIM_INCREASED_MAX_PLAYERS = 50
    ELIM_TURN_SECONDS = 30
    ELIM_MAX_TURN_SCORE = 20
