import asyncio
import logging
import os
import signal
import subprocess
from functools import wraps
from uuid import uuid4

from aiogram import Router, F, types
from aiogram.enums import ChatType, ParseMode
from aiogram.filters import JOIN_TRANSITION, ChatMemberUpdatedFilter, Command, CommandObject, CommandStart
from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from on9wordchainbot.resources import GlobalState, bot, get_pool
from on9wordchainbot.constants import (
    ADMIN_GROUP_ID,
    ADMIN_ID,
    AUTHORIZED_ID,
    BOT_DIR,
    OFFICIAL_GROUP_ID,
    OWNER_ID,
    VIP,
)
from on9wordchainbot.handlers.donation import send_donate_invoice
from on9wordchainbot.models import GAME_MODES
from on9wordchainbot.utils import ADD_TO_GROUP_KEYBOARD, amt_donated, awaitable_to_coroutine, is_word
from on9wordchainbot.words import Words

logger = logging.getLogger(__name__)

router = Router(name=__name__)


def admin_only(f):
    """Decorator restricting a command to fork admins (ADMIN_ID), replying if unauthorized.

    Signature-preserving via functools.wraps: aiogram v3 unwraps to read the real
    handler signature for dependency injection, and **kwargs forwards injected args
    (e.g. command: CommandObject) to the wrapped handler.
    """
    @wraps(f)
    async def wrapped(message: types.Message, *args, **kwargs):
        if message.from_user.id not in ADMIN_ID and message.from_user.id != OWNER_ID:
            await message.reply("⛔ You are not authorized to use this command!")
            return
        return await f(message, *args, **kwargs)

    return wrapped


@router.message(CommandStart(), F.chat.type == ChatType.PRIVATE)
async def cmd_start(message: types.Message) -> None:
    await message.reply(
        "Hi! I host games of word chain in Telegram groups and I am made by @Aswin4122001.\n",
        reply_markup=ADD_TO_GROUP_KEYBOARD
    )


@router.message(Command("feedback"))
async def cmd_feedback(message: types.Message, command: CommandObject) -> None:
    if message.forward_from:  # Avoid re-triggering on forward
        return

    args = command.args
    if not args:
        bot_user = await message.bot.me()
        await message.reply(
            "Function: Send feedback to my owner.\n"
            f"Usage: `/feedback@{bot_user.username} feedback`"
        )
        return

    await asyncio.gather(
        awaitable_to_coroutine(message.forward(ADMIN_GROUP_ID)),
        awaitable_to_coroutine(message.reply("Feedback sent successfully."))
    )


@router.message(Command("maintmode"))
@admin_only
async def cmd_maintmode(message: types.Message) -> None:
    GlobalState.maint_mode = not GlobalState.maint_mode
    await message.reply(
        f"Maintenance mode has been switched {'on' if GlobalState.maint_mode else 'off'}."
    )


@router.message(Command("authorized_users", "au"))
@admin_only
async def cmd_authorized_users(message: types.Message) -> None:
    if not ADMIN_ID:
        await message.reply("No authorized users.")
        return

    user_list = []
    for user_id in ADMIN_ID:
        try:
            user = await bot.get_chat(user_id)  # Fetch user details
            user_list.append(f"👤 `{user_id}` - [{user.full_name}](tg://user?id={user_id})")
        except Exception:
            user_list.append(f"👤 `{user_id}` - Name not found")

    await message.reply(
        "👤 **Authorized Users:**\n" + "\n".join(user_list),
        parse_mode=ParseMode.MARKDOWN,
    )


@router.message(Command("authorized_groups", "ag"))
@admin_only
async def cmd_authorized_groups(message: types.Message) -> None:
    if not AUTHORIZED_ID:
        await message.reply("No authorized groups.")
        return

    group_list = []
    for group_id in AUTHORIZED_ID:
        try:
            group = await bot.get_chat(group_id)  # Fetch group details
            group_list.append(f"📢 `{group_id}` - *{group.title}*")
        except Exception:
            group_list.append(f"📢 `{group_id}` - Name not found")

    await message.reply(
        "📢 **Authorized Groups:**\n" + "\n".join(group_list),
        parse_mode=ParseMode.MARKDOWN,
    )


