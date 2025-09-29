"""
음악 토너먼트 취향 테스트 시스템
설문 → 후보군 압축 → 토너먼트 → 결과 분석/추천
"""

import json
import math
import random
import sys
import webbrowser
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Set, Any
from dataclasses import dataclass, field, asdict
from collections import defaultdict
import numpy as np
from sklearn.cluster import KMeans
from datetime import datetime
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QRadioButton,
    QScrollArea,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

# ============================================================================
# JSON 구조 & 인덱스 가이드
# ============================================================================
# songs.json 은 Song 객체들의 리스트로 구성된다. 새 곡을 추가할 때는 각 항목을
# 채우되, 인덱스를 요구하는 필드는 아래 매핑표를 참고한다.
#
# Song 객체 기본 구조:
# {
#   "id": str,                  # 고유 ID (예: "song_001")
#   "artist": str,              # 아티스트 이름
#   "title": str,               # 곡 제목
#   "youtube_url": str,         # 미리듣기 링크 (선택)
#   "clip": {                   # 미리듣기 구간 정보 (선택)
#       "start_sec": float,     # 시작 위치(초)
#       "preview_sec": float    # 미리듣기 길이(초)
#   },
#   "genres": List[int],        # 기본 장르 코드 (0-base)
#   "tags": {
#       "subgenres": List[int],      # 세부 장르 코드 (0-base)
#       "mood": List[int],           # 무드 코드 (0-base)
#       "energy": float,             # 0.0~1.0 에너지 스코어
#       "valence": float,            # 0.0~1.0 명/암 스코어
#       "tempo_bpm": float,          # BPM
#       "era_year": int,             # 대표 연도
#       "language": int,             # 언어 코드 (0-base)
#       "instrumentation": List[int] # 편성 코드 (0-base)
#   },
#   "popularity": {
#       "awareness_idx": float,      # 0.0~1.0 인지도 지표
#       "yt_views": int,             # 유튜브 조회수
#       "regionality": List[int]     # 인기 지역 코드 (0-base)
#   },
#   "meta": {                        # 추가 메타데이터 (선택)
#       "duration_sec": float,
#       "loudness_lufs": float
#   }
# }
#
# --------------------------------------------------------------------------
# 인덱스 매핑 규칙 (JSON에서는 반드시 0-base 정수 사용)
# --------------------------------------------------------------------------
# Song.genres[*]           → GENRES
# tags.subgenres[*]        → SUBGENRES
# tags.mood[*]             → MOODS
# tags.language            → LANGUAGES
# tags.instrumentation[*]  → INSTRUMENTATIONS
# popularity.regionality[*]→ REGIONALITIES
#
# DataLoader.load_songs()가 로드 시 인덱스를 문자열로 복호화한다.
#
# --------------------------------------------------------------------------
# 주요 코드 매핑 예시
# --------------------------------------------------------------------------
# DataLoader.load_songs()가 로딩 시 위 인덱스들을 문자열/리스트로 복호화하므로 JSON에서는
# 항상 0-base 정수 값만 제공하면 된다.
#
# Song.genres[*] - 기본 장르 코드 (GENRE_CODE_TABLE 기반, 0은 사용 안 함)
# 1: Rock, 2: Pop, 3: Electronic, 4: Hip Hop, 5: Jazz, 6: Classical, 10: Progressive Rock,
# 11: Art Rock, 12: Grunge, 13: Psychedelic Rock, 14: Alternative Rock, 17: Indie Folk,
# 19: Classic Rock, 20: Dance Pop, 21: K-Indie Pop, 22: R&B Pop, 23: Synth Pop,
# 24: Electropop, 26: Alt R&B, 27: Art Pop, 28: Flamenco Pop, 30: French House,
# 32: IDM, 33: Future Bass, 34: Trip Hop, 35: Downtempo, 36: Dance / Electronic,
# 40: Trap, 41: K-Hip Hop, 45: Alternative Hip Hop, 46: Funk Hip Hop, 50: Modal Jazz,
# 51: Jazz Hop, 60: Romantic Classical

# tags.subgenres[*] - 세부 장르 코드 (SUBGENRES)
# 0: alt_pop, 1: alternative_hip_hop, 2: alternative_r&b, 3: alternative_rock, 4: ambient,
# 5: art_pop, 6: blues_rock, 7: chamber_pop, 8: chillhop, 9: contemporary_jazz,
# 10: cool_jazz, 11: dance, 12: dance_pop, 13: disco_pop, 14: downtempo, 15: edm_pop,
# 16: electro_house, 17: electronic, 18: electronica, 19: electropop, 20: experimental,
# 21: experimental_electronic, 22: experimental_pop, 23: flamenco_pop, 24: french_house,
# 25: funk, 26: future_bass, 27: grunge, 28: hard_rock, 29: hip_hop, 30: idm,
# 31: indie_folk, 32: indie_rock, 33: instrumental_hip_hop, 34: jazz_hop, 35: k_indie,
# 36: k_r&b, 37: korean_hip_hop, 38: kpop, 39: lo_fi, 40: modal_jazz, 41: neo_soul,
# 42: opera_rock, 43: piano_solo, 44: pop_ballad, 45: pop_rock, 46: progressive_rock,
# 47: psychedelic_pop, 48: psychedelic_rock, 49: r&b, 50: r&b_pop, 51: rock,
# 52: romantic_classical, 53: soft_rock, 54: synth_pop, 55: synthwave, 56: trap,
# 57: trap_pop, 58: trip_hop, 59: uk_garage, 60: west_coast_hip_hop

# tags.mood[*] - 무드 코드 (MOODS)
# 0: abstract, 1: aggressive, 2: angst, 3: atmospheric, 4: avant_garde, 5: bold,
# 6: bright, 7: building, 8: celebratory, 9: cheerful, 10: complex, 11: confident,
# 12: contemplative, 13: danceable, 14: dark, 15: defiant, 16: dramatic, 17: dreamy,
# 18: driving, 19: dynamic, 20: elegant, 21: emotional, 22: empowering, 23: energetic,
# 24: epic, 25: ethereal, 26: euphoric, 27: fierce, 28: funky, 29: groovy, 30: haunting,
# 31: hopeful, 32: intense, 33: intimate, 34: introspective, 35: ironic, 36: luxurious,
# 37: melancholic, 38: mellow, 39: minimalist, 40: modern, 41: mysterious, 42: mystical,
# 43: nocturnal, 44: nostalgic, 45: passionate, 46: peaceful, 47: playful, 48: powerful,
# 49: raw, 50: rebellious, 51: reflective, 52: relaxed, 53: romantic, 54: satirical,
# 55: seductive, 56: serene, 57: smooth, 58: sophisticated, 59: soulful, 60: surreal,
# 61: trippy, 62: unsettling, 63: upbeat, 64: uplifting, 65: warm, 66: whimsical,
# 67: youthful

# tags.language - 언어 코드 (LANGUAGES)
# 0: en, 1: es, 2: fr, 3: instrumental, 4: ko

# tags.instrumentation[*] - 편성/악기 코드 (INSTRUMENTATIONS)
# 0: 808, 1: bass, 2: drums, 3: electronic_beats, 4: guitar, 5: keyboards, 6: palmas,
# 7: percussion, 8: piano, 9: recorder, 10: samples, 11: saxophone, 12: strings,
# 13: synth, 14: trumpet, 15: vocals, 16: vocoder

# popularity.regionality[*] - 인기 지역 코드 (REGIONALITIES)
# 0: asia, 1: es, 2: eu, 3: fr, 4: global, 5: jp, 6: kr, 7: latam, 8: us

