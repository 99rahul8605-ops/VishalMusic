import asyncio
import os
import random
import re
import time
from difflib import SequenceMatcher

import aiohttp
from py_yt import VideosSearch

from VISHALMUSIC import app
from VISHALMUSIC.core.mongo import mongodb
from VISHALMUSIC.misc import db
from VISHALMUSIC.platforms.Youtube import YouTubeAPI

yt = YouTubeAPI()
autoplay_db = mongodb.autoplay

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  PROTECTION SYSTEM
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

RECENT = {}
RECENT_TITLES = {}
RECENT_MOVIES = {}
AUTO_PLAYING = {}
AUTOPLAY_CONTEXT = {}

# Autoplay recommendation tuning
AUTOPLAY_MIN_SECONDS = int(os.getenv("AUTOPLAY_MIN_SECONDS", "100"))
AUTOPLAY_MAX_SECONDS = int(os.getenv("AUTOPLAY_MAX_SECONDS", "420"))
AUTOPLAY_RESULTS_PER_QUERY = max(4, min(int(os.getenv("AUTOPLAY_RESULTS_PER_QUERY", "6")), 8))
AUTOPLAY_RECENT_LIMIT = max(20, min(int(os.getenv("AUTOPLAY_RECENT_LIMIT", "80")), 200))

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
        "justin bieber", "dua lipa", "weeknd",
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
        "ram", "ganesha", "hanuman", "mahadev", "bhakti",
    ],
    "oldschool": [
        "old", "classic", "90s", "80s", "kishore", "lata", "rafi",
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
    "rocky aur rani": ["rocky", "rani", "rocky aur rani", "kjo"],
    "tu jhoothi main makkaar": ["tu jhoothi", "tjmm", "ranbir", "shraddha"],
    "bhool bhulaiyaa 2": ["bhool bhulaiyaa", "bb2", "kartik aaryan"],
    "brahmastra": ["brahmastra", "astra", "ranbir", "alia"],
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


def _word_or_phrase_present(value: str, key: str) -> bool:
    value = str(value or "").lower()
    key = str(key or "").lower().strip()
    if not key:
        return False

    if " " in key:
        return key in value

    return re.search(
        rf"(?<![a-z0-9]){re.escape(key)}(?![a-z0-9])",
        value,
    ) is not None


async def infer_track_language(title: str, vidid: str = "") -> str:
    """
    Infer the CURRENT/manual song language using py_yt metadata.
    This avoids defaulting a Bhojpuri song to Hindi when its title does not
    literally contain 'Bhojpuri'. Channel names like 'Hamaar Bhojpuri' help.
    """
    direct = detect_lang_signal(title)
    if direct:
        return direct

    if not title:
        return ""

    try:
        data = await VideosSearch(title, limit=3).next()
        rows = data.get("result", []) or []

        rows = sorted(
            rows,
            key=lambda item: 0 if vidid and item.get("id") == vidid else 1,
        )

        for item in rows:
            combined = " ".join(
                str(x or "")
                for x in (
                    item.get("title"),
                    item.get("channel"),
                    item.get("channelTitle"),
                    item.get("uploader"),
                )
            )

            detected = detect_lang_signal(combined)
            if detected:
                return detected
    except Exception:
        pass

    return ""


def detect_lang_signal(text_value):
    """
    Return an explicit language signal or "" when the text does not tell us.
    This is used to reject obviously wrong-language recommendations without
    assuming every title literally contains the language name.
    """
    if not text_value:
        return ""

    value = str(text_value).lower()

    # Artist signal is stronger than generic words.
    for artist, artist_lang in ARTIST_LANG.items():
        if _word_or_phrase_present(value, artist):
            return artist_lang

    # Score language clues; avoid accidental substring matches.
    scores = {}
    for lang, keys in LANG_DB.items():
        score = 0
        for key in keys:
            if _word_or_phrase_present(value, key):
                score += 3 if " " in key else 1
        if score:
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
    if not title:
        return "normal"
    title = title.lower()
    for mood, keys in MOOD_DB.items():
        if any(x in title for x in keys):
            return mood
    return "normal"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🎤 DETECT ARTIST
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

def extract_artist(title):
    """
    Detect only artists we actually recognise.

    The old fallback treated text before "-" as an artist, so a title like
    "O Bedardeya - Arijit Singh" could incorrectly make "O Bedardeya" the
    artist and produce unrelated searches.
    """
    if not title:
        return ""

    title_lower = title.lower()
    for artist, keys in ARTIST_DB.items():
        if artist in title_lower or any(x in title_lower for x in keys):
            return artist

    return ""


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🎬 DETECT MOVIE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

def detect_movie(title):
    if not title:
        return ""
    title = title.lower()
    for movie, keys in MOVIE_DB.items():
        if any(x in title for x in keys):
            return movie
    return ""


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
    AUTOPLAY_CONTEXT.pop(chat_id, None)
    AUTO_PLAYING.pop(chat_id, None)
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
                    "channel": item.get("channel")
                    or item.get("channelTitle")
                    or "",
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

def build_smart_queries(title, artist, movie, lang, mood, chat_id=None):
    """
    Build a RELATED but diverse search set from the last song.

    Priority:
      1) same language
      2) last-song singer/context
      3) new/trending songs
      4) mood/category
      5) variety so the same top few results do not keep returning

    All queries are still searched in parallel.
    """
    year = time.strftime("%Y")
    recent_count = len(RECENT.get(chat_id, [])) if chat_id is not None else 0

    # Rotate discovery wording every transition. This prevents the same static
    # "top hits" query from returning the same 4-5 songs forever.
    discovery_terms = [
        "new release",
        "trending",
        "latest",
        "fresh hits",
        "popular new",
        "chart",
    ]
    d1 = discovery_terms[recent_count % len(discovery_terms)]
    d2 = discovery_terms[(recent_count + 2) % len(discovery_terms)]

    queries = []

    # Singer continuity is a preference, not a hard lock.
    if artist:
        queries.append({
            "q": f"{artist} {lang} {d1} songs {year} official audio",
            "kind": "artist_new",
        })

    # Mood/category continuity from the previous song.
    if mood and mood != "normal":
        queries.append({
            "q": f"{lang} {mood} {d2} songs {year} official audio",
            "kind": "mood_new",
        })

    # A context query ties language + singer + mood together when available.
    context_bits = [lang]
    if artist:
        context_bits.append(artist)
    if mood and mood != "normal":
        context_bits.append(mood)
    context_bits.append("similar songs")
    context_bits.append("official audio")
    queries.append({
        "q": " ".join(context_bits),
        "kind": "similar",
    })

    # Always include new/trending language-wide discovery so autoplay can move
    # to another singer instead of getting stuck on one artist.
    queries.extend([
        {
            "q": f"{lang} {d1} songs {year} official audio",
            "kind": "new_hit",
        },
        {
            "q": f"{lang} {d2} hit songs {year} official audio",
            "kind": "trending",
        },
    ])

    final = []
    seen = set()
    for item in queries:
        q = re.sub(r"\s+", " ", item["q"]).strip()
        key = q.lower()
        if len(q) > 3 and key not in seen:
            seen.add(key)
            final.append({"q": q, "kind": item["kind"]})

    # 5 parallel searches × default 6 results gives a broad pool without
    # serial delay.
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

    hard_bad_words = [
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
    ]

    soft_bad_words = [
        "lyrics", "lyrical", "full song", "extended version",
        "10 hours", "collection",
    ]

    kind_bonus = {
        "artist_new": 380,
        "mood_new": 350,
        "similar": 330,
        "new_hit": 340,
        "trending": 320,
        # Backward/fallback compatibility:
        "hit": 280,
        "mood_hit": 260,
        "artist": 180,
        "language": 120,
    }

    seen_vids = set()

    # Search all focused queries concurrently. This is the main speed fix:
    # 3-4 py_yt searches now take roughly the time of the slowest one instead
    # of their times adding together.
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
            rows = []

        for result_index, details in enumerate(rows):
            try:
                vidid = details.get("vidid") or details.get("id") or ""
                if not vidid or vidid in seen_vids or vidid == last_vidid:
                    continue
                seen_vids.add(vidid)

                raw_title = details.get("title", "") or ""
                title_lower = raw_title.lower().strip()
                norm_title = normalize_title(raw_title)
                channel = str(details.get("channel", "") or "").lower()
                duration = details.get("duration_min") or details.get("duration")
                secs = duration_to_seconds(duration)

                if not raw_title or not norm_title:
                    continue

                if any(x in title_lower for x in hard_bad_words):
                    continue

                if await is_repeat(chat_id, vidid, raw_title):
                    continue

                if original_norm and _same_song(original_norm, norm_title):
                    continue

                if secs and (
                    secs < AUTOPLAY_MIN_SECONDS
                    or secs > AUTOPLAY_MAX_SECONDS
                ):
                    continue

                combined = f"{raw_title} {channel}".lower()

                # PRIORITY #1 — LANGUAGE
                # If the candidate explicitly signals another language, reject
                # it completely. If it has no explicit language word, trust the
                # language-specific search query instead of falsely rejecting it.
                candidate_lang = detect_lang_signal(combined)
                if candidate_lang and candidate_lang != lang:
                    continue

                score = 1000  # same-language search pool
                score += kind_bonus.get(kind, 100)

                # Higher py_yt position is mildly preferred, but cannot override
                # singer/mood priorities.
                score += max(0, 35 - query_index * 4 - result_index * 3)

                # Same singer is only a soft preference, not a requirement.
                same_artist = False
                if artist:
                    artist_lower = artist.lower()
                    same_artist = (
                        artist_lower in title_lower
                        or artist_lower in channel
                    )
                    if same_artist:
                        score += 150
                    elif kind == "artist":
                        score -= 20

                # Mood/category remains useful after language + hit popularity.
                mood_match = False
                if mood and mood != "normal":
                    mood_keys = MOOD_DB.get(mood, [])
                    mood_match = any(x in combined for x in mood_keys)
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
                if kind in {"artist_new", "mood_new", "new_hit", "trending"}:
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

                details["_score"] = score
                details["_kind"] = kind
                details["_same_artist"] = same_artist
                details["_mood_match"] = mood_match
                candidates.append((score, vidid, details))

            except Exception:
                continue


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
        return False

    AUTO_PLAYING[chat_id] = True

    try:
        data = await autoplay_db.find_one({"chat_id": chat_id})
        if not data or not data.get("status"):
            return False

        # Repeat blocking is session-local. If the call/queue was recreated,
        # this clears only this chat's old history.
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
        except Exception:
            return False

        if not last_title:
            queue = db.get(chat_id)
            if queue and len(queue) > 0:
                last_title = queue[0].get("title", "latest hindi song")
            else:
                last_title = "latest hindi song"

        # If the last track was itself chosen by autoplay, keep the known
        # language context even when the YouTube title contains no language word.
        previous_ctx = AUTOPLAY_CONTEXT.get(chat_id) or {}
        if last_vidid and previous_ctx.get("vidid") == last_vidid:
            # Track already chosen by autoplay: preserve recommendation context.
            lang = previous_ctx.get("lang") or detect_lang(last_title)
        else:
            # Manual/current track: infer from title + py_yt channel metadata
            # before falling back to Hindi.
            inferred_lang = await infer_track_language(last_title, last_vidid)
            lang = inferred_lang or detect_lang(last_title)

        print(
            f"🌐 Autoplay language detected: {lang} "
            f"| current={last_title}"
        )

        mood = detect_mood(last_title)
        artist = extract_artist(last_title)

        # If this is an autoplay-selected song, carry forward the known
        # singer/mood when the title itself does not expose them cleanly.
        if last_vidid and previous_ctx.get("vidid") == last_vidid:
            if not artist:
                artist = previous_ctx.get("artist") or ""
            if mood == "normal":
                mood = previous_ctx.get("mood") or "normal"

        movie = detect_movie(last_title)
        if movie:
            _remember_movie(chat_id, movie)

        queries = build_smart_queries(last_title, artist, movie, lang, mood, chat_id=chat_id)
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
        )

        print(
            f"⚡ Autoplay search finished in "
            f"{time.monotonic() - search_started:.2f}s "
            f"({len(queries)} parallel queries)"
        )

        if not ranked:
            # Final fallback is STILL same-language only.
            year = time.strftime("%Y")
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
            )

        if not ranked:
            try:
                await msg.edit_text("❌ ɴᴏ ʀᴇʟᴇᴠᴀɴᴛ ꜱᴏɴɢ ꜰᴏᴜɴᴅ")
            except Exception:
                pass
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

                next_artist = extract_artist(new_title) or artist or ""
                next_mood = detect_mood(new_title)
                if next_mood == "normal":
                    next_mood = mood or "normal"

                AUTOPLAY_CONTEXT[chat_id] = {
                    "vidid": vidid,
                    "lang": lang,
                    "artist": next_artist,
                    "mood": next_mood,
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

        if last_stream_error is not None:
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
        return False

    finally:
        AUTO_PLAYING.pop(chat_id, None)