@router.message(Command("restart"))
@admin_only
async def cmd_restart(message: types.Message) -> None:
    await message.reply("Updating and restarting the bot...")

    # Run git pull to fetch the latest changes
    subprocess.run(["git", "pull"], cwd=BOT_DIR, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # Kill the current process (run_forever.py / restart supervisor brings it back up)
    os.kill(os.getpid(), signal.SIGTERM)


@router.message(Command("leave"), F.chat.type.in_((ChatType.GROUP, ChatType.SUPERGROUP)))
@admin_only
async def cmd_leave(message: types.Message) -> None:
    await message.chat.leave()


class DemoteCallback(CallbackData, prefix="demote"):
    action: str
    entity_id: int
    admin_id: int


@router.message(Command("demote"))
@admin_only
async def cmd_demote(message: types.Message) -> None:
    entity_id = None
    admin_id = message.from_user.id  # Admin who initiated the command

    # If command is used with an ID
    args = message.text.split()
    if len(args) == 2 and args[1].lstrip("-").isdigit():
        entity_id = int(args[1])
    # If the command is used as a reply, get the replied user's ID
    elif message.reply_to_message:
        if message.reply_to_message.from_user:
            entity_id = message.reply_to_message.from_user.id
        elif message.reply_to_message.sender_chat:  # For channels/supergroups
            entity_id = message.reply_to_message.sender_chat.id

    if not entity_id:
        await message.reply(
            "⚠️ Usage: `/demote <user_or_group_id>` or reply to a user's message with `/demote`.\n\n"
            "Example:\n`/demote 123456789` (for users)\nReply to a message with `/demote` (to pick ID automatically)",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    # Check if the ID is actually authorized
    if entity_id not in ADMIN_ID and entity_id not in AUTHORIZED_ID:
        await message.reply("❌ This ID is not in the authorized list.")
        return

    try:
        entity = await bot.get_chat(entity_id)  # Fetch user/group details
        entity_name = entity.full_name if entity.type == "private" else entity.title
    except Exception:
        entity_name = "Unknown"

    # Create confirmation buttons with admin_id restriction
    confirm_markup = InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(
                text="✅ Confirm",
                callback_data=DemoteCallback(action="confirm", entity_id=entity_id, admin_id=admin_id).pack()
            ),
            InlineKeyboardButton(
                text="❌ Cancel",
                callback_data=DemoteCallback(action="cancel", entity_id=entity_id, admin_id=admin_id).pack()
            ),
        ]]
    )

    await message.reply(
        f"⚠️ Are you sure you want to demote [{entity_name}](tg://user?id={entity_id}) (`{entity_id}`)?",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=confirm_markup,
    )


@router.callback_query(DemoteCallback.filter(F.action == "confirm"))
async def confirm_demote(callback_query: types.CallbackQuery, callback_data: DemoteCallback) -> None:
    entity_id = callback_data.entity_id
    admin_id = callback_data.admin_id

    # Restrict button clicks to the admin who issued the command
    if callback_query.from_user.id != admin_id:
        await callback_query.answer("🚫 You are not allowed to confirm this action!", show_alert=True)
        return

    # Ensure owner is not demoted (extra safety)
    if entity_id == OWNER_ID:
        await callback_query.answer(
            "😡 Don't dare to demote my owner! 🚀\nBetter demote yourself!",
            show_alert=True
        )
        return

    try:
        entity = await bot.get_chat(entity_id)  # Fetch user/group details
        entity_name = entity.full_name if entity.type == "private" else entity.title
    except Exception:
        entity_name = "Unknown"

    # Remove from authorized lists
    if entity_id in ADMIN_ID:
        ADMIN_ID.remove(entity_id)
        entity_type = "User"
    elif entity_id in AUTHORIZED_ID:
        AUTHORIZED_ID.remove(entity_id)
        entity_type = "Group"
    else:
        await callback_query.answer("This ID is not authorized.", show_alert=True)
        return

    pool = get_pool()
    async with pool.acquire() as conn:
        if entity_id > 0:  # User
            await conn.execute("DELETE FROM admin_id WHERE user_id = $1;", entity_id)
        else:  # Group
            await conn.execute("DELETE FROM authorized_id WHERE group_id = $1;", entity_id)

    await callback_query.message.edit_text(
        f"❌ {entity_type} [{entity_name}](tg://user?id={entity_id}) (`{entity_id}`) has been **demoted** successfully.",
        parse_mode=ParseMode.MARKDOWN
    )


