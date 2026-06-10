#!/usr/bin/env python3
"""
Noisy Moods: Musik-Gruppe v5.0
Alle Musik-Genres mit Labels, Fingerprints und Render-Overrides.

Ignorierte Labels: Music, Musical instrument, Song, Background music etc.
werden hier explizit registriert damit sie keinen generischen Mood ausloesen.
"""

from moods import register_group, register_ignored_labels

# ============================================================
# Mood-IDs (Musik-Gruppe: 10-19)
# ============================================================
MUSIC    = 10
ROCK     = 11
JAZZ     = 12
HIPHOP   = 13
REGGAE   = 14
PARTY    = 15
CHILL    = 16
CLASSIC  = 17

# ============================================================
# Ignorierte Musik-Labels (zu generisch, dominieren alles)
# ============================================================
IGNORED_MUSIC_LABELS = [
    "Music",
    "Musical instrument",
    "Song",
    "Background music",
    "Theme music",
    "Jingle (music)",
    "Soundtrack music",
    "Pop music",
    "Vocal music",
    "A capella",
    "Independent music",
    "Traditional music",
    "Music of Africa",
    "Music of Asia",
    "Music of Latin America",
    "Music of Bollywood",
    "Christian music",
    "Gospel music",
    "Carnatic music",
    "Video game music",
    "Christmas music",
    "Wedding music",
    "New-age music",
    "Lullaby",
    "Music for children",
]

