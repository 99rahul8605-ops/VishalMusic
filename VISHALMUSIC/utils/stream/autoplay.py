import asyncio
import os
import random
import re
import time

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
AUTO_PLAYING = {}

# Autoplay recommendation tuning
AUTOPLAY_MIN_SECONDS = int(os.getenv("AUTOPLAY_MIN_SECONDS", "100"))
AUTOPLAY_MAX_SECONDS = int(os.getenv("AUTOPLAY_MAX_SECONDS", "420"))
AUTOPLAY_RESULTS_PER_QUERY = max(2, min(int(os.getenv("AUTOPLAY_RESULTS_PER_QUERY", "5")), 8))

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🇮🇳 INDIAN LANGUAGE DATABASE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

LANG_DB = {
    "hindi": ["hindi", "bollywood", "arijit", "jubin", "atif", "hindi song", "bollywood song"],
    "punjabi": ["punjabi", "sidhu", "diljit", "karan", "ammy", "jatt", "punjabi song"],
    "english": ["english", "ed sheeran", "taylor swift", "justin bieber", "english song"],
    "bhojpuri": ["bhojpuri", "pawan singh", "khesari", "bhojpuri song"],
    "haryanvi": ["haryanvi", "khasa", "masoom sharma", "haryanvi song"],
    "gujarati": ["gujarati", "gujju", "garba", "gujarati song"],
    "tamil": ["tamil", "tamil song", "kollywood", "anirudh", "tamil cinema"],
    "telugu": ["telugu", "telugu song", "tollywood", "devi sri", "telugu cinema"],
    "bengali": ["bengali", "bangla", "bengali song"],
    "marathi": ["marathi", "marathi song", "maharashtra"],
    "urdu": ["urdu", "urdu song", "pakistani", "nusrat"],
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🎭 MOOD DATABASE (Indian Context)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

MOOD_DB = {
    "sad": ["sad", "broken", "heart", "bewafa", "alone", "cry", "dard", "tanha", "rula", "sad song"],
    "love": ["love", "romantic", "ishq", "pyaar", "mohabbat", "love song", "romantic song", "pyar", "ishq wala"],
    "party": ["party", "dj", "dance", "club", "bhangra", "party song", "dj song", "dance song", "masala"],
    "wedding": ["wedding", "shaadi", "marriage", "dulhan", "mehendi", "sangeet"],
    "devotional": ["devotional", "bhajan", "aarti", "mantra", "shiva", "krishna", "ram", "ganesha", "hanuman"],
    "oldschool": ["old", "classic", "90s", "80s", "kishore", "lata", "rafi", "old song", "retro", "purana"],
    "punjabi": ["punjabi", "sidhu", "diljit", "bhangra", "jatt", "punjabi song"],
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

def detect_lang(title):
    if not title:
        return "hindi"
    title = title.lower()
    for lang, keys in LANG_DB.items():
        if any(x in title for x in keys):
            return lang
    return "hindi"


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


def _same_song(stored: str, candidate: str) -> bool:
    """
    Fuzzy title match — handles cases where one has extra words.
    e.g. stored="diwaniyat", candidate="diwaniyat ap dhillon shreya ghoshal"
    Both start with "diwaniyat" so they match.
    """
    if not stored or not candidate:
        return False
    if len(stored) < 4 or len(candidate) < 4:
        return False
    short = stored if len(stored) <= len(candidate) else candidate
    long  = candidate if len(stored) <= len(candidate) else stored
    # Match if the longer one starts with the shorter, or shorter is a substring
    return long.startswith(short) or short in long


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🔁 REPEAT CHECK (vidid + fuzzy title)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def is_repeat(chat_id, vidid, title: str = "") -> bool:
    current = time.time()

    # vidid-based check
    if chat_id not in RECENT:
        RECENT[chat_id] = []
    RECENT[chat_id] = [(v, t) for v, t in RECENT[chat_id] if current - t < 7200]
    if vidid in [v for v, _ in RECENT[chat_id]]:
        return True

    # title-based fuzzy check — same song from different channels
    if title:
        norm = normalize_title(title)
        if norm and len(norm) >= 4:
            if chat_id not in RECENT_TITLES:
                RECENT_TITLES[chat_id] = []
            RECENT_TITLES[chat_id] = [
                (n, t) for n, t in RECENT_TITLES[chat_id] if current - t < 7200
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
    if len(RECENT[chat_id]) > 50:
        RECENT[chat_id] = RECENT[chat_id][-50:]

    if title:
        norm = normalize_title(title)
        if norm and len(norm) >= 4:
            if chat_id not in RECENT_TITLES:
                RECENT_TITLES[chat_id] = []
            RECENT_TITLES[chat_id].append((norm, current))
            if len(RECENT_TITLES[chat_id]) > 50:
                RECENT_TITLES[chat_id] = RECENT_TITLES[chat_id][-50:]



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
    Return several results per query instead of only the top result.
    This lets autoplay reject playlists/jukeboxes/long tracks and still pick
    a relevant normal song from positions 2-5.
    """
    results = []

    api_url = os.getenv("API_URL", "").strip().rstrip("/")
    api_key = os.getenv("API_KEY", "").strip()

    if api_url:
        try:
            params = {"q": query, "limit": limit}
            if api_key:
                params["api_key"] = api_key

            timeout = aiohttp.ClientTimeout(total=12)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(f"{api_url}/search", params=params) as resp:
                    if resp.status == 200:
                        data = await resp.json(content_type=None)
                        for item in data.get("results", [])[:limit]:
                            vidid = item.get("id") or item.get("video_id") or ""
                            if not vidid:
                                continue
                            results.append(
                                {
                                    "title": item.get("title", "") or "",
                                    "vidid": vidid,
                                    "duration_min": item.get("duration")
                                    or item.get("duration_min")
                                    or "0:00",
                                    "thumb": item.get("thumbnail") or "",
                                    "channel": item.get("channel")
                                    or item.get("uploader")
                                    or "",
                                }
                            )
        except Exception:
            results = []

    if results:
        return results

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
    Build fewer, more specific searches.

    Avoid "jukebox", "playlist", "all songs" and other queries that naturally
    return long compilations.
    """
    queries = []
    clean_title = normalize_title(title)

    # Strongest context first.
    if artist:
        queries += [
            f"{artist} popular songs official audio",
            f"{artist} hit songs official",
        ]

    if movie:
        queries += [
            f"{movie} songs official audio",
            f"{movie} soundtrack songs",
        ]

    # "Songs like ..." is useful when artist/movie metadata is missing.
    # Same-song variants are hard-filtered later.
    if clean_title and len(clean_title) >= 4:
        queries += [
            f"songs like {clean_title}",
            f"{clean_title} similar {lang} songs",
        ]

    if mood and mood != "normal":
        queries.append(f"{mood} {lang} songs official audio")

    if lang:
        queries += [
            f"popular {lang} songs official audio",
            f"{lang} hit songs official audio",
        ]

    if lang == "hindi":
        queries.append("bollywood hit songs official audio")
    elif lang == "punjabi":
        queries.append("punjabi hit songs official audio")

    # Deduplicate, preserve priority order, keep request count controlled.
    final = []
    for q in queries:
        q = re.sub(r"\s+", " ", q).strip()
        if len(q) > 3 and q.lower() not in {x.lower() for x in final}:
            final.append(q)

    return final[:8]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🎵 BEST SONG FINDER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def get_best_song(chat_id, queries, last_title, last_vidid, artist, movie, mood, lang):
    """
    Search multiple results per query and score only normal-length, relevant
    single songs.
    """
    candidates = []
    original_norm = normalize_title(last_title)

    hard_bad_words = [
        "slowed", "reverb", "8d", "lofi", "lo-fi", "nightcore",
        "dj remix", "remix", "mashup", "bass boosted", "sped up",
        "cover", "karaoke", "instrumental", "acoustic cover",
        "live performance", "live concert", "reaction", "status",
        "whatsapp status", "shorts", "short video", "edit audio",
        "fanmade", "fan made", "teaser", "trailer", "promo",
        "tutorial", "how to", "dance cover", "lyrics status",
        # Long-form / compilation content:
        "jukebox", "audio jukebox", "nonstop", "non stop", "non-stop",
        "playlist", "full album", "all songs", "complete album",
        "compilation", "medley", "greatest hits", "best of",
        "1 hour", "2 hour", "3 hour", "one hour", "hours of",
    ]

    soft_bad_words = [
        "lyrics", "lyrical", "full song", "extended version",
        "10 hours", "collection",
    ]

    seen_vids = set()

    for query_index, q in enumerate(queries):
        try:
            rows = await search_many(q)
        except Exception:
            rows = []

        q_lower = q.lower()
        query_bonus = max(4, 30 - query_index * 4)

        for details in rows:
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

                # Same song from another channel/version.
                if original_norm and _same_song(original_norm, norm_title):
                    continue

                # Strict normal-song duration window.
                if secs:
                    if secs < AUTOPLAY_MIN_SECONDS or secs > AUTOPLAY_MAX_SECONDS:
                        continue

                score = query_bonus

                # Query context bonus: if the search itself was artist/movie
                # specific, trust it more than broad trending searches.
                if artist and artist.lower() in q_lower:
                    score += 30
                if movie and movie.lower() in q_lower:
                    score += 26
                if mood != "normal" and mood.lower() in q_lower:
                    score += 10
                if lang and lang.lower() in q_lower:
                    score += 8

                # Candidate itself confirms context.
                if artist and (
                    artist.lower() in title_lower or artist.lower() in channel
                ):
                    score += 70

                if movie and movie.lower() in title_lower:
                    score += 50

                if mood != "normal":
                    mood_keys = MOOD_DB.get(mood, [])
                    if any(x in title_lower for x in mood_keys):
                        score += 15

                lang_keys = LANG_DB.get(lang, [])
                if lang_keys and any(x in title_lower for x in lang_keys):
                    score += 10

                # Prefer music-label / official style uploads.
                if "official" in title_lower:
                    score += 12
                if any(x in channel for x in ["topic", "vevo", "records", "music"]):
                    score += 15

                # Normal song length sweet spot.
                if secs:
                    if 140 <= secs <= 360:
                        score += 18
                    elif 360 < secs <= AUTOPLAY_MAX_SECONDS:
                        score += 5

                # Clean, normal-sized title.
                word_count = len(norm_title.split())
                if 2 <= word_count <= 10:
                    score += 8
                elif word_count > 16:
                    score -= 12

                if any(x in title_lower for x in soft_bad_words):
                    score -= 20

                candidates.append((score, vidid, details))

            except Exception:
                continue

        # Small yield; don't make autoplay wait unnecessarily.
        await asyncio.sleep(0.04)

    candidates.sort(key=lambda x: x[0], reverse=True)

    if not candidates:
        return None, None

    # Pick among the strongest few instead of always repeating one pattern.
    top_score = candidates[0][0]
    top = [c for c in candidates[:5] if c[0] >= top_score - 8]
    chosen = random.choice(top) if len(top) > 1 else candidates[0]

    return chosen[1], chosen[2]


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

        lang = detect_lang(last_title)
        mood = detect_mood(last_title)
        artist = extract_artist(last_title)
        movie = detect_movie(last_title)

        queries = build_smart_queries(last_title, artist, movie, lang, mood)

        # FIX 1: Pass last_vidid so same song is hard-skipped during search
        vidid, details = await get_best_song(
            chat_id, queries, last_title, last_vidid, artist, movie, mood, lang
        )

        # Filtered fallback: still search normal single songs only.
        if not vidid:
            fallback_queries = []

            if artist:
                fallback_queries.append(f"{artist} top songs official audio")

            if movie:
                fallback_queries.append(f"{movie} popular songs official audio")

            if mood and mood != "normal":
                fallback_queries.append(f"{mood} {lang} hit songs")

            if lang:
                fallback_queries += [
                    f"{lang} popular songs official audio",
                    f"{lang} chart songs official audio",
                ]

            if lang == "hindi":
                fallback_queries += [
                    "bollywood popular songs official audio",
                    "hindi chart songs official audio",
                ]

            vidid, details = await get_best_song(
                chat_id,
                fallback_queries[:6],
                last_title,
                last_vidid,
                artist,
                movie,
                mood,
                lang,
            )

        if not vidid:
            try:
                await msg.edit_text("❌ ɴᴏ ꜱᴏɴɢ ꜰᴏᴜɴᴅ")
            except Exception:
                pass
            return False

        new_title = details.get("title", "") if details else ""
        await add_recent(chat_id, vidid, new_title)

        link = f"https://youtube.com/watch?v={vidid}"

        try:
            thumb = details.get("thumb", "")
            if not thumb or not thumb.startswith("http"):
                thumb = await get_thumbnail_direct(vidid)
        except Exception:
            thumb = await get_thumbnail_direct(vidid)

        language = await get_lang(chat_id)
        _ = get_string(language)

        # FIX 2: stop_stream() REMOVED — bot stays in VC between songs.
        # The stream ended naturally (pytgcalls fired the callback), so the
        # assistant is still physically in the voice chat. Calling stop_stream()
        # was explicitly doing leave_call() which caused the leave + rejoin.
        # stream() → join_call() → assistant.play() handles stream switching
        # without leaving when the assistant is already in the call.

        await stream(
            _,
            msg,
            app.id,
            {
                "link": link,
                "vidid": vidid,
                "title": details.get("title", "🇮🇳 ꜱɪᴍɪʟᴀʀ ɪɴᴅɪᴀɴ ꜱᴏɴɢ"),
                "duration_min": details.get("duration_min", "00:00"),
                "thumb": thumb,
            },
            chat_id,
            "🔁 ᴀᴜᴛᴏᴘʟᴀʏ",
            original_chat_id,
            video=False,
            streamtype="youtube",
        )

        try:
            await msg.delete()
        except Exception:
            pass

        return True

    except Exception:
        return False

    finally:
        AUTO_PLAYING.pop(chat_id, None)
