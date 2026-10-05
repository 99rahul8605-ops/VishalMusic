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
autoplay_history_db = mongodb.autoplay_history

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
AUTOPLAY_RESULTS_PER_QUERY = max(2, min(int(os.getenv("AUTOPLAY_RESULTS_PER_QUERY", "5")), 8))
AUTOPLAY_REPEAT_HOURS = max(2, int(os.getenv("AUTOPLAY_REPEAT_HOURS", "12")))
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
        "bhojpuri", "bhojpuri song", "pawan singh", "khesari",
        "nirahua", "saiya", "saiyan", "raja ji", "tohar", "hamra",
        "bhojpuriya",
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
    "gurinder gill": "punjabi",
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
    "gurinder gill": ["gurinder gill", "gill", "gurinder song"],
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
        if artist in value:
            return artist_lang

    for lang, keys in LANG_DB.items():
        if any(x in value for x in keys):
            return lang

    return ""


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
    Strong duplicate matcher.

    It catches:
      "Pal Pal - Afusic"
      "AFUSIC - Pal Pal (Official Video)"
    even though artist/title order is reversed.
    """
    if not stored or not candidate:
        return False

    a = normalize_title(stored)
    b = normalize_title(candidate)
    if len(a) < 4 or len(b) < 4:
        return False

    if a == b:
        return True

    short = a if len(a) <= len(b) else b
    long = b if len(a) <= len(b) else a
    if len(short) >= 6 and (long.startswith(short) or short in long):
        return True

    ta = set(_song_tokens(a))
    tb = set(_song_tokens(b))
    if ta and tb:
        common = ta & tb
        union = ta | tb

        # Two meaningful shared words with strong overlap is usually the same song.
        if len(common) >= 2 and len(common) / max(1, len(union)) >= 0.55:
            return True

        # Exact token-set match catches reversed artist/title order.
        if len(ta) >= 2 and ta == tb:
            return True

    # Last guard for punctuation/order variants.
    return SequenceMatcher(None, a, b).ratio() >= 0.82


async def _load_persistent_recent(chat_id: int) -> None:
    """
    Restore recent autoplay history from Mongo so restarting/updating the bot
    does not immediately allow the same songs again.
    """
    try:
        doc = await autoplay_history_db.find_one({"chat_id": chat_id}) or {}
        rows = doc.get("songs", []) or []
        now = time.time()
        max_age = AUTOPLAY_REPEAT_HOURS * 3600

        ids = []
        titles = []
        clean_rows = []

        for row in rows[-AUTOPLAY_RECENT_LIMIT:]:
            try:
                ts = float(row.get("ts", 0))
            except Exception:
                ts = 0

            if not ts or now - ts > max_age:
                continue

            vidid = str(row.get("vidid") or "").strip()
            title = str(row.get("title") or "").strip()

            if vidid:
                ids.append((vidid, ts))
            if title:
                norm = normalize_title(title)
                if norm:
                    titles.append((norm, ts))

            clean_rows.append(
                {"vidid": vidid, "title": title, "ts": ts}
            )

        RECENT[chat_id] = ids[-AUTOPLAY_RECENT_LIMIT:]
        RECENT_TITLES[chat_id] = titles[-AUTOPLAY_RECENT_LIMIT:]

        # Opportunistically prune old DB entries.
        if len(clean_rows) != len(rows):
            await autoplay_history_db.update_one(
                {"chat_id": chat_id},
                {"$set": {"songs": clean_rows[-AUTOPLAY_RECENT_LIMIT:]}},
                upsert=True,
            )
    except Exception:
        # In-memory repeat protection still works if Mongo has a temporary issue.
        pass


async def _persist_recent_song(chat_id: int, vidid: str, title: str) -> None:
    try:
        doc = await autoplay_history_db.find_one({"chat_id": chat_id}) or {}
        rows = doc.get("songs", []) or []
        now = time.time()
        max_age = AUTOPLAY_REPEAT_HOURS * 3600

        fresh = []
        for row in rows:
            try:
                ts = float(row.get("ts", 0))
            except Exception:
                ts = 0
            if ts and now - ts <= max_age:
                fresh.append(row)

        # Avoid writing the same exact video twice back-to-back.
        if not fresh or str(fresh[-1].get("vidid") or "") != str(vidid):
            fresh.append(
                {
                    "vidid": str(vidid or ""),
                    "title": str(title or ""),
                    "ts": now,
                }
            )

        await autoplay_history_db.update_one(
            {"chat_id": chat_id},
            {"$set": {"songs": fresh[-AUTOPLAY_RECENT_LIMIT:]}},
            upsert=True,
        )
    except Exception:
        pass


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🔁 REPEAT CHECK (vidid + fuzzy title)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def is_repeat(chat_id, vidid, title: str = "") -> bool:
    current = time.time()

    # vidid-based check
    if chat_id not in RECENT:
        RECENT[chat_id] = []
    RECENT[chat_id] = [(v, t) for v, t in RECENT[chat_id] if current - t < AUTOPLAY_REPEAT_HOURS * 3600]
    if vidid in [v for v, _ in RECENT[chat_id]]:
        return True

    # title-based fuzzy check — same song from different channels
    if title:
        norm = normalize_title(title)
        if norm and len(norm) >= 4:
            if chat_id not in RECENT_TITLES:
                RECENT_TITLES[chat_id] = []
            RECENT_TITLES[chat_id] = [
                (n, t) for n, t in RECENT_TITLES[chat_id] if current - t < AUTOPLAY_REPEAT_HOURS * 3600
            ]
            for stored_norm, _ in RECENT_TITLES[chat_id]:
                if _same_song(stored_norm, norm):
                    return True

    return False


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ➕ ADD RECENT SONG
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def add_recent(chat_id, vidid, title: str = "") -> None:
    if not vidid:
        return
    current = time.time()

    if chat_id not in RECENT:
        RECENT[chat_id] = []
    RECENT[chat_id].append((vidid, current))
    if len(RECENT[chat_id]) > AUTOPLAY_RECENT_LIMIT:
        RECENT[chat_id] = RECENT[chat_id][-AUTOPLAY_RECENT_LIMIT:]

    if title:
        norm = normalize_title(title)
        if norm and len(norm) >= 4:
            if chat_id not in RECENT_TITLES:
                RECENT_TITLES[chat_id] = []
            RECENT_TITLES[chat_id].append((norm, current))
            if len(RECENT_TITLES[chat_id]) > AUTOPLAY_RECENT_LIMIT:
                RECENT_TITLES[chat_id] = RECENT_TITLES[chat_id][-AUTOPLAY_RECENT_LIMIT:]

    await _persist_recent_song(chat_id, vidid, title)



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
                    "_search_query": query,
                }
            )
    except Exception:
        pass

    return results


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  SMART QUERY BUILDER (Indian Focus)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

def build_smart_queries(title, artist, movie, lang, mood):
    """
    Strict recommendation priority:
      1) LANGUAGE
      2) SINGER (same singer preferred; different singer is allowed)
      3) CATEGORY / MOOD

    Every query contains the target language. We intentionally do not search
    the current movie or "songs like <title>" because those were producing
    repetitive soundtrack results and unrelated recommendations.
    """
    queries = []

    # Priority 1 + 2 + 3: ideal match.
    if artist and mood and mood != "normal":
        queries.append(
            {
                "q": f"{lang} {artist} {mood} songs official audio",
                "kind": "artist_mood",
            }
        )

    # Priority 1 + 2: same singer in same language.
    if artist:
        queries += [
            {
                "q": f"{lang} {artist} songs official audio",
                "kind": "artist",
            },
            {
                "q": f"{lang} {artist} hit songs",
                "kind": "artist",
            },
        ]

    # Priority 1 + 3: same language + same category/mood, any singer.
    if mood and mood != "normal":
        queries += [
            {
                "q": f"{lang} {mood} songs official audio",
                "kind": "mood",
            },
            {
                "q": f"popular {lang} {mood} songs",
                "kind": "mood",
            },
        ]

    # Priority 1 only: same language, any singer/category.
    queries += [
        {"q": f"{lang} hit songs official audio", "kind": "language"},
        {"q": f"popular {lang} songs official audio", "kind": "language"},
        {"q": f"latest {lang} songs official audio", "kind": "language"},
    ]

    # Deduplicate while preserving strict order.
    final = []
    seen = set()
    for item in queries:
        q = re.sub(r"\s+", " ", item["q"]).strip()
        key = q.lower()
        if len(q) > 3 and key not in seen:
            seen.add(key)
            final.append({"q": q, "kind": item["kind"]})

    return final[:8]


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
        "artist_mood": 360,
        "artist": 300,
        "mood": 180,
        "language": 100,
    }

    seen_vids = set()

    for query_index, query_item in enumerate(queries):
        if isinstance(query_item, dict):
            q = query_item.get("q", "")
            kind = query_item.get("kind", "language")
        else:
            q = str(query_item)
            kind = "language"

        try:
            rows = await search_many(q)
        except Exception:
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

                # PRIORITY #2 — SINGER
                same_artist = False
                if artist:
                    artist_lower = artist.lower()
                    same_artist = (
                        artist_lower in title_lower
                        or artist_lower in channel
                    )
                    if same_artist:
                        score += 420
                    elif kind in {"artist", "artist_mood"}:
                        # Search was for the same singer but result does not
                        # confirm it. Keep it usable, just below confirmed artist.
                        score -= 80

                # PRIORITY #3 — CATEGORY / MOOD
                mood_match = False
                if mood and mood != "normal":
                    mood_keys = MOOD_DB.get(mood, [])
                    mood_match = any(x in combined for x in mood_keys)
                    if mood_match:
                        score += 210
                    elif kind in {"mood", "artist_mood"}:
                        # Query itself is mood-specific, so do not punish heavily
                        # when the title does not literally say "sad"/"romantic".
                        score += 45

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

        await asyncio.sleep(0.03)

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

        # Restore history first so bot restarts/deploys do not reset repeat protection.
        await _load_persistent_recent(chat_id)

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
            lang = previous_ctx.get("lang") or detect_lang(last_title)
        else:
            lang = detect_lang(last_title)

        mood = detect_mood(last_title)
        artist = extract_artist(last_title)
        movie = detect_movie(last_title)
        if movie:
            _remember_movie(chat_id, movie)

        queries = build_smart_queries(last_title, artist, movie, lang, mood)

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

        if not ranked:
            # Final fallback is STILL same-language only.
            fallback_queries = [
                {"q": f"{lang} hit songs official audio", "kind": "language"},
                {"q": f"popular {lang} songs", "kind": "language"},
                {"q": f"latest {lang} songs", "kind": "language"},
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
                limit=3,
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

                AUTOPLAY_CONTEXT[chat_id] = {
                    "vidid": vidid,
                    "lang": lang,
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