@router.callback_query(DemoteCallback.filter(F.action == "cancel"))
async def cancel_demote(callback_query: types.CallbackQuery, callback_data: DemoteCallback) -> None:
    # Restrict button clicks to the admin who issued the command
    if callback_query.from_user.id != callback_data.admin_id:
        await callback_query.answer("🚫 You are not allowed to cancel this action!", show_alert=True)
        return

    await callback_query.message.edit_text("❌ Demotion cancelled.", parse_mode=ParseMode.MARKDOWN)


class AuthorizeCallback(CallbackData, prefix="authorize"):
    action: str
    entity_id: int
    admin_id: int


@router.message(Command("authorize"))
@admin_only
async def cmd_authorize(message: types.Message) -> None:
    entity_id = None
    admin_id = message.from_user.id  # Admin who initiated the command

    # If command is used with an ID
    args = message.text.split()
    if len(args) == 2 and args[1].lstrip("-").isdigit():
        entity_id = int(args[1])
    # If the command is used as a reply, get the replied user's ID
    elif message.reply_to_message:
        if message.reply_to_message.from_user:
            entity_id = message.reply_to_message.from_user.id
        elif message.reply_to_message.sender_chat:  # For groups/channels
            entity_id = message.reply_to_message.sender_chat.id

    if not entity_id:
        await message.reply(
            "⚠️ Usage: `/authorize <user_or_group_id>` or reply to a user's message with `/authorize`.\n\n"
            "Example:\n`/authorize 123456789` (for users)\nReply to a message with `/authorize` (to pick ID automatically)",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    # Prevent authorizing the owner (already authorized)
    if entity_id == OWNER_ID:
        await message.reply("👑 **The owner is always authorized!** 🚀", parse_mode=ParseMode.MARKDOWN)
        return

    # Check if already authorized
    if entity_id in ADMIN_ID or entity_id in AUTHORIZED_ID:
        await message.reply("✅ This ID is already authorized.")
        return

    try:
        entity = await bot.get_chat(entity_id)  # Fetch user/group details
        entity_name = entity.full_name if entity.type == "private" else entity.title
    except Exception:
        entity_name = "Unknown"

    # Create confirmation buttons with admin_id restriction
    confirm_markup = InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(
                text="✅ Confirm",
                callback_data=AuthorizeCallback(action="confirm", entity_id=entity_id, admin_id=admin_id).pack()
            ),
            InlineKeyboardButton(
                text="❌ Cancel",
                callback_data=AuthorizeCallback(action="cancel", entity_id=entity_id, admin_id=admin_id).pack()
            ),
        ]]
    )

    await message.reply(
        f"⚠️ Are you sure you want to authorize [{entity_name}](tg://user?id={entity_id})?",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=confirm_markup,
    )


@router.callback_query(AuthorizeCallback.filter(F.action == "confirm"))
async def confirm_authorize(callback_query: types.CallbackQuery, callback_data: AuthorizeCallback) -> None:
    entity_id = callback_data.entity_id
    admin_id = callback_data.admin_id

    # Restrict button clicks to the admin who issued the command
    if callback_query.from_user.id != admin_id:
        await callback_query.answer("🚫 You are not allowed to confirm this action!", show_alert=True)
        return

    try:
        entity = await bot.get_chat(entity_id)  # Fetch user/group details
        entity_name = entity.full_name if entity.type == "private" else entity.title
    except Exception:
        entity_name = "Unknown"

    # Add to the appropriate authorization list
    if entity_id > 0:  # User
        ADMIN_ID.append(entity_id)
        entity_type = "User"
    else:  # Group
        AUTHORIZED_ID.append(entity_id)
        entity_type = "Group"

    pool = get_pool()
    async with pool.acquire() as conn:
        if entity_id > 0:  # User
            await conn.execute(
                "INSERT INTO admin_id (user_id) VALUES ($1) ON CONFLICT (user_id) DO NOTHING;", entity_id
            )
        else:  # Group
            await conn.execute(
                "INSERT INTO authorized_id (group_id) VALUES ($1) ON CONFLICT (group_id) DO NOTHING;", entity_id
            )

    await callback_query.message.edit_text(
        f"✅ {entity_type} [{entity_name}](tg://user?id={entity_id}) (`{entity_id}`) has been **authorized** successfully.",
        parse_mode=ParseMode.MARKDOWN
    )


