from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata

_TOKEN = re.compile(r"\w+", re.UNICODE)


def normalize_text(text: str) -> str:
    return " ".join(unicodedata.normalize("NFC", text).split())


def content_hash(payload: object) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class HashingEmbedder:
    """Deterministic test encoder; it is not a production semantic model."""

    dimensions = 64

    def embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for token in _TOKEN.findall(normalize_text(text).lower()):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:2], "big") % self.dimensions
            vector[index] += 1.0 if digest[2] % 2 == 0 else -1.0
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]

