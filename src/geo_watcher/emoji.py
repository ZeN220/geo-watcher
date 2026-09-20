from dataclasses import dataclass
from html import escape


@dataclass(frozen=True, slots=True)
class Emoji:
    id: str
    fallback: str

    def html(self, *, custom: bool = True) -> str:
        if not custom:
            return self.fallback
        return (
            f'<tg-emoji emoji-id="{self.id}">{escape(self.fallback)}</tg-emoji>'
        )


GOOD = Emoji("5377748651768557841", "🟢")
WARN = Emoji("5377673704589243197", "🟡")
BAD = Emoji("5377672802646109842", "🔴")

GEO = Emoji("5879561961934426469", "🌍")
AVAILABILITY = Emoji("5274220354884082834", "📺")

SERVICES = {
    "apple": Emoji("5895654736241101927", "🍎"),
    "bing": Emoji("5879747654845468247", "🔎"),
    "cdn_cloudflare": Emoji("5877404093055503595", "☁️"),
    "cdn_netflix": Emoji("4960802091485364850", "🎬"),
    "cdn_youtube": Emoji("5359523920120651432", "▶️"),
    "chatgpt": Emoji("5877651964208091297", "🤖"),
    "chatgpt_app": Emoji("5877651964208091297", "🤖"),
    "chatgpt_web": Emoji("5877651964208091297", "🤖"),
    "claude_access": Emoji("5299032746025322219", "✳️"),
    "cloudflare": Emoji("5877404093055503595", "☁️"),
    "deezer": Emoji("4985999144192574149", "🎧"),
    "gemini_access": Emoji("5298850360239101612", "✨"),
    "google": Emoji("5879661781269352676", "🔎"),
    "google_captcha": Emoji("5879661781269352676", "🔎"),
    "jetbrains": Emoji("5276466614189960866", "🧑‍💻"),
    "netflix": Emoji("4960802091485364850", "🎬"),
    "netflix_access": Emoji("4960802091485364850", "🎬"),
    "ookla": Emoji("5877610818421395686", "📶"),
    "playstation": Emoji("5206380775213121528", "🎮"),
    "prime": Emoji("4961180134506758889", "🎬"),
    "reddit": Emoji("5359457631595404808", "👽"),
    "reddit_guest": Emoji("5359457631595404808", "👽"),
    "spotify": Emoji("5359342878659191095", "🎧"),
    "spotify_signup": Emoji("5359342878659191095", "🎧"),
    "steam": Emoji("5206370578960760792", "🎮"),
    "tiktok": Emoji("5359640777590841912", "🎵"),
    "tiktok_access": Emoji("5359640777590841912", "🎵"),
    "twitch": Emoji("5359596526542790544", "🎮"),
    "x": Emoji("5204061664671976334", "🐦"),
    "youtube": Emoji("5359523920120651432", "▶️"),
    "youtube_premium_access": Emoji("5359523920120651432", "▶️"),
}