@router.callback_query(AuthorizeCallback.filter(F.action == "cancel"))
async def cancel_authorize(callback_query: types.CallbackQuery, callback_data: AuthorizeCallback) -> None:
    # Restrict button clicks to the admin who issued the command
    if callback_query.from_user.id != callback_data.admin_id:
        await callback_query.answer("🚫 You are not allowed to cancel this action!", show_alert=True)
        return

    await callback_query.message.edit_text("❌ Authorization cancelled.", parse_mode=ParseMode.MARKDOWN)


@router.message(Command("sql"))
@admin_only
async def cmd_sql(message: types.Message, command: CommandObject) -> None:
    args = command.args
    if not args:
        return

    pool = get_pool()
    try:
        async with pool.acquire() as conn:
            res = await conn.fetch(args)
    except Exception as e:
        await message.reply(f"`{e.__class__.__name__}: {str(e)}`")
        return

    if not res:
        await message.reply("No results returned.")
        return

    text = ["*" + " - ".join(res[0].keys()) + "*"]
    for r in res:
        text.append("`" + " - ".join(str(i) for i in r.values()) + "`")
    await message.reply("\n".join(text))


@router.chat_member(ChatMemberUpdatedFilter(JOIN_TRANSITION))
async def new_member(event: types.ChatMemberUpdated) -> None:
    bot = event.bot
    if event.new_chat_member.user.id == bot.id:  # self added to group
        await event.answer(
            "Thanks for adding me.\nAsh bot welcomes you!\nStart a classic game with /startclassic!"
        )
    elif event.chat.id == OFFICIAL_GROUP_ID:
        await event.answer(
            "Welcome to the Word Chain game made by Ash!\nStart a classic game with /startclassic!"
        )


@router.inline_query()
async def inline_handler(inline_query: types.InlineQuery) -> None:
    bot = inline_query.bot
    text = inline_query.query.lower()
    results: list[types.InlineQueryResultUnion] = []

    if not text or inline_query.from_user.id not in VIP and (await amt_donated(inline_query.from_user.id)) < 10:
        for mode in GAME_MODES:
            bot_user = await bot.me()
            command = f"/{mode.command}@{bot_user.username}"
            results.append(
                types.InlineQueryResultArticle(
                    id=str(uuid4()),
                    title="Start " + mode.name,
                    description=command,
                    input_message_content=types.InputTextMessageContent(message_text=command)
                )
            )
        await inline_query.answer(results, is_personal=not text)
        return

    if not is_word(text):
        await inline_query.answer(
            [
                types.InlineQueryResultArticle(
                    id=str(uuid4()),
                    title="A query can only consist of alphabets",
                    description="Try a different query",
                    input_message_content=types.InputTextMessageContent(message_text=r"¯\\_(ツ)\_/¯")
                )
            ],
            is_personal=True
        )
        return

    for word in Words.dawg.iterkeys(text):
        word = word.capitalize()
        results.append(
            types.InlineQueryResultArticle(
                id=str(uuid4()),
                title=word,
                input_message_content=types.InputTextMessageContent(message_text=word)
            )
        )
        if len(results) == 50:  # Max 50 results
            break

    if not results:  # No results
        results.append(
            types.InlineQueryResultArticle(
                id=str(uuid4()),
                title="No results found",
                description="Try a different query",
                input_message_content=types.InputTextMessageContent(message_text=r"¯\\_(ツ)\_/¯")
            )
        )

    await inline_query.answer(results, is_personal=True)


@router.callback_query()
async def callback_query_handler(callback_query: types.CallbackQuery) -> None:
    text = callback_query.data
    if text.startswith("donate"):
        await send_donate_invoice(callback_query.bot, callback_query.from_user.id, int(text.partition(":")[2]) * 100)
    await callback_query.answer()
