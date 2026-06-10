#!/usr/bin/env python3
"""
Noisy Moods Base v5.0 - Mood-Registry & Default-Komponenten

Jeder Mood ist ein Dict mit Overrides. Der Renderer baut den Avatar
aus DEFAULT-Komponenten und wendet nur die Abweichungen an.

Mood-Gruppen registrieren sich hier ueber register_group().
"""

# ============================================================
# Farb-Konstanten
# ============================================================
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
GOLD = (255, 215, 0)
EYE_COLOR = (20, 20, 35)

# ============================================================
# Default-Komponenten (wenn Mood nichts anderes sagt)
# ============================================================
DEFAULT_BODY = {
    "color": (30, 180, 220),         # Noisy-Blau
    "glow": (15, 90, 110),
}

DEFAULT_EYES = {
    "scale_w": 1.0,
    "scale_h": 1.0,
    "look_offset": 0,
    "droopy": False,
}

DEFAULT_MOUTH = {
    "style": "smile",                # smile, open_round, frown, line, grin, neutral
    "width": 1.0,
}

DEFAULT_HAIR = {
    "visible": True,
    "wobble": False,                 # Traegheits-Nachwipp bei Musik
    "color": (139, 90, 43),
    "color_dark": (110, 70, 30),
    "color_light": (165, 110, 55),
}

DEFAULT_PHYSICS = {
    "headbang_speed": 0,             # 0 = kein Headbang
    "headbang_amp": 0,
    "bounce_speed": 0,
    "bounce_amp": 0,
    "sway_speed": 0.05,
    "sway_amp": 2.2,
    "shake_x": 0,
    "shake_y": 0,
}

DEFAULT_PARTICLES = {
    "type": None,                    # None, "note", "zzz", "exclamation", "heart", "sweat", "star"
    "rate": 0,
    "color": None,                   # None = Mood-Farbe verwenden
}

DEFAULT_ACCESSORY = {
    "type": None,                    # None, "headphones", "rasta_hat", "gold_chain", "keyboard"
}

# ============================================================
# Mood-Datenstruktur
# ============================================================
# Jeder Mood ist ein Dict mit diesen Keys (alle optional ausser id/name):
#   id:          int (eindeutig)
#   name:        str (Display-Name)
#   group:       str (Gruppenname)
#   priority:    int (0-100, hoeher = wichtiger)
#   fast_track:  bool (ueberspringt Accumulator wenn True)
#   labels:      dict (AudioSet Label -> diesen Mood)
#   fingerprint: dict (hints, boost, min_hints) fuer Genre-Erkennung
#   body:        dict (Overrides fuer DEFAULT_BODY)
#   eyes:        dict (Overrides fuer DEFAULT_EYES)
#   mouth:       dict (Overrides fuer DEFAULT_MOUTH)
#   hair:        dict (Overrides fuer DEFAULT_HAIR)
#   physics:     dict (Overrides fuer DEFAULT_PHYSICS)
#   particles:   dict (Overrides fuer DEFAULT_PARTICLES)
#   accessory:   dict (Overrides fuer DEFAULT_ACCESSORY)

# ============================================================
# Registry
# ============================================================
_MOOD_REGISTRY = {}        # id -> mood_dict
_LABEL_MAP = {}            # AudioSet label -> mood_id
_MOOD_NAMES = {}           # id -> name
_GROUP_MOODS = {}          # group_name -> [mood_ids]
_IGNORE_LABELS = set()     # Labels die komplett ignoriert werden


def register_mood(mood):
    """Registriert einen einzelnen Mood in der globalen Registry."""
    mid = mood["id"]
    name = mood["name"]

    if mid in _MOOD_REGISTRY:
        raise ValueError("Mood ID %d bereits registriert: %s" % (mid, _MOOD_REGISTRY[mid]["name"]))

    _MOOD_REGISTRY[mid] = mood
    _MOOD_NAMES[mid] = name

    group = mood.get("group", "unknown")
    if group not in _GROUP_MOODS:
        _GROUP_MOODS[group] = []
    _GROUP_MOODS[group].append(mid)

    # Labels mappen
    for label, target in mood.get("labels", {}).items():
        if target is None:
            _IGNORE_LABELS.add(label)
        else:
            _LABEL_MAP[label] = mid


def register_group(moods):
    """Registriert eine Liste von Moods (ganze Gruppe)."""
    for mood in moods:
        register_mood(mood)


def register_ignored_labels(labels):
    """Registriert Labels die komplett ignoriert werden sollen."""
    for label in labels:
        _IGNORE_LABELS.add(label)
        _LABEL_MAP.pop(label, None)


# ============================================================
# Zugriffs-Funktionen
# ============================================================
def get_mood(mood_id):
    """Gibt das komplette Mood-Dict zurueck."""
    return _MOOD_REGISTRY.get(mood_id)


def get_mood_by_label(label):
    """Gibt die Mood-ID fuer ein AudioSet-Label zurueck, oder None."""
    if label in _IGNORE_LABELS:
        return None
    return _LABEL_MAP.get(label)


def get_mood_name(mood_id):
    """Display-Name fuer eine Mood-ID."""
    return _MOOD_NAMES.get(mood_id, "?")


def get_mood_priority(mood_id):
    """Priority-Wert fuer eine Mood-ID."""
    mood = _MOOD_REGISTRY.get(mood_id)
    if mood:
        return mood.get("priority", 30)
    return 30


def is_fast_track(mood_id):
    """Soll dieser Mood den Accumulator ueberspringen?"""
    mood = _MOOD_REGISTRY.get(mood_id)
    if mood:
        return mood.get("fast_track", False)
    return False


def get_all_fingerprints():
    """Gibt alle Genre-Fingerprints zurueck: {mood_id: fingerprint_dict}."""
    fps = {}
    for mid, mood in _MOOD_REGISTRY.items():
        fp = mood.get("fingerprint")
        if fp:
            fps[mid] = fp
    return fps


def get_group_moods(group_name):
    """Gibt alle Mood-IDs einer Gruppe zurueck."""
    return _GROUP_MOODS.get(group_name, [])


def get_all_moods():
    """Gibt die komplette Registry zurueck."""
    return dict(_MOOD_REGISTRY)


def get_all_groups():
    """Gibt alle Gruppen-Namen zurueck."""
    return list(_GROUP_MOODS.keys())


# ============================================================
# Render-Helper: Merged Default + Mood-Overrides
# ============================================================
def get_render_data(mood_id):
    """
    Gibt die kompletten Render-Daten fuer einen Mood zurueck.
    Merged Default-Komponenten mit Mood-Overrides.
    """
    mood = _MOOD_REGISTRY.get(mood_id, {})

    def merge(default, override_key):
        result = dict(default)
        overrides = mood.get(override_key, {})
        result.update(overrides)
        return result

    return {
        "body": merge(DEFAULT_BODY, "body"),
        "eyes": merge(DEFAULT_EYES, "eyes"),
        "mouth": merge(DEFAULT_MOUTH, "mouth"),
        "hair": merge(DEFAULT_HAIR, "hair"),
        "physics": merge(DEFAULT_PHYSICS, "physics"),
        "particles": merge(DEFAULT_PARTICLES, "particles"),
        "accessory": merge(DEFAULT_ACCESSORY, "accessory"),
    }
