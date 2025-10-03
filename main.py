"""
음악 토너먼트 취향 테스트 시스템
설문 → 후보군 압축 → 토너먼트 → 결과 분석/추천
"""

import json
import math
import random
import sys
import webbrowser
import importlib.util
import copy
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Set, Any, Iterable, Callable
from dataclasses import dataclass, field, asdict
from collections import defaultdict, Counter
from urllib.parse import urlparse, parse_qs
import numpy as np
from sklearn.cluster import KMeans, MiniBatchKMeans
from datetime import datetime
from html import escape

from PyQt6.QtCore import Qt, QMarginsF, QSizeF, QEvent, QTimer, QUrl
from PyQt6.QtGui import (
    QKeySequence,
    QShortcut,
    QPdfWriter,
    QPageSize,
    QTextDocument,
)
from PyQt6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QRadioButton,
    QScrollArea,
    QStatusBar,
    QStyle,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
    QSizePolicy,
)

WEB_ENGINE_AVAILABLE = False
MULTIMEDIA_AVAILABLE = False
QWebEngineView = None  # type: ignore
QWebEngineProfile = None  # type: ignore
QMediaPlayer = None  # type: ignore
QAudioOutput = None  # type: ignore

if importlib.util.find_spec("PyQt6.QtWebEngineWidgets"):
    from PyQt6.QtWebEngineWidgets import QWebEngineView  # type: ignore
    from PyQt6.QtWebEngineCore import QWebEngineProfile  # type: ignore

    WEB_ENGINE_AVAILABLE = True

if importlib.util.find_spec("PyQt6.QtMultimedia"):
    from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput  # type: ignore

    MULTIMEDIA_AVAILABLE = True


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


# --------------------------------------------------------------------------
# 설문 선택지 정의 (GUI/CLI 공용)
# --------------------------------------------------------------------------
SURVEY_GENRE_PAIRS: List[Tuple[Tuple[str, str, str], Tuple[str, str, str]]] = [
    (
        ("Rock", "1", "강렬한 기타 리프와 라이브 밴드 사운드 · Foo Fighters, Queen"),
        ("Pop", "2", "멜로디와 훅이 돋보이는 팝 · Taylor Swift, Dua Lipa"),
    ),
    (
        ("Hip-Hop", "1", "비트 위 랩과 그루브 중심 · Kendrick Lamar, 개코"),
        ("Electronic", "2", "신스와 전자 비트 기반 · Daft Punk, Disclosure"),
    ),
    (
        ("Jazz", "1", "즉흥과 스윙 감성 · Miles Davis, 김오키"),
        ("Classical", "2", "관현악과 서정적 선율 · 베토벤, 이루마"),
    ),
    (
        ("K-Pop", "1", "K-팝 아이돌/프로듀싱 사운드 · NewJeans, BTS"),
        ("Indie", "2", "독립 레이블의 개성 있는 음색 · 혁오, Mac DeMarco"),
    ),
]

SURVEY_ERA_OPTIONS: List[Tuple[str, str, str]] = [
    ("레트로 감성 (70-80s)", "1", "디스코·시티팝 등 빈티지한 컬러"),
    ("추억의 90-00s", "2", "발라드와 1세대 아이돌의 향수"),
    ("최신 10s 이후", "3", "트렌디한 최신 프로덕션"),
    ("시대 구애받지 않음", "4", "특정 시대보다 곡 분위기를 중시"),
]

SURVEY_ENERGY_OPTIONS: List[Tuple[str, str, str]] = [
    ("차분한 무드", "1", "잔잔한 템포와 미니멀 편성"),
    ("보통 에너지", "2", "균형 잡힌 리듬과 다이내믹"),
    ("활기찬 느낌", "3", "경쾌한 비트와 밝은 텐션"),
    ("강렬한 사운드", "4", "파워풀한 비트와 폭발감"),
]

SURVEY_POPULARITY_OPTIONS: List[Tuple[str, str, str]] = [
    ("모두가 아는 히트곡", "1", "차트 상위권의 익숙한 멜로디"),
    ("입소문이 난 곡", "2", "마니아층에서 주목받는 추천"),
    ("숨겨진 보석 찾기", "3", "니치하고 실험적인 트랙"),
]

SURVEY_LANGUAGE_OPTIONS: List[Tuple[str, str, str]] = [
    ("한국어 위주", "1", "가사 전달력과 공감을 중시"),
    ("영어/글로벌", "2", "미국·유럽 팝 신을 즐김"),
    ("언어 상관없음", "3", "언어보다 분위기를 우선"),
    ("가사보다 사운드", "4", "보컬보다 연주·사운드 집중"),
]

SURVEY_MOOD_OPTIONS: List[Tuple[str, str, str]] = [
    ("에너지 넘치는/업비트", "1", "업템포와 축제 같은 분위기"),
    ("포근하고 감성적인", "2", "따뜻하고 서정적인 감성"),
    ("그루비하고 리드미컬한", "3", "펑키한 베이스와 리듬"),
    ("잔잔하고 야간 감성", "4", "심야 감성의 차분한 흐름"),
]

SURVEY_SOUND_OPTIONS: List[Tuple[str, str, str]] = [
    ("밴드/어쿠스틱", "1", "기타·드럼이 살아있는 생동감"),
    ("신스/전자음", "2", "신스 패드와 전자 비트"),
    ("피아노/보컬 중심", "3", "피아노와 보컬의 섬세함"),
    ("재즈/브라스 그루브", "4", "브라스 섹션과 스윙 리듬"),
]

SURVEY_REGIONAL_FOCUS_OPTIONS: List[Tuple[str, str, str]] = [
    ("한국 음악만 추천해주세요", "1", "국내 아티스트 위주의 플레이리스트"),
    ("한국·아시아 중심", "2", "한국과 아시아 씬을 넓게 소개"),
    ("글로벌 다양성", "3", "전 세계 다양한 씬을 탐험"),
    ("잘 모르겠어요", "4", "지역 구분 없이 골고루 추천"),
]


def _decode_index_list(values: List[int], lookup: List[str]) -> List[str]:
    return [lookup[v] for v in values if isinstance(v, int) and 0 <= v < len(lookup)]


def _decode_index(value: int, lookup: List[str]) -> Optional[str]:
    if isinstance(value, int) and 0 <= value < len(lookup):
        return lookup[value]
    return None


