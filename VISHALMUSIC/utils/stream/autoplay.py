import asyncio
import os
import random
import re
import time
import traceback
from difflib import SequenceMatcher

import aiohttp
from py_yt import VideosSearch

from VISHALMUSIC import app
from VISHALMUSIC.core.mongo import mongodb
from VISHALMUSIC.misc import db
from VISHALMUSIC.platforms.Youtube import YouTubeAPI

yt = YouTubeAPI()
autoplay_db = mongodb.autoplay
history_db = mongodb.autoplay_history

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  PROTECTION SYSTEM
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

RECENT = {}
RECENT_TITLES = {}
RECENT_MOVIES = {}
RECENT_ARTISTS = {}
AUTO_PLAYING = {}
AUTOPLAY_CONTEXT = {}

# Autoplay recommendation tuning
AUTOPLAY_MIN_SECONDS = int(os.getenv("AUTOPLAY_MIN_SECONDS", "100"))
AUTOPLAY_MAX_SECONDS = int(os.getenv("AUTOPLAY_MAX_SECONDS", "420"))
AUTOPLAY_RESULTS_PER_QUERY = max(4, min(int(os.getenv("AUTOPLAY_RESULTS_PER_QUERY", "6")), 8))
AUTOPLAY_RECENT_LIMIT = max(20, min(int(os.getenv("AUTOPLAY_RECENT_LIMIT", "80")), 200))
# Mongo me history kitni der yaad rakhni hai (bot restart ke baad bhi repeat na ho).
AUTOPLAY_HISTORY_TTL = int(float(os.getenv("AUTOPLAY_HISTORY_TTL_HOURS", "3")) * 3600)
LOADED_HISTORY = set()
# Pool exhaust hone par history poori saaf nahi hoti; sirf itne SABSE RECENT songs
# block rehte hain (purane wapas aa sakte hain, haal ke nahi).
AUTOPLAY_KEEP_ON_EXHAUST = max(0, int(os.getenv("AUTOPLAY_KEEP_ON_EXHAUST", "15")))
# Debug: pichle search me kis wajah se kitne candidates reject hue.
LAST_REJECTS = {}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🇮🇳 INDIAN LANGUAGE DATABASE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

LANG_DB = {
    "hindi": [
        "hindi", "bollywood", "hindi song", "bollywood song",
        "arijit", "jubin", "atif", "shreya ghoshal", "sonu nigam",
        "udit narayan", "alka yagnik", "kumar sanu",
    ],
    "punjabi": [
        "punjabi", "punjabi song", "sidhu", "diljit", "karan aujla",
        "ap dhillon", "jatt", "gabru", "pind", "ve jatta",
    ],
    "english": [
        "english", "english song", "ed sheeran", "taylor swift",
        "justin bieber", "dua lipa", "weeknd", "bruno mars", "coldplay",
        "imagine dragons", "post malone", "billie eilish", "ariana grande",
        "the chainsmokers", "eminem", "adele", "maroon 5", "charlie puth",
        "selena gomez", "shawn mendes", "harry styles", "alan walker",
    ],
    "bhojpuri": [
        "bhojpuri", "bhojpuri song", "hamaar bhojpuri",
        "pawan singh", "khesari", "khesari lal", "shilpi raj",
        "akshara singh", "nirahua", "neelkamal singh",
        "arvind akela kallu", "pramod premi", "ritesh pandey",
        "saiya", "saiyan", "raja ji", "tohar", "hamra", "bhojpuriya",
        "raate diya", "diya butake", "butake", "ka ho", "ae raja",
        "ho raja", "tohra", "hamke", "raua", "babua", "bhatar",
    ],
    "haryanvi": [
        "haryanvi", "haryanvi song", "khasa", "masoom sharma",
        "haryana", "jaat",
    ],
    "gujarati": ["gujarati", "gujju", "garba", "gujarati song"],
    "tamil": ["tamil", "tamil song", "kollywood", "anirudh", "tamil cinema"],
    "telugu": ["telugu", "telugu song", "tollywood", "devi sri", "telugu cinema"],
    "bengali": ["bengali", "bangla", "bengali song", "bangla song"],
    "marathi": [
        "marathi", "marathi song", "maharashtra", "ajay atul",
        "ajay gogavale", "avdhoot gupte", "swapnil bandodkar",
        "tula", "tujha", "tujhya", "majha", "majhi", "maajha",
        "premachi", "manat", "ga", "re mana",
    ],
    "urdu": ["urdu", "urdu song", "pakistani", "nusrat", "qawwali"],
}

ARTIST_LANG = {
    "arijit singh": "hindi",
    "atif aslam": "hindi",
    "jubin nautiyal": "hindi",
    "badshah": "hindi",
    "yo yo honey singh": "hindi",
    "neha kakkar": "hindi",
    "shreya ghoshal": "hindi",
    "sonu nigam": "hindi",
    "alka yagnik": "hindi",
    "udit narayan": "hindi",
    "kumar sanu": "hindi",
    "lata mangeshkar": "hindi",
    "kishore kumar": "hindi",
    "mohammad rafi": "hindi",
    "sidhu moosewala": "punjabi",
    "diljit dosanjh": "punjabi",
    "karan aujla": "punjabi",
    "ap dhillon": "punjabi",
    "gurinder gill": "punjabi",    "pawan singh": "bhojpuri",
    "khesari lal yadav": "bhojpuri",
    "khesari": "bhojpuri",
    "shilpi raj": "bhojpuri",
    "akshara singh": "bhojpuri",
    "ritesh pandey": "bhojpuri",
    "pramod premi yadav": "bhojpuri",
    "neelkamal singh": "bhojpuri",
    "arvind akela kallu": "bhojpuri",
    "dinesh lal yadav": "bhojpuri",
    "nirahua": "bhojpuri",
}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🎭 MOOD DATABASE (Indian Context)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

MOOD_DB = {
    "sad": [
        "sad", "broken", "heartbreak", "heart broken", "bewafa", "alone",
        "cry", "dard", "tanha", "rula", "judai", "judaai", "adhura",
        "sad song", "emotional",
    ],
    "romantic": [
        "love", "romantic", "romance", "ishq", "pyaar", "pyar",
        "mohabbat", "love song", "romantic song", "prem", "aashiq",
    ],
    "party": [
        "party", "dj", "dance", "club", "bhangra", "party song",
        "dj song", "dance song", "masala", "club song",
    ],
    "wedding": [
        "wedding", "shaadi", "marriage", "dulhan", "mehendi",
        "mehndi", "sangeet", "baraat",
    ],
    "devotional": [
        "devotional", "bhajan", "aarti", "mantra", "shiva", "krishna",
        "shri ram", "siya ram", "ganesha", "hanuman", "mahadev", "bhakti",
    ],
    "oldschool": [
        "classic", "90s", "80s", "kishore", "lata", "rafi",
        "old song", "retro", "purana",
    ],
    "sufi": ["sufi", "qawwali", "nusrat", "kalam", "sufiana"],
}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🎤 INDIAN ARTIST DATABASE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

