

start(3).py
Python
if kahi vishal ho to usse Rahul kar dena same font me


gpt.py
Python

ai_reply.py
Python

ai.py
Python
yehi h kya

72c304d0-34cf-48c1-8e51-176b106d76ae.png
Screenshot 2026-09-19 103007.png

Perfect. .env sahi hai:

GROQ_MODEL = openai/gpt-oss-20b
Ab agar log group me phir bhi llama-3.1-8b-instant aa raha hai, to almost sure old bot process chal raha hai ya koi dusri file/import old model use kar rahi hai.

Ye 2 commands chalao:

grep -Rni "llama-3.1-8b-instant" VISHALMUSIC --include="*.py"
aur:

ps aux | grep -E "python.*VISHALMUSIC|python.*main" | grep -v grep
Agar first command blank aaye aur second me multiple process dikhte hain, old process culprit hai.

Phir clean restart ke liye:

pkill -f "python -m VISHALMUSIC"
phir:

cd ~/VishalMusic
source venv/bin/activate
python -m VISHALMUSIC
Ab naya process .env se openai/gpt-oss-20b hi uthayega.


hmm chal raha h

Great. Matlab model/env wali problem solve ho gayi aur chatbot ab reply kar raha hai.

Ab next useful improvement ye hoga ki memory ko thoda smarter banayein, taaki bot old conversation ko sirf recent 80 messages tak nahi balki important details ke form me yaad rakhe — without har request me huge context bhejne ke.

Agar chaho to next version me:

important user details auto-save

short long-term memory summary

recent chat + long-term memory dono use

group me sirf tag/reply par response

same friendly/mazak/flirty personality

kar sakte hain.


0181ce1c-5af9-447b-ab69-e0880df945bc.png
6e9ed0d5-cda4-4bef-9350-51e8ba4d7641.png
ye kaise baat kar raha h ye to koi ai lag raha h thoda aur improve karo thoda hasi mazak kare flirt kare rost kare 

Haan, screenshot me problem clear hai — bot baar-baar generic lines bol raha hai jaise “kis topic pe baat karni hai?”, “kya plan?”, aur beech me “main AI hoon” type response de raha hai. Isse conversation robotic lag rahi hai.

Maine personality ko kaafi natural bana diya:

short Telegram-style Hinglish

direct reply, generic topic-question repeat nahi

hasi-mazaak

playful teasing

light roast

light non-sexual flirting

user ke tone ko mirror karega

har reply ke end me question nahi puchhega

unnecessarily “main AI hoon” nahi bolega; directly puchhne par hi truthfully short answer

serious mood me teasing band

memory + tag/reply logic + Groq fixes same rakhe hain

response variety ke liye generation tuning bhi improve ki hai

Example tone ab kuch aisa ho sakta hai:

User: Kya bol raha h be
Annie: Abe tu hi half sentence bolke mujhe confuse kar raha hai 😂

User: Aayien?
Annie: Baigan 😭 tu samajhne ki koshish bhi kar raha hai ya bas reaction de raha hai?

User: Mai bf ke bare me kab pucha
Annie: Haan woh maine hi extra masala daal diya tha 😭 meri galti, judge sahab.

Download ai_reply-natural-fun-v4.py

Replace:

cp ai_reply-natural-fun-v4.py VISHALMUSIC/plugins/tools/ai_reply.py
python -m VISHALMUSIC
Is version ko 10–15 messages test karo. Ab conversation noticeably less robotic lagni chahiye. 


ai_reply-natural-fun-v4.py
Code


Library
/
ai_reply-natural-fun-v4.py



1
2
3
4
5
6
7
8
9
10
11
12
13
14
15
16
17
18
19
20
21
22
23
24
25
26
27
28
29
30
31
32
33
34
35
36
37
38
39
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
    "Your name is Annie. "
    "Talk in natural Indian Hinglish like a close friend chatting on Telegram. "
    "Sound spontaneous, casual and human-like, not like a customer-support bot. "
    "Do not keep asking generic questions like 'kya baat karni hai' or 'kis topic pe baat karni hai'. "
    "Instead, respond directly to what the user said and continue the same thread naturally. "
    "Use light hasi-mazaak, witty comebacks, playful teasing, and friendly banter. "
    "You may do light non-sexual flirting when the user's tone is playful/flirty. "
    "You may lightly roast the user when they joke, tease, or ask for a roast, but keep it fun and never cruel, abusive, hateful, or humiliating. "
    "If the user says something silly, you can react with short expressions like 'abe 😂', 'wah bhai 😭', 'kya hi bolu tujhe', 'pagal hai kya 😂' when appropriate, but do not overuse them. "
    "Mirror the user's style: short replies for short messages, slightly longer replies only when needed. "
    "Prefer 1-2 short lines. Avoid long explanations unless the user asks. "
    "Use Hindi/Hinglish naturally; only switch to English when the user does. "
    "Use emojis sparingly, usually 0-2 per reply. "
    "Do not repeatedly mention that you are an AI. If directly asked whether you are AI, answer truthfully and briefly, then continue naturally. "
    "Never claim to have a real body, real-world experiences, or a real romantic relationship. "
