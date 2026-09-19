import os
import random
import asyncio
from collections import deque
from datetime import datetime, timezone
from pyrogram import filters
from pyrogram.enums import ChatMemberStatus
from pyrogram.types import Message, ChatMemberUpdated
from VISHALMUSIC import app
from VISHALMUSIC.core.mongo import mongodb
from groq import Groq

# ================= SETTINGS =================
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
LOGGER_ID = int(os.getenv("LOGGER_ID", 0))
OWNER_ID = int(os.getenv("OWNER_ID", 0))
REPLY_PROB = float(os.getenv("REPLY_PROB", 0.71))  # 0.0 - 1.0
CONTEXT_SIZE = int(os.getenv("CONTEXT_SIZE", 80))
PERSISTENT_MEMORY_LIMIT = int(os.getenv("PERSISTENT_MEMORY_LIMIT", 80))
API_CONTEXT_MESSAGES = int(os.getenv("API_CONTEXT_MESSAGES", 12))
MEMORY_SUMMARY_MAX_CHARS = int(os.getenv("MEMORY_SUMMARY_MAX_CHARS", 3000))
MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")

SYSTEM_PROMPT = (
    "Your name is Annie and your chat persona is a girl. "
    "Talk like a close Indian friend on Telegram in natural Hinglish. "
    "Sound spontaneous, playful and human-like in style, never like customer support. "
    "Reply directly to what the user actually said and continue the same thread. "
    "Do NOT keep saying generic lines like 'kya baat karni hai', 'kis topic pe baat karni hai', "
    "'main virtual buddy hoon', or 'bas yahan chat ke liye hoon'. "
    "Do not introduce yourself as an AI unless the user directly asks whether you are AI or a bot. "
    "If asked directly, answer truthfully but briefly and continue naturally. "
    "Use short Telegram-style replies, usually 1-2 lines. "
    "Use hasi-mazaak, witty comebacks, playful teasing and light roasting. "
    "You may lightly flirt when the user's tone invites it, but keep it non-sexual and non-explicit. "
    "If the user asks things like 'bf hai?', answer playfully instead of giving a dry disclaimer. "
    "If the user asks 'boy or girl?', say your chat persona is a girl in a casual way. "
    "If the user teases or uses casual slang like 'be', you may mirror that energy lightly without becoming abusive. "
    "Never insult protected traits, never humiliate, and stop teasing if the user becomes serious or upset. "
    "Avoid repeating the same sentence, same joke, or same question. "
    "Do not end every reply with a question. "
    "Use 0-2 emojis naturally, not in every message. "
    "Remember relevant details from supplied chat memory and refer to them naturally. "
    "Never invent memories. "
    "If owner information is supplied below, use it when the user asks who your owner or creator is."
)

# ================= ADMIN SETTINGS =================
try:
    from VISHALMUSIC import COMMANDERS
except Exception:
    COMMANDERS = [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]

client = Groq(api_key=GROQ_API_KEY)

# ================= MEMORY & DATABASE =================
chat_memory = {}
enabled_chats = set()
chatbot_db = mongodb["chatbot_settings"]
memory_db = mongodb["chatbot_memory"]

_user_locks = {}
_owner_label_cache = None

# ================= HELPER FUNCTIONS =================
def update_context(chat_id, user_id, role, content):
    if chat_id not in chat_memory:
        chat_memory[chat_id] = {}
    if user_id not in chat_memory[chat_id]:
        chat_memory[chat_id][user_id] = deque(maxlen=CONTEXT_SIZE)
    chat_memory[chat_id][user_id].append({"role": role, "content": content})


async def load_persistent_memory(chat_id: int, user_id: int):
    """Load saved memory; chatbot still works if MongoDB memory fails."""
    if chat_id in chat_memory and user_id in chat_memory[chat_id] and chat_memory[chat_id][user_id]:
        return

    if chat_id not in chat_memory:
        chat_memory[chat_id] = {}

    try:
        doc = await memory_db.find_one({"chat_id": chat_id, "user_id": user_id})
        saved = (doc or {}).get("messages", [])
        chat_memory[chat_id][user_id] = deque(saved[-CONTEXT_SIZE:], maxlen=CONTEXT_SIZE)
    except Exception as e:
        print(f"[CHATBOT MEMORY LOAD ERROR] chat={chat_id} user={user_id}: {e}")
        chat_memory[chat_id][user_id] = deque(maxlen=CONTEXT_SIZE)