ARTIST_DB = {
    "arijit singh": ["arijit", "arijit singh", "arijit song", "arijit new"],
    "atif aslam": ["atif", "atif aslam", "atif song"],
    "sidhu moosewala": ["sidhu", "sidhu moosewala", "sidhu song"],
    "diljit dosanjh": ["diljit", "diljit dosanjh", "diljit song"],
    "karan aujla": ["karan", "karan aujla", "karan song"],
    "jubin nautiyal": ["jubin", "jubin nautiyal", "jubin song"],
    "badshah": ["badshah", "badshah song", "badshah new"],
    "yo yo honey singh": ["honey singh", "yo yo", "brown rang", "yo yo honey singh"],
    "neha kakkar": ["neha kakkar", "neha song", "neha new"],
    "shreya ghoshal": ["shreya", "shreya ghoshal", "shreya song"],
    "sonu nigam": ["sonu", "sonu nigam", "sonu song"],
    "alka yagnik": ["alka", "alka yagnik", "alka song"],
    "udit narayan": ["udit", "udit narayan", "udit song"],
    "kumar sanu": ["kumar sanu", "kumar song"],
    "lata mangeshkar": ["lata", "lata mangeshkar", "lata song"],
    "kishore kumar": ["kishore", "kishore kumar", "kishore song"],
    "mohammad rafi": ["rafi", "mohammad rafi", "rafi song"],
    "ap dhillon": ["ap dhillon", "ap", "dhillon", "ap song"],
    "gurinder gill": ["gurinder gill", "gill", "gurinder song"],    "pawan singh": ["pawan singh", "power star pawan singh"],
    "khesari lal yadav": ["khesari lal", "khesari lal yadav", "khesari"],
    "shilpi raj": ["shilpi raj"],
    "akshara singh": ["akshara singh"],
    "ritesh pandey": ["ritesh pandey"],
    "pramod premi yadav": ["pramod premi", "pramod premi yadav"],
    "neelkamal singh": ["neelkamal singh"],
    "arvind akela kallu": ["arvind akela kallu", "kallu"],
    "dinesh lal yadav": ["dinesh lal yadav", "nirahua"],
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🎬 INDIAN MOVIE DATABASE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

MOVIE_DB = {
    "animal": ["animal", "animal song", "animal movie"],
    "kabir singh": ["kabir singh", "kabir movie"],
    "aashiqui 2": ["aashiqui", "aashiqui 2", "aashiqui song"],
    "shershaah": ["shershaah", "shershaah song", "shershaah movie"],
    "pushpa": ["pushpa", "pushpa song", "pushpa movie", "srivali"],
    "kgf": ["kgf", "kgf song", "rocky bhai"],
    "pathaan": ["pathaan", "pathaan song", "shah rukh"],
    "jawan": ["jawan", "jawan song", "jawan movie"],
    "dunki": ["dunki", "dunki song", "dunki movie"],
    "gadar 2": ["gadar", "gadar 2", "gadar song"],
    "rocky aur rani": ["rocky aur rani"],
    "tu jhoothi main makkaar": ["tu jhoothi", "tjmm"],
    "bhool bhulaiyaa 2": ["bhool bhulaiyaa", "bb2", "kartik aaryan"],
    "brahmastra": ["brahmastra"],
    "tanhaji": ["tanhaji", "ajay devgn", "tanhaji song"],
    "chhichhore": ["chhichhore", "sushant", "chhichhore song"],
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  TRENDING KEYWORDS (Indian)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

TRENDING_STYLES = [
    "latest hindi songs",
    "trending punjabi songs",
    "bollywood hits",
    "new indian music",
    "viral indian songs",
    "top 50 india",
    "indian hip hop",
    "indie indian",
]

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🌍 DETECT LANGUAGE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🆕 RELATED / CATEGORY CONTROL
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Same-category singers. Jab ek hi artist ke 2 songs lagatar baj chuke ho to
# autoplay in logo me rotate karta hai (category same, repeat feel nahi).
RELATED_ARTISTS = {
    "arijit singh": ["jubin nautiyal", "atif aslam", "b praak", "darshan raval", "armaan malik", "shreya ghoshal"],
    "atif aslam": ["arijit singh", "rahat fateh ali khan", "mohit chauhan", "jubin nautiyal"],
    "jubin nautiyal": ["arijit singh", "darshan raval", "armaan malik", "stebin ben"],
    "shreya ghoshal": ["arijit singh", "sunidhi chauhan", "shaan", "palak muchhal"],
    "sonu nigam": ["udit narayan", "kumar sanu", "shaan", "kk"],
    "udit narayan": ["kumar sanu", "alka yagnik", "sonu nigam", "abhijeet"],
    "alka yagnik": ["udit narayan", "kumar sanu", "sadhana sargam"],
    "kumar sanu": ["udit narayan", "alka yagnik", "abhijeet"],
    "lata mangeshkar": ["asha bhosle", "mohammad rafi", "kishore kumar", "mukesh"],
    "kishore kumar": ["mohammad rafi", "mukesh", "lata mangeshkar", "asha bhosle"],
    "mohammad rafi": ["kishore kumar", "mukesh", "lata mangeshkar", "manna dey"],
    "neha kakkar": ["tony kakkar", "payal dev", "jubin nautiyal", "dhvani bhanushali"],
    "badshah": ["yo yo honey singh", "raftaar", "king", "guru randhawa"],
    "yo yo honey singh": ["badshah", "raftaar", "guru randhawa"],
    "sidhu moosewala": ["karan aujla", "diljit dosanjh", "ap dhillon", "shubh"],
    "diljit dosanjh": ["karan aujla", "ap dhillon", "guru randhawa", "sidhu moosewala"],
    "karan aujla": ["ap dhillon", "shubh", "sidhu moosewala", "diljit dosanjh"],
    "ap dhillon": ["karan aujla", "shubh", "gurinder gill", "sidhu moosewala"],
    "gurinder gill": ["ap dhillon", "karan aujla", "shubh"],
    "pawan singh": ["khesari lal yadav", "arvind akela kallu", "neelkamal singh", "shilpi raj"],
    "khesari lal yadav": ["pawan singh", "arvind akela kallu", "neelkamal singh", "shilpi raj"],
    "shilpi raj": ["pawan singh", "khesari lal yadav", "akshara singh"],
    "akshara singh": ["shilpi raj", "pawan singh", "khesari lal yadav"],
    "arvind akela kallu": ["pawan singh", "khesari lal yadav", "neelkamal singh"],
    "neelkamal singh": ["pawan singh", "khesari lal yadav", "arvind akela kallu"],
}

# Search query me mood ko natural words me bolna (sirf "oldschool" likhne se
# YouTube kuch nahi samajhta).
MOOD_QUERY = {
    "sad": "sad",
    "romantic": "romantic love",
    "party": "party dance",
    "wedding": "shaadi sangeet",
    "devotional": "bhajan",
    "oldschool": "old classic 90s",
    "sufi": "sufi",
}
# In moods me year ("2026") lagane se purane/devotional songs gayab ho jate hain.
NO_YEAR_MOODS = {"oldschool", "devotional", "sufi"}

# Konsa mood kis mood ke saath chal sakta hai.
MOOD_COMPAT = {
    "sad": {"sad", "romantic", "sufi"},
    "romantic": {"romantic", "sad", "sufi"},
    "party": {"party", "wedding"},
    "wedding": {"wedding", "party", "romantic"},
    "devotional": {"devotional"},
    "oldschool": {"oldschool", "romantic", "sad", "sufi"},
    "sufi": {"sufi", "sad", "romantic"},
}
NORMAL_ALLOWED = {"romantic", "sad", "sufi", "party", "oldschool"}
# Ye categories kabhi cross nahi hongi (bhajan <-> pop, shaadi <-> sad etc.)
HARD_CATEGORIES = {"devotional", "wedding"}
# Seed party/shaadi nahi hai to party/bhajan/shaadi wale songs kabhi nahi aayenge.
HARD_CANDIDATE_MOODS = {"devotional", "wedding", "party"}

# Ek hi singer ke max itne songs lagatar. Uske baad related singers.
AUTOPLAY_MAX_SAME_ARTIST = max(1, int(os.getenv("AUTOPLAY_MAX_SAME_ARTIST", "2")))
# Local/unknown singers ko rokne ke liye minimum views (regional me 1/3).
AUTOPLAY_MIN_VIEWS = int(os.getenv("AUTOPLAY_MIN_VIEWS", "300000"))
REGIONAL_LANGS = {"bhojpuri", "haryanvi", "gujarati", "marathi", "bengali", "urdu"}

# Purane daur ke singers -> in par era "old" lagta hai.
OLD_ERA_ARTISTS = {
    "kishore kumar", "lata mangeshkar", "mohammad rafi", "asha bhosle",
    "mukesh", "manna dey", "kumar sanu", "alka yagnik", "udit narayan",
}
OLD_TOP_ARTISTS = [
    "kishore kumar", "mohammad rafi", "lata mangeshkar", "kumar sanu",
    "udit narayan", "alka yagnik", "asha bhosle", "mukesh",
]
# Singer unknown ho to local singers ki jagah in popular singers se related pool.
LANG_TOP_ARTISTS = {
    "hindi": ["arijit singh", "jubin nautiyal", "atif aslam", "shreya ghoshal", "sonu nigam", "neha kakkar"],
    "punjabi": ["diljit dosanjh", "karan aujla", "ap dhillon", "sidhu moosewala", "shubh"],
    "bhojpuri": ["pawan singh", "khesari lal yadav", "arvind akela kallu", "neelkamal singh", "shilpi raj"],
    "haryanvi": ["masoom sharma", "khasa aala chahar", "renuka panwar"],
    "english": ["ed sheeran", "the weeknd", "dua lipa", "justin bieber"],
}
OLD_DISCOVERY_TERMS = ["evergreen", "superhit", "classic", "golden hits", "old is gold", "90s hits"]

# Ye words akele language decide nahi karenge (Hindi songs me bhi aate hain).
WEAK_LANG_KEYS = {
    "saiya", "saiyan", "raja ji", "tohar", "hamra", "tohra", "hamke", "raua",
    "babua", "bhatar", "ka ho", "ho raja", "ae raja",
    "tula", "tujha", "tujhya", "majha", "majhi", "maajha", "premachi",
    "manat", "ga", "re mana", "pind", "gabru", "jaat", "haryana", "pakistani",
}

# Aise short aliases jo kisi bhi title me mil jate hain ("ap", "karan"...).
AMBIGUOUS_ALIASES = {"ap", "karan", "gill", "sonu", "dhillon", "neha song"}

HARD_BAD_WORDS = [
    "slowed", "reverb", "8d", "lofi", "lo-fi", "nightcore",
    "dj remix", "remix", "mashup", "bass boosted", "sped up",
    "cover", "karaoke", "instrumental", "acoustic cover",
    "live performance", "live concert", "reaction", "status",
    "whatsapp status", "shorts", "short video", "edit audio",
    "fanmade", "fan made", "teaser", "trailer", "promo",
    "tutorial", "how to", "dance cover", "lyrics status",
    "jukebox", "audio jukebox", "nonstop", "non stop", "non-stop",
    "playlist", "full album", "all songs", "complete album",
    "compilation", "medley", "greatest hits", "best of",
    "1 hour", "2 hour", "3 hour", "one hour", "hours of",
    # new
    "unplugged", "reprise", "female version", "male version", "ringtone",
    "bgm", "interview", "making of", "behind the scenes", "full movie",
    "podcast", "dialogue", "scene",
]
# Pehle "cover" jaisa substring "discover"/"recovery" me bhi match ho jata tha.
# Ab sirf poora word/phrase match hota hai.
_HARD_BAD_RE = re.compile(
    r"(?<![a-z0-9])(?:"
    + "|".join(re.escape(w) for w in sorted(HARD_BAD_WORDS, key=len, reverse=True))
    + r")(?![a-z0-9])"
)

SCRIPT_LANG = [
    ("\u0A00", "\u0A7F", "punjabi"),   # Gurmukhi
    ("\u0A80", "\u0AFF", "gujarati"),
    ("\u0B80", "\u0BFF", "tamil"),
    ("\u0C00", "\u0C7F", "telugu"),
    ("\u0980", "\u09FF", "bengali"),
]


def _word_or_phrase_present(value: str, key: str) -> bool:
    """Whole word / whole phrase match (substring match nahi)."""
    value = str(value or "").lower()
    key = str(key or "").lower().strip()
    if not key:
        return False
    return re.search(
        rf"(?<![a-z0-9]){re.escape(key)}(?![a-z0-9])",
        value,
    ) is not None


def _script_lang(text: str) -> str:
    for ch in str(text or ""):
        for lo, hi, lang in SCRIPT_LANG:
            if lo <= ch <= hi:
                return lang
    return ""


def _channel_name(item: dict) -> str:
    """py_yt kabhi channel dict deta hai ({name,id,link}); sirf name lo."""
    ch = item.get("channel") or item.get("channelTitle") or item.get("uploader") or ""
    if isinstance(ch, dict):
        ch = ch.get("name") or ""
    return str(ch)


def _age_years(item: dict):
    """py_yt 'publishedTime' ("11 years ago") -> saal. Unknown = None."""
    raw = str(item.get("publishedTime") or item.get("published") or "").lower()
    m = re.search(r"(\d+)\s*(year|month|week|day|hour)", raw)
    if not m:
        return None
    n, unit = int(m.group(1)), m.group(2)
    return n if unit == "year" else n / {"month": 12, "week": 52, "day": 365, "hour": 8760}[unit]


def _year_in_title(title: str) -> int:
    m = re.search(r"(?<!\d)(19[5-9]\d|20[0-3]\d)(?!\d)", str(title or ""))
    return int(m.group(1)) if m else 0


def _related_pool(artist: str, lang: str, era: str = ""):
    """Related singers; unknown singer ho to language/era ke popular singers."""
    a = (artist or "").lower()
    pool = list(RELATED_ARTISTS.get(a, []))
    if not pool:
        if era == "old" and lang == "hindi":
            pool = list(OLD_TOP_ARTISTS)
        else:
            pool = list(LANG_TOP_ARTISTS.get(lang, []))
    return [x for x in pool if x != a]


def _artist_from_rows(rows, vidid: str = "") -> str:
    """YouTube '<Artist> - Topic' channel se pakka artist nikalo."""
    for item in rows or []:
        if vidid and item.get("id") != vidid:
            continue
        name = _channel_name(item).strip()
        if name.lower().endswith("- topic"):
            return name[:-7].strip().lower()
    return ""


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🌍 DETECT LANGUAGE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def fetch_track_meta(title: str, vidid: str = ""):
    if not title:
        return []
    try:
        data = await VideosSearch(title, limit=3).next()
        rows = data.get("result", []) or []
        return sorted(
            rows,
            key=lambda item: 0 if vidid and item.get("id") == vidid else 1,
        )
    except Exception:
        return []


async def infer_track_language(title: str, vidid: str = "", rows=None) -> str:
    """
    Current/manual song ki language: title -> channel metadata.
    Sirf usi video ki row use hoti hai (pehle doosre search results ka
    channel bhi dekh liya jata tha, jisse galat language aa sakti thi).
    """
    direct = detect_lang_signal(title)
    if direct:
        return direct
    if not title:
        return ""

    if rows is None:
        rows = await fetch_track_meta(title, vidid)

    if vidid:
        rows = [r for r in rows if r.get("id") == vidid] or rows[:1]
    else:
        rows = rows[:1]

    for item in rows:
        combined = f"{item.get('title') or ''} {_channel_name(item)}"
        detected = detect_lang_signal(combined)
        if detected:
            return detected
    return ""


def detect_lang_signal(text_value):
    """
    Explicit language signal ya "". Priority: script > artist > keywords.
    Weak keywords (tula, saiyan, ga...) akele language decide nahi karte.
    """
    if not text_value:
        return ""

    script = _script_lang(text_value)
    if script:
        return script

    value = str(text_value).lower()

    for artist, artist_lang in ARTIST_LANG.items():
        if _word_or_phrase_present(value, artist):
            return artist_lang

    scores = {}
    for lang, keys in LANG_DB.items():
        score = 0.0
        for key in keys:
            if _word_or_phrase_present(value, key):
                if key in WEAK_LANG_KEYS:
                    score += 0.5
                else:
                    score += 3 if " " in key else 1
        if score >= 1:
            scores[lang] = score

    if not scores:
        return ""

    return max(scores, key=scores.get)


def detect_lang(title):
    # First try explicit title/artist clues. Hindi remains the safe default for
    # an unknown first/manual track; once autoplay chooses a track, language is
    # preserved through AUTOPLAY_CONTEXT.
    return detect_lang_signal(title) or "hindi"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🎭 DETECT MOOD
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

def detect_mood(title):
    """Sab moods score karke best chuno (pehle first-match jeet jata tha)."""
    if not title:
        return "normal"
    best, best_score = "normal", 0
    for mood, keys in MOOD_DB.items():
        score = sum(
            2 if " " in k else 1
            for k in keys
            if _word_or_phrase_present(title, k)
        )
        if score > best_score:
            best, best_score = mood, score
    return best


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🎤 DETECT ARTIST
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

def extract_artist(title):
    """
    Sirf pehchane hue artists. Whole-word match + ambiguous short aliases
    ("ap", "karan", "gill"...) ignore, taaki "happy" me "ap" na mile.
    """
    if not title:
        return ""

    for artist, keys in ARTIST_DB.items():
        if _word_or_phrase_present(title, artist):
            return artist
        for k in keys:
            if k in AMBIGUOUS_ALIASES:
                continue
            if _word_or_phrase_present(title, k):
                return artist
    return ""


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🎬 DETECT MOVIE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

def detect_movie(title):
    if not title:
        return ""
    for movie, keys in MOVIE_DB.items():
        if any(_word_or_phrase_present(title, x) for x in keys):
            return movie
    return ""


def _remember_artist(chat_id: int, artist: str) -> None:
    """Last played singers (empty string = unknown singer, streak todta hai)."""
    rows = RECENT_ARTISTS.setdefault(chat_id, [])
    rows.append((artist or "").lower())
    if len(rows) > 10:
        RECENT_ARTISTS[chat_id] = rows[-10:]


def _artist_streak(chat_id: int, artist: str) -> int:
    """Kitne lagatar songs usi artist ke baj chuke."""
    if not artist:
        return 0
    n = 0
    for a in reversed(RECENT_ARTISTS.get(chat_id, [])):
        if a == artist.lower():
            n += 1
        else:
            break
    return n


def _remember_movie(chat_id: int, movie: str) -> None:
    """Keep a short per-chat movie history so autoplay does not stick to one film."""
    if not movie:
        return

    now = time.time()
    rows = RECENT_MOVIES.setdefault(chat_id, [])
    rows[:] = [(m, t) for m, t in rows if now - t < 3600]
    rows.append((movie, now))

    if len(rows) > 8:
        RECENT_MOVIES[chat_id] = rows[-8:]


def _recent_movies(chat_id: int):
    now = time.time()
    rows = RECENT_MOVIES.setdefault(chat_id, [])
    rows[:] = [(m, t) for m, t in rows if now - t < 3600]
    return [m for m, _ in rows[-4:]]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🔤 TITLE NORMALIZER
# Problem: "Diwaniyat" vs "Diwaniyat - AP Dhillon" vs "Diwaniyat Lyrics"
# — different formats, same song. Two-step approach:
# Step 1: Split on " - " / " | " separators to drop artist suffix
# Step 2: Strip bracket content and noise words
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

def normalize_title(title: str) -> str:
    if not title:
        return ""
    t = title.lower().strip()

    # Step 1: Drop artist/channel suffix after separator
    for sep in [" - ", " | ", " — ", " ft ", " feat "]:
        if sep in t:
            t = t.split(sep)[0].strip()
            break

    # Step 2: Remove bracket content — "(Official Video)", "[Lyrics]", etc.
    t = re.sub(r"[\(\[\{][^\)\]\}]*[\)\]\}]", "", t)

    # Step 3: Remove noise words
    noise = [
        "official", "video", "music", "audio", "lyrics", "lyrical",
        "lyric", "full", "hd", "hq", "4k", "song", "new", "latest",
        "visualizer", "teaser", "promo",
    ]
    for w in noise:
        t = re.sub(rf"\b{w}\b", "", t)

    t = re.sub(r"\s+", " ", t).strip()
    return t


def _song_tokens(value: str):
    stop = {
        "official", "video", "audio", "lyrics", "lyrical", "song", "music",
        "full", "hd", "hq", "4k", "new", "latest", "movie", "film",
        "records", "record", "label", "topic", "vevo", "original",
        "version", "feat", "ft", "from",
    }
    value = normalize_title(value)
    return [
        x for x in re.findall(r"[a-z0-9]+", value)
        if len(x) > 1 and x not in stop
    ]


def _same_song(stored: str, candidate: str) -> bool:
    """
    Conservative duplicate matcher.

    Goal:
      - block the same song from another upload/channel
      - do NOT block different songs just because they share 1-2 words

    Older matching was too aggressive and could exhaust the candidate pool,
    causing "no relevant song found" after a few autoplay transitions.
    """
    if not stored or not candidate:
        return False

    a = normalize_title(stored)
    b = normalize_title(candidate)
    if len(a) < 4 or len(b) < 4:
        return False

    if a == b:
        return True

    ta = set(_song_tokens(a))
    tb = set(_song_tokens(b))

    if ta and tb:
        common = ta & tb
        union = ta | tb
        jaccard = len(common) / max(1, len(union))

        # Reordered title/artist or almost-identical upload names.
        if len(common) >= 2 and jaccard >= 0.78:
            return True

        # Same meaningful 3+ token phrase with only small extra decoration.
        if min(len(ta), len(tb)) >= 3:
            smaller = ta if len(ta) <= len(tb) else tb
            larger = tb if len(ta) <= len(tb) else ta
            if smaller.issubset(larger) and len(smaller) / max(1, len(larger)) >= 0.75:
                return True

    # Very high textual similarity only. 0.90 avoids false positives like
    # "Pal Pal" vs "Pal Pal Dil Ke Paas".
    return SequenceMatcher(None, a, b).ratio() >= 0.90


async def _load_history(chat_id: int) -> None:
    """
    Bot restart ke baad Mongo se recent songs/singers wapas load karo.
    Har chat ke liye sirf ek baar. TTL se purani history ignore hoti hai.
    """
    if chat_id in LOADED_HISTORY:
        return
    LOADED_HISTORY.add(chat_id)

    try:
        doc = await history_db.find_one({"chat_id": chat_id})
    except Exception:
        return
    if not doc:
        return

    now = time.time()
    if now - float(doc.get("updated", 0)) > AUTOPLAY_HISTORY_TTL:
        try:
            await history_db.delete_one({"chat_id": chat_id})
        except Exception:
            pass
        return

    _ensure_autoplay_session(chat_id)
    # Memory me pehle se kuch ho to use mat todo (same session chal raha hai).
    if RECENT.get(chat_id) or RECENT_TITLES.get(chat_id):
        return

    def _fresh(rows):
        return [
            (str(v), float(t))
            for v, t in (rows or [])
            if now - float(t) <= AUTOPLAY_HISTORY_TTL
        ]

    RECENT[chat_id] = _fresh(doc.get("vids"))
    RECENT_TITLES[chat_id] = _fresh(doc.get("titles"))
    RECENT_ARTISTS[chat_id] = [str(a) for a in (doc.get("artists") or [])][-10:]
    if doc.get("ctx"):
        AUTOPLAY_CONTEXT[chat_id] = doc["ctx"]
    print(
        f"♻️ Autoplay history restored: {chat_id} "
        f"({len(RECENT[chat_id])} songs)"
    )


async def _save_history(chat_id: int) -> None:
    try:
        await history_db.update_one(
            {"chat_id": chat_id},
            {
                "$set": {
                    "vids": [list(x) for x in RECENT.get(chat_id, [])],
                    "titles": [list(x) for x in RECENT_TITLES.get(chat_id, [])],
                    "artists": RECENT_ARTISTS.get(chat_id, []),
                    "ctx": AUTOPLAY_CONTEXT.get(chat_id),
                    "updated": time.time(),
                }
            },
            upsert=True,
        )
    except Exception as e:
        print(f"⚠️ Autoplay history save failed: {type(e).__name__}: {e}")


def reset_autoplay_session(chat_id: int) -> None:
    """
    Reset repeat/recommendation history ONLY when the real VC playback session
    ends. call.py calls this on actual stop/leave.

    Important: autoplay's prepare_autoplay() may recreate db[chat_id] while the
    assistant stays in VC. That is NOT a new session and must not reset history.
    """
    RECENT.pop(chat_id, None)
    RECENT_TITLES.pop(chat_id, None)
    RECENT_MOVIES.pop(chat_id, None)
    RECENT_ARTISTS.pop(chat_id, None)
    AUTOPLAY_CONTEXT.pop(chat_id, None)
    AUTO_PLAYING.pop(chat_id, None)
    LOADED_HISTORY.discard(chat_id)
    # Real VC stop = naya session -> Mongo history bhi saaf. (Bot crash/restart
    # me ye function nahi chalta, isliye wahan history bachi rehti hai.)
    try:
        asyncio.get_running_loop().create_task(
            history_db.delete_one({"chat_id": chat_id})
        )
    except Exception:
        pass
    print(f"🧹 Autoplay session history cleared: {chat_id}")


def _ensure_autoplay_session(chat_id: int) -> None:
    """
    No queue-object based reset here.

    The old v7/v8 logic used id(db[chat_id]) as a session token. But
    prepare_autoplay() intentionally clears/recreates the queue on next/autoplay
    while keeping the same voice-chat session alive, so /next looked like a new
    session and wiped repeat history.

    Real session resets are now explicit via reset_autoplay_session().
    """
    RECENT.setdefault(chat_id, [])
    RECENT_TITLES.setdefault(chat_id, [])
    RECENT_MOVIES.setdefault(chat_id, [])
    RECENT_ARTISTS.setdefault(chat_id, [])


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🔁 REPEAT CHECK (vidid + fuzzy title)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def is_repeat(chat_id, vidid, title: str = "") -> bool:
    _ensure_autoplay_session(chat_id)

    # Exact video already played in this chat's current session.
    if vidid:
        rows = RECENT.setdefault(chat_id, [])
        if vidid in [v for v, _ in rows]:
            return True

    # Same song from another channel/upload in this same session.
    if title:
        norm = normalize_title(title)
        if norm and len(norm) >= 4:
            rows = RECENT_TITLES.setdefault(chat_id, [])
            for stored_norm, _ in rows:
                if _same_song(stored_norm, norm):
                    return True

    return False


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ➕ ADD RECENT SONG
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def add_recent(chat_id, vidid, title: str = "") -> None:
    if not vidid:
        return

    _ensure_autoplay_session(chat_id)
    current = time.time()

    rows = RECENT.setdefault(chat_id, [])
    if vidid not in [v for v, _ in rows]:
        rows.append((vidid, current))
    if len(rows) > AUTOPLAY_RECENT_LIMIT:
        RECENT[chat_id] = rows[-AUTOPLAY_RECENT_LIMIT:]

    if title:
        norm = normalize_title(title)
        if norm and len(norm) >= 4:
            titles = RECENT_TITLES.setdefault(chat_id, [])
            if not any(_same_song(existing, norm) for existing, _ in titles):
                titles.append((norm, current))
            if len(titles) > AUTOPLAY_RECENT_LIMIT:
                RECENT_TITLES[chat_id] = titles[-AUTOPLAY_RECENT_LIMIT:]



def duration_to_seconds(value) -> int:
    if value is None:
        return 0

    if isinstance(value, (int, float)):
        return max(0, int(value))

    raw = str(value).strip()
    if not raw:
        return 0

    try:
        parts = [int(x) for x in raw.split(":")]
        if len(parts) == 2:
            return parts[0] * 60 + parts[1]
        if len(parts) == 3:
            return parts[0] * 3600 + parts[1] * 60 + parts[2]
    except Exception:
        return 0

    return 0


def _thumb_from_item(item: dict) -> str:
    thumb = item.get("thumbnail") or item.get("thumb") or ""
    if thumb:
        return str(thumb).split("?")[0]

    thumbs = item.get("thumbnails") or []
    if isinstance(thumbs, list) and thumbs:
        last = thumbs[-1]
        if isinstance(last, dict):
            return str(last.get("url") or "").split("?")[0]

    return ""



def parse_view_count(value) -> int:
    """
    Parse py_yt view-count variants into an integer.
    Examples:
      1,234,567
      "1.2M views"
      {"text": "12M views"}
    """
    if value is None:
        return 0

    if isinstance(value, dict):
        value = (
            value.get("text")
            or value.get("short")
            or value.get("simpleText")
            or value.get("viewCount")
            or ""
        )

    if isinstance(value, (int, float)):
        return max(0, int(value))

    s = str(value).strip().lower().replace(",", "")
    if not s:
        return 0

    m = re.search(r"([\d.]+)\s*([kmb])?", s)
    if not m:
        return 0

    try:
        number = float(m.group(1))
    except Exception:
        return 0

    suffix = m.group(2)
    mult = 1
    if suffix == "k":
        mult = 1_000
    elif suffix == "m":
        mult = 1_000_000
    elif suffix == "b":
        mult = 1_000_000_000

    return int(number * mult)


async def search_many(query: str, limit: int = AUTOPLAY_RESULTS_PER_QUERY):
    """
    Candidate search only.

    IMPORTANT: this function does NOT call the Fast audio API. Autoplay first
    searches + ranks songs using py_yt, chooses the final candidate, and only
    then stream() asks Youtube.py/Fast API for that selected video's audio.
    """
    results = []

    try:
        data = await VideosSearch(query, limit=limit).next()
        for item in (data.get("result", []) or [])[:limit]:
            vidid = item.get("id") or ""
            if not vidid:
                continue

            results.append(
                {
                    "title": item.get("title", "") or "",
                    "vidid": vidid,
                    "duration_min": item.get("duration") or "0:00",
                    "thumb": _thumb_from_item(item),
                    "channel": _channel_name(item),
                    "age_years": _age_years(item),
                    "views": parse_view_count(
                        item.get("viewCount")
                        or item.get("views")
                        or item.get("view_count")
                    ),
                    "_search_query": query,
                }
            )
    except Exception:
        pass

    return results


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  SMART QUERY BUILDER (Indian Focus)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

def build_smart_queries(title, artist, movie, lang, mood, chat_id=None, era=""):
    """
    Priority: language > mood/era > singer > related singers.

    - era "old": "latest/new release/2026" kabhi nahi, sirf evergreen/classic.
    - Singer cap (AUTOPLAY_MAX_SAME_ARTIST) hone ke baad query me us singer ka
      naam hi nahi jata; related singers ke naam jate hain.
    - Singer unknown ho to bhi popular same-language singers use hote hain
      (local/random singers ki jagah).
    """
    year = time.strftime("%Y")
    recent_count = len(RECENT.get(chat_id, [])) if chat_id is not None else 0
    old = era == "old"

    terms = OLD_DISCOVERY_TERMS if old else [
        "new release", "trending", "latest", "fresh hits", "popular new", "chart",
    ]
    d1 = terms[recent_count % len(terms)]
    d2 = terms[(recent_count + 2) % len(terms)]

    has_mood = bool(mood and mood != "normal")
    mood_phrase = MOOD_QUERY.get(mood, mood) if has_mood else ""
    if old and "old" not in mood_phrase:
        mood_phrase = f"{mood_phrase} old classic".strip()
    yr = "" if (old or (has_mood and mood in NO_YEAR_MOODS)) else f" {year}"

    streak = _artist_streak(chat_id, artist) if (chat_id is not None and artist) else 0
    capped = streak >= AUTOPLAY_MAX_SAME_ARTIST
    related = _related_pool(artist, lang, era)
    rot = (lambda n: related[(recent_count + n) % len(related)]) if related else None

    queries = []

    # 1) Sabse related
    bits = [lang]
    if artist and not capped:
        bits.append(artist)
    elif rot:
        bits.append(rot(0))
    if mood_phrase:
        bits.append(mood_phrase)
    bits += ["songs", "official audio"]
    queries.append({"q": " ".join(bits), "kind": "similar"})

    # 2) Same singer (cap se pehle)
    if artist and not capped:
        queries.append({
            "q": f"{artist} {lang} {mood_phrase} {d1} songs official audio",
            "kind": "artist_new",
        })

    # 3) Related / popular singers
    if rot:
        for i in range(2 if capped else 1):
            queries.append({
                "q": f"{rot(i + 1)} {lang} {mood_phrase} songs official audio",
                "kind": "related_artist",
            })

    # 4) Mood discovery
    if has_mood:
        queries.append({
            "q": f"{lang} {mood_phrase} {d2} songs{yr} official audio",
            "kind": "mood_new",
        })

    # 5) Language discovery
    queries.append({
        "q": f"{lang} {mood_phrase} {d1} songs{yr} official audio",
        "kind": "new_hit",
    })
    if not has_mood and not old:
        queries.append({
            "q": f"{lang} {d2} hit songs{yr} official audio",
            "kind": "trending",
        })

    final, seen = [], set()
    for item in queries:
        q = re.sub(r"\s+", " ", item["q"]).strip()
        if len(q) > 3 and q.lower() not in seen:
            seen.add(q.lower())
            final.append({"q": q, "kind": item["kind"]})

    return final[:5]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🎵 BEST SONG FINDER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def get_ranked_songs(
    chat_id,
    queries,
    last_title,
    last_vidid,
    artist,
    movie,
    mood,
    lang,
    limit=3,
    era="",
    strict_artist=True,
    strict_lang=True,
):
    """
    Return already-selected/ranked song candidates.

    Search happens entirely before any audio API call. Scoring order is
    intentionally dominant:
        language >> singer >> mood/category >> quality
    """
    candidates = []
    original_norm = normalize_title(last_title)
    current_movie = movie or detect_movie(last_title)
    recent_movies = set(_recent_movies(chat_id))

    soft_bad_words = [
        "lyrics", "lyrical", "full song", "extended version",
        "10 hours", "collection",
    ]

    # "similar" (language + singer + mood) sabse related hai, isliye sabse upar.
    # Pehle new_hit/trending (+70 bonus ke baad) isse aage nikal jate the.
    kind_bonus = {
        "similar": 400,
        "artist_new": 380,
        "related_artist": 360,
        "mood_new": 350,
        "new_hit": 300,
        "trending": 280,
        # Backward/fallback compatibility:
        "hit": 280,
        "mood_hit": 260,
        "artist": 180,
        "language": 120,
    }

    seen_vids = set()

    # Queue me jo songs already line me hain wo bhi repeat na ho.
    queued_vids, queued_titles = set(), []
    for q_item in (db.get(chat_id) or []):
        if isinstance(q_item, dict):
            if q_item.get("vidid"):
                queued_vids.add(q_item["vidid"])
            qt = normalize_title(q_item.get("title", ""))
            if qt:
                queued_titles.append(qt)

    artist_streak = _artist_streak(chat_id, artist) if artist else 0
    related_names = _related_pool(artist, lang, era)
    min_views = (
        AUTOPLAY_MIN_VIEWS // 3 if lang in REGIONAL_LANGS else AUTOPLAY_MIN_VIEWS
    )

    # Search all focused queries concurrently. This is the main speed fix:
    # 3-4 py_yt searches now take roughly the time of the slowest one instead
    # of their times adding together.
    stats = {}

    def _rej(reason):
        stats[reason] = stats.get(reason, 0) + 1

    prepared_queries = []
    search_tasks = []

    for query_item in queries:
        if isinstance(query_item, dict):
            q = query_item.get("q", "")
            kind = query_item.get("kind", "language")
        else:
            q = str(query_item)
            kind = "language"

        if not q:
            continue

        prepared_queries.append((q, kind))
        search_tasks.append(search_many(q))

    if search_tasks:
        search_results = await asyncio.gather(
            *search_tasks,
            return_exceptions=True,
        )
    else:
        search_results = []

    for query_index, ((q, kind), rows) in enumerate(
        zip(prepared_queries, search_results)
    ):
        if isinstance(rows, Exception):
            stats["search_error"] = stats.get("search_error", 0) + 1
            rows = []
        stats["raw_results"] = stats.get("raw_results", 0) + len(rows)

        for result_index, details in enumerate(rows):
            try:
                vidid = details.get("vidid") or details.get("id") or ""
                if not vidid or vidid in seen_vids or vidid == last_vidid:
                    _rej("duplicate_or_current")
                    continue
                seen_vids.add(vidid)

                raw_title = details.get("title", "") or ""
                title_lower = raw_title.lower().strip()
                norm_title = normalize_title(raw_title)
                channel = str(details.get("channel", "") or "").lower()
                duration = details.get("duration_min") or details.get("duration")
                secs = duration_to_seconds(duration)

                if not raw_title or not norm_title:
                    _rej("empty_title")
                    continue

                if _HARD_BAD_RE.search(title_lower):
                    _rej("bad_word(remix/cover/jukebox..)")
                    continue

                if await is_repeat(chat_id, vidid, raw_title):
                    _rej("already_played(repeat)")
                    continue

                if vidid in queued_vids or any(
                    _same_song(qt, norm_title) for qt in queued_titles
                ):
                    _rej("already_in_queue")
                    continue

                if original_norm and _same_song(original_norm, norm_title):
                    _rej("same_as_current_song")
                    continue

                if secs and (
                    secs < AUTOPLAY_MIN_SECONDS
                    or secs > AUTOPLAY_MAX_SECONDS
                ):
                    _rej("duration_out_of_range")
                    continue

                combined = f"{raw_title} {channel}".lower()

                # LOCAL / unknown singer filter: bahut kam views wale skip.
                # (views unknown = 0 to reject nahi karte.)
                cand_views = int(details.get("views") or 0)
                if strict_artist and cand_views and cand_views < min_views:
                    _rej("low_views")
                    continue

                # ERA GUARD: old song ke baad new song nahi.
                cand_age = details.get("age_years")
                # "<Artist> - Topic" uploads ki date release-date jaisi hoti hai,
                # purane gaane bhi recent dikhte hain -> age pe bharosa nahi.
                if "topic" in channel:
                    cand_age = None
                title_year = _year_in_title(raw_title)
                if era == "old":
                    if title_year and title_year >= 2015 and strict_artist:
                        _rej("era_new_title_year")
                        continue
                    if strict_artist and cand_age is not None and cand_age < 3:
                        _rej("era_too_new")
                        continue

                # PRIORITY #1 — LANGUAGE
                # If the candidate explicitly signals another language, reject
                # it completely. If it has no explicit language word, trust the
                # language-specific search query instead of falsely rejecting it.
                candidate_lang = detect_lang_signal(combined)
                if candidate_lang and candidate_lang != lang:
                    if strict_lang:
                        _rej(f"wrong_language({candidate_lang}!={lang})")
                        continue
                    lang_penalty = 300
                else:
                    lang_penalty = 0

                score = 1000  # same-language search pool
                score += kind_bonus.get(kind, 100)
                score -= lang_penalty

                # CATEGORY GUARD — sad ke baad bhajan/shaadi/party jaisa jump
                # nahi. Devotional/wedding hard-block, baaki soft penalty.
                candidate_mood = detect_mood(combined)
                if candidate_mood != "normal":
                    allowed = (
                        MOOD_COMPAT.get(mood, {mood})
                        if mood != "normal"
                        else NORMAL_ALLOWED
                    )
                    if candidate_mood not in allowed:
                        hard = (
                            candidate_mood in HARD_CANDIDATE_MOODS
                            or mood in HARD_CATEGORIES
                        )
                        # Strict pass me hard-block. Fallback pass (strict_artist
                        # False) me sirf bhaari penalty, taaki autoplay kabhi
                        # "no song" hoke VC band na kare.
                        if hard and strict_artist:
                            _rej(f"category_jump({candidate_mood} vs {mood})")
                            continue
                        score -= 300 if hard else 140

                # Higher py_yt position is mildly preferred, but cannot override
                # singer/mood priorities.
                score += max(0, 35 - query_index * 4 - result_index * 3)

                # Same singer is only a soft preference, not a requirement.
                # Era scoring
                if era == "old":
                    if title_year and title_year >= 2015:
                        score -= 200
                    if cand_age is not None and cand_age < 8:
                        score -= 150
                    elif cand_age is not None and cand_age >= 10:
                        score += 60
                    if any(
                        _word_or_phrase_present(combined, x)
                        for x in OLD_ERA_ARTISTS
                    ):
                        score += 80
                elif cand_age is not None and cand_age >= 15:
                    score -= 100

                same_artist = False
                if artist:
                    artist_lower = artist.lower()
                    same_artist = (
                        artist_lower in title_lower
                        or artist_lower in channel
                    )
                    if same_artist:
                        score += 150
                        # Ek hi singer 2 baar lagatar baj chuka -> variety.
                        if artist_streak >= AUTOPLAY_MAX_SAME_ARTIST:
                            if strict_artist:
                                _rej("same_singer_cap")
                                continue
                            score -= 220
                    else:
                        if kind == "artist":
                            score -= 20
                        # Same-category related singer ko bonus.
                        if related_names and any(
                            _word_or_phrase_present(f"{title_lower} {channel}", r)
                            for r in related_names
                        ):
                            score += 130

                # Mood/category remains useful after language + hit popularity.
                mood_match = False
                if mood and mood != "normal":
                    mood_keys = MOOD_DB.get(mood, [])
                    mood_match = any(_word_or_phrase_present(combined, x) for x in mood_keys)
                    if mood_match:
                        score += 160
                    elif kind == "mood_hit":
                        # Query itself is mood-specific, so give a small bonus
                        # even when the title does not literally say the mood.
                        score += 35

                # Do not get stuck on one soundtrack. This is only a lower-level
                # diversity penalty; language/singer/mood always come first.
                candidate_movie = detect_movie(raw_title)
                if (
                    current_movie
                    and candidate_movie
                    and candidate_movie == current_movie
                ):
                    score -= 90
                elif candidate_movie and candidate_movie in recent_movies:
                    score -= 45

                # HIT / POPULARITY preference.
                # Views are a strong signal, but never override a wrong-language
                # rejection above.
                views = int(details.get("views") or 0)
                if views >= 100_000_000:
                    score += 170
                elif views >= 50_000_000:
                    score += 150
                elif views >= 20_000_000:
                    score += 130
                elif views >= 10_000_000:
                    score += 115
                elif views >= 5_000_000:
                    score += 100
                elif views >= 1_000_000:
                    score += 80
                elif views >= 250_000:
                    score += 45

                # New/trending query pools get an explicit boost so autoplay
                # does not keep preferring the same old mega-hits.
                if kind in {"artist_new", "mood_new", "new_hit", "trending", "related_artist"}:
                    score += 70

                if any(x in title_lower for x in ["hit", "superhit", "popular"]):
                    score += 45

                # Quality / normal-song preferences.
                if "official" in title_lower:
                    score += 18
                if any(
                    x in channel
                    for x in ["topic", "vevo", "records", "music"]
                ):
                    score += 18

                if secs:
                    if 140 <= secs <= 360:
                        score += 22
                    elif 360 < secs <= AUTOPLAY_MAX_SECONDS:
                        score += 6

                word_count = len(norm_title.split())
                if 2 <= word_count <= 11:
                    score += 10
                elif word_count > 16:
                    score -= 18

                if any(x in title_lower for x in soft_bad_words):
                    score -= 24

                # Chhota random jitter: same-score songs me har baar same order na ho.
                score += random.randint(0, 20)

                details["_score"] = score
                details["_kind"] = kind
                details["_same_artist"] = same_artist
                details["_mood_match"] = mood_match
                candidates.append((score, vidid, details))

            except Exception as e:
                _rej(f"error:{type(e).__name__}:{e}")
                continue

    stats["accepted"] = len(candidates)
    LAST_REJECTS[chat_id] = stats

    candidates.sort(key=lambda x: x[0], reverse=True)

    ranked = []
    for score, vidid, details in candidates:
        ranked.append((vidid, details, score))
        if len(ranked) >= max(1, limit):
            break

    return ranked


async def get_best_song(
    chat_id,
    queries,
    last_title,
    last_vidid,
    artist,
    movie,
    mood,
    lang,
):
    ranked = await get_ranked_songs(
        chat_id,
        queries,
        last_title,
        last_vidid,
        artist,
        movie,
        mood,
        lang,
        limit=1,
    )
    if not ranked:
        return None, None
    return ranked[0][0], ranked[0][1]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🖼 THUMBNAIL
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def get_thumbnail_direct(video_id):
    urls = [
        f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg",
        f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg",
        f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg",
    ]
    async with aiohttp.ClientSession() as session:
        for url in urls:
            try:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        return url
            except Exception:
                continue
    return urls[-1]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🇮🇳 INDIAN EMOJI
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

def get_indian_emoji():
    emojis = ["🇮🇳","🎧","❤️","🎶","✨","🎤","💖","🎵","🔥","💫","🎸","💕","🪩","🌙","💘","🥰","🎼","⚡","💞","🦋","🎶","💜","🎤","🌸","🕺","💃","💝","🎧","🌈","❣️","🪘","💗","✨","🔥"]
    return random.choice(emojis)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🚀 MAIN AUTOPLAY FUNCTION
#
# FIX 1: last_vidid param added — current song added to RECENT before
#         searching so it can never be picked as the next song.
#         get_best_song also hard-skips repeats (not just penalises).
# FIX 2: stop_stream() removed — assistant stays in VC between songs.
#         Stream ended naturally so bot is already in VC; calling
#         stop_stream() was the only reason it was leaving and rejoining.
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def auto_play_next(
    chat_id: int,
    original_chat_id: int,
    last_title: str = "",
    last_vidid: str = "",
) -> bool:
    """
    Search for next Indian song smartly based on last song's context.
    Returns True if successfully started, False otherwise.
    """
    from VISHALMUSIC.utils.database import get_lang
    from VISHALMUSIC.utils.stream.stream import stream
    from strings import get_string

    # Double-play protection
    if AUTO_PLAYING.get(chat_id):
        print(f"⛔ Autoplay False [{chat_id}]: pichla autoplay abhi chal raha hai (double-play guard)")
        return False

    AUTO_PLAYING[chat_id] = True

    try:
        data = await autoplay_db.find_one({"chat_id": chat_id})
        if not data or not data.get("status"):
            print(f"⛔ Autoplay False [{chat_id}]: autoplay is chat me OFF hai (/autoplay on karo)")
            return False

        # Restart ke baad Mongo se history wapas (sirf pehli baar).
        await _load_history(chat_id)
        _ensure_autoplay_session(chat_id)

        # FIX 1: Mark last played song as recent BEFORE searching
        # Pass title too so same song from different channels is blocked
        if last_vidid:
            await add_recent(chat_id, last_vidid, last_title)

        indian_emoji = get_indian_emoji()

        try:
            msg = await app.send_message(
                original_chat_id,
                f"{indian_emoji} ᴀᴜᴛᴏᴘʟᴀʏ → ꜰᴇᴛᴄʜɪɴɢ ɴᴇxᴛ ꜱᴏɴɢ...........",
            )
        except Exception as e:
            print(f"⛔ Autoplay False [{chat_id}]: msg bhej nahi paya (original_chat_id={original_chat_id}): {type(e).__name__}: {e}")
            return False

        if not last_title:
            queue = db.get(chat_id)
            if queue and len(queue) > 0:
                last_title = queue[0].get("title", "latest hindi song")
            else:
                last_title = "latest hindi song"

        # Context anchor: autoplay chain me language/singer/mood SEED song se
        # hi carry hote hain, taaki dheere-dheere kisi aur category me drift na ho.
        previous_ctx = AUTOPLAY_CONTEXT.get(chat_id) or {}
        in_chain = bool(last_vidid and previous_ctx.get("vidid") == last_vidid)

        if in_chain:
            lang = previous_ctx.get("lang") or detect_lang(last_title)
            artist = previous_ctx.get("artist") or extract_artist(last_title)
            mood = previous_ctx.get("mood") or "normal"
            if mood == "normal":
                mood = detect_mood(last_title)
            era = previous_ctx.get("era") or ""
        else:
            # Manual/new seed song: title + YouTube metadata (ek hi search).
            rows = await fetch_track_meta(last_title, last_vidid)
            inferred_lang = await infer_track_language(last_title, last_vidid, rows=rows)
            lang = inferred_lang or detect_lang(last_title)
            artist = extract_artist(last_title) or _artist_from_rows(rows, last_vidid)
            mood = detect_mood(last_title)
            _remember_artist(chat_id, artist)

            # Era: old singer / "oldschool" mood / upload 10+ saal purana /
            # title me 2012 ya usse pehle ka saal -> "old".
            seed_age = None
            for r in rows:
                if r.get("id") == last_vidid and not _channel_name(r).lower().endswith("topic"):
                    seed_age = _age_years(r)
            ty = _year_in_title(last_title)
            if (
                mood == "oldschool"
                or (artist or "") in OLD_ERA_ARTISTS
                or (seed_age is not None and seed_age >= 10)
                or (ty and ty <= 2012)
            ):
                era = "old"
            elif seed_age is not None and seed_age < 4:
                era = "new"
            else:
                era = ""

        print(
            f"🌐 Autoplay context: lang={lang} artist={artist or '-'} "
            f"mood={mood} era={era or '-'} chain={in_chain} | current={last_title}"
        )

        movie = detect_movie(last_title)
        if movie:
            _remember_movie(chat_id, movie)

        queries = build_smart_queries(
            last_title, artist, movie, lang, mood, chat_id=chat_id, era=era
        )
        search_started = time.monotonic()

        # IMPORTANT:
        # Search/rank the top candidates FIRST. search_many() uses py_yt only,
        # so no Fast API /song request happens during this phase.
        ranked = await get_ranked_songs(
            chat_id,
            queries,
            last_title,
            last_vidid,
            artist,
            movie,
            mood,
            lang,
            limit=3,
            era=era,
        )

        print(
            f"⚡ Autoplay search finished in "
            f"{time.monotonic() - search_started:.2f}s "
            f"({len(queries)} parallel queries)"
        )

        if not ranked:
            # Final fallback is STILL same-language only.
            year = time.strftime("%Y")
            if era == "old":
                fallback_queries = [
                    {"q": f"{lang} old classic songs official audio", "kind": "new_hit"},
                    {"q": f"{lang} evergreen superhit songs official audio", "kind": "trending"},
                    {"q": f"{lang} 90s hit songs official audio", "kind": "hit"},
                ]
            else:
                fallback_queries = [
                {"q": f"{lang} new release songs {year} official audio", "kind": "new_hit"},
                {"q": f"{lang} trending songs {year} official audio", "kind": "trending"},
                {"q": f"{lang} popular songs official audio", "kind": "hit"},
                {"q": f"{lang} fresh music official audio", "kind": "language"},
                ]

            ranked = await get_ranked_songs(
                chat_id,
                fallback_queries,
                last_title,
                last_vidid,
                artist,
                movie,
                mood,
                lang,
                limit=5,
                era=era,
                strict_artist=False,
            )

        if not ranked:
            # Stage 3: history/pool exhaust ho gaya ho sakta hai -> is chat ki
            # history saaf karke (current song rakhke) dobara try.
            print(
                f"⚠️ Autoplay [{chat_id}] fallback khali. rejects="
                f"{LAST_REJECTS.get(chat_id)} -> purani history trim karke retry"
            )
            # Pehle sirf sabse purane songs hatao (haal ke 15 block rehte hain).
            # Phir bhi khali ho to 5, aur aakhir me sirf current song block.
            for keep in (AUTOPLAY_KEEP_ON_EXHAUST, 5, 0):
                RECENT[chat_id] = RECENT.get(chat_id, [])[-keep:] if keep else []
                RECENT_TITLES[chat_id] = (
                    RECENT_TITLES.get(chat_id, [])[-keep:] if keep else []
                )
                if last_vidid:
                    await add_recent(chat_id, last_vidid, last_title)
                ranked = await get_ranked_songs(
                    chat_id, fallback_queries + queries, last_title, last_vidid,
                    artist, movie, mood, lang,
                    limit=5, era=era, strict_artist=False,
                )
                if ranked:
                    print(f"♻️ Autoplay [{chat_id}] history trim: sirf last {keep} block rakhe")
                    break

        if not ranked:
            # Stage 4: aakhri koshish — language rule bhi naram (penalty), taaki
            # "no relevant song" se VC band na ho.
            print(
                f"⚠️ Autoplay [{chat_id}] retry bhi khali. rejects="
                f"{LAST_REJECTS.get(chat_id)} -> language relax"
            )
            ranked = await get_ranked_songs(
                chat_id, fallback_queries + queries, last_title, last_vidid,
                artist, movie, mood, lang,
                limit=5, era=era, strict_artist=False, strict_lang=False,
            )

        if not ranked:
            try:
                await msg.edit_text("❌ ɴᴏ ʀᴇʟᴇᴠᴀɴᴛ ꜱᴏɴɢ ꜰᴏᴜɴᴅ")
            except Exception:
                pass
            print(f"⛔ Autoplay False [{chat_id}]: search me koi candidate nahi bacha (lang={lang}, artist={artist or '-'}, mood={mood}, era={era or '-'}) rejects={LAST_REJECTS.get(chat_id)}")
            return False

        language = await get_lang(chat_id)
        _ = get_string(language)

        # Candidates are already selected before this loop. Only NOW does
        # stream() call Youtube.download(), which contacts the Fast audio API
        # for the chosen video. If the chosen candidate truly cannot start,
        # try the next already-ranked candidate instead of performing a new
        # unrelated search.
        last_stream_error = None

        for candidate_index, (vidid, details, score) in enumerate(ranked, start=1):
            new_title = details.get("title", "") if details else ""
            link = f"https://youtube.com/watch?v={vidid}"

            print(
                f"🎯 Autoplay selected #{candidate_index}: {new_title} "
                f"| language={lang} "
                f"| singer={artist or 'any'} "
                f"| mood={mood} "
                f"| views={details.get('views', 0)} "
                f"| score={score}"
            )

            try:
                thumb = details.get("thumb", "")
                if not thumb or not thumb.startswith("http"):
                    thumb = await get_thumbnail_direct(vidid)
            except Exception:
                thumb = await get_thumbnail_direct(vidid)

            try:
                await stream(
                    _,
                    msg,
                    app.id,
                    {
                        "link": link,
                        "vidid": vidid,
                        "title": details.get(
                            "title",
                            f"{lang} autoplay song",
                        ),
                        "duration_min": details.get(
                            "duration_min",
                            "00:00",
                        ),
                        "thumb": thumb,
                    },
                    chat_id,
                    "🔁 ᴀᴜᴛᴏᴘʟᴀʏ",
                    original_chat_id,
                    video=False,
                    streamtype="youtube",
                )

                # Mark recent only after the selected track actually reached
                # the stream pipeline successfully.
                await add_recent(chat_id, vidid, new_title)

                new_movie = detect_movie(new_title)
                if new_movie:
                    _remember_movie(chat_id, new_movie)

                # Kaun sa singer abhi baja (streak tracking ke liye)
                played_artist = (
                    artist if details.get("_same_artist") else extract_artist(new_title)
                )
                _remember_artist(chat_id, played_artist)

                # Anchor: seed ka artist/mood rakho; sirf seed me na ho to naya lo.
                next_artist = artist or extract_artist(new_title) or ""
                next_mood = mood if mood != "normal" else detect_mood(new_title)

                AUTOPLAY_CONTEXT[chat_id] = {
                    "vidid": vidid,
                    "lang": lang,
                    "artist": next_artist,
                    "mood": next_mood,
                    "era": era,
                }

                last_stream_error = None
                break

            except Exception as e:
                last_stream_error = e
                # Do not retry this failed media candidate immediately.
                await add_recent(chat_id, vidid, new_title)
                print(
                    f"⚠️ Autoplay candidate #{candidate_index} failed: "
                    f"{type(e).__name__}: {e}"
                )

        await _save_history(chat_id)

        if last_stream_error is not None:
            print(f"⛔ Autoplay False [{chat_id}]: stream() fail: {type(last_stream_error).__name__}: {last_stream_error}")
            try:
                await msg.edit_text("❌ ᴀᴜᴛᴏᴘʟᴀʏ ᴀᴜᴅɪᴏ ꜰᴇᴛᴄʜ ꜰᴀɪʟᴇᴅ")
            except Exception:
                pass
            return False

        try:
            await msg.delete()
        except Exception:
            pass

        return True

    except Exception:
        # Pehle error chup-chap nigal liya jata tha; ab log hoga.
        print(f"❌ Autoplay crashed:\n{traceback.format_exc()}")
        return False

    finally:
        AUTO_PLAYING.pop(chat_id, None)
