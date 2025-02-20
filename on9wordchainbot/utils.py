import random
from functools import wraps
from string import ascii_lowercase
from typing import Any, Callable, List, Optional, Set

from aiocache import cached
from aiogram import types

from . import bot, on9bot, pool
from .constants import ADMIN_GROUP_ID, VIP, AUTHORIZED_ID
from .words import Words


def is_word(s: str) -> bool:
    return all(c in ascii_lowercase for c in s)


def check_word_existence(word: str) -> bool:
    return word in Words.dawg


def filter_words(
    min_len: int = 1,
    prefix: Optional[str] = None,
    required_letter: Optional[str] = None,
    banned_letters: Optional[List[str]] = None,
    exclude_words: Optional[Set[str]] = None
) -> List[str]:
    words = Words.dawg.keys(prefix) if prefix else Words.dawg.keys()
    if min_len > 1:
        words = [w for w in words if len(w) >= min_len]
    if required_letter:
        words = [w for w in words if required_letter in w]
    if banned_letters:
        words = [w for w in words if all(i not in w for i in banned_letters)]
    if exclude_words:
        words = [w for w in words if w not in exclude_words]
    return words


def get_random_word(
    min_len: int = 1,
    prefix: Optional[str] = None,
    required_letter: Optional[str] = None,
    banned_letters: Optional[List[str]] = None,
    exclude_words: Optional[Set[str]] = None
) -> Optional[str]:
    words = filter_words(min_len, prefix, required_letter, banned_letters, exclude_words)
    return random.choice(words) if words else None


async def send_admin_group(*args: Any, **kwargs: Any) -> types.Message:
    return await bot.send_message(ADMIN_GROUP_ID, *args, **kwargs)


@cached(ttl=15)
async def amt_donated(user_id: int) -> int:
    async with pool.acquire() as conn:
        amt = await conn.fetchval("SELECT SUM(amount) FROM donation WHERE user_id = $1;", user_id)
        return amt or 0


@cached(ttl=15)
async def has_star(user_id: int) -> bool:
    return user_id in VIP or user_id == on9bot.id or await amt_donated(user_id)


def inline_keyboard_from_button(button: types.InlineKeyboardButton) -> types.InlineKeyboardMarkup:
    return types.InlineKeyboardMarkup(inline_keyboard=[[button]])


ADD_TO_GROUP_KEYBOARD = inline_keyboard_from_button(
    types.InlineKeyboardButton("Add to group", url="https://t.me/gamebotbyashbot?startgroup=_")
)
ADD_ON9BOT_TO_GROUP_KEYBOARD = inline_keyboard_from_button(
    types.InlineKeyboardButton("Add Ash helper bot to group", url="https://t.me/gamebotbyashbot?startgroup=_")
)


def send_private_only_message(f: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(f)
    async def inner(message: types.Message, *args: Any, **kwargs: Any) -> None:
        if message.chat.id < 0:
            await message.reply("Please use this command in private.", allow_sending_without_reply=True)
            return
        await f(message, *args, **kwargs)

    return inner


def send_groups_only_message(f: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(f)
    async def inner(message: types.Message, *args: Any, **kwargs: Any) -> None:
        if message.chat.id > 0:  # If it's a private chat
            await message.reply(
                "🚫 This command can only be used in groups.",
                allow_sending_without_reply=True,
                reply_markup=ADD_TO_GROUP_KEYBOARD
            )
            return
        
        # Check if the group is authorized
        if message.chat.id not in AUTHORIZED_ID:
            await message.reply(
                f"⛔ This group is not authorized to use this command.\n"
                f"Please contact my boss @Aswin4122001 to authorize this group: `{message.chat.id}`",
                parse_mode=types.ParseMode.MARKDOWN,
                allow_sending_without_reply=True
            )
            return

        await f(message, *args, **kwargs)

    return inner