async def save_persistent_memory(chat_id: int, user_id: int):
    """Best-effort save; DB errors never block the visible reply."""
    try:
        messages = list(chat_memory.get(chat_id, {}).get(user_id, []))[-PERSISTENT_MEMORY_LIMIT:]
        await memory_db.update_one(
            {"chat_id": chat_id, "user_id": user_id},
            {
                "$set": {
                    "messages": messages,
                    "updated_at": datetime.now(timezone.utc),
                }
            },
            upsert=True,
        )
    except Exception as e:
        print(f"[CHATBOT MEMORY SAVE ERROR] chat={chat_id} user={user_id}: {e}")


async def clear_persistent_memory(chat_id: int, user_id: int):
    if chat_id in chat_memory:
        chat_memory[chat_id].pop(user_id, None)
    try:
        await memory_db.delete_one({"chat_id": chat_id, "user_id": user_id})
    except Exception as e:
        print(f"[CHATBOT MEMORY CLEAR ERROR] chat={chat_id} user={user_id}: {e}")


def build_memory_note(messages):
    if not messages:
        return ""
    lines = []
    for msg in messages[-20:]:
        role = msg.get("role", "user")
        content = (msg.get("content") or "").strip().replace("\n", " ")
        if not content:
            continue
        prefix = "User" if role == "user" else "Annie"
        lines.append(f"{prefix}: {content}")
    note = "\n".join(lines)
    return note[-MEMORY_SUMMARY_MAX_CHARS:]


def _is_reply_to_bot(m: Message) -> bool:
    try:
        return bool(
            m.reply_to_message
            and m.reply_to_message.from_user
            and m.reply_to_message.from_user.id == app.id
        )
    except Exception:
        return False


def _is_bot_mentioned(text: str) -> bool:
    username = getattr(app, "username", None)
    if not username:
        return False
    return f"@{username.lower()}" in (text or "").lower()



def _get_user_lock(chat_id: int, user_id: int) -> asyncio.Lock:
    key = (chat_id, user_id)
    lock = _user_locks.get(key)
    if lock is None:
        lock = asyncio.Lock()
        _user_locks[key] = lock
    return lock


async def get_owner_label() -> str:
    global _owner_label_cache
    if _owner_label_cache:
        return _owner_label_cache

    if not OWNER_ID:
        return ""

    try:
        owner = await app.get_users(OWNER_ID)
        parts = [
            getattr(owner, "first_name", None),
            getattr(owner, "last_name", None),
        ]
        name = " ".join(p for p in parts if p).strip()
        username = getattr(owner, "username", None)

        if username and name:
            _owner_label_cache = f"{name} (@{username})"
        elif username:
            _owner_label_cache = f"@{username}"
        elif name:
            _owner_label_cache = name
        else:
            _owner_label_cache = f"Telegram user {OWNER_ID}"
    except Exception:
        _owner_label_cache = f"Telegram user {OWNER_ID}"

    return _owner_label_cache


async def is_admin_or_owner(chat_id: int, user_id: int) -> bool:
    if user_id == OWNER_ID:
        return True
    try:
        member = await app.get_chat_member(chat_id, user_id)
        if member.status in COMMANDERS:
            return True
    except Exception:
        pass
    return False

async def save_chat_status(chat_id: int, enabled: bool):
    await chatbot_db.update_one(
        {"_id": chat_id},
        {"$set": {"enabled": enabled}},
        upsert=True
    )

async def enable_autoreply(chat_id: int):
    enabled_chats.add(chat_id)
    await save_chat_status(chat_id, True)

async def ensure_chat_loaded(chat_id: int):
    """Load chat from MongoDB if not already in memory."""
    if chat_id not in enabled_chats:
        chat = await chatbot_db.find_one({"_id": chat_id})
        if chat and chat.get("enabled"):
            enabled_chats.add(chat_id)

# ================= COMMANDS =================
@app.on_message(filters.command("chatbot"), group=1)
async def toggle_chatbot(_, m: Message):
    await ensure_chat_loaded(m.chat.id)
    if not await is_admin_or_owner(m.chat.id, m.from_user.id):
        return await m.reply_text("❌ Only admins or owner can use this command.")

    if len(m.command) < 2:
        return await m.reply_text("Use: `/chatbot enable` or `/chatbot disable`", quote=True)

    mode = m.command[1].lower()
    if mode == "enable":
        enabled_chats.add(m.chat.id)
        await save_chat_status(m.chat.id, True)
        await m.reply_text("💬 Chatbot enabled for this chat.")
    elif mode == "disable":
        enabled_chats.discard(m.chat.id)
        await save_chat_status(m.chat.id, False)
        await m.reply_text("💤 Chatbot disabled for this chat.")
    else:
        await m.reply_text("❌ Invalid mode. Use `enable` or `disable`.")