def build_youtube_embed_url(url: str) -> Optional[str]:
    if not url:
        return None

    normalized = url.strip()
    if not normalized:
        return None

    parsed = urlparse(normalized)
    if not parsed.scheme:
        normalized = "https://" + normalized
        parsed = urlparse(normalized)

    host = parsed.netloc.lower()
    path = parsed.path

    # Direct embed links can be reused as-is
    if ("youtube.com" in host or "youtube-nocookie.com" in host) and path.startswith("/embed/"):
        base_host = "https://www.youtube.com" if "youtube.com" in host else "https://www.youtube-nocookie.com"
        if parsed.query:
            return f"{base_host}{path}?{parsed.query}"
        return f"{base_host}{path}"

    video_id: Optional[str] = None

    if host.endswith("youtu.be"):
        video_id = path.lstrip("/") or None
    elif "youtube.com" in host or "youtube-nocookie.com" in host:
        if path.startswith("/watch"):
            query = parse_qs(parsed.query)
            video_id = query.get("v", [None])[0]
        elif path.startswith("/shorts/"):
            video_id = path.split("/shorts/")[-1].split("/")[0]
        elif path.startswith("/v/"):
            video_id = path.split("/v/")[-1].split("/")[0]

    if not video_id:
        return None

    video_id = video_id.strip()
    if not video_id:
        return None

    return f"https://www.youtube.com/embed/{video_id}?rel=0"

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
                    meta=item.get('meta', {})
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

        def prompt_multi_selection(title: str, options: List[Tuple[str, str]]) -> List[str]:
            if not options:
                return []

            print(f"\n{title}")
            for idx, (label, _) in enumerate(options, 1):
                print(f" {idx}. {label}")
            print("   (쉼표로 여러 개 선택 · 건너뛰려면 Enter)")

            raw = input("   선택: ").strip()
            if not raw:
                return []

            values: List[str] = []
            normalized = [(label.lower(), value) for label, value in options]
            value_lookup = {value.lower(): value for _, value in options}

            for token in raw.split(','):
                choice = token.strip()
                if not choice:
                    continue
                if choice.isdigit():
                    idx = int(choice)
                    if 1 <= idx <= len(options):
                        values.append(options[idx - 1][1])
                    continue

                lowered = choice.lower()
                if lowered in value_lookup:
                    values.append(value_lookup[lowered])
                    continue

                for label, value in normalized:
                    if lowered == label:
                        values.append(value)
                        break

            return sorted(dict.fromkeys(values))

        # 1. 장르 선호도 (쌍대 비교)
        print("\n[1단계] 두 장르 중 지금 더 끌리는 쪽을 골라보세요")

        genre_scores = defaultdict(int)
        for i, pair in enumerate(SURVEY_GENRE_PAIRS, 1):
            (g1_label, g1_value, g1_desc), (g2_label, g2_value, g2_desc) = pair
            print(f"\n{i}. {g1_label} vs {g2_label}")
            print(f"   {g1_value}. {g1_label} - {g1_desc}")
            print(f"   {g2_value}. {g2_label} - {g2_desc}")
            print("   s. 잘 모르겠음 - 둘 다 좋아요 · 상황에 따라 달라요")
            choice = input("   선택 (1/2/s): ").strip()
            if choice == g1_value:
                genre_scores[g1_label] += 1
            elif choice == g2_value:
                genre_scores[g2_label] += 1

        # 2. 시대 선호도
        print("\n[2단계] 플레이리스트의 분위기를 결정할 시대감은?")
        for label, value, description in SURVEY_ERA_OPTIONS:
            print(f" {value}. {label} - {description}")
        era = input("선택: ").strip()
        era_map = {'1': 1980, '2': 2000, '3': 2015, '4': None}
        preferred_era = era_map.get(era)

        # 3. 에너지 레벨
        print("\n[3단계] 선호하는 에너지 레벨은?")
        for label, value, description in SURVEY_ENERGY_OPTIONS:
            print(f" {value}. {label} - {description}")
        energy = input("선택: ").strip()
        energy_map = {'1': 0.2, '2': 0.5, '3': 0.7, '4': 0.9}
        preferred_energy = energy_map.get(energy, 0.5)

        # 4. 음악 발견 스타일
        print("\n[4단계] 어떤 방식의 음악 발견을 더 즐기나요?")
        for label, value, description in SURVEY_POPULARITY_OPTIONS:
            print(f" {value}. {label} - {description}")
        popularity = input("선택: ").strip()
        pop_map = {'1': 0.8, '2': 0.5, '3': 0.2}
        preferred_popularity = pop_map.get(popularity, 0.5)

        # 5. 언어 선호
        print("\n[5단계] 가사 언어에 대해 어떤 취향에 가깝나요?")
        for label, value, description in SURVEY_LANGUAGE_OPTIONS:
            print(f" {value}. {label} - {description}")
        lang_choice = input("선택: ").strip()
        language_pref_map = {
            '1': {'preferred': 'ko', 'languages': {'ko'}, 'strict': False},
            '2': {'preferred': 'en', 'languages': {'en', 'es', 'fr'}, 'strict': False},
            '3': {'preferred': None, 'languages': set(), 'strict': False},
            '4': {'preferred': 'instrumental', 'languages': {'instrumental'}, 'strict': True},
        }
        language_pref = language_pref_map.get(lang_choice, {'preferred': None, 'languages': set(), 'strict': False})
        preferred_language = language_pref['preferred']

        # 6. 무드 선호
        print("\n[6단계] 이번 플레이리스트에서 느끼고 싶은 무드는?")
        for label, value, description in SURVEY_MOOD_OPTIONS:
            print(f" {value}. {label} - {description}")
        mood_choice = input("선택: ").strip()
        mood_map = {
            '1': {'moods': {'energetic', 'empowering', 'upbeat'}, 'weight': 0.9},
            '2': {'moods': {'romantic', 'dreamy', 'mellow'}, 'weight': 0.7},
            '3': {'moods': {'groovy', 'funky', 'soulful'}, 'weight': 0.8},
            '4': {'moods': {'introspective', 'nocturnal', 'melancholic'}, 'weight': 0.85},
        }
        mood_pref = mood_map.get(mood_choice, {'moods': set(), 'weight': 0.0})

        # 7. 사운드 질감
        print("\n[7단계] 어떤 사운드 질감에 더 마음이 가나요?")
        for label, value, description in SURVEY_SOUND_OPTIONS:
            print(f" {value}. {label} - {description}")
        sound_choice = input("선택: ").strip()
        sound_map = {
            '1': {'instrumentations': {'guitar', 'drums', 'bass', 'vocals'}},
            '2': {'instrumentations': {'synth', 'electronic_beats', 'samples'}},
            '3': {'instrumentations': {'piano', 'strings', 'vocals'}},
            '4': {'instrumentations': {'saxophone', 'trumpet', 'bass'}},
        }
        sound_pref = sound_map.get(sound_choice, {'instrumentations': set()})

        # 8. 지역/씬 집중도
        print("\n[8단계] 특정 지역의 음악에 마음이 가나요?")
        for label, value, description in SURVEY_REGIONAL_FOCUS_OPTIONS:
            print(f" {value}. {label} - {description}")
        regional_choice = input("선택: ").strip()
        regional_focus_map = {
            '1': 'k_only',
            '2': 'k_prefer',
            '3': 'global',
            '4': 'neutral',
        }
        regional_focus = regional_focus_map.get(regional_choice, 'neutral')

        genre_options = sorted({name for name in GENRE_CODE_TABLE.values()})
        genre_pairs = [(label, label) for label in genre_options]
        mood_pairs = [
            (mood.replace('_', ' ').title(), mood)
            for mood in MOODS
        ]
        instrumentation_pairs = [
            (inst.replace('_', ' ').title(), inst)
            for inst in INSTRUMENTATIONS
        ]

        excluded_genres = prompt_multi_selection(
            "[9단계] 이번 플레이리스트에서 피하고 싶은 장르가 있다면 골라주세요",
            genre_pairs,
        )
        excluded_moods = prompt_multi_selection(
            "[10단계] 피하고 싶은 무드가 있다면 선택해주세요",
            mood_pairs,
        )
        excluded_instrumentations = prompt_multi_selection(
            "[11단계] 듣고 싶지 않은 편성/악기가 있나요?",
            instrumentation_pairs,
        )

        profile = {
            'genre_scores': dict(genre_scores),
            'preferred_era': preferred_era,
            'preferred_energy': preferred_energy,
            'preferred_popularity': preferred_popularity,
            'preferred_language': preferred_language,
            'preferred_languages': sorted(language_pref['languages']),
            'language_strict': language_pref['strict'],
            'preferred_moods': sorted(mood_pref['moods']),
            'mood_weight': mood_pref['weight'],
            'preferred_instrumentations': sorted(sound_pref['instrumentations']),
            'regional_focus': regional_focus,
            'excluded_genres': excluded_genres,
            'excluded_moods': excluded_moods,
            'excluded_instrumentations': excluded_instrumentations,
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
        def _profile_set(key: str) -> Set[str]:
            values = self.profile.get(key)
            if isinstance(values, (list, tuple, set)):
                return {str(item) for item in values if isinstance(item, str) and item}
            return set()

        excluded_genres = _profile_set('excluded_genres')
        excluded_moods = _profile_set('excluded_moods')
        excluded_instrumentations = _profile_set('excluded_instrumentations')

        song_tags = song.tags if isinstance(song.tags, dict) else {}
        song_genres = {genre for genre in (song.genres or []) if isinstance(genre, str)}
        if excluded_genres and song_genres & excluded_genres:
            return float('-inf')

        song_moods = {
            mood for mood in (song_tags.get('mood') or []) if isinstance(mood, str)
        }
        if excluded_moods and song_moods & excluded_moods:
            return float('-inf')

        song_instrumentations = {
            inst for inst in (song_tags.get('instrumentation') or []) if isinstance(inst, str)
        }
        if excluded_instrumentations and song_instrumentations & excluded_instrumentations:
            return float('-inf')

        score = 0.0
        language = song_tags.get('language')

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
            elif preferred_language == 'instrumental' and language != 'instrumental':
                score -= 0.2
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

        preferred_moods = set(self.profile.get('preferred_moods') or [])
        mood_weight = float(self.profile.get('mood_weight') or 0.0)
        if preferred_moods:
            song_moods = set(song.tags.get('mood') or [])
            if song_moods:
                overlap = preferred_moods & song_moods
                if overlap:
                    score += 0.3 + mood_weight * 0.4 + 0.05 * max(0, len(overlap) - 1)
                else:
                    score -= 0.1 * max(1.0, mood_weight)

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

        preferred_instrumentations = set(self.profile.get('preferred_instrumentations') or [])
        if preferred_instrumentations:
            song_instrumentations = set(song.tags.get('instrumentation') or [])
            if song_instrumentations:
                overlap = preferred_instrumentations & song_instrumentations
                if overlap:
                    score += 0.25 + 0.1 * len(overlap)
                else:
                    score -= 0.05

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

class PreferenceSummarizer:
    """토너먼트 결과를 바탕으로 취향을 한 문장으로 묘사한다."""

    GENRE_LABELS = {
        "Rock": "록",
        "Pop": "팝",
        "Electronic": "일렉트로닉",
        "Hip Hop": "힙합",
        "Jazz": "재즈",
        "Classical": "클래식",
        "Progressive Rock": "프로그레시브 록",
        "Art Rock": "아트 록",
        "Grunge": "그런지",
        "Psychedelic Rock": "사이키델릭 록",
        "Alternative Rock": "얼터너티브 록",
        "Indie Folk": "인디 포크",
        "Classic Rock": "클래식 록",
        "Dance Pop": "댄스 팝",
        "K-Indie Pop": "케이 인디 팝",
        "R&B Pop": "알앤비 팝",
        "Synth Pop": "신스 팝",
        "Electropop": "일렉트로팝",
    }

    SUBGENRE_TONES = {
        "alt_pop": "대담한 얼터 팝",
        "alternative_r&b": "대체 R&B",
        "alternative_rock": "거친 얼터 록",
        "ambient": "미세한 앰비언트 텍스처",
        "art_pop": "예술적 팝 감각",
        "chillhop": "느긋한 칠합",
        "dance_pop": "반짝이는 댄스 팝",
        "edm_pop": "EDM 팝",
        "electronic": "전자음 레이어",
        "electropop": "전자 팝",
        "future_bass": "반짝이는 퓨처 베이스",
        "grunge": "거친 그런지",
        "indie_folk": "포근한 인디 포크",
        "indie_rock": "인디 록",
        "jazz_hop": "재지한 재즈합",
        "k_indie": "케이 인디",
        "k_r&b": "케이 알앤비",
        "kpop": "케이팝",
        "lo_fi": "로파이 질감",
        "neo_soul": "네오 소울",
        "progressive_rock": "기교적인 프로그 록",
        "psychedelic_pop": "사이키델릭 팝",
        "psychedelic_rock": "몽환 록",
        "synth_pop": "신스 팝",
        "synthwave": "신스웨이브",
        "trip_hop": "몽환적인 트립합",
    }

    LANGUAGE_LABELS = {
        "en": "영어",
        "es": "스페인어",
        "fr": "프랑스어",
        "instrumental": "가사 없이",
        "ko": "한국어",
    }

    INSTRUMENT_TONES = {
        "synth": "신시사이저",
        "guitar": "기타 리프",
        "piano": "피아노 선율",
        "strings": "스트링 편곡",
        "bass": "베이스 그루브",
        "808": "808 베이스",
        "drums": "라이브 드럼",
        "electronic_beats": "전자 비트",
        "percussion": "퍼커션 결",
        "vocals": "보컬 하모니",
        "keyboards": "키보드 사운드",
    }

    _TERM_GLOSSARY: Dict[str, Dict[str, str]] = {}

    @classmethod
    def glossary(cls) -> Dict[str, Dict[str, str]]:
        if cls._TERM_GLOSSARY:
            return cls._TERM_GLOSSARY

        glossary: Dict[str, Dict[str, str]] = {}

        for code, label in cls.GENRE_LABELS.items():
            glossary[code] = {
                "label": label,
                "description": f"{label} 장르의 정서를 의미해요 (원문: {code}).",
            }

        for code, tone in cls.SUBGENRE_TONES.items():
            pretty = code.replace("_", " ")
            glossary[code] = {
                "label": tone,
                "description": f"{tone} 무드는 세부 장르 '{pretty}'의 매력을 설명합니다.",
            }

        for code, tone in cls.INSTRUMENT_TONES.items():
            glossary[code] = {
                "label": tone,
                "description": f"{tone} 사운드가 편성의 핵심이라는 뜻이에요.",
            }

        cls._TERM_GLOSSARY = glossary
        return cls._TERM_GLOSSARY

    @staticmethod
    def _normalize_profile(profile: Optional[Dict[str, Any]]) -> Dict[str, Set[str]]:
        keys = [
            "preferred_moods",
            "preferred_instrumentations",
            "preferred_languages",
            "excluded_genres",
            "excluded_moods",
            "excluded_instrumentations",
        ]
        normalized: Dict[str, Set[str]] = {key: set() for key in keys}
        normalized["preferred_language"] = set()

        if not isinstance(profile, dict):
            return normalized

        for key in keys:
            values = profile.get(key)
            if isinstance(values, (list, tuple, set)):
                normalized[key] = {str(value) for value in values if isinstance(value, str) and value}

        preferred_language = profile.get("preferred_language")
        if isinstance(preferred_language, str) and preferred_language:
            normalized["preferred_language"] = {preferred_language}

        return normalized

    @staticmethod
    def _format_human_list(values: Iterable[str]) -> str:
        items = [str(value) for value in values if value]
        if not items:
            return ""
        preview = items[:3]
        text = ", ".join(preview)
        if len(items) > 3:
            text += " 등"
        return text

    def _describe_exclusions(self, profile_info: Dict[str, Set[str]]) -> Optional[str]:
        if not isinstance(profile_info, dict):
            return None

        fragments: List[str] = []

        excluded_genres = profile_info.get("excluded_genres") or set()
        if excluded_genres:
            labels = [self._genre_label(value) for value in sorted(excluded_genres)]
            label_text = self._format_human_list(labels)
            if label_text:
                fragments.append(f"{label_text} 장르")

        excluded_moods = profile_info.get("excluded_moods") or set()
        if excluded_moods:
            labels = [
                self.MOOD_DESCRIPTIONS.get(value, value.replace('_', ' ').title())
                for value in sorted(excluded_moods)
            ]
            label_text = self._format_human_list(labels)
            if label_text:
                fragments.append(f"{label_text} 무드")

        excluded_instruments = profile_info.get("excluded_instrumentations") or set()
        if excluded_instruments:
            labels = [
                self.INSTRUMENT_TONES.get(value, value.replace('_', ' ').title())
                for value in sorted(excluded_instruments)
            ]
            label_text = self._format_human_list(labels)
            if label_text:
                fragments.append(f"{label_text} 편성")

        if not fragments:
            return None

        phrase = " · ".join(fragments)
        return f"또한 {phrase}은(는) 되도록 피하고 싶어해요"

    def summarize(
        self,
        champion: Optional[Song],
        top_songs: List[Song],
        profile: Optional[Dict[str, Any]] = None,
    ) -> str:
        songs: List[Song] = []
        if champion:
            songs.append(champion)
        songs.extend(song for song in top_songs if song and song is not champion)
        songs = [s for s in songs if s]

        if not songs:
            return "취향 데이터를 확인할 수 없어 요약을 생성하지 못했습니다."

        features = self._analyze_features(songs, champion)
        profile_info = self._normalize_profile(profile)

        body_clauses = [self._intro_clause(champion)]
        for builder in (
            self._describe_genre,
            self._describe_energy_mood,
            self._describe_era,
            self._describe_language,
            self._describe_instrumentation,
        ):
            clause = builder(features)
            if clause:
                body_clauses.append(clause)
        exclusion_clause = self._describe_exclusions(profile_info)
        if exclusion_clause:
            body_clauses.append(exclusion_clause)

        tail = self._tail_clause(features)

        sentence_body = ", ".join(part.strip(" ,") for part in body_clauses if part)
        if tail and sentence_body:
            sentence = f"{sentence_body}, {tail}"
        else:
            sentence = tail or sentence_body

        if not sentence.endswith("."):
            sentence += "."
        return sentence

    def _analyze_features(self, songs: List[Song], champion: Optional[Song]) -> Dict[str, Any]:
        genre_counter: Counter = Counter()
        subgenre_counter: Counter = Counter()
        language_counter: Counter = Counter()
        instrument_counter: Counter = Counter()
        mood_counter: Counter = Counter()

        energy_values: List[float] = []
        valence_values: List[float] = []
        era_values: List[int] = []

        for song in songs:
            genres = song.genres or []
            if genres:
                weight = 1.0 / len(genres)
                for genre in genres:
                    genre_counter[genre] += weight

            subgenres = song.tags.get("subgenres") or []
            if isinstance(subgenres, list) and subgenres:
                weight = 1.0 / len(subgenres)
                for subgenre in subgenres:
                    if isinstance(subgenre, str):
                        subgenre_counter[subgenre] += weight

            language = song.tags.get("language")
            if isinstance(language, str):
                language_counter[language] += 1

            instrumentation = song.tags.get("instrumentation") or []
            if isinstance(instrumentation, list) and instrumentation:
                weight = 1.0 / len(instrumentation)
                for inst in instrumentation:
                    if isinstance(inst, str):
                        instrument_counter[inst] += weight

            moods = song.tags.get("mood") or []
            if isinstance(moods, list) and moods:
                weight = 1.0 / len(moods)
                for mood in moods:
                    if isinstance(mood, str):
                        mood_counter[mood] += weight

            energy = song.tags.get("energy")
            if isinstance(energy, (int, float)):
                energy_values.append(float(energy))

            valence = song.tags.get("valence")
            if isinstance(valence, (int, float)):
                valence_values.append(float(valence))

            era = song.tags.get("era_year")
            if isinstance(era, int):
                era_values.append(era)

        def ratio(counter: Counter) -> List[Tuple[str, float]]:
            total = sum(counter.values())
            if not total:
                return []
            return [(key, counter[key] / total) for key in counter]

        genre_ratios = sorted(ratio(genre_counter), key=lambda x: x[1], reverse=True)
        subgenre_ratios = sorted(ratio(subgenre_counter), key=lambda x: x[1], reverse=True)
        instrument_ratios = sorted(ratio(instrument_counter), key=lambda x: x[1], reverse=True)
        language_ratios = sorted(ratio(language_counter), key=lambda x: x[1], reverse=True)

        features: Dict[str, Any] = {
            "champion": champion,
            "genre_ratios": genre_ratios,
            "subgenre_ratios": subgenre_ratios,
            "instrument_ratios": instrument_ratios,
            "language_ratios": language_ratios,
            "mood_counter": mood_counter,
            "energy_avg": sum(energy_values) / len(energy_values) if energy_values else None,
            "valence_avg": sum(valence_values) / len(valence_values) if valence_values else None,
            "era_values": era_values,
        }
        return features

    def _intro_clause(self, champion: Optional[Song]) -> str:
        if champion:
            return f"결승에서 {champion.artist}의 \"{champion.get_display_title()}\"을(를) 선택한 걸 보면"
        return "상위 곡들의 공통점을 살펴보면"

    def _describe_genre(self, features: Dict[str, Any]) -> Optional[str]:
        genre_ratios: List[Tuple[str, float]] = features["genre_ratios"]
        subgenre_ratios: List[Tuple[str, float]] = features["subgenre_ratios"]
        if not genre_ratios:
            return None

        primary_genre, primary_ratio = genre_ratios[0]
        secondary_clause = None
        if len(genre_ratios) > 1:
            secondary_genre, secondary_ratio = genre_ratios[1]
            if abs(primary_ratio - secondary_ratio) <= 0.12:
                secondary_clause = f"{self._genre_label(primary_genre)}와(과) {self._genre_label(secondary_genre)}을(를) 두루 즐기고"
        if not secondary_clause:
            if primary_ratio >= 0.65:
                secondary_clause = f"{self._genre_label(primary_genre)} 중심의 취향이고"
            elif primary_ratio >= 0.5:
                secondary_clause = f"{self._genre_label(primary_genre)}을(를) 주축으로 삼고"
            else:
                secondary_clause = f"{self._genre_label(primary_genre)}을(를) 기반으로 다양하게 즐기고"

        accent = None
        if subgenre_ratios:
            subgenre, sub_ratio = subgenre_ratios[0]
            if sub_ratio >= 0.25:
                accent = f"특히 {self._subgenre_label(subgenre)} 무드를 놓치지 않는 편이며"

        if accent:
            return f"{secondary_clause} {accent}".strip()
        return secondary_clause

    def _describe_energy_mood(self, features: Dict[str, Any]) -> Optional[str]:
        energy = features.get("energy_avg")
        valence = features.get("valence_avg")
        if energy is None and valence is None:
            return None

        energy_clause = None
        if energy >= 0.75:
            energy_clause = "에너지는 강하게 끌어올리고"
        elif energy >= 0.6:
            energy_clause = "에너지는 단단한 비트에 기대고"
        elif energy >= 0.48:
            energy_clause = "에너지는 차분하게 유지하고"
        else:
            energy_clause = "에너지는 잔잔하게 두고"

        valence_clause = None
        if valence is not None:
            if valence >= 0.68:
                valence_clause = "감정선은 밝고 경쾌한 쪽을 찾는 편"
            elif valence >= 0.54:
                valence_clause = "감정선은 명암을 고르게 섞는 편"
            elif valence >= 0.42:
                valence_clause = "감정선은 살짝 어두운 기운을 남겨두고"
            else:
                valence_clause = "감정선은 짙고 서늘한 편"

        clauses = [c for c in (energy_clause, valence_clause) if c]
        return " ".join(clauses) if clauses else None

    def _describe_era(self, features: Dict[str, Any]) -> Optional[str]:
        era_values: List[int] = features.get("era_values") or []
        if not era_values:
            return None

        min_year = min(era_values)
        max_year = max(era_values)
        avg_year = sum(era_values) / len(era_values)
        spread = max_year - min_year

        anchor = self._era_anchor(avg_year)
        if spread <= 6:
            return f"감성은 {anchor} 즈음에 주로 머물고"
        if spread <= 15:
            return f"감성은 {anchor}을 중심으로 약간 넓게 펼쳐지고"
        return f"감성은 {min_year}년부터 {max_year}년대까지 폭넓게 이어지고"

    def _describe_language(self, features: Dict[str, Any]) -> Optional[str]:
        language_ratios: List[Tuple[str, float]] = features["language_ratios"]
        if not language_ratios:
            return None
        primary_language, primary_ratio = language_ratios[0]
        label = self.LANGUAGE_LABELS.get(primary_language, primary_language)
        diversity = sum(1 for _ in language_ratios)

        if primary_language == "instrumental":
            if primary_ratio >= 0.6:
                return "언어는 가사 없는 트랙에서 편안함을 느끼고"
            return "언어는 가사 없는 트랙을 슬쩍 끼워 넣고"

        if primary_ratio >= 0.7:
            return f"언어는 {label} 보컬일 때 가장 좋은 편"
        if primary_ratio >= 0.5:
            return f"언어는 {label}를 중심에 두되 다른 언어도 기꺼이 받아들이고"
        if diversity >= 3:
            return "언어 장벽은 거의 느끼지 않고"
        return f"언어는 {label}를 포함해 자유롭게 넘나들고"

    def _describe_instrumentation(self, features: Dict[str, Any]) -> Optional[str]:
        instrument_ratios: List[Tuple[str, float]] = features["instrument_ratios"]
        if not instrument_ratios:
            return None
        primary_inst, primary_ratio = instrument_ratios[0]
        tone = self.INSTRUMENT_TONES.get(primary_inst)
        if not tone:
            tone = primary_inst.replace("_", " ")

        if primary_ratio >= 0.55:
            return f"사운드는 {tone}가 중심을 잡고"
        if primary_ratio >= 0.38:
            return f"사운드는 {tone}에 은근히 무게를 두고"
        return None

    def _tail_clause(self, features: Dict[str, Any]) -> str:
        energy = features.get("energy_avg")
        valence = features.get("valence_avg")
        if energy is None and valence is None:
            return "이런 취향이 선명하게 드러납니다"

        if energy is not None and valence is not None and energy >= 0.72 and valence >= 0.6:
            return "밝고 활기찬 곡을 주로 선호합니다"
        if energy is not None and valence is not None and energy >= 0.7 and valence < 0.5:
            return "강한 리듬과 어두운 분위기의 곡을 즐깁니다"
        if energy is not None and valence is not None and energy <= 0.45 and valence >= 0.55:
            return "부드럽고 따뜻한 멜로디에 끌립니다"
        if energy is not None and valence is not None and energy <= 0.45 and valence < 0.5:
            return "차분하고 어두운 곡을 선호합니다"
        if energy is not None and valence is None:
            if energy >= 0.7:
                return "리듬감 있는 곡을 좋아합니다"
            if energy <= 0.45:
                return "잔잔한 곡을 오래 듣는 편입니다"
            return "균형 잡힌 비트를 편안하게 즐깁니다"
        if valence is not None and energy is None:
            if valence >= 0.6:
                return "밝고 낙관적인 정서를 선호합니다"
            if valence < 0.45:
                return "차갑고 서늘한 정서를 선호합니다"
            return "감정의 균형을 유지하는 곡을 좋아합니다"
        return "이런 취향이 잘 드러납니다"

    def _genre_label(self, genre: str) -> str:
        return self.GENRE_LABELS.get(genre, genre)

    def _subgenre_label(self, subgenre: str) -> str:
        return self.SUBGENRE_TONES.get(subgenre, subgenre.replace("_", " "))

    def _era_anchor(self, year: float) -> str:
        if year >= 2018:
            return "2010년대 후반 이후"
        if year >= 2012:
            return "2010년대 중반"
        if year >= 2006:
            return "2000년대 후반"
        if year >= 1998:
            return "90년대 말~2000년대 초"
        if year >= 1990:
            return "90년대 초중반"
        if year >= 1980:
            return "80년대"
        if year >= 1970:
            return "70년대"
        return "60년대 이전"

# ============================================================================
# 결과 분석
# ============================================================================

class ResultAnalyzer:
    def __init__(
        self,
        match_history: List[Match],
        all_songs: List[Song],
        survey_profile: Optional[Dict[str, Any]] = None,
    ):
        self.match_history = match_history
        self.all_songs = all_songs
        self.survey_profile = survey_profile or {}

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

        summarizer = PreferenceSummarizer()
        preference_summary = summarizer.summarize(champion, participated[:5], self.survey_profile)

        print(f"\n🧭 취향 한 줄 요약: {preference_summary}")

        return {
            'champion': champion,
            'top_songs': participated[:5],
            'total_matches': total_matches,
            'choice_distribution': dict(choice_counts),
            'preference_summary': preference_summary
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
        def _to_set(key: str) -> Set[str]:
            values = self.profile.get(key)
            if isinstance(values, (list, tuple, set)):
                return {str(item) for item in values if isinstance(item, str) and item}
            return set()
        self.language_whitelist: Set[str] = _to_set('preferred_languages')
        self.language_strict: bool = bool(self.profile.get('language_strict') and self.language_whitelist)
        self.preferred_language: Optional[str] = self.profile.get('preferred_language')
        self.regional_focus: str = self.profile.get('regional_focus', 'neutral')
        self.preferred_moods: Set[str] = _to_set('preferred_moods')
        self.mood_weight: float = float(self.profile.get('mood_weight') or 0.0)
        self.preferred_instrumentations: Set[str] = _to_set('preferred_instrumentations')
        self.excluded_genres: Set[str] = _to_set('excluded_genres')
        self.excluded_moods: Set[str] = _to_set('excluded_moods')
        self.excluded_instrumentations: Set[str] = _to_set('excluded_instrumentations')
        self.selector = CandidateSelector(all_songs, self.profile)

        self._genre_index = self._build_index(
            genre for song in all_songs for genre in (song.genres or []) if genre
        )
        self._mood_index = self._build_index(
            mood for song in all_songs for mood in (song.tags.get('mood') or []) if mood
        )
        self._feature_cache: Dict[str, np.ndarray] = {}
        self._cluster_labels: Dict[str, int] = {}
        self._cluster_model: Optional[Any] = None
        self._clusters_ready: bool = False

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

        self._ensure_clusters()
        winner_clusters = Counter()
        for winner in top_winners:
            label = self._cluster_labels.get(winner.id)
            if label is not None:
                winner_clusters[label] += 1

        dominant_clusters: Set[int] = {label for label, _ in winner_clusters.most_common(2)}
        cluster_balance_enabled = bool(self._cluster_labels) and bool(dominant_clusters)

        scored_entries: List[Dict[str, Any]] = []
        for song in candidates:
            if self._violates_exclusions(song):
                continue
            base_score = self.selector.compute_base_score(song, self.language_whitelist, self.language_strict)
            if base_score == float('-inf'):
                continue

            similarity_score, anchor, shared_tags = self._analyze_similarity(song, top_winners)

            if base_score <= 0 and similarity_score <= 0:
                continue

            cluster_label = self._cluster_labels.get(song.id)

            language_note = self._describe_language_fit(song)
            region_note = self._describe_region_fit(song)
            freshness_score, freshness_note = self._freshness_profile(song)
            mood_note = self._describe_mood_fit(song)
            instrumentation_note = self._describe_instrumentation_fit(song)
            exclusion_note = self._describe_exclusion_alignment(song)

            scored_entries.append({
                'song': song,
                'score': base_score + similarity_score,
                'freshness': freshness_score,
                'anchor': anchor,
                'shared_tags': shared_tags,
                'language_note': language_note,
                'region_note': region_note,
                'freshness_note': freshness_note,
                'mood_note': mood_note,
                'instrumentation_note': instrumentation_note,
                'exclusion_note': exclusion_note,
                'cluster_label': cluster_label,
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

        def select_balanced(entries: List[Dict[str, Any]], count: int) -> List[Dict[str, Any]]:
            if count <= 0:
                return []

            filtered = [entry for entry in entries if entry['song'].id not in used_ids]
            if not filtered:
                return []

            if not cluster_balance_enabled:
                return filtered[:count]

            new_cluster: List[Dict[str, Any]] = []
            familiar_cluster: List[Dict[str, Any]] = []
            for entry in filtered:
                label = entry.get('cluster_label')
                if label is not None and label not in dominant_clusters:
                    new_cluster.append(entry)
                else:
                    familiar_cluster.append(entry)

            selected: List[Dict[str, Any]] = []
            new_target = min(len(new_cluster), max(1, math.ceil(count * 0.5))) if new_cluster else 0
            selected.extend(new_cluster[:new_target])

            if len(selected) < count:
                selected.extend(familiar_cluster[:count - len(selected)])

            if len(selected) < count and len(new_cluster) > new_target:
                selected.extend(new_cluster[new_target:new_target + (count - len(selected))])

            return selected[:count]

        selected_fresh_entries = select_balanced(fresh_candidates, n_fresh)
        for entry in selected_fresh_entries:
            if cluster_balance_enabled:
                label = entry.get('cluster_label')
                if label is not None and label not in dominant_clusters:
                    entry['cluster_note'] = "새로운 군집 탐색으로 발견한 사운드"
            formatted = self._format_entry(entry, category='fresh')
            fresh_recs.append(formatted)
            used_ids.add(entry['song'].id)

        if len(fresh_recs) < n_fresh:
            remaining = [entry for entry in scored_entries if entry['song'].id not in used_ids]
            additional_entries = select_balanced(remaining, n_fresh - len(fresh_recs))
            for entry in additional_entries:
                if cluster_balance_enabled:
                    label = entry.get('cluster_label')
                    if label is not None and label not in dominant_clusters:
                        entry['cluster_note'] = "새로운 군집 탐색으로 발견한 사운드"
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

    @staticmethod
    def _build_index(values: Iterable[str]) -> Dict[str, int]:
        unique_values = [value for value in dict.fromkeys(values)]
        return {value: idx for idx, value in enumerate(unique_values)}

    def _violates_exclusions(self, song: Song) -> bool:
        if not (self.excluded_genres or self.excluded_moods or self.excluded_instrumentations):
            return False

        tags = song.tags if isinstance(song.tags, dict) else {}
        if self.excluded_genres and any(
            isinstance(genre, str) and genre in self.excluded_genres
            for genre in (song.genres or [])
        ):
            return True

        if self.excluded_moods and any(
            isinstance(mood, str) and mood in self.excluded_moods
            for mood in (tags.get('mood') or [])
        ):
            return True

        if self.excluded_instrumentations and any(
            isinstance(inst, str) and inst in self.excluded_instrumentations
            for inst in (tags.get('instrumentation') or [])
        ):
            return True

        return False

    @staticmethod
    def _format_exclusion_values(values: Set[str], formatter: Optional[Callable[[str], str]] = None) -> Optional[str]:
        if not values:
            return None
        labels: List[str] = []
        for value in sorted(values):
            if not isinstance(value, str):
                continue
            if formatter:
                label = formatter(value)
            else:
                label = value.replace('_', ' ').title()
            if label:
                labels.append(label)
        if not labels:
            return None
        preview = labels[:3]
        text = ", ".join(preview)
        if len(labels) > 3:
            text += " 등"
        return text

    def _describe_exclusion_alignment(self, song: Song) -> Optional[str]:
        if not (self.excluded_genres or self.excluded_moods or self.excluded_instrumentations):
            return None

        tags = song.tags if isinstance(song.tags, dict) else {}
        fragments: List[str] = []

        if self.excluded_genres and not any(
            isinstance(genre, str) and genre in self.excluded_genres
            for genre in (song.genres or [])
        ):
            text = self._format_exclusion_values(self.excluded_genres, lambda value: value)
            if text:
                fragments.append(f"장르 {text}")

        if self.excluded_moods and not any(
            isinstance(mood, str) and mood in self.excluded_moods
            for mood in (tags.get('mood') or [])
        ):
            text = self._format_exclusion_values(
                self.excluded_moods,
                lambda value: value.replace('_', ' ').title(),
            )
            if text:
                fragments.append(f"무드 {text}")

        if self.excluded_instrumentations and not any(
            isinstance(inst, str) and inst in self.excluded_instrumentations
            for inst in (tags.get('instrumentation') or [])
        ):
            text = self._format_exclusion_values(
                self.excluded_instrumentations,
                lambda value: value.replace('_', ' ').title(),
            )
            if text:
                fragments.append(f"편성 {text}")

        if not fragments:
            return None

        joined = " · ".join(fragments)
        return f"제외 요청한 조건 충족: {joined}"

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

    def _describe_mood_fit(self, song: Song) -> Optional[str]:
        if not self.preferred_moods:
            return None

        song_moods = set(song.tags.get('mood') or [])
        if not song_moods:
            return None

        overlap = sorted(self.preferred_moods & song_moods)
        if not overlap:
            return None

        friendly = [self._format_tag_name(tag) for tag in overlap[:2]]
        if len(friendly) == 1:
            return f"선호 무드 {friendly[0]} 감성 반영"
        return f"원하는 무드 {', '.join(friendly)}를 살린 트랙"

    def _describe_instrumentation_fit(self, song: Song) -> Optional[str]:
        if not self.preferred_instrumentations:
            return None

        song_instrumentations = set(song.tags.get('instrumentation') or [])
        if not song_instrumentations:
            return None

        overlap = sorted(self.preferred_instrumentations & song_instrumentations)
        if not overlap:
            return None

        friendly = [self._format_tag_name(tag) for tag in overlap[:2]]
        return f"선호 사운드 ({', '.join(friendly)})와 잘 맞아요"

    @staticmethod
    def _format_tag_name(tag: str) -> str:
        return tag.replace('_', ' ').title()

    def _build_feature_vector(self, song: Song) -> np.ndarray:
        if song.id in self._feature_cache:
            return self._feature_cache[song.id]

        genre_vec = np.zeros(len(self._genre_index), dtype=float)
        for genre in song.genres or []:
            idx = self._genre_index.get(genre)
            if idx is not None:
                genre_vec[idx] = 1.0

        mood_vec = np.zeros(len(self._mood_index), dtype=float)
        song_moods = song.tags.get('mood') or []
        if song_moods:
            weight = 1.0 / len(song_moods)
            for mood in song_moods:
                idx = self._mood_index.get(mood)
                if idx is not None:
                    mood_vec[idx] += weight

        def safe_float(value: Any) -> float:
            return float(value) if isinstance(value, (int, float)) else 0.0

        energy = safe_float(song.tags.get('energy'))
        valence = safe_float(song.tags.get('valence'))
        balance = energy - valence
        tempo = safe_float(song.tags.get('tempo_bpm')) / 200.0
        era_norm = safe_float(song.tags.get('era_year')) / 2100.0
        awareness = safe_float(song.popularity.get('awareness_idx'))
        yt_views = safe_float(song.popularity.get('yt_views'))
        log_views = math.log10(yt_views + 1.0) / 8.0 if yt_views > 0 else 0.0
        duration_norm = safe_float((song.meta or {}).get('duration_sec')) / 600.0

        numeric_features = np.array([
            energy,
            valence,
            balance,
            tempo,
            era_norm,
            awareness,
            log_views,
            duration_norm,
        ], dtype=float)

        segments: List[np.ndarray] = []
        if genre_vec.size:
            segments.append(genre_vec)
        if mood_vec.size:
            segments.append(mood_vec)
        segments.append(numeric_features)

        feature_vector = np.concatenate(segments) if len(segments) > 1 else segments[0]
        self._feature_cache[song.id] = feature_vector
        return feature_vector

    def _ensure_clusters(self):
        if self._clusters_ready:
            return

        feature_matrix: List[np.ndarray] = []
        songs_for_clustering: List[Song] = []
        for song in self.all_songs:
            vector = self._build_feature_vector(song)
            if vector.size == 0:
                continue
            feature_matrix.append(vector)
            songs_for_clustering.append(song)

        if not songs_for_clustering:
            self._clusters_ready = True
            return

        if len(songs_for_clustering) == 1:
            self._cluster_labels[songs_for_clustering[0].id] = 0
            self._clusters_ready = True
            return

        matrix = np.vstack(feature_matrix)
        n_songs = len(songs_for_clustering)

        profile_k = self.profile.get('cluster_count') if isinstance(self.profile, dict) else None
        n_clusters = 0
        if isinstance(profile_k, int) and profile_k >= 2:
            n_clusters = min(profile_k, n_songs)

        if not n_clusters:
            heuristic = max(2, int(round(math.sqrt(n_songs))))
            n_clusters = min(max(2, heuristic), min(20, n_songs))

        if n_clusters > n_songs:
            n_clusters = n_songs

        if n_clusters <= 1:
            for idx, song in enumerate(songs_for_clustering):
                self._cluster_labels[song.id] = idx
            self._clusters_ready = True
            return

        if n_songs > 80:
            model = MiniBatchKMeans(
                n_clusters=n_clusters,
                random_state=42,
                batch_size=min(256, n_songs),
                n_init=10,
            )
        else:
            model = KMeans(
                n_clusters=n_clusters,
                random_state=42,
                n_init=10,
            )

        labels = model.fit_predict(matrix)
        for song, label in zip(songs_for_clustering, labels):
            self._cluster_labels[song.id] = int(label)

        self._cluster_model = model
        self._clusters_ready = True

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

        mood_note = entry.get('mood_note')
        if mood_note:
            parts.append(mood_note)

        instrumentation_note = entry.get('instrumentation_note')
        if instrumentation_note:
            parts.append(instrumentation_note)

        exclusion_note = entry.get('exclusion_note')
        if exclusion_note:
            parts.append(exclusion_note)

        cluster_note = entry.get('cluster_note')
        if cluster_note:
            parts.append(cluster_note)

        freshness_note = entry.get('freshness_note')
        if freshness_note and (category == 'fresh' or entry.get('freshness', 0) >= 0.5):
            parts.append(freshness_note)

        usage_tip = self._suggest_usage_context(song)
        if usage_tip:
            parts.append(f"이 곡은 언제 어울려요: {usage_tip}")

        unique_parts = list(dict.fromkeys(parts))
        reason = " / ".join(unique_parts) if unique_parts else "토너먼트 기록 기반으로 엄선했어요"

        return {
            'song': song,
            'reason': reason,
            'category': category,
            'usage_tip': usage_tip,
        }

    def _suggest_usage_context(self, song: Song) -> Optional[str]:
        tags = song.tags if isinstance(song.tags, dict) else {}

        def as_float(value: Any) -> Optional[float]:
            return float(value) if isinstance(value, (int, float)) else None

        energy = as_float(tags.get('energy'))
        valence = as_float(tags.get('valence'))
        tempo = as_float(tags.get('tempo_bpm'))
        moods = [m for m in (tags.get('mood') or []) if isinstance(m, str)]

        if energy is not None and valence is not None:
            if energy >= 0.72 and valence >= 0.55:
                return "출근길이나 운동 전에 기분을 끌어올리고 싶을 때"
            if energy >= 0.7 and valence < 0.5:
                return "격하게 집중하거나 러닝으로 텐션을 끌어올리고 싶을 때"
            if energy <= 0.4 and valence >= 0.55:
                return "늦은 저녁 포근하게 휴식하고 싶을 때"
            if energy <= 0.4 and valence < 0.45:
                return "새벽 감성으로 잔잔하게 몰입하고 싶을 때"

        if energy is not None:
            if energy >= 0.65:
                return "주말 드라이브처럼 에너지가 필요할 때"
            if energy <= 0.35:
                return "집에서 조용히 쉬고 싶을 때"

        if valence is not None:
            if valence >= 0.65:
                return "마음이 가벼워지는 밝은 순간을 만들고 싶을 때"
            if valence <= 0.4:
                return "차분한 분위기 속에 사색하고 싶을 때"

        if tempo is not None:
            if tempo >= 128:
                return "파티나 운동처럼 리듬감이 필요한 순간"
            if tempo <= 80:
                return "늦은 밤 잔잔한 무드로 하루를 정리하고 싶을 때"

        mood_sets = {
            "relaxed": {"relaxed", "serene", "peaceful", "mellow"},
            "energetic": {"energetic", "upbeat", "empowering", "driving", "dynamic"},
            "dreamy": {"dreamy", "nocturnal", "ambient", "mystical", "ethereal"},
            "romantic": {"romantic", "intimate", "warm"},
        }
        mood_set = set(moods)
        if mood_sets["relaxed"] & mood_set:
            return "카페에서 느긋하게 쉴 때"
        if mood_sets["energetic"] & mood_set:
            return "기분 전환이 필요할 때"
        if mood_sets["dreamy"] & mood_set:
            return "밤 산책처럼 몽환적인 분위기를 즐기고 싶을 때"
        if mood_sets["romantic"] & mood_set:
            return "잔잔한 데이트나 감성적인 순간"

        return None

# ============================================================================
# 메인 애플리케이션
# ============================================================================


TOURNAMENT_SIZE_PRESETS: List[Tuple[str, int]] = [
    ("빠른 토너먼트 (16강)", 16),
    ("표준 토너먼트 (32강)", 32),
    ("확장 토너먼트 (64강)", 64),
]

DEFAULT_TOURNAMENT_SIZE = 32


BEGINNER_PRESETS: Dict[str, Dict[str, Any]] = {
    "k_pop_quick": {
        "title": "K-POP 퀵 매치",
        "description": "최신 K-POP과 글로벌 팝을 좋아하시는 분들에게 추천해요.",
        "tournament_size": 16,
        "survey_profile": {
            "genre_scores": {"K-Indie Pop": 5, "Dance Pop": 4, "Electronic": 2},
            "preferred_era": 2020,
            "preferred_energy": 0.78,
            "preferred_popularity": 0.7,
            "preferred_language": "ko",
            "preferred_languages": ["ko", "en"],
            "language_strict": False,
            "preferred_moods": ["energetic", "upbeat", "playful"],
            "mood_weight": 0.9,
            "preferred_instrumentations": ["synth", "vocals", "drums"],
            "excluded_genres": ["Classical", "Jazz"],
            "excluded_moods": ["melancholic", "dark", "introspective"],
            "excluded_instrumentations": ["strings", "saxophone", "trumpet"],
            "regional_focus": "k_prefer",
        },
    },
    "chill_indie": {
        "title": "차분한 인디 감성",
        "description": "포근한 인디와 어쿠스틱 사운드를 좋아하시는 분들에게 추천해요.",
        "tournament_size": 16,
        "survey_profile": {
            "genre_scores": {"Indie Folk": 5, "Alternative Rock": 2, "Jazz": 1},
            "preferred_era": 2010,
            "preferred_energy": 0.4,
            "preferred_popularity": 0.35,
            "preferred_language": None,
            "preferred_languages": [],
            "language_strict": False,
            "preferred_moods": ["dreamy", "mellow", "introspective"],
            "mood_weight": 0.85,
            "preferred_instrumentations": ["guitar", "piano", "vocals"],
            "excluded_genres": ["Electronic", "Hip Hop"],
            "excluded_moods": ["aggressive", "fierce", "powerful"],
            "excluded_instrumentations": ["808", "samples", "synth"],
            "regional_focus": "neutral",
        },
    },
    "global_energy": {
        "title": "글로벌 에너지 믹스",
        "description": "신스와 리듬이 살아있는 글로벌 댄스 플로어를 좋아하시는 분들에게 추천해요.",
        "tournament_size": 32,
        "survey_profile": {
            "genre_scores": {"Electronic": 5, "Pop": 3, "Hip Hop": 2},
            "preferred_era": 2018,
            "preferred_energy": 0.88,
            "preferred_popularity": 0.65,
            "preferred_language": "en",
            "preferred_languages": ["en", "es", "fr"],
            "language_strict": False,
            "preferred_moods": ["energetic", "empowering", "uplifting"],
            "mood_weight": 0.9,
            "preferred_instrumentations": ["synth", "samples", "drums"],
            "excluded_genres": ["Classical", "Jazz", "Indie Folk"],
            "excluded_moods": ["peaceful", "serene", "minimalist"],
            "excluded_instrumentations": ["strings", "piano", "guitar"],
            "regional_focus": "global",
        },
    },
    "classic_k_rock": {
        "title": "추억의 한국 락",
        "description": "90-00년대 한국 락과 밴드 사운드를 좋아하시는 분들에게 추천해요.",
        "tournament_size": 32,
        "survey_profile": {
            "genre_scores": {"Rock": 5, "Classic Rock": 4, "Alternative Rock": 2},
            "preferred_era": 1995,
            "preferred_energy": 0.68,
            "preferred_popularity": 0.4,
            "preferred_language": "ko",
            "preferred_languages": ["ko"],
            "language_strict": True,
            "preferred_moods": ["nostalgic", "powerful", "emotional"],
            "mood_weight": 0.92,
            "preferred_instrumentations": ["guitar", "drums", "vocals"],
            "excluded_genres": ["Electronic", "Hip Hop", "Pop"],
            "excluded_moods": ["danceable", "playful", "cheerful"],
            "excluded_instrumentations": ["808", "samples", "synth"],
            "regional_focus": "k_prefer",
        },
    },
    "nighttime_dreampop": {
        "title": "밤 감성 드림팝",
        "description": "새벽 감성의 몽환적인 드림팝과 신스 사운드를 좋아하시는 분들에게 추천해요.",
        "tournament_size": 16,
        "survey_profile": {
            "genre_scores": {"Art Pop": 5, "Electronic": 2, "Pop": 1},
            "preferred_era": 2020,
            "preferred_energy": 0.15,
            "preferred_popularity": 0.3,
            "preferred_language": "en",
            "preferred_languages": ["en"],
            "language_strict": False,
            "preferred_moods": ["dreamy", "ethereal", "nocturnal"],
            "mood_weight": 0.97,
            "preferred_instrumentations": ["synth", "guitar", "vocals"],
            "excluded_genres": ["Hip Hop", "Jazz", "Classical"],
            "excluded_moods": ["aggressive", "fierce", "celebratory"],
            "excluded_instrumentations": ["808", "trumpet", "saxophone"],
            "regional_focus": "neutral",
        },
    },
}


def determine_effective_tournament_size(
    desired: int,
    available: int,
    allowed_sizes: Optional[List[int]] = None,
) -> Tuple[int, bool]:
    """Return a feasible tournament size within available songs.

    Parameters
    ----------
    desired: int
        Requested bracket size (e.g., 16, 32, 64).
    available: int
        Number of songs that can be used as candidates.
    allowed_sizes: Optional[List[int]]
        Whitelisted preset sizes. Defaults to the preset values.

    Returns
    -------
    Tuple[int, bool]
        (effective_size, adjusted_flag)
    """

    if allowed_sizes is None:
        allowed_sizes = [value for _, value in TOURNAMENT_SIZE_PRESETS]

    if available <= 0:
        return 0, desired != 0

    if desired <= available:
        return desired, False

    fallback_candidates = [size for size in allowed_sizes if size <= available]
    if fallback_candidates:
        fallback = max(fallback_candidates)
    else:
        if available < 2:
            fallback = available
        else:
            power = 2 ** int(math.floor(math.log2(available)))
            fallback = max(2, power)

    return fallback, True


class MusicTournamentApp:
    def __init__(self, songs_file: str):
        self.songs_file = songs_file
        self.songs = []
        self.survey_profile = {}
        self.candidates = []
        self.champion = None
        self.seed_scores: Dict[str, float] = {}
        self.tournament_size = DEFAULT_TOURNAMENT_SIZE

    def run(self):
        """전체 프로세스 실행"""
        print("\n" + "="*60)
        print("🎵 음악 취향 테스트")
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
        desired_size = self.prompt_tournament_size()
        available = len(self.songs)
        effective_size, adjusted = determine_effective_tournament_size(desired_size, available)
        if adjusted and effective_size > 0:
            print(
                f"⚠️ 선택한 토너먼트 규모({desired_size}강)가 사용 가능한 곡 수({available}곡)보다 많아 {effective_size}강으로 조정합니다."
            )
        if effective_size <= 0:
            print("✗ 토너먼트를 구성할 곡이 없습니다. 프로그램을 종료합니다.")
            return

        self.tournament_size = effective_size

        selector = CandidateSelector(self.songs, self.survey_profile)
        self.candidates = selector.select_candidates(k=effective_size)
        self.seed_scores = selector.get_seed_scores()

        if len(self.candidates) < 2:
            print("✗ 토너먼트를 진행하기에 곡이 부족합니다. 프로그램을 종료합니다.")
            return

        if len(self.candidates) % 2 == 1:
            removed = self.candidates.pop()
            if removed:
                self.seed_scores.pop(removed.id, None)
                print(
                    f"⚠️ 홀수 후보 조정을 위해 {removed.artist} - {removed.get_display_title()} 곡을 제외합니다."
                )

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
        analyzer = ResultAnalyzer(engine.match_history, self.candidates, self.survey_profile)
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

    def prompt_tournament_size(self) -> int:
        print("\n원하는 토너먼트 규모를 선택하세요:")
        for idx, (label, value) in enumerate(TOURNAMENT_SIZE_PRESETS, 1):
            print(f"  {idx}. {label}")
        print(f"  기본값: Enter 입력 시 {DEFAULT_TOURNAMENT_SIZE}강")

        allowed_values = {value for _, value in TOURNAMENT_SIZE_PRESETS}
        while True:
            choice = input("선택 (번호 또는 강 수): ").strip()
            if not choice:
                return DEFAULT_TOURNAMENT_SIZE
            if choice.isdigit():
                number = int(choice)
                if 1 <= number <= len(TOURNAMENT_SIZE_PRESETS):
                    return TOURNAMENT_SIZE_PRESETS[number - 1][1]
                if number in allowed_values:
                    return number
            print("지원하는 번호 또는 강 수(예: 16, 32, 64)를 입력해주세요.")

# ============================================================================
# GUI 애플리케이션
# ============================================================================



def build_track_preview_html(embed_url: str) -> str:
    """YouTube 플레이어를 DOMContentLoaded 이후에 초기화하는 HTML 스니펫을 생성한다."""

    # json.dumps 를 이용해 URL을 안전하게 이스케이프한다.
    safe_embed_url = json.dumps(embed_url)

    return f"""
<!DOCTYPE html>
<html lang=\"ko\">
<head>
    <meta charset=\"utf-8\" />
    <style>
        html, body {{
            margin: 0;
            padding: 0;
            background: #000;
            height: 100%;
        }}
        #player-container {{
            position: absolute;
            inset: 0;
        }}
        iframe {{
            width: 100%;
            height: 100%;
            border: 0;
        }}
    </style>
</head>
<body>
    <div id=\"player-container\"></div>
    <script>
        const embedUrl = {safe_embed_url};

        function mountPlayer() {{
            const container = document.getElementById('player-container');
            if (!container || container.dataset.initialized === 'true') {{
                return;
            }}

            const iframe = document.createElement('iframe');
            iframe.src = embedUrl;
            iframe.title = 'YouTube video player';
            const featurePermissions = [
                'accelerometer',
                'autoplay',
                'clipboard-write',
                'encrypted-media',
                'gyroscope',
                'picture-in-picture'
            ];
            iframe.setAttribute('allow', featurePermissions.join('; '));
            iframe.allowFullscreen = true;
            container.appendChild(iframe);
            container.dataset.initialized = 'true';
        }}

        if (document.readyState === 'loading') {{
            document.addEventListener('DOMContentLoaded', mountPlayer);
        }} else {{
            mountPlayer();
        }}
    </script>
</body>
</html>
"""


class SongPreviewEmbed(QFrame):
    def __init__(self, parent: Optional[QWidget] = None, minimum_height: int = 200):
        super().__init__(parent)
        self.setObjectName("SongPreviewEmbed")
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.caption_label = QLabel()
        self.caption_label.setObjectName("BodyLabel")
        self.caption_label.setWordWrap(True)
        layout.addWidget(self.caption_label)

        self.web_view: QWebEngineView | None = None
        self._current_embed_url: Optional[str] = None
        if WEB_ENGINE_AVAILABLE:
            self.web_view = QWebEngineView()
            self.web_view.setObjectName("SongPreviewEmbedView")
            self.web_view.setMinimumHeight(minimum_height)

            profile = self.web_view.page().profile()
            cache_root = Path.home() / ".cache" / "whats-my-music-flavor"
            http_cache_path = cache_root / "http-cache"
            persistent_path = cache_root / "persistent-storage"
            for directory in (http_cache_path, persistent_path):
                directory.mkdir(parents=True, exist_ok=True)

            profile.setHttpCacheType(QWebEngineProfile.HttpCacheType.DiskHttpCache)
            profile.setCachePath(str(http_cache_path))
            profile.setPersistentStoragePath(str(persistent_path))

            layout.addWidget(self.web_view)

        self.current_song: Optional[Song] = None

        self.set_song(None)

    def set_song(self, song: Optional[Song]) -> None:
        self.current_song = song

        if not song:
            self._show_message("미리 볼 곡이 없습니다.")
            return

        if not song.youtube_url:
            self._show_message("이 곡은 영상 미리보기를 지원하지 않습니다.")
            return

        embed_url = build_youtube_embed_url(song.youtube_url)
        if not embed_url:
            self._show_message("이 곡의 링크는 영상 미리보기 형식으로 변환할 수 없습니다.")
            return

        if not self.web_view:
            self._show_message("이 환경에서는 영상 미리보기를 사용할 수 없습니다. PyQt6-WebEngine을 설치해주세요.")
            return

        caption = f"{song.artist} - {song.get_display_title()} 영상 미리보기"

        if self._current_embed_url == embed_url:
            self.caption_label.setText(caption)
            return

        preview_html = build_track_preview_html(embed_url)
        self.web_view.setHtml(preview_html, QUrl("https://www.youtube.com"))
        self._current_embed_url = embed_url
        self.caption_label.setText(caption)

    def _show_message(self, message: str) -> None:
        self.caption_label.setText(message)
        self._current_embed_url = None
        if self.web_view:
            self.web_view.setUrl(QUrl("about:blank"))


class MusicTournamentGUI(QMainWindow):
    GENRE_PAIRS = SURVEY_GENRE_PAIRS

    ERA_OPTIONS = SURVEY_ERA_OPTIONS

    ENERGY_OPTIONS = SURVEY_ENERGY_OPTIONS

    POPULARITY_OPTIONS = SURVEY_POPULARITY_OPTIONS

    LANGUAGE_OPTIONS = SURVEY_LANGUAGE_OPTIONS

    MOOD_OPTIONS = SURVEY_MOOD_OPTIONS

    SOUND_OPTIONS = SURVEY_SOUND_OPTIONS

    REGIONAL_FOCUS_OPTIONS = SURVEY_REGIONAL_FOCUS_OPTIONS

    TOURNAMENT_SIZE_OPTIONS = TOURNAMENT_SIZE_PRESETS

    MOOD_DESCRIPTIONS = {
        "abstract": "추상적인 무드",
        "aggressive": "과감한 에너지",
        "angst": "거친 감정선",
        "atmospheric": "공간감 있는 분위기",
        "avant_garde": "실험적인 기조",
        "bold": "대담한 무드",
        "bright": "밝은 톤",
        "building": "차곡차곡 고조되는 전개",
        "celebratory": "축제 같은 분위기",
        "cheerful": "경쾌한 기운",
        "complex": "복합적인 진행",
        "confident": "자신감 넘치는 바이브",
        "contemplative": "사색적인 정서",
        "danceable": "몸이 저절로 움직이는 리듬",
        "dark": "어두운 기운",
        "defiant": "거침없는 태도",
        "dramatic": "드라마틱한 전개",
        "dreamy": "몽환적인 무드",
        "driving": "질주감 있는 비트",
        "dynamic": "다이내믹한 흐름",
        "elegant": "우아한 감성",
        "emotional": "감성 짙은 표현",
        "empowering": "힘이 되는 메시지",
        "energetic": "에너지 폭발",
        "epic": "장대한 스케일",
        "ethereal": "신비로운 공기감",
        "euphoric": "황홀한 고조",
        "fierce": "날 선 텐션",
        "funky": "펑키한 그루브",
        "groovy": "그루비한 리듬",
        "haunting": "잔향이 남는 여운",
        "hopeful": "희망찬 기운",
        "intense": "강렬한 몰입감",
        "intimate": "속삭이듯 친밀한 무드",
        "introspective": "내면을 들여다보는 감성",
        "ironic": "위트 있는 반전",
        "luxurious": "고급스러운 결",
        "melancholic": "쓸쓸한 감성",
        "mellow": "부드러운 결",
        "minimalist": "미니멀한 사운드",
        "modern": "현대적인 터치",
        "mysterious": "오묘한 긴장감",
        "mystical": "신비로운 의식감",
        "nocturnal": "야간 드라이브 감성",
        "nostalgic": "향수를 자극하는 무드",
        "passionate": "열정적인 호흡",
        "peaceful": "평온한 정서",
        "playful": "장난기 어린 리듬",
        "powerful": "압도적인 힘",
        "raw": "날것의 에너지",
        "rebellious": "반항적인 기운",
        "reflective": "되돌아보는 정서",
        "relaxed": "느긋한 흐름",
        "romantic": "로맨틱한 감성",
        "satirical": "풍자적인 뉘앙스",
        "seductive": "매혹적인 분위기",
        "serene": "고요한 공기",
        "smooth": "매끈한 질감",
        "sophisticated": "세련된 무드",
        "soulful": "소울풀한 감성",
        "surreal": "초현실적인 기운",
        "trippy": "헤롱거리는 사이키델릭",
        "unsettling": "살짝 불안한 긴장감",
        "upbeat": "업비트 에너지",
        "uplifting": "들어올려 주는 무드",
        "warm": "따뜻한 온기",
        "whimsical": "기발한 상상력",
        "youthful": "청량한 젊은 기운",
    }

    INSTRUMENT_DESCRIPTIONS = {
        "808": "808 베이스 웨이브",
        "bass": "두터운 베이스 라인",
        "drums": "라이브 드럼 질감",
        "electronic_beats": "전자 비트 드라이브",
        "guitar": "기타 리프 중심",
        "keyboards": "키보드 패드",
        "palmas": "플라멩코 박수 리듬",
        "percussion": "퍼커션 리듬 포인트",
        "piano": "피아노 중심 선율",
        "recorder": "리코더 선율",
        "samples": "샘플링 텍스처",
        "saxophone": "색소폰 솔로",
        "strings": "스트링 편곡",
        "synth": "반짝이는 전자 사운드",
        "trumpet": "트럼펫 브라스",
        "vocals": "보컬 하모니 강조",
        "vocoder": "보코더 이펙트",
    }

    def __init__(self, songs_file: str):
        super().__init__()
        self.songs_file = songs_file
        self.setWindowTitle("Whats My Music Flavor · 음악 취향 테스트")
        self.resize(1000, 760)

        self.shortcuts: List[QShortcut] = []
        self.history_show_all = False
        self.history_max_rows = 10
        self.tournament_size_combo: Optional[QComboBox] = None
        self.selected_tournament_size = DEFAULT_TOURNAMENT_SIZE
        self.stage_order: List[str] = ["start", "survey", "tournament", "results"]
        self.stage_descriptions: Dict[str, str] = {
            "start": "서비스 소개와 준비 단계",
            "survey": "선호도를 입력하고 토너먼트를 준비해요",
            "tournament": "두 곡씩 비교하며 최애를 골라보세요",
            "results": "챔피언과 추천 플레이리스트를 확인하세요",
        }
        self.stage_buttons: Dict[str, QPushButton] = {}
        self.stage_summary_label: Optional[QLabel] = None
        self.unlocked_stages: Set[str] = {"start", "survey"}
        self.active_stage = "start"

        central = QWidget()
        central.setObjectName("CentralWidget")
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(32, 32, 32, 32)
        main_layout.setSpacing(20)

        header = QFrame()
        header.setObjectName("HeaderCard")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(28, 24, 28, 24)
        header_layout.setSpacing(8)

        overline = QLabel("WHATS MY MUSIC FLAVOR")
        overline.setObjectName("OverlineLabel")
        header_layout.addWidget(overline)

        title_label = QLabel("토너먼트 취향 테스트")
        title_label.setObjectName("HeroTitle")
        header_layout.addWidget(title_label)

        subtitle_label = QLabel("설문부터 추천까지, 당신의 음악 취향을 찾아드립니다.")
        subtitle_label.setObjectName("HeroSubtitle")
        subtitle_label.setWordWrap(True)
        header_layout.addWidget(subtitle_label)

        main_layout.addWidget(header)

        stage_navigator = self.build_stage_navigator()
        main_layout.addWidget(stage_navigator)

        self.content_frame = QFrame()
        self.content_frame.setObjectName("ContentFrame")
        self.content_layout = QVBoxLayout(self.content_frame)
        self.content_layout.setContentsMargins(24, 24, 24, 24)
        self.content_layout.setSpacing(20)
        self.content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        main_layout.addWidget(self.content_frame, 1)

        self.footer_frame = QFrame()
        self.footer_frame.setObjectName("FooterFrame")
        footer_layout = QHBoxLayout(self.footer_frame)
        footer_layout.setContentsMargins(0, 0, 0, 0)
        footer_layout.setSpacing(12)
        footer_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        footer_notice = QLabel(
            "곡 정보에 오류를 발견하셨나요? '문제 신고 · 개선 제안하기' 버튼으로 알려주시면, 서비스 개선에 큰 힘이 됩니다."
        )
        footer_notice.setObjectName("FooterNotice")
        footer_notice.setWordWrap(True)
        footer_notice.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        footer_notice.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        footer_layout.addWidget(footer_notice, 1)
        self.footer_notice = footer_notice

        self.report_issue_button = QPushButton("문제 신고 · 개선 제안하기")
        self.report_issue_button.setObjectName("ReportIssueButton")
        self.report_issue_button.setProperty("variant", "primary")
        self.report_issue_button.clicked.connect(self.open_issue_link)
        footer_layout.addWidget(self.report_issue_button, 0, Qt.AlignmentFlag.AlignRight)

        main_layout.addWidget(self.footer_frame)

        self.report_issue_button.installEventFilter(self)
        self.footer_notice.installEventFilter(self)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        self.apply_modern_theme()
        self.sync_footer_height()

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

    def open_issue_link(self):
        webbrowser.open("https://github.com/cheesedongjin/WhatsMyMusicFlavor/issues")

    def sync_footer_height(self):
        if not hasattr(self, "report_issue_button") or not hasattr(self, "footer_frame"):
            return

        button_height = max(
            self.report_issue_button.height(),
            self.report_issue_button.sizeHint().height(),
        )
        if button_height <= 0:
            return

        self.footer_frame.setFixedHeight(button_height)
        self.footer_frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        if hasattr(self, "footer_notice"):
            self.footer_notice.setMinimumHeight(button_height)
            self.footer_notice.setMaximumHeight(button_height)
            self.footer_notice.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def eventFilter(self, obj, event):
        if obj in (getattr(self, "report_issue_button", None), getattr(self, "footer_notice", None)):
            if event.type() in {
                QEvent.Type.Show,
                QEvent.Type.Resize,
                QEvent.Type.StyleChange,
                QEvent.Type.PolishRequest,
            }:
                QTimer.singleShot(0, self.sync_footer_height)
        return super().eventFilter(obj, event)

    def apply_modern_theme(self):
        self.setStyleSheet(
            """
QMainWindow {
    background-color: #020617;
}
QWidget {
    background-color: transparent;
    color: #e2e8f0;
    font-family: 'Pretendard', 'Segoe UI', sans-serif;
    font-size: 15px;
}
QWidget#CentralWidget {
    background-color: #0f172a;
    border-radius: 28px;
}
QFrame#HeaderCard {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #1e293b, stop:1 #0f172a);
    border-radius: 24px;
}
QFrame#ContentFrame {
    background-color: rgba(15, 23, 42, 0.45);
    border-radius: 24px;
    padding: 12px;
}
QFrame#FooterFrame {
    background-color: rgba(15, 23, 42, 0.92);
    border-radius: 16px;
    padding: 0 16px;
}
QFrame#ContentSection {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(4, 10, 28, 0.98), stop:1 rgba(2, 6, 23, 0.94));
    border: 1px solid rgba(56, 189, 248, 0.16);
    border-radius: 20px;
    padding: 4px;
}
QFrame#StageNavigator {
    background-color: rgba(15, 23, 42, 0.65);
    border: 1px solid rgba(56, 189, 248, 0.18);
    border-radius: 18px;
}
QLabel#StageSummaryLabel {
    color: #94a3b8;
    font-size: 13px;
}
QPushButton#StagePill {
    background-color: rgba(148, 163, 184, 0.16);
    border: none;
    border-radius: 16px;
    padding: 8px 18px;
    font-weight: 600;
    color: #cbd5f5;
}
QPushButton#StagePill:enabled:hover {
    background-color: rgba(148, 163, 184, 0.28);
}
QPushButton#StagePill:checked,
QPushButton#StagePill[active="true"] {
    background-color: #38bdf8;
    color: #0f172a;
}
QPushButton#StagePill:disabled {
    color: rgba(148, 163, 184, 0.5);
    background-color: rgba(148, 163, 184, 0.08);
}
QWidget#ChipContainer {
    background-color: rgba(148, 163, 184, 0.08);
    border-radius: 16px;
    padding: 12px;
}
QLabel#HighlightChip {
    background-color: rgba(56, 189, 248, 0.15);
    border-radius: 14px;
    padding: 10px 12px;
    color: #e0f2fe;
    font-weight: 600;
}
QLabel#OverlineLabel {
    color: #38bdf8;
    letter-spacing: 2px;
    font-weight: 600;
    text-transform: uppercase;
    font-size: 13px;
}
QLabel#HeroTitle {
    font-size: 28px;
    font-weight: 700;
    color: #f8fafc;
}
QLabel#HeroSubtitle {
    color: #cbd5f5;
    font-size: 16px;
    line-height: 1.4em;
}
QLabel#SectionTitle {
    font-size: 22px;
    font-weight: 700;
    color: #f8fafc;
}
QLabel#SectionSubtitle {
    font-size: 18px;
    font-weight: 600;
    color: #e2e8f0;
}
QLabel#BodyLabel {
    color: #cbd5f5;
    line-height: 1.5em;
}
QLabel#ChampionTitle {
    font-size: 20px;
    font-weight: 700;
    color: #38bdf8;
}
QLabel#MatchStatusLabel {
    font-size: 18px;
    font-weight: 600;
    color: #f1f5f9;
}
QLabel#RoundBadge {
    background-color: rgba(56, 189, 248, 0.16);
    color: #38bdf8;
    font-weight: 600;
    border-radius: 14px;
    padding: 6px 12px;
    font-size: 13px;
}
QLabel#SongTitle {
    font-size: 17px;
    font-weight: 600;
    color: #f8fafc;
}
QLabel#MetaLabel {
    color: #94a3b8;
}
QLabel[role="helper"] {
    color: #94a3b8;
}
QLabel#ProgressCaption {
    color: #94a3b8;
    font-size: 13px;
}
QGroupBox {
    background-color: rgba(15, 23, 42, 0.75);
    border: 1px solid rgba(148, 163, 184, 0.25);
    border-radius: 16px;
    margin-top: 12px;
    padding: 20px;
}
QGroupBox::title {
    color: #38bdf8;
    font-weight: 600;
    margin-left: 12px;
    padding: 0 6px;
}
QGroupBox#SongCard {
    padding: 28px 24px 24px 24px;
    border-radius: 20px;
}
QGroupBox#SongCard[side="A"] {
    border: 1px solid rgba(56, 189, 248, 0.45);
}
QGroupBox#SongCard[side="B"] {
    border: 1px solid rgba(129, 140, 248, 0.45);
}
QGroupBox#SongCard:hover {
    background-color: rgba(56, 189, 248, 0.12);
}
QFrame#InsightCard {
    background-color: rgba(15, 23, 42, 0.85);
    border: 1px solid rgba(56, 189, 248, 0.2);
    border-radius: 20px;
    padding: 20px;
}
QGroupBox#InsightGroup {
    background-color: rgba(15, 23, 42, 0.85);
    border: 1px solid rgba(148, 163, 184, 0.25);
    border-radius: 20px;
    padding: 20px;
}
QLabel#RecommendationGroupLabel {
    color: #38bdf8;
    font-weight: 600;
    margin-top: 6px;
}
QLabel#FooterNotice {
    color: #94a3b8;
    font-size: 11px;
    line-height: 1.2em;
}
QPushButton {
    background-color: rgba(148, 163, 184, 0.18);
    border: none;
    border-radius: 12px;
    padding: 8px 16px;
    color: #e2e8f0;
    font-weight: 600;
    min-height: 36px;
}
QPushButton#ReportIssueButton {
    padding: 4px 12px;
    min-height: 28px;
    font-size: 12px;
}
QPushButton:hover {
    background-color: rgba(148, 163, 184, 0.32);
}
QPushButton:pressed {
    background-color: rgba(148, 163, 184, 0.4);
}
QPushButton[variant="primary"] {
    background-color: #38bdf8;
    color: #0f172a;
}
QPushButton[variant="primary"]:hover {
    background-color: #0ea5e9;
}
QPushButton[variant="primary"]:pressed {
    background-color: #0284c7;
}
QPushButton[variant="ghost"] {
    background-color: transparent;
    border: 1px solid rgba(148, 163, 184, 0.4);
    color: #cbd5f5;
}
QPushButton[variant="ghost"]:hover {
    background-color: rgba(148, 163, 184, 0.2);
}
QPushButton[variant="ghost"]:pressed {
    background-color: rgba(148, 163, 184, 0.3);
}
QStatusBar {
    background-color: #0b1120;
    color: #94a3b8;
    padding: 8px 16px;
    border-top: 1px solid rgba(148, 163, 184, 0.25);
}
QProgressBar {
    background-color: rgba(148, 163, 184, 0.16);
    border: 1px solid rgba(56, 189, 248, 0.28);
    border-radius: 10px;
    height: 20px;
    padding: 2px;
}
QProgressBar::chunk {
    border-radius: 10px;
    background-color: #38bdf8;
    margin: 1px;
}
QScrollArea {
    border: none;
    background: transparent;
}
QScrollArea > QWidget > QWidget {
    background: transparent;
}
QScrollBar:vertical {
    background: transparent;
    width: 12px;
    margin: 8px 0 8px 0;
}
QScrollBar::handle:vertical {
    background: rgba(148, 163, 184, 0.5);
    border-radius: 6px;
}
QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {
    height: 0;
}
QRadioButton {
    spacing: 8px;
    color: #e2e8f0;
}
QRadioButton::indicator {
    width: 18px;
    height: 18px;
}
QRadioButton::indicator {
    border-radius: 9px;
    border: 2px solid rgba(148, 163, 184, 0.6);
    background: transparent;
}
QRadioButton::indicator:checked {
    background-color: #38bdf8;
    border: 2px solid #38bdf8;
}
QRadioButton::indicator:hover {
    border: 2px solid #0ea5e9;
}
QTreeWidget#MatchHistoryTree {
    background-color: rgba(15, 23, 42, 0.85);
    border: 1px solid rgba(148, 163, 184, 0.25);
    border-radius: 16px;
    color: #e2e8f0;
    alternate-background-color: rgba(15, 23, 42, 0.7);
}
QTreeWidget#MatchHistoryTree::item {
    height: 28px;
}
QTreeWidget#MatchHistoryTree::item:hover {
    background-color: rgba(56, 189, 248, 0.18);
}
QTreeWidget#MatchHistoryTree::item:selected {
    background-color: rgba(56, 189, 248, 0.35);
    color: #0f172a;
}
QHeaderView::section {
    background-color: rgba(148, 163, 184, 0.18);
    border: none;
    color: #cbd5f5;
    padding: 6px;
    font-weight: 600;
}
            """
        )


    def build_stage_navigator(self) -> QFrame:
        container = QFrame()
        container.setObjectName("StageNavigator")
        layout = QHBoxLayout(container)
        layout.setContentsMargins(24, 14, 24, 14)
        layout.setSpacing(12)
        for stage in self.stage_order:
            label = {
                "start": "1. 시작",
                "survey": "2. 설문",
                "tournament": "3. 토너먼트",
                "results": "4. 결과",
            }[stage]
            button = QPushButton(label)
            button.setObjectName("StagePill")
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setToolTip(self.stage_descriptions.get(stage, ""))
            button.clicked.connect(lambda _=False, s=stage: self.navigate_to_stage(s))
            layout.addWidget(button)
            self.stage_buttons[stage] = button
        layout.addStretch(1)
        summary = QLabel(self.stage_descriptions.get(self.active_stage, ""))
        summary.setObjectName("StageSummaryLabel")
        summary.setWordWrap(True)
        layout.addWidget(summary, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.stage_summary_label = summary
        self.update_stage_indicator()
        return container

    def update_stage_indicator(self):
        for stage, button in self.stage_buttons.items():
            is_active = stage == self.active_stage
            is_unlocked = stage in self.unlocked_stages or is_active
            button.setEnabled(is_unlocked)
            button.setChecked(is_active)
            button.setProperty("active", "true" if is_active else "false")
            button.style().unpolish(button)
            button.style().polish(button)
        if self.stage_summary_label:
            self.stage_summary_label.setText(self.stage_descriptions.get(self.active_stage, ""))

    def set_active_stage(self, stage: str):
        if stage not in self.stage_order:
            return
        if stage not in self.unlocked_stages:
            self.unlocked_stages.add(stage)
        self.active_stage = stage
        self.update_stage_indicator()

    def navigate_to_stage(self, stage: str):
        if stage not in self.unlocked_stages and stage != self.active_stage:
            return
        if stage == self.active_stage:
            return
        if stage == "start":
            self.show_start_view()
        elif stage == "survey":
            self.show_survey_view()
        elif stage == "tournament":
            if self.engine and (self.current_round_matches or self.current_round_winners):
                self.show_match_view()
        elif stage == "results":
            if self.engine and self.champion:
                self.show_results_view()

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
        self.history_show_all = False
        self.tournament_size_combo = None
        self.selected_tournament_size = DEFAULT_TOURNAMENT_SIZE
        self.beginner_preset_active = False
        self.genre_groups: List[Tuple[QButtonGroup, Tuple[str, str]]] = []
        self.era_group: Optional[QButtonGroup] = None
        self.energy_group: Optional[QButtonGroup] = None
        self.popularity_group: Optional[QButtonGroup] = None
        self.language_group: Optional[QButtonGroup] = None
        self.mood_group: Optional[QButtonGroup] = None
        self.sound_group: Optional[QButtonGroup] = None
        self.regional_focus_group: Optional[QButtonGroup] = None
        self.unlocked_stages = {"start", "survey"}
        self.active_stage = "start"
        self.update_stage_indicator()


    def clear_content(self):
        if self.shortcuts:
            for shortcut in self.shortcuts:
                shortcut.setEnabled(False)
                shortcut.deleteLater()
            self.shortcuts.clear()
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def show_start_view(self):
        self.reset_state()
        self.clear_content()
        self.set_active_stage("start")

        widget = QFrame()
        widget.setObjectName("ContentSection")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(18)

        title = QLabel("당신의 음악 취향을 발견해보세요")
        title.setObjectName("SectionTitle")
        layout.addWidget(title)

        intro = QLabel("간단한 설문과 토너먼트를 통해 나만의 플레이리스트를 완성해보세요.")
        intro.setObjectName("BodyLabel")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        chip_container = QWidget()
        chip_container.setObjectName("ChipContainer")
        chip_layout = QHBoxLayout(chip_container)
        chip_layout.setContentsMargins(0, 0, 0, 0)
        chip_layout.setSpacing(12)
        chip_messages = [
            "🧭 단계별 네비게이션으로 진행 상황 확인",
            "📊 라운드별 진행도를 실시간으로 체크",
            "💡 결과 카드에서 추천과 통계를 한눈에",
        ]
        for message in chip_messages:
            chip = QLabel(message)
            chip.setObjectName("HighlightChip")
            chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
            chip.setWordWrap(True)
            chip_layout.addWidget(chip, 1)
        layout.addWidget(chip_container)

        bullet_points = [
            ("🎧", "선호 장르와 무드를 분석해 한 눈에 정리된 취향 리포트를 제공합니다."),
            ("🚀", "토너먼트 결과를 바탕으로 새로운 추천곡까지 이어지는 경험을 만나보세요."),
        ]
        for icon, text in bullet_points:
            bullet = QLabel(f"{icon} {text}")
            bullet.setObjectName("BodyLabel")
            bullet.setProperty("role", "helper")
            bullet.setWordWrap(True)
            layout.addWidget(bullet)

        if BEGINNER_PRESETS:
            preset_section = QFrame()
            preset_section.setObjectName("PresetSection")
            preset_layout = QVBoxLayout(preset_section)
            preset_layout.setContentsMargins(20, 16, 20, 16)
            preset_layout.setSpacing(12)

            preset_title = QLabel("⏱️ 바로 시작하고 싶다면 프리셋을 선택해보세요")
            preset_title.setObjectName("SectionSubtitle")
            preset_title.setWordWrap(True)
            preset_layout.addWidget(preset_title)

            cards_container = QFrame()
            cards_container.setObjectName("PresetCardContainer")
            cards_layout = QHBoxLayout(cards_container)
            cards_layout.setContentsMargins(0, 0, 0, 0)
            cards_layout.setSpacing(16)

            for key, config in BEGINNER_PRESETS.items():
                card = QFrame()
                card.setObjectName("PresetCard")
                card_layout = QVBoxLayout(card)
                card_layout.setContentsMargins(18, 16, 18, 16)
                card_layout.setSpacing(10)

                name_label = QLabel(config.get("title", key))
                name_label.setObjectName("PresetTitle")
                name_label.setWordWrap(True)
                card_layout.addWidget(name_label)

                desc_label = QLabel(config.get("description", ""))
                desc_label.setObjectName("BodyLabel")
                desc_label.setProperty("role", "helper")
                desc_label.setWordWrap(True)
                card_layout.addWidget(desc_label)

                size_label = QLabel(f"규모: {config.get('tournament_size', DEFAULT_TOURNAMENT_SIZE)}강")
                size_label.setProperty("role", "helper")
                size_label.setWordWrap(True)
                card_layout.addWidget(size_label)

                preset_button = QPushButton("프리셋으로 바로 시작")
                preset_button.setCursor(Qt.CursorShape.PointingHandCursor)
                preset_button.setProperty("variant", "secondary")
                preset_button.clicked.connect(lambda _=False, preset_key=key: self.apply_beginner_preset(preset_key))
                card_layout.addWidget(preset_button)

                card_layout.addStretch(1)
                cards_layout.addWidget(card)

            cards_layout.addStretch(1)
            preset_layout.addWidget(cards_container)
            layout.addWidget(preset_section)

        start_button = QPushButton("설문조사부터 시작하기")
        start_button.setProperty("variant", "primary")
        start_button.setCursor(Qt.CursorShape.PointingHandCursor)
        start_button.setMinimumHeight(48)
        start_button.clicked.connect(self.show_survey_view)
        layout.addWidget(start_button, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addStretch(1)

        self.content_layout.addWidget(widget)
        self.update_status("간단한 설문부터 시작해볼까요?")

    def apply_beginner_preset(self, preset_key: str):
        preset = BEGINNER_PRESETS.get(preset_key)
        if not preset:
            QMessageBox.warning(self, "프리셋 오류", "선택한 프리셋을 찾을 수 없습니다. 다시 시도해주세요.")
            return

        profile_data = preset.get("survey_profile", {})
        if not isinstance(profile_data, dict):
            profile_data = {}

        self.survey_profile = copy.deepcopy(profile_data)

        tournament_size = preset.get("tournament_size", DEFAULT_TOURNAMENT_SIZE)
        try:
            self.selected_tournament_size = int(tournament_size)
        except (TypeError, ValueError):
            self.selected_tournament_size = DEFAULT_TOURNAMENT_SIZE

        self.beginner_preset_active = True
        self.set_active_stage("tournament")
        self.update_status(f"'{preset.get('title', '프리셋')}' 프리셋으로 토너먼트를 준비합니다.")
        self.begin_tournament()

    def show_survey_view(self):
        self.clear_content()
        self.set_active_stage("survey")

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        form = QFrame()
        form.setObjectName("ContentSection")
        form_layout = QVBoxLayout(form)
        form_layout.setContentsMargins(32, 32, 32, 32)
        form_layout.setSpacing(18)

        header = QLabel("취향 탐색 설문")
        header.setObjectName("SectionTitle")
        form_layout.addWidget(header)

        description = QLabel("선호하는 음악 스타일을 알려주시면 더 정교한 토너먼트를 준비해드릴게요.")
        description.setObjectName("BodyLabel")
        description.setWordWrap(True)
        form_layout.addWidget(description)
        tip = QLabel("각 항목의 선택은 즉시 저장되며, 상단 단계 표시줄로 언제든 이전 단계로 돌아갈 수 있어요.")
        tip.setProperty("role", "helper")
        tip.setWordWrap(True)
        form_layout.addWidget(tip)
        form_layout.addSpacing(4)

        self.genre_groups: List[Tuple[QButtonGroup, Tuple[str, str]]] = []
        self.excluded_genre_checks: List[QCheckBox] = []
        self.excluded_mood_checks: List[QCheckBox] = []
        self.excluded_instrument_checks: List[QCheckBox] = []
        for idx, pair in enumerate(self.GENRE_PAIRS, 1):
            (g1_label, g1_value, g1_desc), (g2_label, g2_value, g2_desc) = pair
            box = QGroupBox(f"{idx}. {g1_label} vs {g2_label}")
            box_layout = QHBoxLayout(box)
            box_layout.setSpacing(16)
            group = QButtonGroup(box)
            self.add_radio_option(
                box_layout,
                group,
                f"{g1_label} 선호",
                g1_value,
                g1_desc,
            )
            self.add_radio_option(
                box_layout,
                group,
                f"{g2_label} 선호",
                g2_value,
                g2_desc,
            )
            self.add_radio_option(
                box_layout,
                group,
                "잘 모르겠음",
                "s",
                "둘 다 좋아요 · 상황에 따라 달라요",
            )
            box_layout.addStretch(1)
            self.genre_groups.append((group, (g1_label, g2_label)))
            form_layout.addWidget(box)

        self.era_group = self.build_radio_section(form_layout, "시대 선호", self.ERA_OPTIONS, default="2")
        self.energy_group = self.build_radio_section(form_layout, "에너지 레벨", self.ENERGY_OPTIONS, default="3")
        self.popularity_group = self.build_radio_section(form_layout, "음악 발견 스타일", self.POPULARITY_OPTIONS, default="2")
        self.language_group = self.build_radio_section(form_layout, "가사 언어", self.LANGUAGE_OPTIONS, default="3")
        self.mood_group = self.build_radio_section(form_layout, "무드", self.MOOD_OPTIONS, default="2")
        self.sound_group = self.build_radio_section(form_layout, "사운드 질감", self.SOUND_OPTIONS, default="1")
        self.regional_focus_group = self.build_radio_section(form_layout, "국가/지역 취향", self.REGIONAL_FOCUS_OPTIONS, default="4")

        genre_options = sorted({name for name in GENRE_CODE_TABLE.values()})
        mood_pairs = [
            (self.MOOD_DESCRIPTIONS.get(mood, mood.replace('_', ' ').title()), mood)
            for mood in MOODS
        ]
        mood_pairs.sort(key=lambda item: item[0])
        instrument_pairs = [
            (self.INSTRUMENT_DESCRIPTIONS.get(inst, inst.replace('_', ' ').title()), inst)
            for inst in INSTRUMENTATIONS
        ]
        instrument_pairs.sort(key=lambda item: item[0])

        self.excluded_genre_checks = self.build_checkbox_section(
            form_layout,
            "제외할 장르", 
            [(label, label) for label in genre_options],
            columns=3,
            helper_text="듣고 싶지 않은 장르는 선택하지 않아도 괜찮아요.",
        )
        self.excluded_mood_checks = self.build_checkbox_section(
            form_layout,
            "제외할 무드",
            mood_pairs,
            columns=4,
            helper_text="피하고 싶은 분위기가 있다면 체크해주세요.",
        )
        self.excluded_instrument_checks = self.build_checkbox_section(
            form_layout,
            "제외할 편성/악기",
            instrument_pairs,
            columns=3,
            helper_text="귀에 거슬리는 악기가 있다면 선택해보세요.",
        )

        profile_snapshot = self.survey_profile if isinstance(self.survey_profile, dict) else {}

        def apply_existing_checks(checks: List[QCheckBox], key: str) -> None:
            if not isinstance(profile_snapshot, dict):
                return
            values = profile_snapshot.get(key)
            if not isinstance(values, (list, tuple, set)):
                return
            selected = {str(v) for v in values if isinstance(v, str)}
            for checkbox in checks:
                value = checkbox.property("value")
                if isinstance(value, str) and value in selected:
                    checkbox.setChecked(True)

        apply_existing_checks(self.excluded_genre_checks, "excluded_genres")
        apply_existing_checks(self.excluded_mood_checks, "excluded_moods")
        apply_existing_checks(self.excluded_instrument_checks, "excluded_instrumentations")


        size_box = QGroupBox("토너먼트 규모")
        size_box.setObjectName("OptionGroup")
        size_layout = QVBoxLayout(size_box)
        size_layout.setSpacing(12)

        size_description = QLabel("경기 수와 시간을 고려해 원하는 토너먼트 규모를 선택하세요.")
        size_description.setProperty("role", "helper")
        size_description.setWordWrap(True)
        size_layout.addWidget(size_description)

        combo = QComboBox()
        combo.setCursor(Qt.CursorShape.PointingHandCursor)
        default_index = 0
        for idx, (label, value) in enumerate(self.TOURNAMENT_SIZE_OPTIONS):
            combo.addItem(label, value)
            if value == self.selected_tournament_size:
                default_index = idx
        combo.setCurrentIndex(default_index)
        size_layout.addWidget(combo)
        self.tournament_size_combo = combo

        size_hint = QLabel("빠른 16강부터 확장 64강까지 선택할 수 있어요.")
        size_hint.setProperty("role", "helper")
        size_hint.setWordWrap(True)
        size_layout.addWidget(size_hint)

        form_layout.addWidget(size_box)

        start_button = QPushButton("토너먼트 시작")
        start_button.setProperty("variant", "primary")
        start_button.setCursor(Qt.CursorShape.PointingHandCursor)
        start_button.clicked.connect(self.begin_tournament)
        form_layout.addWidget(start_button, alignment=Qt.AlignmentFlag.AlignRight)
        form_layout.addStretch(1)

        scroll.setWidget(form)
        self.content_layout.addWidget(scroll)
        self.update_status("설문 응답을 바탕으로 맞춤 토너먼트를 준비합니다.")

    def add_radio_option(
        self,
        parent_layout: QHBoxLayout,
        group: QButtonGroup,
        text: str,
        value: str,
        description: str,
        checked: bool = False,
    ) -> QRadioButton:
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(4)
        container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        btn = QRadioButton(text)
        btn.setProperty("value", value)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        if description:
            btn.setToolTip(description)
        if checked:
            btn.setChecked(True)
        group.addButton(btn)
        container_layout.addWidget(btn)

        if description:
            helper = QLabel(description)
            helper.setProperty("role", "helper")
            helper.setWordWrap(True)
            helper.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
            container_layout.addWidget(helper)

        container_layout.addStretch(1)
        parent_layout.addWidget(container)
        return btn

    def build_radio_section(
        self,
        layout: QVBoxLayout,
        title: str,
        options: List[Tuple[str, str, str]],
        default: Optional[str] = None,
    ) -> QButtonGroup:
        box = QGroupBox(title)
        box.setObjectName("OptionGroup")
        box_layout = QHBoxLayout(box)
        box_layout.setSpacing(16)
        group = QButtonGroup(box)
        for text, value, description in options:
            self.add_radio_option(
                box_layout,
                group,
                text,
                value,
                description,
                checked=bool(default is not None and value == default),
            )
        box_layout.addStretch(1)
        layout.addWidget(box)
        return group

    def build_checkbox_section(
        self,
        layout: QVBoxLayout,
        title: str,
        options: List[Tuple[str, str]],
        columns: int = 3,
        helper_text: Optional[str] = None,
    ) -> List[QCheckBox]:
        box = QGroupBox(title)
        box.setObjectName("OptionGroup")
        box_layout = QVBoxLayout(box)
        box_layout.setSpacing(10)

        if helper_text:
            helper = QLabel(helper_text)
            helper.setProperty("role", "helper")
            helper.setWordWrap(True)
            box_layout.addWidget(helper)

        grid = QGridLayout()
        grid.setSpacing(8)
        grid.setHorizontalSpacing(16)
        checkboxes: List[QCheckBox] = []
        for idx, (label, value) in enumerate(options):
            checkbox = QCheckBox(label)
            checkbox.setProperty("value", value)
            checkbox.setCursor(Qt.CursorShape.PointingHandCursor)
            row = idx // max(1, columns)
            col = idx % max(1, columns)
            grid.addWidget(checkbox, row, col)
            checkboxes.append(checkbox)

        box_layout.addLayout(grid)
        layout.addWidget(box)
        return checkboxes

    def begin_tournament(self):
        preset_active = bool(getattr(self, "beginner_preset_active", False))

        if not preset_active:
            genre_scores: Dict[str, int] = defaultdict(int)
            for group, (g1, g2) in self.genre_groups:
                button = group.checkedButton() if group else None
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
            language_pref_map = {
                "1": {"preferred": "ko", "languages": {"ko"}, "strict": False},
                "2": {"preferred": "en", "languages": {"en", "es", "fr"}, "strict": False},
                "3": {"preferred": None, "languages": set(), "strict": False},
                "4": {"preferred": "instrumental", "languages": {"instrumental"}, "strict": True},
            }
            mood_map = {
                "1": {"moods": {"energetic", "empowering", "upbeat"}, "weight": 0.9},
                "2": {"moods": {"romantic", "dreamy", "mellow"}, "weight": 0.7},
                "3": {"moods": {"groovy", "funky", "soulful"}, "weight": 0.8},
                "4": {"moods": {"introspective", "nocturnal", "melancholic"}, "weight": 0.85},
            }
            sound_map = {
                "1": {"instrumentations": {"guitar", "drums", "bass", "vocals"}},
                "2": {"instrumentations": {"synth", "electronic_beats", "samples"}},
                "3": {"instrumentations": {"piano", "strings", "vocals"}},
                "4": {"instrumentations": {"saxophone", "trumpet", "bass"}},
            }
            regional_focus_map = {"1": "k_only", "2": "k_prefer", "3": "global", "4": "neutral"}

            def group_value(group: Optional[QButtonGroup], default: str) -> str:
                if not group:
                    return default
                button = group.checkedButton()
                return button.property("value") if button else default

            language_pref = language_pref_map.get(
                group_value(self.language_group, "3"),
                {"preferred": None, "languages": set(), "strict": False},
            )
            mood_pref = mood_map.get(
                group_value(self.mood_group, "2"),
                {"moods": set(), "weight": 0.0},
            )
            sound_pref = sound_map.get(
                group_value(self.sound_group, "1"),
                {"instrumentations": set()},
            )
            regional_focus = regional_focus_map.get(
                group_value(self.regional_focus_group, "4"),
                "neutral",
            )

            def collect_checked(checks: Optional[Iterable[QCheckBox]]) -> List[str]:
                values: List[str] = []
                if not checks:
                    return values
                for checkbox in checks:
                    if not isinstance(checkbox, QCheckBox):
                        continue
                    if checkbox.isChecked():
                        value = checkbox.property("value")
                        if isinstance(value, str) and value:
                            values.append(value)
                return sorted(dict.fromkeys(values))

            survey_profile: Dict[str, Any] = {
                "genre_scores": dict(genre_scores),
                "preferred_era": era_map.get(group_value(self.era_group, "2")),
                "preferred_energy": energy_map.get(group_value(self.energy_group, "3"), 0.5),
                "preferred_popularity": pop_map.get(group_value(self.popularity_group, "2"), 0.5),
                "preferred_language": language_pref["preferred"],
                "preferred_languages": sorted(language_pref["languages"]),
                "language_strict": language_pref["strict"],
                "preferred_moods": sorted(mood_pref["moods"]),
                "mood_weight": mood_pref["weight"],
                "preferred_instrumentations": sorted(sound_pref["instrumentations"]),
                "regional_focus": regional_focus,
                "excluded_genres": collect_checked(getattr(self, "excluded_genre_checks", [])),
                "excluded_moods": collect_checked(getattr(self, "excluded_mood_checks", [])),
                "excluded_instrumentations": collect_checked(getattr(self, "excluded_instrument_checks", [])),
            }
        else:
            survey_profile = (
                copy.deepcopy(self.survey_profile)
                if isinstance(self.survey_profile, dict)
                else {}
            )

        def _coerce_float(value: Any, default: float) -> float:
            if value is None:
                return default
            try:
                return float(value)
            except (TypeError, ValueError):
                return default

        def _coerce_int(value: Any) -> Optional[int]:
            if value is None:
                return None
            try:
                return int(value)
            except (TypeError, ValueError):
                return None

        genre_scores = survey_profile.get("genre_scores", {})
        if not isinstance(genre_scores, dict):
            genre_scores = {}
        survey_profile["genre_scores"] = {
            str(k): int(v)
            for k, v in genre_scores.items()
            if isinstance(k, str) and isinstance(v, (int, float))
        }

        def _normalize_str_list(value: Any) -> List[str]:
            if isinstance(value, (list, tuple, set)):
                return sorted({str(item) for item in value if isinstance(item, str) and item})
            return []

        survey_profile["preferred_languages"] = _normalize_str_list(survey_profile.get("preferred_languages"))
        survey_profile["preferred_moods"] = _normalize_str_list(survey_profile.get("preferred_moods"))
        survey_profile["preferred_instrumentations"] = _normalize_str_list(
            survey_profile.get("preferred_instrumentations")
        )
        survey_profile["excluded_genres"] = _normalize_str_list(survey_profile.get("excluded_genres"))
        survey_profile["excluded_moods"] = _normalize_str_list(survey_profile.get("excluded_moods"))
        survey_profile["excluded_instrumentations"] = _normalize_str_list(
            survey_profile.get("excluded_instrumentations")
        )

        survey_profile["preferred_era"] = _coerce_int(survey_profile.get("preferred_era"))
        survey_profile["preferred_energy"] = _coerce_float(survey_profile.get("preferred_energy"), 0.5)
        survey_profile["preferred_popularity"] = _coerce_float(
            survey_profile.get("preferred_popularity"),
            0.5,
        )
        survey_profile["preferred_language"] = (
            survey_profile.get("preferred_language")
            if isinstance(survey_profile.get("preferred_language"), str)
            else None
        )
        survey_profile["language_strict"] = bool(survey_profile.get("language_strict", False))
        survey_profile["mood_weight"] = _coerce_float(survey_profile.get("mood_weight"), 0.0)

        regional_focus = survey_profile.get("regional_focus", "neutral")
        if regional_focus not in {"k_only", "k_prefer", "global", "neutral"}:
            regional_focus = "neutral"
        survey_profile["regional_focus"] = regional_focus

        self.survey_profile = survey_profile
        self.beginner_preset_active = False

        desired_size = self.selected_tournament_size
        if not preset_active and self.tournament_size_combo:
            data = self.tournament_size_combo.currentData()
            if isinstance(data, int):
                desired_size = data
            else:
                try:
                    desired_size = int(data)
                except (TypeError, ValueError):
                    desired_size = DEFAULT_TOURNAMENT_SIZE
        available = len(self.songs)
        effective_size, adjusted = determine_effective_tournament_size(desired_size, available)
        if adjusted and effective_size > 0:
            QMessageBox.warning(
                self,
                "후보 수 조정",
                f"선택한 토너먼트 규모({desired_size}강)가 사용 가능한 곡 수({available}곡)보다 많아 {effective_size}강으로 조정했습니다.",
            )
        if effective_size <= 0:
            QMessageBox.warning(
                self,
                "후보 부족",
                "토너먼트를 구성할 곡이 없습니다. 데이터를 확인해주세요.",
            )
            self.show_start_view()
            return
        self.selected_tournament_size = effective_size

        selector = CandidateSelector(self.songs, self.survey_profile)
        self.candidates = selector.select_candidates(k=effective_size)
        self.seed_scores = selector.get_seed_scores()

        if len(self.candidates) < 2:
            QMessageBox.warning(self, "후보 부족", "토너먼트를 진행하기에 곡이 부족합니다. 데이터를 확인해주세요.")
            self.show_start_view()
            return

        if len(self.candidates) % 2 == 1:
            removed = self.candidates.pop()
            if removed:
                self.seed_scores.pop(removed.id, None)

        self.selected_tournament_size = len(self.candidates)

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
        self.total_matches = len(self.candidates) - 1 if len(self.candidates) >= 2 else 0

        self.update_status(f"{self.selected_tournament_size}강 토너먼트를 준비 중입니다.")
        self.show_match_view()

    def show_match_view(self):
        self.clear_content()
        self.set_active_stage("tournament")

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        container = QFrame()
        container.setObjectName("ContentSection")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(18)

        title = QLabel("토너먼트 진행 중")
        title.setObjectName("SectionTitle")
        layout.addWidget(title)

        self.round_badge = QLabel()
        self.round_badge.setObjectName("RoundBadge")
        layout.addWidget(self.round_badge, 0, Qt.AlignmentFlag.AlignLeft)

        self.match_status_label = QLabel()
        self.match_status_label.setObjectName("MatchStatusLabel")
        layout.addWidget(self.match_status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%p% 완료")
        layout.addWidget(self.progress_bar)

        self.progress_summary_label = QLabel()
        self.progress_summary_label.setObjectName("ProgressCaption")
        self.progress_summary_label.setWordWrap(True)
        layout.addWidget(self.progress_summary_label)

        cards_container = QWidget()
        cards_container.setObjectName("MatchCardsContainer")
        cards_layout = QHBoxLayout(cards_container)
        cards_layout.setContentsMargins(0, 0, 0, 0)
        cards_layout.setSpacing(16)
        self.card_a = self.create_song_card(cards_container, "A 곡", "A")
        self.card_b = self.create_song_card(cards_container, "B 곡", "B")
        cards_layout.addWidget(self.card_a["box"], 1)
        cards_layout.addWidget(self.card_b["box"], 1)
        layout.addWidget(cards_container)

        self.helper_label = QLabel("키보드 A/B/T/S로도 선택할 수 있어요.")
        self.helper_label.setProperty("role", "helper")
        self.helper_label.setWordWrap(True)
        layout.addWidget(self.helper_label)

        button_row = QWidget()
        button_layout = QGridLayout(button_row)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(12)

        def add_button(text: str, row: int, col: int, choice: str):
            button = QPushButton(text)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(lambda _=False, c=choice: self.on_choice(c))
            button_layout.addWidget(button, row, col)

        add_button("둘 다 좋아요", 0, 0, "T")
        add_button("건너뛰기", 0, 1, "S")
        layout.addWidget(button_row)

        shortcut_map = {"A": "A", "B": "B", "T": "T", "S": "S"}
        for key, choice in shortcut_map.items():
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.activated.connect(lambda c=choice: self.on_choice(c))
            self.shortcuts.append(shortcut)

        scroll.setWidget(container)
        self.content_layout.addWidget(scroll)
        self.update_status("토너먼트가 진행 중입니다. 클릭 한 번으로 선택하세요!")
        self.display_current_match()

    def format_song_summary(self, song: Song) -> Dict[str, Any]:
        tags = song.tags if isinstance(song.tags, dict) else {}

        era_label = self._format_era_label(tags.get("era_year"))
        genre_label, genre_key = self._primary_genre_label(song)
        base_segment = " ".join(part for part in (era_label, genre_label) if part).strip()

        subgenre_phrase, subgenre_key = self._subgenre_descriptor(tags.get("subgenres"))
        instrumentation_phrase, inst_key = self._instrumentation_descriptor(tags.get("instrumentation"))
        mood_phrase = self._mood_descriptor(tags.get("mood"))

        detail_candidates = [subgenre_phrase, instrumentation_phrase, mood_phrase]
        detail_parts: List[str] = []
        glossary_keys: List[str] = []
        if genre_key:
            glossary_keys.append(genre_key)
        for key in (subgenre_key, inst_key):
            if key and key not in glossary_keys:
                glossary_keys.append(key)

        for phrase in detail_candidates:
            if phrase and phrase not in detail_parts:
                detail_parts.append(phrase)

        summary_segments: List[str] = []
        if base_segment:
            summary_segments.append(base_segment)
        for phrase in detail_parts:
            if phrase not in summary_segments:
                summary_segments.append(phrase)
            if len(summary_segments) >= 3:
                break

        if summary_segments:
            summary_text = " · ".join(summary_segments)
        else:
            summary_text = "태그 정보가 충분하지 않습니다"

        highlight: Optional[str] = None
        focus: Optional[str] = None
        if detail_parts:
            selected = detail_parts[:2]
            if len(selected) == 1:
                focus = selected[0]
            else:
                conjunction = self._select_conjunction(selected[0])
                focus = f"{selected[0]}{conjunction} {selected[1]}"
        elif genre_label:
            focus = genre_label
        elif era_label:
            focus = era_label

        if focus:
            focus_with_particle = self._attach_object_particle(focus)
            highlight = f"이런 분께 추천: {focus_with_particle} 좋아한다면"

        return {
            "summary": summary_text,
            "highlight": highlight,
            "glossary_keys": glossary_keys,
        }

    def _format_era_label(self, era_year: Optional[Any]) -> Optional[str]:
        if not isinstance(era_year, int):
            return None
        year = era_year
        if year >= 2024:
            return "2020년대 중반"
        if year >= 2020:
            return "2020년대 초반"
        if year >= 2018:
            return "2010년대 후반"
        if year >= 2012:
            return "2010년대 중반"
        if year >= 2006:
            return "2000년대 후반"
        if year >= 1998:
            return "90년대 말~2000년대 초"
        if year >= 1990:
            return "90년대 초중반"
        if year >= 1980:
            return "80년대"
        if year >= 1970:
            return "70년대"
        if year >= 1960:
            return "60년대"
        return "60년대 이전"

    def _primary_genre_label(self, song: Song) -> Tuple[Optional[str], Optional[str]]:
        genres = song.genres or []
        if not genres and song.genre_codes:
            genres = decode_genre_names(song.genre_codes)
        if not genres:
            return None, None
        primary = genres[0]
        label = PreferenceSummarizer.GENRE_LABELS.get(primary, primary)
        key = primary if primary in PreferenceSummarizer.GENRE_LABELS else None
        return label, key

    def _subgenre_descriptor(self, subgenres: Optional[Any]) -> Tuple[Optional[str], Optional[str]]:
        if not isinstance(subgenres, list):
            return None, None
        for item in subgenres:
            if not isinstance(item, str):
                continue
            descriptor = PreferenceSummarizer.SUBGENRE_TONES.get(item)
            if descriptor:
                return descriptor, item
        for item in subgenres:
            if isinstance(item, str):
                return item.replace("_", " ") + " 무드", None
        return None, None

    def _mood_descriptor(self, moods: Optional[Any]) -> Optional[str]:
        if not isinstance(moods, list):
            return None
        for mood in moods:
            if not isinstance(mood, str):
                continue
            descriptor = self.MOOD_DESCRIPTIONS.get(mood)
            if descriptor:
                return descriptor
        for mood in moods:
            if isinstance(mood, str):
                return mood.replace("_", " ") + " 무드"
        return None

    def _instrumentation_descriptor(self, instrumentation: Optional[Any]) -> Tuple[Optional[str], Optional[str]]:
        if not isinstance(instrumentation, list):
            return None, None
        for inst in instrumentation:
            if not isinstance(inst, str):
                continue
            descriptor = PreferenceSummarizer.INSTRUMENT_TONES.get(inst)
            if descriptor:
                return descriptor, inst
            descriptor = self.INSTRUMENT_DESCRIPTIONS.get(inst)
            if descriptor:
                return descriptor, inst
        for inst in instrumentation:
            if isinstance(inst, str):
                return inst.replace("_", " ") + " 사운드", None
        return None, None

    @staticmethod
    def _attach_object_particle(phrase: str) -> str:
        trimmed = phrase.strip()
        if not trimmed:
            return trimmed
        last_char = trimmed[-1]
        if "가" <= last_char <= "힣":
            code = ord(last_char) - 0xAC00
            particle = "를" if code % 28 == 0 else "을"
        else:
            particle = "를"
        return f"{trimmed}{particle}"

    @staticmethod
    def _select_conjunction(phrase: str) -> str:
        trimmed = phrase.strip()
        if not trimmed:
            return "와"
        last_char = trimmed[-1]
        if "가" <= last_char <= "힣":
            code = ord(last_char) - 0xAC00
            return "과" if code % 28 != 0 else "와"
        return "와"

    def create_song_card(self, parent: QWidget, title: str, side: str) -> Dict[str, Any]:
        box = QGroupBox(title)
        box.setObjectName("SongCard")
        box.setProperty("side", side)
        layout = QVBoxLayout(box)
        layout.setSpacing(10)
        name_label = QLabel()
        name_label.setObjectName("SongTitle")
        layout.addWidget(name_label)
        meta_label = QLabel()
        meta_label.setObjectName("MetaLabel")
        layout.addWidget(meta_label)
        tag_label = QLabel()
        tag_label.setWordWrap(True)
        tag_label.setProperty("role", "helper")
        tag_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.MinimumExpanding)
        layout.addWidget(tag_label)
        glossary_button = QToolButton()
        glossary_button.setObjectName("GlossaryButton")
        glossary_button.setText("용어 설명 보기")
        glossary_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxInformation))
        glossary_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        glossary_button.setCursor(Qt.CursorShape.PointingHandCursor)
        glossary_button.setProperty("role", "helper")
        glossary_button.setVisible(False)
        glossary_button.clicked.connect(self._handle_glossary_button_click)
        layout.addWidget(glossary_button, alignment=Qt.AlignmentFlag.AlignLeft)
        preview_embed = SongPreviewEmbed(box, minimum_height=160)
        layout.addWidget(preview_embed)
        layout.addStretch(1)
        select_button = QPushButton(f"{side} 곡 선택")
        select_button.setProperty("variant", "primary")
        select_button.setCursor(Qt.CursorShape.PointingHandCursor)
        select_button.clicked.connect(lambda _=False, c=side: self.on_choice(c))
        layout.addWidget(select_button)
        return {
            "box": box,
            "title": name_label,
            "meta": meta_label,
            "tag": tag_label,
            "glossary_button": glossary_button,
            "preview_embed": preview_embed,
            "button": select_button,
        }


    def update_song_card(self, card: Dict[str, Any], song: Song) -> None:
        card["title"].setText(song.get_display_title())
        rating = song.rating if song.rating else 1500
        card["meta"].setText(f"{song.artist} · 예상 레이팅 {rating:.0f}")
        summary_info = self.format_song_summary(song)
        lines: List[str] = []
        summary_text = summary_info.get("summary")
        if summary_text:
            lines.append(summary_text)
        highlight = summary_info.get("highlight")
        if highlight:
            lines.append(highlight)
        card["tag"].setText("\n".join(lines))
        glossary_button = card.get("glossary_button")
        glossary_keys = summary_info.get("glossary_keys") if isinstance(summary_info, dict) else None
        keys_list = list(glossary_keys or [])
        if glossary_button:
            glossary_button.setProperty("glossaryKeys", keys_list)
            glossary_button.setVisible(bool(keys_list))
            glossary_button.setEnabled(bool(keys_list))
            if keys_list:
                glossary_button.setToolTip("요약에 등장하는 용어 설명을 확인해보세요.")
            else:
                glossary_button.setToolTip("")
        card["preview_embed"].set_song(song)

    def _handle_glossary_button_click(self):
        sender = self.sender()
        if not sender:
            return
        keys = sender.property("glossaryKeys") if hasattr(sender, "property") else None
        key_list: List[str] = []
        if isinstance(keys, (list, tuple, set)):
            key_list = [str(key) for key in keys]
        elif isinstance(keys, str):
            key_list = [keys]
        self.show_glossary_popup(key_list)

    def show_glossary_popup(self, keys: Iterable[str]):
        glossary = PreferenceSummarizer.glossary()
        rows: List[str] = []
        for key in keys:
            info = glossary.get(str(key))
            if not info:
                continue
            label = info.get("label", str(key))
            description = info.get("description", "")
            rows.append(f"• {label}: {description}")
        if not rows:
            QMessageBox.information(self, "용어 설명", "설명할 용어가 없습니다.")
            return
        message = "\n".join(rows)
        QMessageBox.information(self, "용어 설명", message)

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
        total_rounds = len(self.bracket) if self.bracket else 1
        if hasattr(self, "round_badge"):
            self.round_badge.setText(f"ROUND {self.current_round_number} / {total_rounds}")
        self.match_status_label.setText(
            f"{match.match_id} · 라운드 {self.current_round_number}의 {self.current_match_index + 1}/{len(self.current_round_matches)} 매치"
        )
        self.helper_label.setText(
            f"{match.song_a.get_display_title()} vs {match.song_b.get_display_title()}\n키보드 A/B/T/S로도 빠르게 선택할 수 있어요."
        )
        self.update_song_card(self.card_a, match.song_a)
        self.update_song_card(self.card_b, match.song_b)
        progress_ratio = len(self.engine.match_history) / self.total_matches if self.total_matches else 0
        self.progress_bar.setValue(int(progress_ratio * 100))
        if hasattr(self, "progress_summary_label"):
            played = len(self.engine.match_history)
            self.progress_summary_label.setText(
                f"전체 {self.total_matches} 매치 중 {played} 완료 · 다음 선택: {match.match_id}"
            )

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
        self.set_active_stage("results")
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        container = QFrame()
        container.setObjectName("ContentSection")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(18)

        title = QLabel("토너먼트 결과")
        title.setObjectName("SectionTitle")
        layout.addWidget(title)

        scroll.setWidget(container)
        self.content_layout.addWidget(scroll)

        if not self.champion or not self.engine:
            message = QLabel("토너먼트 결과가 존재하지 않습니다.")
            message.setObjectName("BodyLabel")
            layout.addWidget(message)
            back = QPushButton("처음으로")
            back.setCursor(Qt.CursorShape.PointingHandCursor)
            back.clicked.connect(self.show_start_view)
            layout.addWidget(back, alignment=Qt.AlignmentFlag.AlignLeft)
            layout.addStretch(1)
            self.update_status("토너먼트 결과가 없습니다.")
            return

        analyzer = ResultAnalyzer(self.engine.match_history, self.candidates, self.survey_profile)
        self.report = analyzer.generate_report(self.champion)
        recommender = RecommendationEngine(self.songs, self.candidates, self.survey_profile)
        self.recommendations = recommender.generate_recommendations(self.report["top_songs"])

        summary_card = QFrame()
        summary_card.setObjectName("InsightCard")
        summary_layout = QVBoxLayout(summary_card)
        summary_layout.setSpacing(8)

        champion_label = QLabel(
            f"우승 곡: {self.champion.artist} - {self.champion.get_display_title()}"
        )
        champion_label.setObjectName("ChampionTitle")
        summary_layout.addWidget(champion_label)

        record_label = QLabel(
            f"레이팅 {self.champion.rating:.1f} · 전적 {self.champion.wins}승 {self.champion.losses}패"
        )
        record_label.setObjectName("BodyLabel")
        summary_layout.addWidget(record_label)

        summary_text = self.report.get("preference_summary") if self.report else None
        if summary_text:
            summary_label = QLabel(f"취향 요약: {summary_text}")
            summary_label.setObjectName("BodyLabel")
            summary_label.setWordWrap(True)
            summary_layout.addWidget(summary_label)

        champion_embed = SongPreviewEmbed(summary_card, minimum_height=200)
        champion_embed.set_song(self.champion)
        summary_layout.addWidget(champion_embed)

        if self.report["top_songs"]:
            playlist_label = QLabel("상위 플레이리스트")
            playlist_label.setObjectName("RecommendationGroupLabel")
            summary_layout.addWidget(playlist_label)
            for idx, song in enumerate(self.report["top_songs"], 1):
                song_label = QLabel(
                    f"{idx}. {song.artist} - {song.get_display_title()}"
                )
                song_label.setObjectName("BodyLabel")
                summary_layout.addWidget(song_label)

        layout.addWidget(summary_card)

        stats = self.report["choice_distribution"]
        stats_card = QFrame()
        stats_card.setObjectName("InsightCard")
        stats_layout = QVBoxLayout(stats_card)
        stats_layout.setSpacing(6)
        stats_title = QLabel("선택 통계")
        stats_title.setObjectName("RecommendationGroupLabel")
        stats_layout.addWidget(stats_title)
        stats_label = QLabel(
            f"총 매치 {self.report['total_matches']} · A {stats.get('A', 0)} · B {stats.get('B', 0)} · 둘 다 {stats.get('T', 0)} · 건너뛰기 {stats.get('S', 0)}"
        )
        stats_label.setObjectName("BodyLabel")
        stats_label.setProperty("role", "helper")
        stats_label.setWordWrap(True)
        stats_layout.addWidget(stats_label)
        layout.addWidget(stats_card)

        self.render_recommendations(layout)
        self.render_match_history(layout)

        back_button = QPushButton("처음으로 돌아가기")
        back_button.setCursor(Qt.CursorShape.PointingHandCursor)
        back_button.clicked.connect(self.show_start_view)

        export_button = QPushButton("결과 내보내기")
        export_button.setCursor(Qt.CursorShape.PointingHandCursor)
        export_button.clicked.connect(self.export_results)

        button_row = QHBoxLayout()
        button_row.setSpacing(12)
        button_row.addWidget(back_button)
        button_row.addWidget(export_button)
        button_row.addStretch(1)
        layout.addLayout(button_row)
        layout.addStretch(1)

        self.update_status("결과를 확인하고 추천곡과 매치 히스토리를 아래에서 확인해보세요.")

    def export_results(self):
        if not getattr(self, "report", None):
            self.update_status("내보낼 결과가 없습니다.")
            QMessageBox.warning(self, "내보내기 실패", "저장할 토너먼트 결과가 없습니다.")
            return

        try:
            context = self._gather_export_context()
            html = self._build_export_html(context)
        except Exception as exc:
            self.update_status("결과 내보내기 구성에 실패했습니다.")
            QMessageBox.warning(self, "내보내기 실패", f"PDF 생성 준비 중 오류가 발생했습니다.\n{exc}")
            return

        default_path = Path.home() / "music_tournament_result.pdf"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "PDF로 저장",
            str(default_path),
            "PDF 파일 (*.pdf);;모든 파일 (*)",
        )
        if not file_path:
            self.update_status("결과 내보내기가 취소되었습니다.")
            return

        file_path = Path(file_path)
        if file_path.suffix.lower() != ".pdf":
            file_path = file_path.with_suffix(".pdf")

        try:
            self._write_pdf(file_path, html)
            self.update_status(f"결과를 '{file_path.name}' PDF로 저장했습니다.")
            QMessageBox.information(self, "저장 완료", "결과가 PDF로 저장되었습니다.")
        except Exception as exc:
            self.update_status("PDF 저장에 실패했습니다.")
            QMessageBox.warning(self, "저장 실패", f"PDF 저장 중 오류가 발생했습니다.\n{exc}")

    def _gather_export_context(self) -> Dict[str, Any]:
        report: Dict[str, Any] = getattr(self, "report", {}) or {}
        recommendations: Dict[str, Any] = getattr(self, "recommendations", {}) or {}

        champion: Optional[Song] = report.get("champion") or getattr(self, "champion", None)
        top_songs: List[Song] = report.get("top_songs") or []

        champion_summary = (
            self.format_song_summary(champion)
            if champion
            else {"summary": None, "highlight": None, "glossary_keys": []}
        )

        top_song_entries: List[Dict[str, Any]] = []
        for idx, song in enumerate(top_songs, 1):
            if not song:
                continue
            summary_info = self.format_song_summary(song)
            top_song_entries.append(
                {
                    "index": idx,
                    "title": song.get_display_title(),
                    "artist": song.artist,
                    "rating": song.rating,
                    "summary": summary_info.get("summary"),
                    "highlight": summary_info.get("highlight"),
                    "glossary_keys": summary_info.get("glossary_keys"),
                }
            )

        recommendation_groups: List[Dict[str, Any]] = []
        recommendation_mapping = (
            ("🎯 취향 저격 트랙", recommendations.get("core", [])),
            ("🌱 새롭게 시도해볼 곡", recommendations.get("fresh", [])),
        )
        for label, entries in recommendation_mapping:
            items: List[Dict[str, Any]] = []
            for entry in entries:
                song = entry.get("song") if isinstance(entry, dict) else None
                if not song:
                    continue
                summary_info = self.format_song_summary(song)
                items.append(
                    {
                        "title": song.get_display_title(),
                        "artist": song.artist,
                        "reason": entry.get("reason") if isinstance(entry, dict) else None,
                        "summary": summary_info.get("summary"),
                        "highlight": summary_info.get("highlight"),
                        "glossary_keys": summary_info.get("glossary_keys"),
                        "usage_tip": entry.get("usage_tip") if isinstance(entry, dict) else None,
                    }
                )
            if items:
                recommendation_groups.append({"label": label, "items": items})

        return {
            "generated_at": datetime.now(),
            "champion": {
                "title": champion.get_display_title() if champion else "-",
                "artist": champion.artist if champion else "-",
                "rating": champion.rating if champion else None,
                "record": f"{champion.wins}승 {champion.losses}패" if champion else None,
                "summary": champion_summary.get("summary"),
                "highlight": champion_summary.get("highlight"),
                "glossary_keys": champion_summary.get("glossary_keys"),
            },
            "summary": report.get("preference_summary"),
            "total_matches": report.get("total_matches"),
            "choice_distribution": report.get("choice_distribution", {}),
            "top_songs": top_song_entries,
            "recommendations": recommendation_groups,
            "glossary": PreferenceSummarizer.glossary(),
        }

    def _build_export_html(self, context: Dict[str, Any]) -> str:
        def safe(text: Optional[Any]) -> str:
            if text is None:
                return ""
            return escape(str(text))

        def render_text_block(text: Optional[Any], css_class: str) -> str:
            if not text:
                return ""
            escaped = safe(text).replace("\n", "<br>")
            return f"<div class='{css_class}'>{escaped}</div>"

        glossary_map: Dict[str, Dict[str, str]] = context.get("glossary", {}) or {}

        def render_glossary_block(keys: Optional[Any]) -> str:
            if not keys:
                return ""
            rows = []
            for key in keys:
                info = glossary_map.get(str(key))
                if not info:
                    continue
                label = safe(info.get("label"))
                description = safe(info.get("description"))
                rows.append(
                    f"<li><span class='annotation-term'>{label}</span><span class='annotation-desc'>{description}</span></li>"
                )
            if not rows:
                return ""
            return "<div class='annotation-block'><div class='annotation-title'>용어 노트</div><ul class='annotation-list'>" + "".join(rows) + "</ul></div>"

        def render_usage_block(tip: Optional[Any]) -> str:
            if not tip:
                return ""
            return (
                "<div class='annotation-block usage-block'>"
                "<div class='annotation-title'>이 곡은 언제 어울려요</div>"
                f"<p class='annotation-text'>{safe(tip)}</p></div>"
            )

        generated_at = context.get("generated_at")
        generated_text = generated_at.strftime("%Y.%m.%d %H:%M") if generated_at else ""

        champion = context.get("champion", {})
        top_songs = context.get("top_songs", [])
        recommendations = context.get("recommendations", [])
        stats = context.get("choice_distribution", {}) or {}
        total_matches = context.get("total_matches")
        summary = context.get("summary")

        champion_rating_value = champion.get("rating")
        if isinstance(champion_rating_value, (int, float)):
            champion_rating_display = f"{champion_rating_value:.1f}"
        else:
            champion_rating_display = "-"
        champion_record = champion.get("record") or "-"
        champion_summary_html = render_text_block(champion.get("summary"), "champion-summary")
        champion_highlight_html = render_text_block(champion.get("highlight"), "champion-highlight")
        champion_glossary_html = render_glossary_block(champion.get("glossary_keys"))

        top_song_html = ""
        if top_songs:
            items = []
            for entry in top_songs:
                rating = entry.get("rating")
                rating_text = f" · 레이팅 {rating:.1f}" if isinstance(rating, (int, float)) else ""
                header = (
                    "<div class='song-header'>"
                    f"<span class='song-title'>{safe(entry.get('title'))}</span>"
                    f"<span class='song-artist'> — {safe(entry.get('artist'))}</span>"
                    + (f"<span class='song-meta'>{safe(rating_text)}</span>" if rating_text else "")
                    + "</div>"
                )
                summary_block = render_text_block(entry.get("summary"), "song-summary")
                highlight_block = render_text_block(entry.get("highlight"), "song-highlight")
                glossary_block = render_glossary_block(entry.get("glossary_keys"))
                items.append("<li>" + header + summary_block + highlight_block + glossary_block + "</li>")
            top_song_html = "<section><h2>상위 플레이리스트</h2><ol>" + "".join(items) + "</ol></section>"

        recommendation_html = ""
        if recommendations:
            sections = []
            for group in recommendations:
                rows = []
                for idx, item in enumerate(group.get("items", []), 1):
                    summary_block = render_text_block(item.get("summary"), "recommendation-summary")
                    highlight_block = render_text_block(item.get("highlight"), "recommendation-highlight")
                    reason_block = render_text_block(item.get("reason"), "recommendation-reason")
                    usage_block = render_usage_block(item.get("usage_tip"))
                    glossary_block = render_glossary_block(item.get("glossary_keys"))
                    rows.append(
                        "<div class='recommendation-item'>"
                        f"<div class='recommendation-title'>{idx}. {safe(item.get('title'))}</div>"
                        f"<div class='recommendation-artist'>{safe(item.get('artist'))}</div>"
                        + summary_block
                        + highlight_block
                        + reason_block
                        + usage_block
                        + glossary_block
                        + "</div>"
                    )
                sections.append(
                    f"<div class='recommendation-group'><h3>{safe(group.get('label'))}</h3>"
                    + "".join(rows)
                    + "</div>"
                )
            recommendation_html = "<section><h2>맞춤 추천</h2>" + "".join(sections) + "</section>"

        stats_html = ""
        if total_matches is not None or stats:
            stats_rows = []
            if total_matches is not None:
                stats_rows.append(
                    f"<div class='stat-row'><span class='stat-label'>총 매치</span><span class='stat-value'>{safe(total_matches)}</span></div>"
                )
            label_map = {
                "A": "A 선택",
                "B": "B 선택",
                "T": "둘 다",
                "S": "건너뛰기",
            }
            for key, label in label_map.items():
                if key in stats:
                    stats_rows.append(
                        f"<div class='stat-row'><span class='stat-label'>{label}</span><span class='stat-value'>{safe(stats.get(key))}</span></div>"
                    )
            stats_html = "<section><h2>선택 통계</h2>" + "".join(stats_rows) + "</section>"

        summary_html = ""
        if summary:
            summary_html = (
                "<section><h2>취향 요약</h2>"
                f"<p class='summary-text'>{safe(summary)}</p></section>"
            )

        html = f"""
<!DOCTYPE html>
<html lang=\"ko\">
<head>
    <meta charset=\"utf-8\">
    <style>
        body {{
            font-family: 'Apple SD Gothic Neo', 'Malgun Gothic', 'Pretendard', sans-serif;
            color: #1f2933;
            margin: 0;
            padding: 36px 48px;
            background: #ffffff;
            font-size: 14px;
        }}
        header {{
            border-bottom: 2px solid #e5e9f0;
            margin-bottom: 24px;
            padding-bottom: 12px;
        }}
        h1 {{
            font-size: 30px;
            margin: 0;
        }}
        h2 {{
            font-size: 22px;
            margin-top: 28px;
            margin-bottom: 12px;
        }}
        h3 {{
            font-size: 18px;
            margin-bottom: 8px;
        }}
        p {{
            line-height: 1.6;
            font-size: 14px;
            margin: 0;
        }}
        .meta {{
            color: #64748b;
            font-size: 13px;
            margin-top: 4px;
        }}
        .champion-card {{
            border-radius: 12px;
            border: 1px solid #e2e8f0;
            padding: 20px;
            background: linear-gradient(135deg, #f8fafc, #ffffff);
        }}
        .champion-title {{
            font-size: 24px;
            font-weight: 600;
            margin-bottom: 6px;
        }}
        .champion-artist {{
            color: #475569;
            font-size: 16px;
        }}
        .champion-meta {{
            margin-top: 10px;
            display: flex;
            gap: 12px;
            font-size: 14px;
            color: #0f172a;
        }}
        .champion-summary {{
            margin-top: 12px;
            color: #334155;
            line-height: 1.6;
        }}
        .champion-highlight {{
            margin-top: 6px;
            color: #0f172a;
            font-size: 13px;
            font-weight: 600;
        }}
        section {{
            margin-top: 24px;
        }}
        ol {{
            margin: 0;
            padding-left: 20px;
        }}
        ol li {{
            margin-bottom: 12px;
            font-size: 14px;
        }}
        .song-header {{
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
            align-items: baseline;
        }}
        .song-title {{
            font-weight: 600;
            color: #1e293b;
            font-size: 15px;
        }}
        .song-artist {{
            color: #475569;
            font-size: 13px;
        }}
        .song-meta {{
            color: #64748b;
            font-size: 13px;
        }}
        .song-summary {{
            margin-top: 4px;
            color: #475569;
            line-height: 1.5;
        }}
        .song-highlight {{
            margin-top: 2px;
            color: #0f172a;
            font-size: 13px;
            font-weight: 500;
        }}
        .stat-row {{
            display: flex;
            justify-content: space-between;
            border-bottom: 1px dashed #e2e8f0;
            padding: 6px 0;
            font-size: 14px;
        }}
        .stat-label {{
            color: #475569;
        }}
        .stat-value {{
            font-weight: 600;
        }}
        .summary-text {{
            background: #f8fafc;
            border-radius: 10px;
            padding: 16px;
            font-size: 14px;
        }}
        .recommendation-group {{
            border: 1px solid #e2e8f0;
            border-radius: 12px;
            padding: 16px;
            margin-bottom: 16px;
            background: #fcfdff;
        }}
        .recommendation-item {{
            margin-bottom: 12px;
            padding: 10px 12px;
            border-radius: 10px;
            background: #f8fafc;
        }}
        .recommendation-title {{
            font-weight: 600;
            font-size: 15px;
            color: #1e293b;
        }}
        .recommendation-artist {{
            color: #475569;
            font-size: 13px;
        }}
        .recommendation-summary {{
            margin-top: 6px;
            color: #334155;
            line-height: 1.5;
        }}
        .recommendation-highlight {{
            margin-top: 4px;
            color: #0f172a;
            font-size: 13px;
            font-weight: 500;
        }}
        .recommendation-reason {{
            color: #334155;
            font-size: 13px;
            margin-top: 4px;
            line-height: 1.5;
        }}
        .annotation-block {{
            margin-top: 6px;
            padding: 8px 10px;
            border-left: 3px solid #94a3b8;
            background: #f8fafc;
            color: #475569;
            font-size: 12px;
        }}
        .annotation-title {{
            font-weight: 600;
            margin-bottom: 4px;
            color: #0f172a;
        }}
        .annotation-list {{
            margin: 0;
            padding-left: 16px;
        }}
        .annotation-list li {{
            margin-bottom: 2px;
        }}
        .annotation-term {{
            font-weight: 600;
            margin-right: 4px;
        }}
        .annotation-desc {{
            color: #1f2937;
        }}
        .annotation-text {{
            margin: 0;
            line-height: 1.6;
        }}
        footer {{
            margin-top: 32px;
            font-size: 12px;
            color: #94a3b8;
            text-align: right;
        }}
    </style>
</head>
<body>
    <header>
        <h1>WhatsMyMusicFlavor · 결과 리포트</h1>
        <div class='meta'>생성일시 {safe(generated_text)}</div>
    </header>
    <section class='champion-card'>
        <div class='champion-title'>{safe(champion.get('title'))}</div>
        <div class='champion-artist'>{safe(champion.get('artist'))}</div>
        <div class='champion-meta'>
            <span>레이팅 {safe(champion_rating_display)}</span>
            <span>{safe(champion_record)}</span>
        </div>
        {champion_summary_html}
        {champion_highlight_html}
        {champion_glossary_html}
    </section>
    {summary_html}
    {stats_html}
    {top_song_html}
    {recommendation_html}
    <footer>이 리포트는 WhatsMyMusicFlavor에서 생성되었습니다.</footer>
</body>
</html>
"""
        return html

    def _write_pdf(self, file_path: Path, html: str) -> None:
        document = QTextDocument()
        document.setHtml(html)

        writer = QPdfWriter(str(file_path))
        writer.setResolution(96)
        writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        writer.setPageMargins(QMarginsF(12, 12, 12, 12))

        layout_rect = writer.pageLayout().paintRectPixels(writer.resolution())
        document.setPageSize(QSizeF(layout_rect.size()))

        document.print(writer)

    def render_recommendations(self, layout: QVBoxLayout):
        section_title = QLabel("맞춤 추천")
        section_title.setObjectName("SectionSubtitle")
        layout.addWidget(section_title)
        card = QFrame()
        card.setObjectName("InsightCard")
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(10)
        core_recs = self.recommendations.get("core", []) if self.recommendations else []
        fresh_recs = self.recommendations.get("fresh", []) if self.recommendations else []
        if not core_recs and not fresh_recs:
            empty_label = QLabel("추천할 곡이 없습니다.")
            empty_label.setObjectName("BodyLabel")
            card_layout.addWidget(empty_label)
            layout.addWidget(card)
            return
        for title, entries in (("🎯 취향 저격 트랙", core_recs), ("🌱 새롭게 시도해볼 곡", fresh_recs)):
            if not entries:
                continue
            group_label = QLabel(title)
            group_label.setObjectName("RecommendationGroupLabel")
            card_layout.addWidget(group_label)
            for idx, entry in enumerate(entries, 1):
                song = entry["song"]
                reason = entry["reason"]
                summary_info = self.format_song_summary(song)
                summary_text = summary_info.get("summary") if isinstance(summary_info, dict) else None
                highlight_text = summary_info.get("highlight") if isinstance(summary_info, dict) else None
                glossary_keys = list(summary_info.get("glossary_keys") or []) if isinstance(summary_info, dict) else []
                song_label = QLabel(
                    f"{idx}. {song.artist} - {song.get_display_title()}"
                )
                song_label.setObjectName("BodyLabel")
                card_layout.addWidget(song_label)
                if summary_text:
                    summary_label = QLabel(summary_text)
                    summary_label.setObjectName("BodyLabel")
                    summary_label.setWordWrap(True)
                    card_layout.addWidget(summary_label)
                if highlight_text:
                    highlight_label = QLabel(highlight_text)
                    highlight_label.setObjectName("BodyLabel")
                    highlight_label.setProperty("role", "helper")
                    highlight_label.setWordWrap(True)
                    card_layout.addWidget(highlight_label)
                reason_label = QLabel(reason)
                reason_label.setObjectName("BodyLabel")
                reason_label.setProperty("role", "helper")
                reason_label.setWordWrap(True)
                usage_tip = entry.get("usage_tip")
                usage_sentence = f"이 곡은 언제 어울려요: {usage_tip}" if usage_tip else None
                if usage_sentence and usage_sentence in reason:
                    parts = [part for part in reason.split(" / ") if part and part != usage_sentence]
                    reason_display = " / ".join(parts)
                    if not reason_display:
                        reason_display = usage_sentence
                else:
                    reason_display = reason
                reason_label.setText(reason_display)
                card_layout.addWidget(reason_label)
                if usage_sentence and usage_sentence != reason_display:
                    usage_label = QLabel(usage_sentence)
                    usage_label.setObjectName("BodyLabel")
                    usage_label.setWordWrap(True)
                    card_layout.addWidget(usage_label)
                glossary_button = QToolButton(card)
                glossary_button.setObjectName("GlossaryButton")
                glossary_button.setText("용어 설명 보기")
                glossary_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxInformation))
                glossary_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
                glossary_button.setCursor(Qt.CursorShape.PointingHandCursor)
                glossary_button.setProperty("glossaryKeys", glossary_keys)
                glossary_button.clicked.connect(self._handle_glossary_button_click)
                glossary_button.setVisible(bool(glossary_keys))
                card_layout.addWidget(glossary_button, alignment=Qt.AlignmentFlag.AlignLeft)
                embed = SongPreviewEmbed(card, minimum_height=160)
                embed.set_song(song)
                card_layout.addWidget(embed)
            card_layout.addSpacing(6)
        layout.addWidget(card)

    def render_match_history(self, layout: QVBoxLayout):
        group = QGroupBox("매치 히스토리")
        group.setObjectName("InsightGroup")
        group_layout = QVBoxLayout(group)
        group_layout.setSpacing(12)

        if not self.engine or not self.engine.match_history:
            empty_label = QLabel("진행된 매치가 없습니다.")
            empty_label.setObjectName("BodyLabel")
            empty_label.setProperty("role", "helper")
            group_layout.addWidget(empty_label)
            layout.addWidget(group)
            return

        tree = QTreeWidget()
        tree.setObjectName("MatchHistoryTree")
        tree.setColumnCount(4)
        tree.setHeaderLabels(["매치", "대진", "선택", "승자"])
        tree.setRootIsDecorated(False)
        tree.setAlternatingRowColors(True)
        header = tree.header()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        group_layout.addWidget(tree)

        history: List[Match] = list(self.engine.match_history)

        def format_choice(match: Match) -> str:
            mapping = {
                "A": f"A - {match.song_a}",
                "B": f"B - {match.song_b}",
                "T": "둘 다 선택",
                "S": "건너뛰기",
            }
            return mapping.get(match.choice or "", "-")

        def refresh_tree():
            tree.clear()
            if self.history_show_all or len(history) <= self.history_max_rows:
                rows = history
            else:
                rows = history[-self.history_max_rows :]
            for match in reversed(rows):
                pairing = f"{match.song_a} vs {match.song_b}"
                winner_text = str(match.winner) if match.winner else "-"
                item = QTreeWidgetItem([
                    match.match_id,
                    pairing,
                    format_choice(match),
                    winner_text,
                ])
                tree.addTopLevelItem(item)

        refresh_tree()

        if len(history) > self.history_max_rows:
            toggle_button = QPushButton("전체 보기" if not self.history_show_all else "최근만 보기")
            toggle_button.setCursor(Qt.CursorShape.PointingHandCursor)
            toggle_button.setProperty("variant", "ghost")

            def toggle_history():
                self.history_show_all = not self.history_show_all
                toggle_button.setText("최근만 보기" if self.history_show_all else "전체 보기")
                refresh_tree()

            toggle_button.clicked.connect(toggle_history)
            group_layout.addWidget(toggle_button, alignment=Qt.AlignmentFlag.AlignLeft)

        layout.addWidget(group)

    def run(self):
        if not self.valid:
            return
        self.show_start_view()
        self.showMaximized()
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
    
