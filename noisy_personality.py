#!/usr/bin/env python3
"""
Noisy Personality v5.0 - Moflin-inspirierte Adaptive Emotional Intelligence
Vier Achsen die sich ueber Tage/Wochen durch Audio-Erfahrung entwickeln.

Differenzierte Updates fuer alle 35 Moods:
  energy    - Hohe Energie bei Rock, Party; niedrig bei Sleep, Chill
  cheerful  - Steigt bei Lachen, Musik; sinkt bei Angst, Trauer
  shy       - Steigt bei Schreck; sinkt bei sozialer Interaktion
  affection - Steigt bei Interaktion; sinkt bei Vernachlaessigung
"""

import os
import time
import json
import random
from noisy_config import (
    PERSONALITY_FILE, PERSONALITY_DECAY_RATE,
    GENRE_AFFINITY_GAIN, GENRE_AFFINITY_DECAY,
    GENRE_AFFINITY_THRESHOLD, GENRE_AFFINITY_MAX,
)

# Mood-IDs importieren
from moods.musik import MUSIC, ROCK, JAZZ, HIPHOP, REGGAE, PARTY, CHILL, CLASSIC
from moods.emotionen import LISTEN, LAUGH, SAD, SCARED, EMPATHY, CURIOUS
from moods.koerper import SLEEP, FART, EAT, EXERCISE
from moods.umgebung import WORK, NATURE, WEATHER, TRAFFIC, HOUSE
from moods.idle import BORED


# ============================================================
# Personality-Aenderung pro Mood
# Jeder Mood hat Einfluss auf die 4 Achsen.
# Werte: (energy_delta, cheerful_delta, shy_delta, affection_delta)
# Basisschritt = 0.001, die Werte hier sind Multiplikatoren.
# ============================================================
MOOD_PERSONALITY_EFFECTS = {
    # --- MUSIK ---
    MUSIC:   ( 0.3,  0.8,  0.0,  0.4),  # Leicht positiv
    ROCK:    ( 1.5,  1.0, -0.3,  0.5),  # Sehr energetisch, etwas offener
    JAZZ:    (-0.3,  0.8,  0.0,  0.5),  # Ruhig, freudig
    HIPHOP:  ( 1.2,  0.8, -0.2,  0.5),  # Energetisch
    REGGAE:  (-0.5,  1.0,  0.0,  0.5),  # Entspannt, freudig
    PARTY:   ( 1.5,  1.5, -0.5,  0.8),  # Maximal energetisch, sehr freudig, offen
    CHILL:   (-0.5,  0.5,  0.0,  0.3),  # Entspannt
    CLASSIC: (-0.2,  0.5,  0.0,  0.3),  # Ruhig, kultiviert

    # --- EMOTIONEN ---
    LISTEN:  ( 0.0,  0.0, -0.3,  0.3),  # Sozial -> weniger scheu, mehr Bindung
    LAUGH:   ( 0.8,  1.5, -0.5,  1.0),  # Sehr freudig, sehr offen, starke Bindung
    SAD:     (-0.5, -0.8,  0.3,  0.5),  # Traurig, zurueckgezogen aber mitfuehlend
    SCARED:  ( 0.5, -1.0,  1.0, -0.2),  # Erschrocken -> scheuer, weniger freudig
    EMPATHY: ( 0.0,  0.5, -0.2,  0.8),  # Mitgefuehl -> freudig (hilft!), starke Bindung
    CURIOUS: ( 0.5,  0.3, -0.8,  0.3),  # Neugier -> weniger scheu, etwas energetischer

    # --- KOERPER ---
    SLEEP:   (-0.8,  0.0,  0.0, -0.3),  # Energie sinkt, leichte Vernachlaessigung
    FART:    ( 0.3,  0.5, -0.2,  0.2),  # Lustig, leicht offen
    EAT:     ( 0.2,  0.3,  0.0,  0.2),  # Zufrieden
    EXERCISE:( 1.0,  0.3, -0.2,  0.2),  # Energetisch

    # --- UMGEBUNG ---
    WORK:    ( 0.5,  0.2,  0.0,  0.3),  # Produktiv, leichte Bindung
    NATURE:  (-0.3,  0.5,  0.0,  0.3),  # Entspannt, freudig
    WEATHER: (-0.2,  0.2,  0.0,  0.1),  # Leicht beruhigend
    TRAFFIC: ( 0.0, -0.2,  0.2,  0.0),  # Leicht stressig
    HOUSE:   ( 0.0,  0.1,  0.0,  0.1),  # Neutral, leicht positiv

    # --- IDLE ---
    BORED:   (-0.5, -0.3,  0.2, -0.5),  # Gelangweilt -> Energie sinkt, Vernachlaessigung
}
# Idle-Animations (alle gleich: leicht negativ weil allein)
# Werden nicht einzeln gemappt, da sie alle Unterformen von BORED sind


