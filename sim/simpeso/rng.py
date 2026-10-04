"""Seeded dice. derive(seed, *keys) gives an independent stream per key path, so adding a feature
(a new key) never shifts the numbers another feature already draws."""
import hashlib
import random


def derive(seed: int, *keys) -> random.Random:
    material = "|".join([str(int(seed))] + [str(k) for k in keys]).encode("utf-8")
    digest = hashlib.sha256(material).digest()
    return random.Random(int.from_bytes(digest[:8], "big"))


def stable_hash(obj) -> str:
    """SHA-256 of a canonical JSON rendering, for plan and action-log hashes."""
    import json
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str, separators=(",", ":")).encode("utf-8")).hexdigest()