GENRE_CODE_TABLE: Dict[int, str] = {
    1: "Rock",
    2: "Pop",
    3: "Electronic",
    4: "Hip Hop",
    5: "Jazz",
    6: "Classical",
    10: "Progressive Rock",
    11: "Art Rock",
    12: "Grunge",
    13: "Psychedelic Rock",
    14: "Alternative Rock",
    17: "Indie Folk",
    19: "Classic Rock",
    20: "Dance Pop",
    21: "K-Indie Pop",
    22: "R&B Pop",
    23: "Synth Pop",
    24: "Electropop",
    26: "Alt R&B",
    27: "Art Pop",
    28: "Flamenco Pop",
    30: "French House",
    32: "IDM",
    33: "Future Bass",
    34: "Trip Hop",
    35: "Downtempo",
    36: "Dance / Electronic",
    40: "Trap",
    41: "K-Hip Hop",
    45: "Alternative Hip Hop",
    46: "Funk Hip Hop",
    50: "Modal Jazz",
    51: "Jazz Hop",
    60: "Romantic Classical",
}

MAX_GENRE_CODE = max(GENRE_CODE_TABLE)
GENRES: List[str] = ["Unknown"] * (MAX_GENRE_CODE + 1)
for code, name in GENRE_CODE_TABLE.items():
    GENRES[code] = name


def decode_genre_names(codes: List[int]) -> List[str]:
    """Return deduplicated, human-friendly names for the given genre codes."""
    names: List[str] = []
    for code in codes:
        if isinstance(code, int) and 0 <= code < len(GENRES):
            name = GENRES[code]
            if name != "Unknown" and name not in names:
                names.append(name)
    return names


SUBGENRES: List[str] = [
    "alt_pop",
    "alternative_hip_hop",
    "alternative_r&b",
    "alternative_rock",
    "ambient",
    "art_pop",
    "blues_rock",
    "chamber_pop",
    "chillhop",
    "contemporary_jazz",
    "cool_jazz",
    "dance",
    "dance_pop",
    "disco_pop",
    "downtempo",
    "edm_pop",
    "electro_house",
    "electronic",
    "electronica",
    "electropop",
    "experimental",
    "experimental_electronic",
    "experimental_pop",
    "flamenco_pop",
    "french_house",
    "funk",
    "future_bass",
    "grunge",
    "hard_rock",
    "hip_hop",
    "idm",
    "indie_folk",
    "indie_rock",
    "instrumental_hip_hop",
    "jazz_hop",
    "k_indie",
    "k_r&b",
    "korean_hip_hop",
    "kpop",
    "lo_fi",
    "modal_jazz",
    "neo_soul",
    "opera_rock",
    "piano_solo",
    "pop_ballad",
    "pop_rock",
    "progressive_rock",
    "psychedelic_pop",
    "psychedelic_rock",
    "r&b",
    "r&b_pop",
    "rock",
    "romantic_classical",
    "soft_rock",
    "synth_pop",
    "synthwave",
    "trap",
    "trap_pop",
    "trip_hop",
    "uk_garage",
    "west_coast_hip_hop",
]

MOODS: List[str] = [
    "abstract",
    "aggressive",
    "angst",
    "atmospheric",
    "avant_garde",
    "bold",
    "bright",
    "building",
    "celebratory",
    "cheerful",
    "complex",
    "confident",
    "contemplative",
    "danceable",
    "dark",
    "defiant",
    "dramatic",
    "dreamy",
    "driving",
    "dynamic",
    "elegant",
    "emotional",
    "empowering",
    "energetic",
    "epic",
    "ethereal",
    "euphoric",
    "fierce",
    "funky",
    "groovy",
    "haunting",
    "hopeful",
    "intense",
    "intimate",
    "introspective",
    "ironic",
    "luxurious",
    "melancholic",
    "mellow",
    "minimalist",
    "modern",
    "mysterious",
    "mystical",
    "nocturnal",
    "nostalgic",
    "passionate",
    "peaceful",
    "playful",
    "powerful",
    "raw",
    "rebellious",
    "reflective",
    "relaxed",
    "romantic",
    "satirical",
    "seductive",
    "serene",
    "smooth",
    "sophisticated",
    "soulful",
    "surreal",
    "trippy",
    "unsettling",
    "upbeat",
    "uplifting",
    "warm",
    "whimsical",
    "youthful",
]

LANGUAGES: List[str] = ["en", "es", "fr", "instrumental", "ko"]

INSTRUMENTATIONS: List[str] = [
    "808",
    "bass",
    "drums",
    "electronic_beats",
    "guitar",
    "keyboards",
    "palmas",
    "percussion",
    "piano",
    "recorder",
    "samples",
    "saxophone",
    "strings",
    "synth",
    "trumpet",
    "vocals",
    "vocoder",
]

REGIONALITIES: List[str] = [
    "asia",
    "es",
    "eu",
    "fr",
    "global",
    "jp",
    "kr",
    "latam",
    "us",
]


def _decode_index_list(values: List[int], lookup: List[str]) -> List[str]:
    return [lookup[v] for v in values if isinstance(v, int) and 0 <= v < len(lookup)]


def _decode_index(value: int, lookup: List[str]) -> Optional[str]:
    if isinstance(value, int) and 0 <= value < len(lookup):
        return lookup[value]
    return None

# ============================================================================
# 데이터 모델
# ============================================================================

@dataclass
class Song:
    id: str
    artist: str
    title: str
    youtube_url: str
    title_kor: Optional[str] = None
    genre_codes: List[int] = field(default_factory=list)
    genres: List[str] = field(default_factory=list)
    tags: Dict = field(default_factory=dict)
    popularity: Dict = field(default_factory=dict)
    meta: Dict = field(default_factory=dict)
    clip: Dict = field(default_factory=dict)
    
    # 학습 데이터
    rating: float = 0.0
    wins: int = 0
    losses: int = 0
    matches: int = 0
    
    def __str__(self):
        return f"{self.artist} - {self.get_display_title()}"

    def get_display_title(self) -> str:
        if self.title_kor:
            return f"{self.title} ({self.title_kor})"
        return self.title

@dataclass
class Match:
    round_num: int
    match_id: str
    song_a: Song
    song_b: Song
    winner: Optional[Song] = None
    choice: Optional[str] = None  # 'A', 'B', 'both', 'skip'
    timestamp: Optional[str] = None

@dataclass
class UserProfile:
    genre_weights: Dict[int, float] = field(default_factory=dict)
    attribute_weights: Dict[str, float] = field(default_factory=dict)
    confidence_scores: Dict[str, float] = field(default_factory=dict)
    total_matches: int = 0
    
# ============================================================================
# 데이터 로더 & 검증
# ============================================================================

