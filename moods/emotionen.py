#!/usr/bin/env python3
"""
Noisy Moods: Emotionen-Gruppe v5.0
Menschliche Emotionen und Reaktionen auf emotionale Sounds.
Fast-Track fuer Impulse (SCARED, LAUGH).
"""

from moods import register_group

# ============================================================
# Mood-IDs (Emotionen-Gruppe: 20-29)
# ============================================================
LISTEN   = 20
LAUGH    = 21
SAD      = 22
SCARED   = 23
EMPATHY  = 24
CURIOUS  = 25

# ============================================================
# Mood-Definitionen
# ============================================================
EMOTIONEN_MOODS = [
    # ----------------------------------------------------------
    # LISTEN (Default-Mood: Noisy hoert aufmerksam zu)
    # ----------------------------------------------------------
    {
        "id": LISTEN,
        "name": "LISTEN",
        "group": "emotionen",
        "priority": 30,
        "fast_track": False,
        "labels": {
            "Hands": LISTEN,
            "Finger snapping": LISTEN,
            "Clapping": LISTEN,
            "Heart sounds, heartbeat": LISTEN,
            "Heart murmur": LISTEN,
            "Animal": LISTEN,
            "Domestic animals, pets": LISTEN,
            "Dog": LISTEN,
            "Bark": LISTEN,
            "Yip": LISTEN,
            "Bow-wow": LISTEN,
            "Cat": LISTEN,
            "Meow": LISTEN,
            "Livestock, farm animals, working animals": LISTEN,
            "Horse": LISTEN,
            "Clip-clop": LISTEN,
            "Neigh, whinny": LISTEN,
            "Cattle, bovinae": LISTEN,
            "Moo": LISTEN,
            "Cowbell": LISTEN,
            "Pig": LISTEN,
            "Goat": LISTEN,
            "Bleat": LISTEN,
            "Sheep": LISTEN,
            "Fowl": LISTEN,
            "Chicken, rooster": LISTEN,
            "Cluck": LISTEN,
            "Crowing, cock-a-doodle-doo": LISTEN,
            "Turkey": LISTEN,
            "Gobble": LISTEN,
            "Duck": LISTEN,
            "Quack": LISTEN,
            "Goose": LISTEN,
            "Honk": LISTEN,
            "Wild animals": LISTEN,
            "Bird": LISTEN,
            "Bird vocalization, bird call, bird song": LISTEN,
            "Chirp, tweet": LISTEN,
            "Squawk": LISTEN,
            "Pigeon, dove": LISTEN,
            "Coo": LISTEN,
            "Crow": LISTEN,
            "Caw": LISTEN,
            "Owl": LISTEN,
            "Hoot": LISTEN,
            "Bird flight, flapping wings": LISTEN,
            "Canidae, dogs, wolves": LISTEN,
            "Rodents, rats, mice": LISTEN,
            "Mouse": LISTEN,
            "Patter": LISTEN,
            "Insect": LISTEN,
            "Cricket": LISTEN,
            "Mosquito": LISTEN,
            "Fly, housefly": LISTEN,
            "Buzz": LISTEN,
            "Bee, wasp, etc.": LISTEN,
            "Frog": LISTEN,
            "Croak": LISTEN,
            "Snake": LISTEN,
            "Whale vocalization": LISTEN,
            "Door": LISTEN,
            "Doorbell": LISTEN,
            "Ding-dong": LISTEN,
            "Sliding door": LISTEN,
            "Knock": LISTEN,
            "Tap": LISTEN,
            "Squeak": LISTEN,
            "Telephone": LISTEN,
            "Telephone bell ringing": LISTEN,
            "Ringtone": LISTEN,
            "Telephone dialing, DTMF": LISTEN,
            "Dial tone": LISTEN,
            "Busy signal": LISTEN,
            "Keys jangling": LISTEN,
            "Coin (dropping)": LISTEN,
            "Scissors": LISTEN,
            "Zipper (clothing)": LISTEN,
            "Camera": LISTEN,
            "Single-lens reflex camera": LISTEN,
            "Printer": LISTEN,
            "Vehicle horn, car horn, honking": LISTEN,
            "Toot": LISTEN,
            "Bicycle bell": LISTEN,
            "Bicycle": LISTEN,
            "Skateboard": LISTEN,
            "Train whistle": LISTEN,
            "Train horn": LISTEN,
            "Boat, Water vehicle": LISTEN,
            "Ship": LISTEN,
            "Motorboat, speedboat": LISTEN,
            "Sailboat, sailing ship": LISTEN,
            "Ice cream truck, ice cream van": LISTEN,
            "Whistle": LISTEN,
        },
        "body": {
            "color": (30, 180, 220),
            "glow": (15, 90, 110),
        },
        "mouth": {"style": "smile"},
    },

    # ----------------------------------------------------------
    # LAUGH (Fast-Track! Sofort reagieren)
    # ----------------------------------------------------------
    {
        "id": LAUGH,
        "name": "LAUGH",
        "group": "emotionen",
        "priority": 85,
        "fast_track": True,
        "labels": {
            "Laughter": LAUGH,
            "Baby laughter": LAUGH,
            "Giggle": LAUGH,
            "Snicker": LAUGH,
            "Belly laugh": LAUGH,
            "Chuckle, chortle": LAUGH,
        },
        "body": {
            "color": (255, 220, 0),
            "glow": (180, 160, 0),
        },
        "eyes": {"scale_h": 0.5},
        "mouth": {"style": "grin", "width": 1.3},
        "physics": {
            "bounce_speed": 0.6,
            "bounce_amp": 8,
        },
        "particles": {"type": "star", "rate": 0.20, "color": (255, 255, 100)},
    },

    # ----------------------------------------------------------
    # SAD (Mitgefuehl)
    # ----------------------------------------------------------
    {
        "id": SAD,
        "name": "SAD",
        "group": "emotionen",
        "priority": 70,
        "fast_track": False,
        "labels": {
            "Crying, sobbing": SAD,
            "Baby cry, infant cry": SAD,
            "Whimper": SAD,
            "Wail, moan": SAD,
            "Sigh": SAD,
            "Howl": SAD,
            "Whimper (dog)": SAD,
        },
        "body": {
            "color": (80, 80, 200),
            "glow": (40, 40, 120),
        },
        "eyes": {"scale_h": 0.8, "look_offset": -3},
        "mouth": {"style": "frown"},
        "particles": {"type": "heart", "rate": 0.08, "color": (100, 200, 255)},
    },

    # ----------------------------------------------------------
    # SCARED (Fast-Track! Sofort reagieren bei Knall/Schrei)
    # ----------------------------------------------------------
    {
        "id": SCARED,
        "name": "SCARED",
        "group": "emotionen",
        "priority": 100,
        "fast_track": True,
        "labels": {
            "Shout": SCARED,
            "Bellow": SCARED,
            "Whoop": SCARED,
            "Yell": SCARED,
            "Battle cry": SCARED,
            "Children shouting": SCARED,
            "Screaming": SCARED,
            "Growling": SCARED,
            "Roaring cats (lions, tigers)": SCARED,
            "Roar": SCARED,
            "Hiss": SCARED,
            "Caterwaul": SCARED,
            "Thunder": SCARED,
            "Thunderstorm": SCARED,
            "Fire": SCARED,
            "Explosion": SCARED,
            "Gunshot, gunfire": SCARED,
            "Machine gun": SCARED,
            "Fusillade": SCARED,
            "Artillery fire": SCARED,
            "Cap gun": SCARED,
            "Boom": SCARED,
            "Eruption": SCARED,
            "Slam": SCARED,
            "Smash, crash": SCARED,
            "Breaking": SCARED,
            "Shatter": SCARED,
            "Bang": SCARED,
            "Siren": SCARED,
            "Civil defense siren": SCARED,
            "Fire alarm": SCARED,
            "Smoke detector, smoke alarm": SCARED,
            "Police car (siren)": SCARED,
            "Ambulance (siren)": SCARED,
            "Fire engine, fire truck (siren)": SCARED,
            "Foghorn": SCARED,
            "Alarm": SCARED,
            "Alarm clock": SCARED,
            "Buzzer": SCARED,
            "Fireworks": SCARED,
            "Firecracker": SCARED,
        },
        "body": {
            "color": (255, 0, 0),
            "glow": (200, 0, 0),
        },
        "eyes": {"scale_w": 1.6, "scale_h": 1.7},
        "mouth": {"style": "open_round"},
        "physics": {
            "shake_x": 8,
            "shake_y": 6,
        },
        "particles": {"type": "exclamation", "rate": 0.35, "color": (255, 255, 0)},
    },

    # ----------------------------------------------------------
    # EMPATHY (Husten, Niesen -> Mitgefuehl/Gesundheit)
    # ----------------------------------------------------------
    {
        "id": EMPATHY,
        "name": "EMPATHY",
        "group": "emotionen",
        "priority": 75,
        "fast_track": True,
        "labels": {
            "Cough": EMPATHY,
            "Sneeze": EMPATHY,
            "Throat clearing": EMPATHY,
            "Wheeze": EMPATHY,
            "Gasp": EMPATHY,
            "Sniff": EMPATHY,
        },
        "body": {
            "color": (100, 200, 150),
            "glow": (50, 120, 80),
        },
        "eyes": {"scale_w": 1.2, "scale_h": 1.1},
        "mouth": {"style": "concerned"},
        "particles": {"type": "heart", "rate": 0.15, "color": (255, 150, 150)},
    },

    # ----------------------------------------------------------
    # CURIOUS (unbekannte/neue Geraeusche)
    # ----------------------------------------------------------
    {
        "id": CURIOUS,
        "name": "CURIOUS",
        "group": "emotionen",
        "priority": 45,
        "fast_track": False,
        "labels": {
            "Rattle": CURIOUS,
            "Creak": CURIOUS,
            "Rustle": CURIOUS,
            "Scratch": CURIOUS,
            "Scrape": CURIOUS,
            "Clicking": CURIOUS,
            "Clickety-clack": CURIOUS,
            "Rumble": CURIOUS,
            "Jingle, tinkle": CURIOUS,
            "Zing": CURIOUS,
            "Boing": CURIOUS,
            "Crunch": CURIOUS,
            "Squeal": CURIOUS,
            "Whir": CURIOUS,
            "Clatter": CURIOUS,
            "Plop": CURIOUS,
            "Ping": CURIOUS,
            "Ding": CURIOUS,
            "Clang": CURIOUS,
            "Beep, bleep": CURIOUS,
            "Burst, pop": CURIOUS,
            "Splash, splatter": CURIOUS,
            "Drip": CURIOUS,
            "Whoosh, swoosh, swish": CURIOUS,
            "Thump, thud": CURIOUS,
            "Thunk": CURIOUS,
            "Bounce": CURIOUS,
            "Roll": CURIOUS,
        },
        "body": {
            "color": (200, 180, 50),
            "glow": (120, 100, 25),
        },
        "eyes": {"scale_w": 1.3, "scale_h": 1.2, "look_offset": 8},
        "mouth": {"style": "neutral"},
    },
]

# ============================================================
# Registrierung
# ============================================================
register_group(EMOTIONEN_MOODS)
