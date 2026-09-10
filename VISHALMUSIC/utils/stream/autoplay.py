import asyncio
import random
import re
import time

import aiohttp

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
    if not title:
        return ""
    title_lower = title.lower()
    for artist, keys in ARTIST_DB.items():
        if any(x in title_lower for x in keys):
            return artist
    parts = re.split(r"[-|(]", title)
    if len(parts) > 1:
        candidate = parts[0].strip()
        if len(candidate) < 30:
            return candidate
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


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  SMART QUERY BUILDER (Indian Focus)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

def build_smart_queries(title, artist, movie, lang, mood):
    queries = []

    clean_title = re.sub(
        r"official|video|lyrics|lyrical|hd|4k|music|song|audio|full|hq",
        "",
        title,
        flags=re.IGNORECASE,
    ).strip()

    queries.append(clean_title)
    queries.append(f"{clean_title} song")
    queries.append(f"{clean_title} official")

    if artist:
        queries.append(f"{artist} songs")
        queries.append(f"{artist} hits")
        queries.append(f"{artist} best songs")
        if movie:
            queries.append(f"{artist} {movie} song")
        if lang:
            queries.append(f"{artist} {lang} songs")

    if movie:
        queries.append(f"{movie} songs")
        queries.append(f"{movie} all songs")
        queries.append(f"{movie} jukebox")
        queries.append(f"{movie} playlist")

    if mood == "sad":
        queries += ["sad hindi songs", "heartbreak songs hindi", "bewafa songs"]
    elif mood == "love":
        queries += ["romantic hindi songs", "love songs bollywood", "ishq wala song"]
    elif mood == "party":
        queries += ["party punjabi songs", "dance songs bollywood"]
    elif mood == "wedding":
        queries += ["wedding songs hindi", "shaadi ke gane"]
    elif mood == "devotional":
        queries += ["bhajan", "aarti songs", "hanuman chalisa"]
    elif mood == "oldschool":
        queries += ["90s hindi songs", "old bollywood songs", "retro hindi songs"]
    elif mood == "sufi":
        queries += ["sufi songs hindi", "qawwali hits"]

    if lang == "hindi":
        queries += ["latest bollywood hits", "trending hindi songs"]
    elif lang == "punjabi":
        queries += ["latest punjabi songs", "punjabi hits"]
    elif lang == "bhojpuri":
        queries.append("bhojpuri hits")
    elif lang == "haryanvi":
        queries.append("haryanvi songs 2025")
    elif lang == "gujarati":
        queries.append("gujarati garba songs")
    elif lang == "tamil":
        queries.append("tamil hits")
    elif lang == "telugu":
        queries.append("telugu hits")
    elif lang == "bengali":
        queries.append("bengali songs")
    elif lang == "marathi":
        queries.append("marathi songs")
    elif lang == "urdu":
        queries.append("urdu songs")

    if len(queries) < 5:
        queries.extend(TRENDING_STYLES)

    bad_words = [
        "slowed", "reverb", "lofi", "8d", "live", "mix", "dj remix",
        "bass boosted", "cover", "karaoke", "instrumental", "sped up",
    ]

    final = []
    for q in queries:
        q_lower = q.lower()
        if not any(bad in q_lower for bad in bad_words):
            if q not in final and len(q) > 3:
                final.append(q)

    return final[:20]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🎵 BEST SONG FINDER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def get_best_song(chat_id, queries, last_title, last_vidid, artist, movie, mood, lang):
    """
    Pick a cleaner autoplay recommendation.
    Priorities:
      - no repeats
      - avoid remix/cover/karaoke/live/status/shorts/lyrics-only junk
      - prefer official/topic/audio uploads
      - prefer same artist/movie/language when relevant
      - avoid candidates that are too similar to the just-played song
    """
    candidates = []
    original_norm = normalize_title(last_title)
    original_words = [w for w in original_norm.split() if len(w) > 2]

    hard_bad_words = [
        "slowed", "reverb", "8d", "lofi", "lo-fi", "nightcore",
        "dj remix", "remix", "mashup", "bass boosted", "sped up",
        "cover", "karaoke", "instrumental", "acoustic cover",
        "live performance", "live concert", "reaction", "status",
        "whatsapp status", "shorts", "short video", "edit audio",
        "fanmade", "fan made", "teaser", "trailer", "promo",
        "tutorial", "how to", "dance cover", "lyrics status",
    ]

    preferred_words = [
        "official audio", "official song", "official music video",
        "provided to youtube", "topic", "vevo", "records", "music",
    ]

    seen_vids = set()

    for q in queries:
        try:
            details, vidid = await yt.track(q)
            if not vidid or vidid in seen_vids:
                continue
            seen_vids.add(vidid)

            if vidid == last_vidid:
                continue

            raw_title = details.get("title", "") or ""
            title = raw_title.lower().strip()
            norm_title = normalize_title(raw_title)
            duration = details.get("duration_min", "0:00") or "0:00"

            if any(x in title for x in hard_bad_words):
                continue

            if await is_repeat(chat_id, vidid, raw_title):
                continue

            # Don't autoplay the same song from another channel/version.
            if original_norm and norm_title and _same_song(original_norm, norm_title):
                continue

            # Reject suspiciously tiny/long tracks for normal music autoplay.
            try:
                parts = [int(x) for x in str(duration).split(":")]
                if len(parts) == 2:
                    secs = parts[0] * 60 + parts[1]
                elif len(parts) == 3:
                    secs = parts[0] * 3600 + parts[1] * 60 + parts[2]
                else:
                    secs = 0
                if secs and (secs < 100 or secs > 720):
                    continue
            except Exception:
                pass

            score = 0

            # Same artist is useful, but should not overwhelm everything else.
            if artist and artist.lower() in title:
                score += 55

            # Same movie/album context.
            if movie and movie.lower() in title:
                score += 40

            # Language/context relevance.
            lang_keys = LANG_DB.get(lang, [])
            if lang_keys and any(x in title for x in lang_keys):
                score += 20

            if mood != "normal":
                mood_keywords = MOOD_DB.get(mood, [])
                if any(x in title for x in mood_keywords):
                    score += 10

            # Prefer official / topic / label-style uploads.
            if any(x in title for x in preferred_words):
                score += 20

            # Some overlap with current title is okay, but too much means likely same track/version.
            overlap = sum(1 for w in original_words if w in norm_title)
            if overlap:
                score += min(overlap * 4, 16)

            # Reward normal-looking song titles.
            if 2 <= len(norm_title.split()) <= 10:
                score += 8

            # Penalise cluttered upload titles.
            clutter = [
                "full video", "full song", "lyrics", "lyrical", "jukebox",
                "playlist", "compilation", "nonstop", "medley",
            ]
            if any(x in title for x in clutter):
                score -= 18

            candidates.append((score, vidid, details))

        except Exception:
            continue

        await asyncio.sleep(0.12)

    candidates.sort(key=lambda x: x[0], reverse=True)

    if candidates:
        best = candidates[0]
        return best[1], best[2]

    return None, None


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

        # Robust fallback chain.
        # yt.track(query) returns only one top result, so try several varied
        # searches. This avoids autoplay dying when the first result is the
        # same/recent song.
        if not vidid:
            fallback_queries = []

            if artist:
                fallback_queries += [
                    f"{artist} popular songs",
                    f"{artist} best songs",
                    f"{artist} hits",
                    f"{artist} top songs",
                ]

            if movie:
                fallback_queries += [
                    f"{movie} songs",
                    f"{movie} soundtrack",
                    f"{movie} popular songs",
                ]

            if mood and mood != "normal":
                fallback_queries += [
                    f"{mood} {lang} songs",
                    f"popular {mood} songs",
                ]

            if lang:
                fallback_queries += [
                    f"popular {lang} songs",
                    f"{lang} hits",
                    f"top {lang} songs",
                    f"trending {lang} songs",
                ]

            fallback_queries += [
                "popular hindi songs",
                "bollywood hits",
                "trending indian songs",
                "top indian songs",
            ]

            fallback_bad = [
                "slowed", "reverb", "8d", "lofi", "lo-fi", "nightcore",
                "dj remix", "remix", "mashup", "bass boosted", "sped up",
                "cover", "karaoke", "instrumental", "reaction", "status",
                "whatsapp status", "shorts", "fanmade", "fan made",
            ]

            for fq in fallback_queries:
                try:
                    cand_details, cand_vidid = await yt.track(fq)
                    if not cand_vidid or cand_vidid == last_vidid:
                        continue

                    cand_title = (cand_details or {}).get("title", "")
                    cand_title_lower = cand_title.lower()

                    if any(x in cand_title_lower for x in fallback_bad):
                        continue

                    if await is_repeat(chat_id, cand_vidid, cand_title):
                        continue

                    details, vidid = cand_details, cand_vidid
                    break
                except Exception:
                    continue

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
            autoplay_next=True,
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
