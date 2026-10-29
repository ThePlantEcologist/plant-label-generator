"""Saved accounts for the Plant Label Generator, backed by Supabase.

Only invited users (emails listed in the ``invited_users`` table) get saved
settings, icons, and frequent-plant suggestions. Everyone else can still use
the app as a guest; nothing is written to Supabase for guests.

All calls run on the Streamlit server with the project's *secret* key, so the
key never reaches the browser. Tables have row level security turned on with
no public policies, which means the publishable key cannot read them.
"""

from __future__ import annotations

import hashlib
import io
from typing import Any

import requests
from PIL import Image

ICON_BUCKET = "label-icons"
ICON_SLOTS = (1, 2)
ICON_MAX_PIXELS = 800  # longest side after resizing
ICON_MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # reject anything bigger before resizing
REQUEST_TIMEOUT = 15


class UserStoreError(RuntimeError):
    """Raised when Supabase returns an error."""


def normalize_email(email: str | None) -> str:
    return (email or "").strip().lower()


def prepare_icon(image_bytes: bytes) -> bytes:
    """Shrink an uploaded image and convert it to PNG for storage."""
    if len(image_bytes) > ICON_MAX_UPLOAD_BYTES:
        raise ValueError("That image is over 5 MB. Please use a smaller file.")
    try:
        image = Image.open(io.BytesIO(image_bytes))
        image.load()
    except Exception as exc:  # noqa: BLE001 - Pillow raises many types
        raise ValueError("That file doesn't look like an image Pillow can read.") from exc

    if image.mode not in ("RGB", "RGBA"):
        image = image.convert("RGBA")
    image.thumbnail((ICON_MAX_PIXELS, ICON_MAX_PIXELS))

    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


class UserStore:
    """Thin Supabase REST client for the app's four features."""

    def __init__(self, url: str, secret_key: str, session: requests.Session | None = None):
        self.url = url.rstrip("/")
        self.session = session or requests.Session()
        self.session.headers["apikey"] = secret_key
        # Legacy service_role keys are JWTs and also need a Bearer header.
        # New sb_secret_ keys must only go in the apikey header.
        if secret_key.startswith("eyJ"):
            self.session.headers["Authorization"] = f"Bearer {secret_key}"

    @classmethod
    def from_secrets(cls, secrets: Any) -> "UserStore | None":
        """Build a store from st.secrets, or return None if not configured."""
        try:
            section = secrets["supabase"]
            url = section["url"]
            key = section["secret_key"]
        except (KeyError, FileNotFoundError, AttributeError):
            return None
        if not url or not key:
            return None
        return cls(url, key)

    # ----- low-level helpers -------------------------------------------------

    def _rest(self, method: str, path: str, **kwargs) -> requests.Response:
        response = self.session.request(
            method, f"{self.url}/rest/v1/{path}", timeout=REQUEST_TIMEOUT, **kwargs
        )
        if response.status_code >= 400:
            raise UserStoreError(f"Supabase error {response.status_code}: {response.text[:300]}")
        return response

    def _storage(self, method: str, path: str, **kwargs) -> requests.Response:
        return self.session.request(
            method, f"{self.url}/storage/v1/{path}", timeout=REQUEST_TIMEOUT, **kwargs
        )

    @staticmethod
    def _folder(email: str) -> str:
        # Hash the email so addresses never appear in storage paths.
        return hashlib.sha256(normalize_email(email).encode()).hexdigest()[:32]

    def _icon_path(self, email: str, slot: int) -> str:
        if slot not in ICON_SLOTS:
            raise ValueError(f"Icon slot must be one of {ICON_SLOTS}.")
        return f"{self._folder(email)}/slot{slot}.png"

    # ----- invitations -------------------------------------------------------

    def is_invited(self, email: str) -> bool:
        email = normalize_email(email)
        if not email:
            return False
        rows = self._rest(
            "GET", "invited_users", params={"email": f"eq.{email}", "select": "email"}
        ).json()
        return bool(rows)

    # ----- settings ----------------------------------------------------------

    def get_settings(self, email: str) -> dict:
        rows = self._rest(
            "GET",
            "user_settings",
            params={"email": f"eq.{normalize_email(email)}", "select": "settings"},
        ).json()
        return (rows[0].get("settings") or {}) if rows else {}

    def save_settings(self, email: str, settings: dict) -> None:
        self._rest(
            "POST",
            "user_settings",
            json={"email": normalize_email(email), "settings": settings},
            headers={"Prefer": "resolution=merge-duplicates,return=minimal"},
        )

    # ----- icons -------------------------------------------------------------

    def get_icon(self, email: str, slot: int) -> bytes | None:
        response = self._storage(
            "GET", f"object/authenticated/{ICON_BUCKET}/{self._icon_path(email, slot)}"
        )
        if response.status_code == 200:
            return response.content
        if response.status_code in (400, 404):
            return None  # Storage reports a missing object as 400 or 404
        raise UserStoreError(f"Couldn't load icon {slot}: {response.status_code} {response.text[:200]}")

    def save_icon(self, email: str, slot: int, png_bytes: bytes) -> None:
        response = self._storage(
            "POST",
            f"object/{ICON_BUCKET}/{self._icon_path(email, slot)}",
            data=png_bytes,
            headers={"Content-Type": "image/png", "x-upsert": "true", "cache-control": "no-cache"},
        )
        if response.status_code >= 400:
            raise UserStoreError(f"Couldn't save icon {slot}: {response.status_code} {response.text[:200]}")

    def delete_icon(self, email: str, slot: int) -> None:
        response = self._storage(
            "DELETE",
            f"object/{ICON_BUCKET}",
            json={"prefixes": [self._icon_path(email, slot)]},
        )
        if response.status_code >= 400:
            raise UserStoreError(f"Couldn't delete icon {slot}: {response.status_code} {response.text[:200]}")

    # ----- frequent plants ---------------------------------------------------

    def record_plant_usage(self, email: str, plants: list[dict]) -> None:
        """Add one use for each loaded plant (by its Plant Toolbox URL)."""
        items = []
        seen = set()
        for plant in plants:
            url = (plant.get("Source URL") or "").strip()
            if not url or url in seen or plant.get("Common Name") == "Error":
                continue
            seen.add(url)
            items.append(
                {
                    "url": url,
                    "common_name": plant.get("Common Name") or None,
                    "scientific_name": plant.get("Scientific Name") or None,
                }
            )
        if items:
            self._rest(
                "POST",
                "rpc/record_plant_usage",
                json={"p_email": normalize_email(email), "p_items": items},
            )

    def top_plants(self, email: str, limit: int = 10) -> list[dict]:
        return self._rest(
            "GET",
            "plant_link_usage",
            params={
                "email": f"eq.{normalize_email(email)}",
                "select": "url,common_name,scientific_name,use_count",
                "order": "use_count.desc,last_used.desc",
                "limit": str(limit),
            },
        ).json()

    def forget_plant(self, email: str, url: str) -> None:
        self._rest(
            "DELETE",
            "plant_link_usage",
            params={"email": f"eq.{normalize_email(email)}", "url": f"eq.{url}"},
        )