class NoisyPersonality:
    """
    Adaptive Emotional Intelligence nach Moflin-Vorbild.
    Vier Achsen (0.0-1.0):
      energy    - Wie aktiv/bewegt reagiert Noisy
      cheerful  - Wie freudig/positiv ist die Grundstimmung
      shy       - Wie zurueckhaltend bei neuen Sounds
      affection - Wie stark die Bindung an regelmaessige Interaktion
    """

    def __init__(self, filepath=None, logger=None):
        self.filepath = filepath or PERSONALITY_FILE
        self.log = logger
        self.birth_time = time.time()
        self.total_interactions = 0
        self.energy = 0.5
        self.cheerful = 0.5
        self.shy = 0.5
        self.affection = 0.5
        self.noisy_id = random.randint(0, 65535)
        self.mood_history = {}
        self.genre_affinity = {}   # {mood_id_str: 0.0-1.0}
        self.load()

    def _log(self, msg, level='info'):
        if self.log:
            getattr(self.log, level)(msg)

    def load(self):
        try:
            if os.path.exists(self.filepath):
                with open(self.filepath, 'r') as f:
                    data = json.load(f)
                self.birth_time = data.get('birth_time', self.birth_time)
                self.noisy_id = data.get('noisy_id', self.noisy_id)
                self.total_interactions = data.get('total_interactions', 0)
                self.energy = data.get('energy', 0.5)
                self.cheerful = data.get('cheerful', 0.5)
                self.shy = data.get('shy', 0.5)
                self.affection = data.get('affection', 0.5)
                self.mood_history = data.get('mood_history', {})
                self.genre_affinity = data.get('genre_affinity', {})
                self._log("Persoenlichkeit geladen: Tag %.1f, %d Interaktionen" %
                          (self.get_age_days(), self.total_interactions))
                self._log("  E=%.2f C=%.2f S=%.2f A=%.2f" %
                          (self.energy, self.cheerful, self.shy, self.affection))
        except Exception as e:
            self._log("Persoenlichkeit laden fehlgeschlagen: %s" % e, 'warning')

    def save(self):
        try:
            data = {
                'birth_time': self.birth_time,
                'noisy_id': self.noisy_id,
                'total_interactions': self.total_interactions,
                'energy': round(self.energy, 4),
                'cheerful': round(self.cheerful, 4),
                'shy': round(self.shy, 4),
                'affection': round(self.affection, 4),
                'mood_history': self.mood_history,
                'genre_affinity': {k: round(v, 4) for k, v in self.genre_affinity.items()},
                'last_save': time.time(),
            }
            with open(self.filepath, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            self._log("Persoenlichkeit speichern fehlgeschlagen: %s" % e, 'warning')

    @staticmethod
    def clamp(v):
        return max(0.0, min(1.0, v))

    def update(self, mood_id, rms=0.0):
        """
        Aktualisiere Persoenlichkeit basierend auf aktuellem Mood.
        Differenzierte Reaktionen pro Mood ueber MOOD_PERSONALITY_EFFECTS.
        """
        self.total_interactions += 1
        mood_str = str(mood_id)
        self.mood_history[mood_str] = self.mood_history.get(mood_str, 0) + 1

        step = 0.001

        # Effekte fuer diesen Mood holen (oder BORED als Fallback fuer Idle)
        effects = MOOD_PERSONALITY_EFFECTS.get(mood_id)
        if effects is None:
            # Unbekannter Mood (z.B. Idle-Animations) -> BORED-Effekte
            effects = MOOD_PERSONALITY_EFFECTS.get(BORED, (0, 0, 0, 0))

        e_delta, c_delta, s_delta, a_delta = effects

        self.energy = self.clamp(self.energy + step * e_delta)
        self.cheerful = self.clamp(self.cheerful + step * c_delta)
        self.shy = self.clamp(self.shy + step * s_delta)
        self.affection = self.clamp(self.affection + step * a_delta)

        # RMS-Bonus: Laute Umgebung macht energetischer
        if rms > 0.5:
            self.energy = self.clamp(self.energy + step * 0.3)

        # Decay zum Neutral (langsam)
        for attr in ['energy', 'cheerful', 'shy', 'affection']:
            val = getattr(self, attr)
            if val > 0.5:
                setattr(self, attr, self.clamp(val - PERSONALITY_DECAY_RATE))
            elif val < 0.5:
                setattr(self, attr, self.clamp(val + PERSONALITY_DECAY_RATE))

    def get_age_days(self):
        return (time.time() - self.birth_time) / 86400

    def get_dominant_trait(self):
        traits = {'energy': self.energy, 'cheerful': self.cheerful,
                  'shy': self.shy, 'affection': self.affection}
        return max(traits, key=traits.get)

    def get_dict(self):
        return {
            'energy': self.energy,
            'cheerful': self.cheerful,
            'shy': self.shy,
            'affection': self.affection,
        }

    # ----------------------------------------------------------
    # Genre Affinity (Langzeitgedaechtnis fuer Musikgenres)
    # ----------------------------------------------------------
    MUSIC_MOODS = {MUSIC, ROCK, JAZZ, HIPHOP, REGGAE, PARTY, CHILL, CLASSIC}

    def update_genre_affinity(self, mood_id):
        """
        Erhoeht Affinitaet fuer aktives Musik-Genre.
        Wird pro Audio-Zyklus aufgerufen wenn Musik laeuft.
        """
        if mood_id not in self.MUSIC_MOODS:
            return
        key = str(mood_id)
        current = self.genre_affinity.get(key, 0.0)
        self.genre_affinity[key] = min(GENRE_AFFINITY_MAX,
                                        current + GENRE_AFFINITY_GAIN)

    def decay_genre_affinity(self):
        """Langsamer Verfall aller Genre-Affinitaeten (pro Zyklus)."""
        dead = []
        for key in self.genre_affinity:
            self.genre_affinity[key] = max(0.0,
                                            self.genre_affinity[key] - GENRE_AFFINITY_DECAY)
            if self.genre_affinity[key] <= 0.0:
                dead.append(key)
        for key in dead:
            del self.genre_affinity[key]

    def is_favorite_genre(self, mood_id):
        """True wenn dieses Genre ueber dem Lieblings-Schwellenwert liegt."""
        return self.genre_affinity.get(str(mood_id), 0.0) >= GENRE_AFFINITY_THRESHOLD

    def get_genre_affinity(self, mood_id):
        """Gibt Affinitaets-Score fuer ein Genre zurueck (0.0-1.0)."""
        return self.genre_affinity.get(str(mood_id), 0.0)

    def get_favorite_genres(self):
        """Gibt sortierte Liste von (mood_id, score) fuer alle Favoriten zurueck."""
        favs = [(int(k), v) for k, v in self.genre_affinity.items()
                if v >= GENRE_AFFINITY_THRESHOLD]
        return sorted(favs, key=lambda x: -x[1])