# ============================================================
# Mood-Definitionen
# ============================================================
MUSIK_MOODS = [
    # ----------------------------------------------------------
    # MUSIC (generisch - Fallback wenn kein Genre erkannt)
    # ----------------------------------------------------------
    {
        "id": MUSIC,
        "name": "MUSIC",
        "group": "musik",
        "priority": 50,
        "fast_track": False,
        "labels": {
            "Singing": MUSIC,
            "Male singing": MUSIC,
            "Female singing": MUSIC,
            "Child singing": MUSIC,
            "Synthetic singing": MUSIC,
            "Choir": MUSIC,
            "Yodeling": MUSIC,
            "Humming": MUSIC,
            "Mantra": MUSIC,
            "Chant": MUSIC,
            "Whistling": MUSIC,
            "Plucked string instrument": MUSIC,
            "Keyboard (musical)": MUSIC,
            "Percussion": MUSIC,
            "Drum kit": MUSIC,
            "Orchestra": MUSIC,
            "Brass instrument": MUSIC,
            "Bowed string instrument": MUSIC,
            "String section": MUSIC,
            "Wind instrument, woodwind instrument": MUSIC,
            "Flute": MUSIC,
            "Harp": MUSIC,
            "Bell": MUSIC,
            "Church bell": MUSIC,
            "Jingle bell": MUSIC,
            "Bicycle bell": MUSIC,
            "Tuning fork": MUSIC,
            "Chime": MUSIC,
            "Wind chime": MUSIC,
            "Change ringing (campanology)": MUSIC,
            "Harmonica": MUSIC,
            "Accordion": MUSIC,
            "Bagpipes": MUSIC,
            "Didgeridoo": MUSIC,
            "Shofar": MUSIC,
            "Theremin": MUSIC,
            "Singing bowl": MUSIC,
            "Guitar": MUSIC,
            "Acoustic guitar": MUSIC,
            "Banjo": MUSIC,
            "Sitar": MUSIC,
            "Mandolin": MUSIC,
            "Zither": MUSIC,
            "Ukulele": MUSIC,
            "Piano": MUSIC,
            "Organ": MUSIC,
            "Electronic organ": MUSIC,
            "Harpsichord": MUSIC,
            "Drum": MUSIC,
            "Snare drum": MUSIC,
            "Rimshot": MUSIC,
            "Drum roll": MUSIC,
            "Bass drum": MUSIC,
            "Timpani": MUSIC,
            "Tabla": MUSIC,
            "Cymbal": MUSIC,
            "Hi-hat": MUSIC,
            "Wood block": MUSIC,
            "Tambourine": MUSIC,
            "Rattle (instrument)": MUSIC,
            "Maraca": MUSIC,
            "Gong": MUSIC,
            "Tubular bells": MUSIC,
            "Mallet percussion": MUSIC,
            "Marimba, xylophone": MUSIC,
            "Glockenspiel": MUSIC,
            "Vibraphone": MUSIC,
            "French horn": MUSIC,
            "Trombone": MUSIC,
            "Violin, fiddle": MUSIC,
            "Pizzicato": MUSIC,
            "Cello": MUSIC,
            "Double bass": MUSIC,
            "Radio": MUSIC,
            "Television": MUSIC,
        },
        "body": {
            "color": (30, 180, 220),
            "glow": (15, 90, 110),
        },
        "accessory": {"type": "headphones"},
        "particles": {"type": "note", "rate": 0.20},
    },

    # ----------------------------------------------------------
    # ROCK
    # ----------------------------------------------------------
    {
        "id": ROCK,
        "name": "ROCK",
        "group": "musik",
        "priority": 90,
        "fast_track": False,
        "labels": {
            "Rock music": ROCK,
            "Rock and roll": ROCK,
            "Heavy metal": ROCK,
            "Punk rock": ROCK,
            "Grunge": ROCK,
            "Progressive rock": ROCK,
            "Psychedelic rock": ROCK,
            "Electric guitar": ROCK,
            "Bass guitar": ROCK,
            "Steel guitar, slide guitar": ROCK,
            "Tapping (guitar technique)": ROCK,
            "Distortion": ROCK,
            "Power tool": ROCK,
            "Strum": ROCK,
            "Angry music": ROCK,
        },
        "fingerprint": {
            "hints": [
                "Electric guitar", "Distortion", "Drum kit", "Snare drum",
                "Cymbal", "Bass guitar", "Strum", "Power tool", "Guitar",
                "Tapping (guitar technique)", "Bass drum", "Hi-hat",
                "Heavy metal", "Punk rock", "Grunge",
            ],
            "boost": 2.0,
            "min_hints": 1,
        },
        "body": {
            "color": (255, 30, 30),
            "glow": (180, 15, 15),
        },
        "physics": {
            "headbang_speed": 0.85,
            "headbang_amp": 26,
        },
        "hair": {"wobble": True},
        "accessory": {"type": "headphones"},
        "particles": {"type": "note", "rate": 0.30, "color": (255, 100, 50)},
    },

    # ----------------------------------------------------------
    # JAZZ
    # ----------------------------------------------------------
    {
        "id": JAZZ,
        "name": "JAZZ",
        "group": "musik",
        "priority": 80,
        "fast_track": False,
        "labels": {
            "Jazz": JAZZ,
            "Swing music": JAZZ,
            "Blues": JAZZ,
            "Bluegrass": JAZZ,
            "Soul music": JAZZ,
            "Rhythm and blues": JAZZ,
            "Saxophone": JAZZ,
            "Trumpet": JAZZ,
            "Clarinet": JAZZ,
            "Hammond organ": JAZZ,
            "Electric piano": JAZZ,
        },
        "fingerprint": {
            "hints": [
                "Saxophone", "Trumpet", "Piano", "Double bass",
                "Trombone", "Clarinet", "Vibraphone", "Hammond organ",
                "Electric piano", "Swing music", "Blues",
            ],
            "boost": 2.0,
            "min_hints": 1,
        },
        "body": {
            "color": (180, 120, 255),
            "glow": (90, 60, 180),
        },
        "physics": {
            "sway_speed": 0.12,
            "sway_amp": 16,
        },
        "accessory": {"type": "headphones"},
        "particles": {"type": "note", "rate": 0.20, "color": (180, 130, 255)},
    },

    # ----------------------------------------------------------
    # HIPHOP
    # ----------------------------------------------------------
    {
        "id": HIPHOP,
        "name": "HIPHOP",
        "group": "musik",
        "priority": 85,
        "fast_track": False,
        "labels": {
            "Hip hop music": HIPHOP,
            "Rapping": HIPHOP,
            "Beatboxing": HIPHOP,
            "Scratching (performance technique)": HIPHOP,
            "Drum machine": HIPHOP,
            "Sampler": HIPHOP,
            "Funk": HIPHOP,
        },
        "fingerprint": {
            "hints": [
                "Rapping", "Beatboxing", "Drum machine",
                "Sampler", "Scratching (performance technique)",
                "Hip hop music", "Synthesizer",
            ],
            "boost": 2.0,
            "min_hints": 1,
        },
        "body": {
            "color": (255, 200, 0),
            "glow": (180, 140, 0),
        },
        "physics": {
            "bounce_speed": 0.55,
            "bounce_amp": 32,
        },
        "accessory": {"type": "gold_chain"},
        "particles": {"type": "note", "rate": 0.25, "color": (255, 215, 0)},
    },

    # ----------------------------------------------------------
    # REGGAE
    # ----------------------------------------------------------
    {
        "id": REGGAE,
        "name": "REGGAE",
        "group": "musik",
        "priority": 80,
        "fast_track": False,
        "labels": {
            "Reggae": REGGAE,
            "Ska": REGGAE,
            "Steelpan": REGGAE,
            "Afrobeat": REGGAE,
        },
        "fingerprint": {
            "hints": [
                "Bass guitar", "Guitar", "Drum", "Ska",
                "Reggae", "Steelpan", "Percussion",
            ],
            "boost": 2.0,
            "min_hints": 1,
        },
        "body": {
            "color": (0, 200, 80),
            "glow": (0, 120, 40),
        },
        "physics": {
            "sway_speed": 0.22,
            "sway_amp": 9,
            "bounce_speed": 0.18,
            "bounce_amp": 6,
        },
        "accessory": {"type": "rasta_hat"},
        "particles": {"type": "note", "rate": 0.20, "color": (0, 220, 100)},
    },

    # ----------------------------------------------------------
    # PARTY (Elektronisch, Dance, Disco)
    # ----------------------------------------------------------
    {
        "id": PARTY,
        "name": "PARTY",
        "group": "musik",
        "priority": 85,
        "fast_track": False,
        "labels": {
            "Disco": PARTY,
            "House music": PARTY,
            "Techno": PARTY,
            "Electronic dance music": PARTY,
            "Trance music": PARTY,
            "Dance music": PARTY,
            "Salsa music": PARTY,
            "Drum and bass": PARTY,
            "Dubstep": PARTY,
            "Electronic music": PARTY,
            "Electronica": PARTY,
            "Flamenco": PARTY,
            "Synthesizer": PARTY,
            "Exciting music": PARTY,
            "Happy music": PARTY,
            "Funny music": PARTY,
            "Cheering": PARTY,
            "Applause": PARTY,
            "Children playing": PARTY,
            "Crowd": PARTY,
        },
        "fingerprint": {
            "hints": [
                "Disco", "House music", "Techno", "Electronic dance music",
                "Trance music", "Dance music", "Salsa music",
                "Synthesizer", "Drum machine", "Cheering", "Crowd",
            ],
            "boost": 1.5,
            "min_hints": 1,
        },
        "body": {
            "color": (255, 0, 180),
            "glow": (180, 0, 120),
        },
        "physics": {
            "bounce_speed": 0.8,
            "bounce_amp": 22,
            "sway_speed": 0.6,
            "sway_amp": 12,
        },
        "accessory": {"type": "headphones"},
        "particles": {"type": "star", "rate": 0.30, "color": (255, 100, 255)},
    },

    # ----------------------------------------------------------
    # CHILL (Ambient, Natur-Musik, ruhige Musik)
    # ----------------------------------------------------------
    {
        "id": CHILL,
        "name": "CHILL",
        "group": "musik",
        "priority": 40,
        "fast_track": False,
        "labels": {
            "Ambient music": CHILL,
            "Tender music": CHILL,
            "Sad music": CHILL,
            "Folk music": CHILL,
            "Country": CHILL,
            "Middle Eastern music": CHILL,
        },
        "body": {
            "color": (60, 140, 180),
            "glow": (30, 70, 90),
        },
        "physics": {
            "sway_speed": 0.04,
            "sway_amp": 3,
        },
        "accessory": {"type": "headphones"},
        "particles": {"type": "note", "rate": 0.08, "color": (100, 180, 220)},
    },

    # ----------------------------------------------------------
    # CLASSIC (Klassische Musik, Opera)
    # ----------------------------------------------------------
    {
        "id": CLASSIC,
        "name": "CLASSIC",
        "group": "musik",
        "priority": 60,
        "fast_track": False,
        "labels": {
            "Classical music": CLASSIC,
            "Opera": CLASSIC,
            "Scary music": CLASSIC,
        },
        "body": {
            "color": (220, 200, 255),
            "glow": (120, 100, 180),
        },
        "physics": {
            "sway_speed": 0.08,
            "sway_amp": 6,
        },
        "accessory": {"type": "headphones"},
        "particles": {"type": "note", "rate": 0.12, "color": (200, 180, 255)},
    },
]

# ============================================================
# Registrierung
# ============================================================
register_ignored_labels(IGNORED_MUSIC_LABELS)
register_group(MUSIK_MOODS)