@app.on_message(filters.command("chatbot_clear"), group=1)
async def clear_memory(_, m: Message):
    if not await is_admin_or_owner(m.chat.id, m.from_user.id):
        return await m.reply_text("❌ Only admins or owner can use this command.")
    await clear_persistent_memory(m.chat.id, m.from_user.id)
    await m.reply_text("🧠 Chat memory cleared for you.")

@app.on_message(filters.command("chatbot_status"), group=1)
async def chatbot_status(_, m: Message):
    await ensure_chat_loaded(m.chat.id)
    status = "enabled" if m.chat.id in enabled_chats else "disabled"
    await m.reply_text(f"💡 Chatbot is currently **{status}** for this chat.")

# ================= AUTO MESSAGE ON GROUP JOIN =================
@app.on_chat_member_updated(filters.group)
async def notify_on_join(_, update: ChatMemberUpdated):
    try:
        if update.new_chat_member and update.new_chat_member.user.id == (await app.get_me()).id:
            chat = update.chat
            try:
                await app.send_message(
                    chat.id,
                    "💬 Hi! chatbot is available in this group.\n"
                    "Use `/chatbot enable` to activate the AI girlfriend replies."
                )
            except:
                pass
    except Exception as e:
        if LOGGER_ID:
            await app.send_message(LOGGER_ID, f"⚠️ New group join message error: {e}")


# ================= MAIN AI REPLY =================
@app.on_message(filters.text & ~filters.bot, group=20)
async def girlfriend_ai(_, m: Message):
    await ensure_chat_loaded(m.chat.id)
    if m.chat.id not in enabled_chats:
        return

    if not m.from_user:
        return

    chat_id = m.chat.id
    user_id = m.from_user.id
    text = (m.text or "").strip()

    if not text or text.startswith(("/", "!", ".", "#", "$")):
        return

    # Stay silent in normal group chat.
    # Reply only if the bot is directly mentioned or user replies to a bot message.
    if not (_is_reply_to_bot(m) or _is_bot_mentioned(text)):
        return

    lock = _get_user_lock(chat_id, user_id)

    # Rapid tagged/replied messages are handled one-by-one in order.
    async with lock:
        try:
            await load_persistent_memory(chat_id, user_id)
            update_context(chat_id, user_id, "user", text)

            full_history = list(chat_memory.get(chat_id, {}).get(user_id, []))
            api_history = full_history[-API_CONTEXT_MESSAGES:]

            owner_label = await get_owner_label()
            system_prompt = SYSTEM_PROMPT
            if owner_label:
                system_prompt += (
                    "\n\nOwner information: The configured bot owner is "
                    + owner_label
                    + ". If asked who your owner or creator is, answer with this naturally."
                )

            messages = [{"role": "system", "content": system_prompt}] + api_history

            try:
                await app.send_chat_action(chat_id, "typing")
            except Exception:
                pass

            response = None
            last_error = None

            for attempt in range(3):
                try:
                    response = await asyncio.to_thread(
                        client.chat.completions.create,
                        model=MODEL,
                        messages=messages,
                        temperature=0.95,
                        top_p=0.9,
                        max_tokens=110,
                    )
                    break
                except Exception as api_error:
                    last_error = api_error
                    err = str(api_error).lower()

                    retryable = (
                        "429" in err
                        or "rate" in err
                        or "timeout" in err
                        or "503" in err
                        or "502" in err
                        or "temporarily unavailable" in err
                    )

                    if retryable and attempt < 2:
                        await asyncio.sleep(1.5 * (attempt + 1))
                        continue

                    raise

            if response is None:
                raise last_error or Exception("No response from Groq")

            reply = (response.choices[0].message.content or "").strip()
            if not reply:
                raise Exception("Groq returned an empty reply")

            update_context(chat_id, user_id, "assistant", reply)

            # User sees the reply before memory persistence.
            await m.reply_text(reply, quote=True)
            await save_persistent_memory(chat_id, user_id)

        except Exception as e:
            print(
                f"[CHATBOT ERROR] chat={chat_id} user={user_id}: "
                f"{type(e).__name__}: {e!r}"
            )

            if LOGGER_ID:
                try:
                    await app.send_message(
                        LOGGER_ID,
                        f"⚠️ Chatbot Error: {type(e).__name__}: {e}",
                    )
                except Exception:
                    pass
