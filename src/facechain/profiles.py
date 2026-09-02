"""Group verified matches into distinct social accounts.

A face search returns *posts*. Several of them often belong to one account, and what a user
actually wants is the account list, not a list of URLs. This module derives platform and handle
where the URL shape allows it, and collapses posts to accounts.

Deliberately conservative: where a handle cannot be derived from the URL alone -- Instagram post
permalinks like /p/ABC123/ carry no handle -- the post is reported under the platform with the
handle left unknown rather than guessed. Inventing a handle would put a fabricated identity next
to a real cosine score, which is exactly the kind of overstatement this project avoids elsewhere.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from .search.candidates import registrable_host

# Path shapes that carry an account handle. Anything not matched here yields handle=None.
HANDLE_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("instagram", re.compile(r"^/([A-Za-z0-9._]{2,30})/?$")),
    ("x", re.compile(r"^/([A-Za-z0-9_]{1,15})(?:/status/\d+)?/?$")),
    ("twitter", re.compile(r"^/([A-Za-z0-9_]{1,15})(?:/status/\d+)?/?$")),
    ("linkedin", re.compile(r"^/in/([A-Za-z0-9\-_%]{3,120})/?$")),
    ("tiktok", re.compile(r"^/@([A-Za-z0-9._]{2,30})")),
    ("threads", re.compile(r"^/@([A-Za-z0-9._]{2,30})")),
    ("youtube", re.compile(r"^/@([A-Za-z0-9._\-]{2,60})")),
    ("facebook", re.compile(r"^/([A-Za-z0-9.]{5,60})/?$")),
    ("reddit", re.compile(r"^/(?:user|u)/([A-Za-z0-9_\-]{3,30})")),
    ("bsky", re.compile(r"^/profile/([A-Za-z0-9.\-]{3,120})")),
    ("github", re.compile(
        r"^/([A-Za-z0-9](?:[A-Za-z0-9\-]{0,37}[A-Za-z0-9])?)(?:/[^/]+)?/?$"
    )),
    ("gitlab", re.compile(
        r"^/([A-Za-z0-9](?:[A-Za-z0-9_\-.]{0,253}[A-Za-z0-9])?)(?:/[^/]+)?/?$"
    )),
    ("soundcloud", re.compile(r"^/([A-Za-z0-9_\-]{3,50})/?$")),
]

PLATFORM_NAMES = {
    "instagram": "Instagram", "x": "X", "twitter": "X", "linkedin": "LinkedIn",
    "tiktok": "TikTok", "threads": "Threads", "youtube": "YouTube",
    "facebook": "Facebook", "reddit": "Reddit", "bsky": "Bluesky",
    "github": "GitHub", "gitlab": "GitLab", "soundcloud": "SoundCloud",
}


@dataclass
class Account:
    platform: str
    handle: str | None
    urls: list[str] = field(default_factory=list)
    best_cosine: float = 0.0
    # "face" = independently embedded and scored. "linked" = published on a face-verified page.
    origin: str = "face"

    @property
    def display(self) -> str:
        name = PLATFORM_NAMES.get(self.platform, self.platform or "web")
        return f"{name} · @{self.handle}" if self.handle else f"{name} · (post)"

    @property
    def profile_url(self) -> str | None:
        """A canonical profile link, only where the platform makes one derivable."""
        if not self.handle:
            return None
        h = self.handle
        return {
            "instagram": f"https://www.instagram.com/{h}/",
            "x": f"https://x.com/{h}", "twitter": f"https://x.com/{h}",
            "linkedin": f"https://www.linkedin.com/in/{h}/",
            "tiktok": f"https://www.tiktok.com/@{h}",
            "threads": f"https://www.threads.net/@{h}",
            "youtube": f"https://www.youtube.com/@{h}",
            "facebook": f"https://www.facebook.com/{h}/",
            "reddit": f"https://www.reddit.com/user/{h}/",
            "bsky": f"https://bsky.app/profile/{h}",
            "github": f"https://github.com/{h}",
            "gitlab": f"https://gitlab.com/{h}",
            "soundcloud": f"https://soundcloud.com/{h}",
        }.get(self.platform)


def platform_of(url: str) -> str:
    host = registrable_host(url)
    for key in PLATFORM_NAMES:
        if host == f"{key}.com" or host.endswith(f".{key}.com") or host == f"{key}.app":
            return key
    if host.endswith(".net") and "threads" in host:
        return "threads"
    return host or "web"


def handle_of(url: str) -> str | None:
    """Extract an account handle, or None when the URL shape does not carry one."""
    platform = platform_of(url)
    try:
        path = urlsplit(url).path or "/"
    except ValueError:
        return None

    # Reserved path segments that look like handles but are not.
    reserved = {
        "p", "reel", "reels", "explore", "posts", "pub", "dir", "shorts", "watch", "video",
        "about", "features", "login", "signup", "settings", "orgs", "marketplace", "topics",
        "collections", "events", "sponsors", "notifications", "issues", "pulls", "search",
        "new", "dashboard", "pricing", "enterprise", "trending", "blog", "apps", "org",
    }
    for key, pattern in HANDLE_PATTERNS:
        if key != platform:
            continue
        m = pattern.match(path)
        if m:
            h = m.group(1)
            return None if h.lower() in reserved else h
    return None


def group_accounts(matches: list[tuple[str, float]]) -> list[Account]:
    """Collapse (url, cosine) pairs into distinct accounts, best score first.

    Posts whose handle cannot be derived stay separate rather than being merged into a guessed
    account.
    """
    by_key: dict[tuple[str, str | None, str], Account] = {}
    for url, score in matches:
        platform = platform_of(url)
        handle = handle_of(url)
        # Unknown handles are keyed by url so they are never wrongly merged together.
        key = (platform, handle, "" if handle else url)
        acct = by_key.get(key)
        if acct is None:
            acct = Account(platform=platform, handle=handle)
            by_key[key] = acct
        if url not in acct.urls:
            acct.urls.append(url)
        acct.best_cosine = max(acct.best_cosine, float(score))

    return sorted(by_key.values(), key=lambda a: a.best_cosine, reverse=True)