class DataLoader:
    @staticmethod
    def load_songs(filepath: str) -> List[Song]:
        """JSON 파일에서 곡 목록 로드"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            songs = []
            for item in data:
                tags_raw = item.get('tags', {})
                tags = dict(tags_raw)
                if 'subgenres' in tags:
                    tags['subgenres'] = _decode_index_list(tags.get('subgenres', []), SUBGENRES)
                if 'mood' in tags:
                    tags['mood'] = _decode_index_list(tags.get('mood', []), MOODS)
                if 'language' in tags:
                    decoded_lang = _decode_index(tags.get('language'), LANGUAGES)
                    if decoded_lang is not None:
                        tags['language'] = decoded_lang
                if 'instrumentation' in tags:
                    tags['instrumentation'] = _decode_index_list(tags.get('instrumentation', []), INSTRUMENTATIONS)

                popularity_raw = item.get('popularity', {})
                popularity = dict(popularity_raw)
                if 'regionality' in popularity:
                    popularity['regionality'] = _decode_index_list(popularity.get('regionality', []), REGIONALITIES)

                genre_codes = [code for code in item.get('genres', []) if isinstance(code, int)]
                genre_names = decode_genre_names(genre_codes)

                song = Song(
                    id=item['id'],
                    artist=item['artist'],
                    title=item['title'],
                    youtube_url=item.get('youtube_url', ''),
                    title_kor=item.get('title_kor'),
                    genre_codes=genre_codes,
                    genres=genre_names,
                    tags=tags,
                    popularity=popularity,
                    meta=item.get('meta', {}),
                    clip=item.get('clip', {})
                )
                songs.append(song)
            
            print(f"✓ {len(songs)}곡 로드 완료")
            return songs
        except Exception as e:
            print(f"✗ 파일 로드 실패: {e}")
            return []
    
    @staticmethod
    def validate_songs(songs: List[Song]) -> bool:
        """필수 필드 검증"""
        issues = []
        for i, song in enumerate(songs):
            if not song.id:
                issues.append(f"곡 {i}: ID 누락")
            if not song.artist or not song.title:
                issues.append(f"곡 {i}: 아티스트/제목 누락")
        
        if issues:
            print("검증 오류:")
            for issue in issues[:5]:
                print(f"  - {issue}")
            return False
        return True

# ============================================================================
# 설문 엔진
# ============================================================================

class SurveyEngine:
    def __init__(self, songs: List[Song]):
        self.songs = songs
        self.responses = {}
        
    def run_survey(self) -> Dict:
        """사전 설문 실행"""
        print("\n" + "="*60)
        print("🎵 음악 취향 설문 시작 (약 2분 소요)")
        print("="*60)
        
        # 1. 장르 선호도 (쌍대 비교)
        print("\n[1단계] 두 장르 중 더 선호하는 쪽을 선택하세요")
        genre_pairs = [
            ("Rock", "Pop"),
            ("Hip-Hop", "Electronic"),
            ("Jazz", "Classical"),
            ("K-Pop", "Indie")
        ]
        
        genre_scores = defaultdict(int)
        for i, (g1, g2) in enumerate(genre_pairs, 1):
            print(f"\n{i}. {g1} vs {g2}")
            choice = input("   선택 (1/2/s=skip): ").strip()
            if choice == '1':
                genre_scores[g1] += 1
            elif choice == '2':
                genre_scores[g2] += 1
        
        # 2. 시대 선호도
        print("\n[2단계] 선호하는 음악 시대는?")
        print("1. 1970s-1980s  2. 1990s-2000s  3. 2010s 이후  4. 상관없음")
        era = input("선택: ").strip()
        era_map = {'1': 1980, '2': 2000, '3': 2015, '4': None}
        preferred_era = era_map.get(era)
        
        # 3. 에너지 레벨
        print("\n[3단계] 선호하는 에너지 레벨은?")
        print("1. 차분함  2. 보통  3. 활기참  4. 매우 강렬함")
        energy = input("선택: ").strip()
        energy_map = {'1': 0.2, '2': 0.5, '3': 0.7, '4': 0.9}
        preferred_energy = energy_map.get(energy, 0.5)
        
        # 4. 인지도 성향
        print("\n[4단계] 어떤 곡을 선호하시나요?")
        print("1. 유명한 히트곡  2. 적당히 알려진 곡  3. 숨은 명곡")
        popularity = input("선택: ").strip()
        pop_map = {'1': 0.8, '2': 0.5, '3': 0.2}
        preferred_popularity = pop_map.get(popularity, 0.5)
        
        # 5. 언어 선호
        print("\n[5단계] 선호하는 가사 언어는?")
        print("1. 한국어  2. 영어  3. 기타  4. 상관없음")
        lang = input("선택: ").strip()
        lang_map = {'1': 'ko', '2': 'en', '3': 'other', '4': None}
        preferred_language = lang_map.get(lang)

        # 6. 언어 집중도
        print("\n[6단계] 특정 언어 위주로 음악을 듣는 편인가요?")
        print("1. 거의 한국어만  2. 한국어/영어 위주  3. 영어/글로벌 위주  4. 다양하게 듣는다")
        language_focus_choice = input("선택: ").strip()
        global_languages = {'en', 'es', 'fr', 'instrumental'}
        language_focus_map = {
            '1': {'languages': {'ko'}, 'strict': True},
            '2': {'languages': {'ko', 'en'}, 'strict': True},
            '3': {'languages': global_languages, 'strict': True},
            '4': {'languages': set(), 'strict': False},
        }
        language_focus = language_focus_map.get(language_focus_choice, {'languages': set(), 'strict': False})

        # 7. 지역/씬 집중도
        print("\n[7단계] 특정 지역 음악에 더 끌리나요?")
        print("1. 한국 음악만 찾는다  2. 한국/아시아 음악 위주  3. 글로벌 다양성 선호  4. 잘 모르겠다")
        regional_choice = input("선택: ").strip()
        regional_focus_map = {
            '1': 'k_only',
            '2': 'k_prefer',
            '3': 'global',
            '4': 'neutral',
        }
        regional_focus = regional_focus_map.get(regional_choice, 'neutral')

        profile = {
            'genre_scores': dict(genre_scores),
            'preferred_era': preferred_era,
            'preferred_energy': preferred_energy,
            'preferred_popularity': preferred_popularity,
            'preferred_language': preferred_language,
            'preferred_languages': sorted(language_focus['languages']),
            'language_strict': language_focus['strict'],
            'regional_focus': regional_focus
        }
        
        print("\n✓ 설문 완료!")
        return profile

# ============================================================================
# 후보군 선택 & 시딩
# ============================================================================

class CandidateSelector:
    def __init__(self, songs: List[Song], survey_profile: Dict):
        self.songs = songs
        self.profile = survey_profile
        self.seed_scores: Dict[str, float] = {}

    def compute_base_score(self, song: Song, language_whitelist: Set[str], language_strict: bool) -> float:
        """설문 기반 초기 점수 계산"""
        score = 0.0
        language = song.tags.get('language')

        if language_strict and language_whitelist and (not language or language not in language_whitelist):
            return float('-inf')

        if language_whitelist:
            if language in language_whitelist:
                score += 1.0 if language_strict else 0.6
            else:
                score += 0.1

        preferred_language = self.profile.get('preferred_language')
        if preferred_language:
            if language == preferred_language:
                score += 0.5
            else:
                score -= 0.1

        genre_scores: Dict[str, int] = self.profile.get('genre_scores', {})
        if genre_scores and song.genres:
            match_weight = sum(genre_scores.get(genre, 0) for genre in song.genres if genre in genre_scores)
            if match_weight:
                score += 0.8 + match_weight * 0.3
            else:
                score += 0.2
        else:
            score += 0.3

        if self.profile.get('preferred_era'):
            song_year = song.tags.get('era_year', 2000)
            era_diff = abs(song_year - self.profile['preferred_era'])
            era_score = max(0, 1 - era_diff / 30)
            score += era_score

        if 'energy' in song.tags and self.profile.get('preferred_energy') is not None:
            energy_diff = abs(song.tags['energy'] - self.profile['preferred_energy'])
            energy_score = 1 - energy_diff
            score += energy_score

        awareness = song.popularity.get('awareness_idx', 0.5)
        pop_diff = abs(awareness - self.profile['preferred_popularity'])
        pop_score = 1 - pop_diff
        score += pop_score * 0.5

        regional_focus = self.profile.get('regional_focus', 'neutral')
        regionality = set(song.popularity.get('regionality', []))
        if regional_focus == 'k_only':
            if language == 'ko' or 'kr' in regionality or 'asia' in regionality:
                score += 1.2
            else:
                return float('-inf')
        elif regional_focus == 'k_prefer':
            if language == 'ko' or 'kr' in regionality:
                score += 0.8
            elif 'asia' in regionality:
                score += 0.4
            else:
                score += 0.1
        elif regional_focus == 'global':
            if regionality & {'global', 'us', 'eu'} or language in {'en', 'es', 'fr'}:
                score += 0.7
            else:
                score += 0.2

        return score

    def select_candidates(self, k: int = 32) -> List[Song]:
        """상위 K개 후보 선택 (다양성 고려)"""
        language_whitelist: Set[str] = set(self.profile.get('preferred_languages') or [])
        language_strict = bool(self.profile.get('language_strict') and language_whitelist)

        if language_strict:
            filtered = [song for song in self.songs if song.tags.get('language') in language_whitelist]
            if filtered:
                songs_to_score = filtered
            else:
                songs_to_score = self.songs
                language_strict = False
        else:
            songs_to_score = self.songs

        scored_songs: List[Tuple[Song, float]] = []
        for song in songs_to_score:
            score = self.compute_base_score(song, language_whitelist, language_strict)
            if score != float('-inf'):
                scored_songs.append((song, score))

        if not scored_songs:
            scored_songs = [(song, 0.0) for song in self.songs]

        scored_songs.sort(key=lambda x: x[1], reverse=True)
        self.seed_scores = {song.id: score for song, score in scored_songs}

        pool = scored_songs[:min(k*2, len(scored_songs))]
        selected: List[Song] = []

        for song, _ in pool:
            if len(selected) >= k:
                break
            same_artist = sum(1 for s in selected if s.artist == song.artist)
            if same_artist < 2:
                selected.append(song)

        while len(selected) < k and len(pool) > len(selected):
            for song, _ in pool:
                if song not in selected:
                    selected.append(song)
                    if len(selected) >= k:
                        break

        print(f"\n✓ {len(selected)}개 후보곡 선정 완료")
        return selected

    def get_seed_scores(self) -> Dict[str, float]:
        """시드 배치를 위해 계산된 점수를 반환"""
        return dict(self.seed_scores)


class BracketGenerator:
    @staticmethod
    def create_bracket(candidates: List[Song], seed_scores: Optional[Dict[str, float]] = None) -> List[List[Match]]:
        """토너먼트 브래킷 생성 (점수 기반 시딩 지원)"""
        if seed_scores:
            ordered = sorted(candidates, key=lambda s: seed_scores.get(s.id, 0.0), reverse=True)
        else:
            ordered = candidates[:]
            random.shuffle(ordered)

        if len(ordered) % 2 == 1:
            ordered = ordered[:-1]

        rounds: List[List[Match]] = []
        current_round: List[Match] = []
        half = len(ordered) // 2

        for i in range(half):
            song_a = ordered[i]
            song_b = ordered[-(i + 1)]
            match = Match(
                round_num=1,
                match_id=f"R1-M{i+1}",
                song_a=song_a,
                song_b=song_b
            )
            current_round.append(match)

        if current_round:
            rounds.append(current_round)
        return rounds

# ============================================================================
# 토너먼트 엔진 (학습 포함)
# ============================================================================

class TournamentEngine:
    def __init__(self, initial_rating: float = 1500.0, k_factor: float = 32.0):
        self.initial_rating = initial_rating
        self.k_factor = k_factor
        self.match_history = []
        
    def expected_score(self, rating_a: float, rating_b: float) -> float:
        """Elo 기대 승률"""
        return 1 / (1 + math.pow(10, (rating_b - rating_a) / 400))
    
    def update_ratings(self, song_a: Song, song_b: Song, result: str):
        """Elo 레이팅 업데이트"""
        if song_a.rating == 0:
            song_a.rating = self.initial_rating
        if song_b.rating == 0:
            song_b.rating = self.initial_rating
        
        expected_a = self.expected_score(song_a.rating, song_b.rating)
        
        if result == 'A':
            actual_a = 1.0
            song_a.wins += 1
            song_b.losses += 1
        elif result == 'B':
            actual_a = 0.0
            song_b.wins += 1
            song_a.losses += 1
        elif result == 'both':
            actual_a = 0.5
        else:  # skip
            return
        
        song_a.rating += self.k_factor * (actual_a - expected_a)
        song_b.rating += self.k_factor * ((1 - actual_a) - (1 - expected_a))
        
        song_a.matches += 1
        song_b.matches += 1
    
    def run_match(self, match: Match) -> Optional[Song]:
        """매치 실행 (사용자 입력)"""
        print("\n" + "-"*60)
        print(f"🎵 {match.match_id}")
        print(f"A. {match.song_a}")
        print(f"   [{match.song_a.youtube_url[:50]}...]")
        print(f"\nB. {match.song_b}")
        print(f"   [{match.song_b.youtube_url[:50]}...]")
        print("-"*60)
        
        while True:
            choice = input("선택 (A/B/둘다=T/건너뛰기=S): ").strip().upper()
            if choice in ['A', 'B', 'T', 'S']:
                break
            print("잘못된 입력입니다. A, B, T, S 중 선택하세요.")
        
        match.choice = choice
        match.timestamp = datetime.now().isoformat()
        
        self.update_ratings(match.song_a, match.song_b, choice)
        self.match_history.append(match)
        
        if choice == 'A':
            match.winner = match.song_a
            return match.song_a
        elif choice == 'B':
            match.winner = match.song_b
            return match.song_b
        elif choice == 'T':
            # 둘 다 좋음: 더 낮은 레이팅을 가진 쪽을 진출
            match.winner = match.song_a if match.song_a.rating <= match.song_b.rating else match.song_b
            return match.winner
        else:
            # 건너뛰기: 랜덤 선택
            match.winner = random.choice([match.song_a, match.song_b])
            return match.winner

    def resolve_match(self, match: Match, choice: str) -> Optional[Song]:
        """GUI 등 외부 입력으로 매치 결과 처리"""
        choice = choice.upper()

        if choice not in ['A', 'B', 'T', 'S']:
            raise ValueError("choice must be one of 'A', 'B', 'T', 'S'")

        match.choice = choice
        match.timestamp = datetime.now().isoformat()

        self.update_ratings(match.song_a, match.song_b, choice)
        self.match_history.append(match)

        if choice == 'A':
            match.winner = match.song_a
        elif choice == 'B':
            match.winner = match.song_b
        elif choice == 'T':
            match.winner = match.song_a if match.song_a.rating <= match.song_b.rating else match.song_b
        else:
            match.winner = random.choice([match.song_a, match.song_b])

        return match.winner

    def run_tournament(self, bracket: List[List[Match]]) -> Song:
        """전체 토너먼트 진행"""
        print("\n" + "="*60)
        print("🏆 토너먼트 시작!")
        print("="*60)
        
        current_winners = []
        round_num = 1
        
        for round_matches in bracket:
            print(f"\n\n{'='*60}")
            print(f"📍 라운드 {round_num} ({len(round_matches)}개 매치)")
            print("="*60)
            
            round_winners = []
            for i, match in enumerate(round_matches, 1):
                print(f"\n[매치 {i}/{len(round_matches)}]")
                winner = self.run_match(match)
                if winner:
                    round_winners.append(winner)
            
            current_winners = round_winners
            round_num += 1
            
            # 다음 라운드 생성
            if len(current_winners) > 1:
                next_round = []
                for i in range(0, len(current_winners), 2):
                    if i + 1 < len(current_winners):
                        match = Match(
                            round_num=round_num,
                            match_id=f"R{round_num}-M{i//2+1}",
                            song_a=current_winners[i],
                            song_b=current_winners[i+1]
                        )
                        next_round.append(match)
                bracket.append(next_round)
            else:
                break
        
        champion = current_winners[0] if current_winners else None
        return champion

# ============================================================================
# 결과 분석
# ============================================================================

class ResultAnalyzer:
    def __init__(self, match_history: List[Match], all_songs: List[Song]):
        self.match_history = match_history
        self.all_songs = all_songs
    
    def generate_report(self, champion: Song) -> Dict:
        """결과 리포트 생성"""
        print("\n" + "="*60)
        print("📊 결과 분석")
        print("="*60)
        
        # 우승곡
        print(f"\n🏆 우승: {champion}")
        print(f"   최종 레이팅: {champion.rating:.1f}")
        print(f"   전적: {champion.wins}승 {champion.losses}패")
        
        # 상위곡
        participated = [s for s in self.all_songs if s.matches > 0]
        participated.sort(key=lambda x: x.rating, reverse=True)
        
        print(f"\n📈 상위 5곡:")
        for i, song in enumerate(participated[:5], 1):
            print(f"   {i}. {song} (레이팅: {song.rating:.1f})")
        
        # 매치 통계
        total_matches = len(self.match_history)
        choice_counts = defaultdict(int)
        for match in self.match_history:
            choice_counts[match.choice] += 1
        
        print(f"\n📊 매치 통계:")
        print(f"   총 매치: {total_matches}")
        print(f"   A 선택: {choice_counts['A']}")
        print(f"   B 선택: {choice_counts['B']}")
        print(f"   둘 다: {choice_counts['T']}")
        print(f"   건너뛰기: {choice_counts['S']}")
        
        return {
            'champion': champion,
            'top_songs': participated[:5],
            'total_matches': total_matches,
            'choice_distribution': dict(choice_counts)
        }

# ============================================================================
# 추천 엔진
# ============================================================================

class RecommendationEngine:
    """토너먼트 결과를 활용해 맞춤 추천을 생성한다."""

    LANGUAGE_DISPLAY = {
        'en': '영어',
        'es': '스페인어',
        'fr': '프랑스어',
        'instrumental': '연주곡',
        'ko': '한국어',
    }

    REGION_DISPLAY = {
        'asia': '아시아',
        'es': '스페인',
        'eu': '유럽',
        'fr': '프랑스',
        'global': '글로벌',
        'jp': '일본',
        'kr': '한국',
        'latam': '라틴 아메리카',
        'us': '미국',
    }

    def __init__(self, all_songs: List[Song], participated_songs: List[Song], survey_profile: Optional[Dict] = None):
        self.all_songs = all_songs
        self.participated = set(s.id for s in participated_songs)
        self.profile = survey_profile or {}
        self.language_whitelist: Set[str] = set(self.profile.get('preferred_languages') or [])
        self.language_strict: bool = bool(self.profile.get('language_strict') and self.language_whitelist)
        self.preferred_language: Optional[str] = self.profile.get('preferred_language')
        self.regional_focus: str = self.profile.get('regional_focus', 'neutral')
        self.selector = CandidateSelector(all_songs, self.profile)

    def generate_recommendations(
        self,
        top_songs: List[Song],
        n_core: int = 7,
        n_fresh: int = 3
    ) -> Dict[str, List[Dict[str, Any]]]:
        """설문 결과와 토너먼트 상위 곡을 기반으로 추천을 생성한다."""

        if not top_songs:
            return {'core': [], 'fresh': []}

        top_winners = top_songs[:3]
        candidates = [s for s in self.all_songs if s.id not in self.participated]

        scored_entries: List[Dict[str, Any]] = []
        for song in candidates:
            base_score = self.selector.compute_base_score(song, self.language_whitelist, self.language_strict)
            if base_score == float('-inf'):
                continue

            similarity_score, anchor, shared_tags = self._analyze_similarity(song, top_winners)

            if base_score <= 0 and similarity_score <= 0:
                continue

            language_note = self._describe_language_fit(song)
            region_note = self._describe_region_fit(song)
            freshness_score, freshness_note = self._freshness_profile(song)

            scored_entries.append({
                'song': song,
                'score': base_score + similarity_score,
                'freshness': freshness_score,
                'anchor': anchor,
                'shared_tags': shared_tags,
                'language_note': language_note,
                'region_note': region_note,
                'freshness_note': freshness_note,
            })

        if not scored_entries:
            return {'core': [], 'fresh': []}

        scored_entries.sort(key=lambda item: (item['score'], item['freshness']), reverse=True)

        core_recs: List[Dict[str, Any]] = []
        used_ids: Set[str] = set()
        for entry in scored_entries:
            if len(core_recs) >= n_core:
                break
            formatted = self._format_entry(entry, category='core')
            core_recs.append(formatted)
            used_ids.add(entry['song'].id)

        fresh_candidates = [
            entry for entry in scored_entries
            if entry['song'].id not in used_ids and entry['freshness'] >= 0.45 and entry['score'] > 0
        ]
        fresh_candidates.sort(key=lambda item: (item['freshness'], item['score']), reverse=True)

        fresh_recs: List[Dict[str, Any]] = []
        for entry in fresh_candidates[:n_fresh]:
            formatted = self._format_entry(entry, category='fresh')
            fresh_recs.append(formatted)
            used_ids.add(entry['song'].id)

        if len(fresh_recs) < n_fresh:
            remaining = [entry for entry in scored_entries if entry['song'].id not in used_ids]
            for entry in remaining:
                if len(fresh_recs) >= n_fresh:
                    break
                formatted = self._format_entry(entry, category='fresh')
                fresh_recs.append(formatted)
                used_ids.add(entry['song'].id)

        return {'core': core_recs, 'fresh': fresh_recs}

    def show_recommendations(self, recommendations: Dict[str, List[Dict[str, Any]]]):
        """추천 결과 출력"""
        print("\n" + "="*60)
        print("💡 추천 곡 목록")
        print("="*60)

        core = recommendations.get('core', []) if recommendations else []
        fresh = recommendations.get('fresh', []) if recommendations else []

        if not core and not fresh:
            print("추천할 곡이 없습니다.")
            return

        if core:
            print("\n🎯 취향 저격 추천")
            for idx, entry in enumerate(core, 1):
                song = entry['song']
                reason = entry['reason']
                print(f"\n{idx}. {song}")
                print(f"   이유: {reason}")
                print(f"   링크: {song.youtube_url}")

        if fresh:
            print("\n🌱 새롭게 시도해볼 곡")
            for idx, entry in enumerate(fresh, 1):
                song = entry['song']
                reason = entry['reason']
                print(f"\n{idx}. {song}")
                print(f"   이유: {reason}")
                print(f"   링크: {song.youtube_url}")

    def _analyze_similarity(self, song: Song, winners: List[Song]) -> Tuple[float, Optional[Song], List[str]]:
        """상위 곡과의 유사도를 계산한다."""

        best_score = 0.0
        best_anchor: Optional[Song] = None
        best_tags: List[str] = []

        song_genres = set(song.genres or [])
        song_subgenres = set(song.tags.get('subgenres', []))

        for winner in winners:
            shared_genres = sorted(song_genres & set(winner.genres or []))
            shared_subgenres = sorted(song_subgenres & set(winner.tags.get('subgenres', [])))

            similarity = 0.0
            if shared_genres:
                similarity += 0.8 + 0.25 * len(shared_genres)
            if shared_subgenres:
                similarity += 0.4 + 0.1 * len(shared_subgenres)

            song_energy = song.tags.get('energy')
            winner_energy = winner.tags.get('energy')
            if isinstance(song_energy, (int, float)) and isinstance(winner_energy, (int, float)):
                energy_diff = abs(song_energy - winner_energy)
                similarity += max(0.0, 0.5 - energy_diff)

            song_valence = song.tags.get('valence')
            winner_valence = winner.tags.get('valence')
            if isinstance(song_valence, (int, float)) and isinstance(winner_valence, (int, float)):
                valence_diff = abs(song_valence - winner_valence)
                similarity += max(0.0, 0.3 - valence_diff)

            if similarity > best_score:
                best_score = similarity
                best_anchor = winner
                highlight = shared_subgenres or shared_genres
                best_tags = highlight[:2]

        return best_score, best_anchor, best_tags

    def _describe_language_fit(self, song: Song) -> Optional[str]:
        language = song.tags.get('language')
        if not language:
            return None

        display = self.LANGUAGE_DISPLAY.get(language, language)

        if self.language_strict and language in self.language_whitelist:
            return f"{display} 가사 선호를 정확히 반영"

        if self.language_whitelist and language in self.language_whitelist:
            return f"{display} 트랙도 즐겨 듣는 편"

        if self.preferred_language and language == self.preferred_language:
            return f"{display} 중심 취향을 고려"

        if not self.language_whitelist and not self.preferred_language and language:
            return None

        return None

    def _describe_region_fit(self, song: Song) -> Optional[str]:
        regionality = set(song.popularity.get('regionality', []))
        language = song.tags.get('language')

        if self.regional_focus in {'k_only', 'k_prefer'}:
            if language == 'ko':
                return "한국어 곡 중심 취향을 반영"
            if 'kr' in regionality:
                return "한국 씬에서 주목받는 곡"
            if 'asia' in regionality:
                return "아시아 씬과 연결된 사운드"

        if self.regional_focus == 'global':
            for code in ['global', 'us', 'eu', 'latam']:
                if code in regionality:
                    region_name = self.REGION_DISPLAY.get(code, code)
                    return f"{region_name} 트렌드를 느낄 수 있는 곡"

        return None

    def _freshness_profile(self, song: Song) -> Tuple[float, Optional[str]]:
        era_year = song.tags.get('era_year')
        awareness = song.popularity.get('awareness_idx')

        freshness = 0.0
        note: Optional[str] = None

        if isinstance(era_year, (int, float)):
            year = int(era_year)
            if year >= 2020:
                freshness += 0.7
                note = f"{year}년대 최신 감각"
            elif year >= 2015:
                freshness += 0.5
                note = f"{year}년 이후 발표된 비교적 최신곡"
            elif year >= 2010:
                freshness += 0.3
                note = f"{year}년대의 감성을 담은 곡"

        if isinstance(awareness, (int, float)) and awareness < 0.4:
            freshness += 0.2
            if not note:
                note = "아직 널리 알려지지 않은 보석"

        return min(freshness, 1.0), note

    def _format_entry(self, entry: Dict[str, Any], category: str) -> Dict[str, Any]:
        song = entry['song']
        anchor: Optional[Song] = entry.get('anchor')
        shared_tags: List[str] = entry.get('shared_tags') or []
        parts: List[str] = []

        if anchor:
            if shared_tags:
                highlight = ", ".join(shared_tags)
                parts.append(f"{anchor}와 닮은 {highlight}")
            else:
                parts.append(f"{anchor}의 무드를 잇는 트랙")

        language_note = entry.get('language_note')
        if language_note:
            parts.append(language_note)

        region_note = entry.get('region_note')
        if region_note:
            parts.append(region_note)

        freshness_note = entry.get('freshness_note')
        if freshness_note and (category == 'fresh' or entry.get('freshness', 0) >= 0.5):
            parts.append(freshness_note)

        unique_parts = list(dict.fromkeys(parts))
        reason = " / ".join(unique_parts) if unique_parts else "토너먼트 기록 기반으로 엄선했어요"

        return {
            'song': song,
            'reason': reason,
            'category': category,
        }

# ============================================================================
# 메인 애플리케이션
# ============================================================================

class MusicTournamentApp:
    def __init__(self, songs_file: str):
        self.songs_file = songs_file
        self.songs = []
        self.survey_profile = {}
        self.candidates = []
        self.champion = None
        self.seed_scores: Dict[str, float] = {}
        
    def run(self):
        """전체 프로세스 실행"""
        print("\n" + "="*60)
        print("🎵 음악 토너먼트 취향 테스트")
        print("="*60)
        
        # 1. 데이터 로드
        print("\n1️⃣ 데이터 로딩 중...")
        loader = DataLoader()
        self.songs = loader.load_songs(self.songs_file)
        
        if not self.songs or not loader.validate_songs(self.songs):
            print("✗ 데이터 로드 실패. 프로그램을 종료합니다.")
            return
        
        # 2. 설문
        print("\n2️⃣ 사전 설문")
        survey = SurveyEngine(self.songs)
        self.survey_profile = survey.run_survey()
        
        # 3. 후보 선택
        print("\n3️⃣ 후보곡 선정 중...")
        selector = CandidateSelector(self.songs, self.survey_profile)
        self.candidates = selector.select_candidates(k=32)
        self.seed_scores = selector.get_seed_scores()

        # 4. 브래킷 생성
        print("\n4️⃣ 토너먼트 브래킷 생성 중...")
        bracket_gen = BracketGenerator()
        bracket = bracket_gen.create_bracket(self.candidates, self.seed_scores)
        if bracket and bracket[0]:
            print(f"✓ {len(bracket[0])}개 매치로 구성된 브래킷 생성 완료")
        else:
            print("경기를 구성할 후보가 충분하지 않아 기본 시드를 적용합니다.")

        # 5. 토너먼트 진행
        print("\n5️⃣ 토너먼트 진행")
        input("\n준비되셨으면 Enter를 눌러주세요...")
        
        engine = TournamentEngine()
        self.champion = engine.run_tournament(bracket)
        
        # 6. 결과 분석
        print("\n6️⃣ 결과 분석")
        analyzer = ResultAnalyzer(engine.match_history, self.candidates)
        report = analyzer.generate_report(self.champion)
        
        # 7. 추천
        print("\n7️⃣ 추천곡 생성 중...")
        recommender = RecommendationEngine(self.songs, self.candidates, self.survey_profile)
        recommendations = recommender.generate_recommendations(report['top_songs'])
        recommender.show_recommendations(recommendations)
        
        # 종료
        print("\n" + "="*60)
        print("✨ 테스트 완료! 음악을 즐기세요 🎵")
        print("="*60)

# ============================================================================
# GUI 애플리케이션
# ============================================================================



class MusicTournamentGUI(QMainWindow):
    GENRE_PAIRS = [
        ("Rock", "Pop"),
        ("Hip-Hop", "Electronic"),
        ("Jazz", "Classical"),
        ("K-Pop", "Indie"),
    ]

    ERA_OPTIONS = [
        ("1970s-1980s", "1"),
        ("1990s-2000s", "2"),
        ("2010s 이후", "3"),
        ("상관없음", "4"),
    ]

    ENERGY_OPTIONS = [
        ("차분한 무드", "1"),
        ("보통 에너지", "2"),
        ("활기찬 느낌", "3"),
        ("강렬한 사운드", "4"),
    ]

    POPULARITY_OPTIONS = [
        ("유명한 히트곡", "1"),
        ("적당히 알려진 곡", "2"),
        ("숨은 명곡", "3"),
    ]

    LANGUAGE_OPTIONS = [
        ("한국어", "1"),
        ("영어", "2"),
        ("기타 언어", "3"),
        ("상관없음", "4"),
    ]

    LANGUAGE_FOCUS_OPTIONS = [
        ("거의 한국어만 들어요", "1"),
        ("한국어/영어 위주", "2"),
        ("영어/글로벌 위주", "3"),
        ("다양한 언어 환영", "4"),
    ]

    REGIONAL_FOCUS_OPTIONS = [
        ("한국 음악만 추천해주세요", "1"),
        ("한국·아시아 중심", "2"),
        ("글로벌 다양성", "3"),
        ("잘 모르겠어요", "4"),
    ]

    def __init__(self, songs_file: str):
        super().__init__()
        self.songs_file = songs_file
        self.setWindowTitle("Whats My Music Flavor · 토너먼트 취향 테스트")
        self.resize(960, 720)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(16)

        title_label = QLabel("Whats My Music Flavor")
        title_font = QFont("Pretendard", 18)
        title_font.setBold(True)
        title_label.setFont(title_font)
        subtitle_label = QLabel("나만의 음악 토너먼트")
        subtitle_font = QFont("Pretendard", 26)
        subtitle_font.setBold(True)
        subtitle_label.setFont(subtitle_font)
        main_layout.addWidget(title_label)
        main_layout.addWidget(subtitle_label)

        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(16)
        self.content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        main_layout.addWidget(self.content_widget, 1)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        loader = DataLoader()
        self.songs = loader.load_songs(self.songs_file)
        if not self.songs or not loader.validate_songs(self.songs):
            QMessageBox.critical(self, "데이터 오류", "곡 데이터를 불러오지 못했습니다. songs.json 파일을 확인해주세요.")
            self.valid = False
            return

        self.valid = True
        self.reset_state()
        self.update_status(f"{len(self.songs)}곡 데이터를 성공적으로 불러왔어요.")

    def update_status(self, message: str):
        self.status_bar.showMessage(message)


    def reset_state(self):
        self.survey_profile: Dict[str, Any] = {}
        self.candidates: List[Song] = []
        self.engine: Optional[TournamentEngine] = None
        self.bracket: List[List[Match]] = []
        self.current_round_number = 1
        self.current_round_matches: List[Match] = []
        self.current_round_winners: List[Song] = []
        self.current_match_index = 0
        self.active_match: Optional[Match] = None
        self.total_matches = 0
        self.champion: Optional[Song] = None
        self.report: Dict[str, Any] = {}
        self.recommendations: Dict[str, List[Dict[str, Any]]] = {"core": [], "fresh": []}
        self.seed_scores: Dict[str, float] = {}


    def clear_content(self):
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def show_start_view(self):
        self.reset_state()
        self.clear_content()

        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)
        layout.addWidget(QLabel("당신의 음악 취향을 발견해보세요"))
        intro = QLabel("간단한 설문과 토너먼트를 통해 나만의 플레이리스트를 만들어보세요.")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        start_button = QPushButton("지금 시작하기")
        start_button.setCursor(Qt.CursorShape.PointingHandCursor)
        start_button.clicked.connect(self.show_survey_view)
        layout.addWidget(start_button, alignment=Qt.AlignmentFlag.AlignLeft)

        self.content_layout.addWidget(widget)
        self.update_status("간단한 설문부터 시작해볼까요?")

    def show_survey_view(self):
        self.clear_content()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        form = QWidget()
        form_layout = QVBoxLayout(form)
        form_layout.setSpacing(12)

        self.genre_groups: List[Tuple[QButtonGroup, Tuple[str, str]]] = []
        for idx, (g1, g2) in enumerate(self.GENRE_PAIRS, 1):
            box = QGroupBox(f"{idx}. {g1} vs {g2}")
            box_layout = QHBoxLayout(box)
            group = QButtonGroup(box)
            for text, value in ((f"{g1} 선호", "1"), (f"{g2} 선호", "2"), ("잘 모르겠음", "s")):
                btn = QRadioButton(text)
                btn.setProperty("value", value)
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                group.addButton(btn)
                box_layout.addWidget(btn)
            self.genre_groups.append((group, (g1, g2)))
            form_layout.addWidget(box)

        self.era_group = self.build_radio_section(form_layout, "시대 선호", self.ERA_OPTIONS, default="2")
        self.energy_group = self.build_radio_section(form_layout, "에너지 레벨", self.ENERGY_OPTIONS, default="3")
        self.popularity_group = self.build_radio_section(form_layout, "인기도 선호", self.POPULARITY_OPTIONS, default="2")
        self.language_group = self.build_radio_section(form_layout, "가사 언어", self.LANGUAGE_OPTIONS, default="4")
        self.language_focus_group = self.build_radio_section(form_layout, "언어 집중도", self.LANGUAGE_FOCUS_OPTIONS, default="4")
        self.regional_focus_group = self.build_radio_section(form_layout, "국가/지역 취향", self.REGIONAL_FOCUS_OPTIONS, default="4")

        start_button = QPushButton("토너먼트 시작")
        start_button.setCursor(Qt.CursorShape.PointingHandCursor)
        start_button.clicked.connect(self.begin_tournament)
        form_layout.addWidget(start_button, alignment=Qt.AlignmentFlag.AlignRight)
        form_layout.addStretch(1)

        scroll.setWidget(form)
        self.content_layout.addWidget(scroll)
        self.update_status("설문 응답을 바탕으로 맞춤 토너먼트를 준비합니다.")

    def build_radio_section(self, layout: QVBoxLayout, title: str, options: List[Tuple[str, str]], default: Optional[str] = None) -> QButtonGroup:
        box = QGroupBox(title)
        box_layout = QHBoxLayout(box)
        group = QButtonGroup(box)
        for text, value in options:
            btn = QRadioButton(text)
            btn.setProperty("value", value)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            if default is not None and value == default:
                btn.setChecked(True)
            group.addButton(btn)
            box_layout.addWidget(btn)
        layout.addWidget(box)
        return group

    def begin_tournament(self):
        genre_scores: Dict[str, int] = defaultdict(int)
        for group, (g1, g2) in self.genre_groups:
            button = group.checkedButton()
            if not button:
                continue
            value = button.property("value")
            if value == "1":
                genre_scores[g1] += 1
            elif value == "2":
                genre_scores[g2] += 1

        era_map = {"1": 1980, "2": 2000, "3": 2015, "4": None}
        energy_map = {"1": 0.2, "2": 0.5, "3": 0.7, "4": 0.9}
        pop_map = {"1": 0.8, "2": 0.5, "3": 0.2}
        lang_map = {"1": "ko", "2": "en", "3": "other", "4": None}
        global_languages = {"en", "es", "fr", "instrumental"}
        language_focus_map = {
            "1": {"languages": {"ko"}, "strict": True},
            "2": {"languages": {"ko", "en"}, "strict": True},
            "3": {"languages": global_languages, "strict": True},
            "4": {"languages": set(), "strict": False},
        }
        regional_focus_map = {"1": "k_only", "2": "k_prefer", "3": "global", "4": "neutral"}

        def group_value(group: QButtonGroup, default: str) -> str:
            button = group.checkedButton()
            return button.property("value") if button else default

        lang_focus_value = group_value(self.language_focus_group, "4")
        language_focus = language_focus_map.get(lang_focus_value, {"languages": set(), "strict": False})
        regional_focus = regional_focus_map.get(group_value(self.regional_focus_group, "4"), "neutral")

        self.survey_profile = {
            "genre_scores": dict(genre_scores),
            "preferred_era": era_map.get(group_value(self.era_group, "2")),
            "preferred_energy": energy_map.get(group_value(self.energy_group, "3"), 0.5),
            "preferred_popularity": pop_map.get(group_value(self.popularity_group, "2"), 0.5),
            "preferred_language": lang_map.get(group_value(self.language_group, "4")),
            "preferred_languages": sorted(language_focus["languages"]),
            "language_strict": language_focus["strict"],
            "regional_focus": regional_focus,
        }

        selector = CandidateSelector(self.songs, self.survey_profile)
        self.candidates = selector.select_candidates(k=min(32, len(self.songs)))
        self.seed_scores = selector.get_seed_scores()

        if len(self.candidates) < 2:
            QMessageBox.warning(self, "후보 부족", "토너먼트를 진행하기에 곡이 부족합니다. 데이터를 확인해주세요.")
            self.show_start_view()
            return

        if len(self.candidates) % 2 == 1:
            removed = self.candidates.pop()
            if removed:
                self.seed_scores.pop(removed.id, None)

        self.engine = TournamentEngine()
        bracket_gen = BracketGenerator()
        self.bracket = bracket_gen.create_bracket(self.candidates, self.seed_scores)
        if not self.bracket:
            QMessageBox.warning(self, "브래킷 생성 실패", "토너먼트를 구성할 수 있는 매치가 부족합니다. 응답을 조정해보세요.")
            self.show_start_view()
            return

        self.current_round_number = 1
        self.current_round_matches = self.bracket[0] if self.bracket else []
        self.current_round_winners = []
        self.current_match_index = 0
        self.total_matches = max(1, len(self.candidates) - 1)

        self.update_status("토너먼트를 준비 중입니다.")
        self.show_match_view()

    def show_match_view(self):
        self.clear_content()

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(12)
        layout.addWidget(QLabel("토너먼트 진행"))

        self.match_status_label = QLabel()
        layout.addWidget(self.match_status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        layout.addWidget(self.progress_bar)

        cards_container = QWidget()
        cards_layout = QHBoxLayout(cards_container)
        self.card_a = self.create_song_card(cards_container, "A 곡")
        self.card_b = self.create_song_card(cards_container, "B 곡")
        cards_layout.addWidget(self.card_a["box"])
        cards_layout.addWidget(self.card_b["box"])
        layout.addWidget(cards_container)

        self.helper_label = QLabel("마음에 드는 곡을 선택하세요.")
        layout.addWidget(self.helper_label)

        button_row = QWidget()
        button_layout = QGridLayout(button_row)
        button_layout.setSpacing(8)

        def add_button(text: str, row: int, col: int, choice: str):
            button = QPushButton(text)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(lambda _=False, c=choice: self.on_choice(c))
            button_layout.addWidget(button, row, col)

        add_button("A 곡 선택", 0, 0, "A")
        add_button("B 곡 선택", 0, 1, "B")
        add_button("둘 다 좋아요", 1, 0, "T")
        add_button("건너뛰기", 1, 1, "S")
        layout.addWidget(button_row)

        self.content_layout.addWidget(container)
        self.update_status("토너먼트가 진행 중입니다. 클릭 한 번으로 선택하세요!")
        self.display_current_match()

    def create_song_card(self, parent: QWidget, title: str):
        box = QGroupBox(title)
        layout = QVBoxLayout(box)
        name_label = QLabel()
        layout.addWidget(name_label)
        meta_label = QLabel()
        layout.addWidget(meta_label)
        tag_label = QLabel()
        tag_label.setWordWrap(True)
        layout.addWidget(tag_label)
        link_label = QLabel()
        link_label.setTextFormat(Qt.TextFormat.RichText)
        link_label.setOpenExternalLinks(True)
        layout.addWidget(link_label)
        return {"box": box, "title": name_label, "meta": meta_label, "tag": tag_label, "link": link_label}


    def update_song_card(self, card: Dict[str, QLabel], song: Song):
        card["title"].setText(song.get_display_title())
        rating = song.rating if song.rating else 1500
        card["meta"].setText(f"{song.artist} · 예상 레이팅 {rating:.0f}")
        details: List[str] = []
        if song.tags.get("era_year"):
            details.append(f"{song.tags['era_year']}년대")
        if song.tags.get("energy") is not None:
            details.append(f"에너지 {song.tags['energy']*100:.0f}%")
        if song.genres:
            details.append("장르 " + ", ".join(song.genres[:2]))
        elif song.genre_codes:
            details.append("장르 코드 " + ", ".join(map(str, song.genre_codes[:3])))
        card["tag"].setText(" · ".join(details))
        if song.youtube_url:
            card["link"].setOpenExternalLinks(True)
            card["link"].setText(f'<a href="{song.youtube_url}">YouTube에서 듣기 ↗</a>')
        else:
            card["link"].setOpenExternalLinks(False)
            card["link"].setText("<span style='color:#9ca3af;'>링크 정보가 없습니다</span>")

    def display_current_match(self):
        if not self.current_round_matches:
            champion = self.current_round_winners[0] if self.current_round_winners else None
            self.finish_tournament(champion)
            return
        if self.current_match_index >= len(self.current_round_matches):
            self.prepare_next_round()
            return

        self.active_match = self.current_round_matches[self.current_match_index]
        match = self.active_match
        self.match_status_label.setText(
            f"라운드 {self.current_round_number} · 매치 {self.current_match_index + 1}/{len(self.current_round_matches)}"
        )
        self.helper_label.setText(f"{match.song_a.artist} vs {match.song_b.artist}")
        self.update_song_card(self.card_a, match.song_a)
        self.update_song_card(self.card_b, match.song_b)
        progress_ratio = len(self.engine.match_history) / self.total_matches if self.total_matches else 0
        self.progress_bar.setValue(int(progress_ratio * 100))

    def on_choice(self, choice: str):
        if not self.active_match or not self.engine:
            return
        winner = self.engine.resolve_match(self.active_match, choice)
        if winner:
            self.current_round_winners.append(winner)
        self.current_match_index += 1
        progress_ratio = len(self.engine.match_history) / self.total_matches if self.total_matches else 0
        self.progress_bar.setValue(int(progress_ratio * 100))
        self.display_current_match()

    def prepare_next_round(self):
        winners = self.current_round_winners
        if not winners:
            self.finish_tournament(None)
            return
        if len(winners) == 1:
            self.finish_tournament(winners[0])
            return
        self.current_round_number += 1
        next_round: List[Match] = []
        for i in range(0, len(winners), 2):
            if i + 1 < len(winners):
                next_round.append(Match(
                    round_num=self.current_round_number,
                    match_id=f"R{self.current_round_number}-M{i // 2 + 1}",
                    song_a=winners[i],
                    song_b=winners[i + 1],
                ))
        self.current_round_matches = next_round
        self.current_round_winners = []
        self.current_match_index = 0
        self.display_current_match()

    def finish_tournament(self, champion: Optional[Song]):
        self.champion = champion
        self.show_results_view()

    def show_results_view(self):
        self.clear_content()
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(12)
        self.content_layout.addWidget(container)

        if not self.champion or not self.engine:
            message = QLabel("토너먼트 결과가 존재하지 않습니다.")
            layout.addWidget(message)
            back = QPushButton("처음으로")
            back.setCursor(Qt.CursorShape.PointingHandCursor)
            back.clicked.connect(self.show_start_view)
            layout.addWidget(back, alignment=Qt.AlignmentFlag.AlignLeft)
            self.update_status("토너먼트 결과가 없습니다.")
            return

        analyzer = ResultAnalyzer(self.engine.match_history, self.candidates)
        self.report = analyzer.generate_report(self.champion)
        recommender = RecommendationEngine(self.songs, self.candidates, self.survey_profile)
        self.recommendations = recommender.generate_recommendations(self.report["top_songs"])

        champion_label = QLabel(f"우승 곡: {self.champion}")
        layout.addWidget(champion_label)
        record_label = QLabel(
            f"레이팅 {self.champion.rating:.1f} · 전적 {self.champion.wins}승 {self.champion.losses}패"
        )
        layout.addWidget(record_label)
        if self.champion.youtube_url:
            link = QLabel(f'<a href="{self.champion.youtube_url}">YouTube에서 우승 곡 듣기 ↗</a>')
            link.setTextFormat(Qt.TextFormat.RichText)
            link.setOpenExternalLinks(True)
            layout.addWidget(link)

        if self.report["top_songs"]:
            layout.addWidget(QLabel("상위 플레이리스트"))
            for idx, song in enumerate(self.report["top_songs"], 1):
                layout.addWidget(QLabel(f"{idx}. {song}"))

        stats = self.report["choice_distribution"]
        layout.addWidget(QLabel(
            f"총 매치 {self.report['total_matches']} · A {stats.get('A', 0)} · B {stats.get('B', 0)} · 둘 다 {stats.get('T', 0)} · 건너뛰기 {stats.get('S', 0)}"
        ))

        self.render_recommendations(layout)

        back_button = QPushButton("처음으로 돌아가기")
        back_button.setCursor(Qt.CursorShape.PointingHandCursor)
        back_button.clicked.connect(self.show_start_view)
        layout.addWidget(back_button, alignment=Qt.AlignmentFlag.AlignLeft)
        self.update_status("결과를 확인하고 추천곡을 감상해보세요.")

    def render_recommendations(self, layout: QVBoxLayout):
        layout.addWidget(QLabel("맞춤 추천"))
        core_recs = self.recommendations.get("core", []) if self.recommendations else []
        fresh_recs = self.recommendations.get("fresh", []) if self.recommendations else []
        if not core_recs and not fresh_recs:
            layout.addWidget(QLabel("추천할 곡이 없습니다."))
            return
        for title, entries in (("🎯 취향 저격 트랙", core_recs), ("🌱 새롭게 시도해볼 곡", fresh_recs)):
            if not entries:
                continue
            layout.addWidget(QLabel(title))
            for idx, entry in enumerate(entries, 1):
                song = entry["song"]
                reason = entry["reason"]
                layout.addWidget(QLabel(f"{idx}. {song}"))
                reason_label = QLabel(reason)
                reason_label.setWordWrap(True)
                layout.addWidget(reason_label)
                if song.youtube_url:
                    link = QLabel(f'<a href="{song.youtube_url}">YouTube에서 듣기 ↗</a>')
                    link.setTextFormat(Qt.TextFormat.RichText)
                    link.setOpenExternalLinks(True)
                    layout.addWidget(link)

    def run(self):
        if not self.valid:
            return
        self.show_start_view()
        self.show()
# ============================================================================
# 실행
# ============================================================================

def main():
    songs_file = Path("songs.json")

    if not songs_file.exists():
        print("✗ songs.json 파일을 찾을 수 없습니다. 프로젝트 루트에 파일을 추가해주세요.")
        return

    app = QApplication(sys.argv)
    gui = MusicTournamentGUI(str(songs_file))
    if not gui.valid:
        return
    gui.run()
    app.exec()


if __name__ == "__main__":
    main()
    
