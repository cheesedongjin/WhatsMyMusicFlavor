"""
음악 토너먼트 취향 테스트 시스템
설문 → 후보군 압축 → 토너먼트 → 결과 분석/추천
"""

import json
import math
import random
import webbrowser
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, field, asdict
from collections import defaultdict
import numpy as np
from sklearn.cluster import KMeans
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox

# ============================================================================
# 데이터 모델
# ============================================================================

@dataclass
class Song:
    id: str
    artist: str
    title: str
    youtube_url: str
    genres: List[int]
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
        return f"{self.artist} - {self.title}"

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
                song = Song(
                    id=item['id'],
                    artist=item['artist'],
                    title=item['title'],
                    youtube_url=item.get('youtube_url', ''),
                    genres=item.get('genres', []),
                    tags=item.get('tags', {}),
                    popularity=item.get('popularity', {}),
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
        
        profile = {
            'genre_scores': dict(genre_scores),
            'preferred_era': preferred_era,
            'preferred_energy': preferred_energy,
            'preferred_popularity': preferred_popularity,
            'preferred_language': preferred_language
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
        
    def compute_base_score(self, song: Song) -> float:
        """설문 기반 초기 점수 계산"""
        score = 0.0
        
        # 장르 매칭 (간단화: 장르명 기반)
        genre_match = 0.5  # 기본값
        score += genre_match
        
        # 시대 매칭
        if self.profile.get('preferred_era'):
            song_year = song.tags.get('era_year', 2000)
            era_diff = abs(song_year - self.profile['preferred_era'])
            era_score = max(0, 1 - era_diff / 30)
            score += era_score
        
        # 에너지 매칭
        if 'energy' in song.tags:
            energy_diff = abs(song.tags['energy'] - self.profile['preferred_energy'])
            energy_score = 1 - energy_diff
            score += energy_score
        
        # 인지도 매칭
        awareness = song.popularity.get('awareness_idx', 0.5)
        pop_diff = abs(awareness - self.profile['preferred_popularity'])
        pop_score = 1 - pop_diff
        score += pop_score * 0.5
        
        return score
    
    def select_candidates(self, k: int = 32) -> List[Song]:
        """상위 K개 후보 선택 (다양성 고려)"""
        # 1차: 점수 계산
        scored_songs = [(song, self.compute_base_score(song)) for song in self.songs]
        scored_songs.sort(key=lambda x: x[1], reverse=True)
        
        # 2차: 상위 K*2 중에서 다양성 고려하여 K개 선택
        pool = scored_songs[:min(k*2, len(scored_songs))]
        selected = []
        
        for song, score in pool:
            if len(selected) >= k:
                break
            # 간단 다양성 체크: 같은 아티스트가 너무 많으면 제외
            same_artist = sum(1 for s in selected if s.artist == song.artist)
            if same_artist < 2:
                selected.append(song)
        
        # 부족하면 나머지 추가
        while len(selected) < k and len(pool) > len(selected):
            for song, _ in pool:
                if song not in selected:
                    selected.append(song)
                    if len(selected) >= k:
                        break
        
        print(f"\n✓ {len(selected)}개 후보곡 선정 완료")
        return selected

class BracketGenerator:
    @staticmethod
    def create_bracket(candidates: List[Song]) -> List[List[Match]]:
        """토너먼트 브래킷 생성 (단순 랜덤 시딩)"""
        random.shuffle(candidates)
        
        rounds = []
        current_round = []
        
        # 1라운드 매치 생성
        for i in range(0, len(candidates), 2):
            if i + 1 < len(candidates):
                match = Match(
                    round_num=1,
                    match_id=f"R1-M{i//2+1}",
                    song_a=candidates[i],
                    song_b=candidates[i+1]
                )
                current_round.append(match)
        
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
    def __init__(self, all_songs: List[Song], participated_songs: List[Song]):
        self.all_songs = all_songs
        self.participated = set(s.id for s in participated_songs)
    
    def generate_recommendations(self, top_songs: List[Song], n: int = 10) -> List[Tuple[Song, str]]:
        """추천곡 생성"""
        if not top_songs:
            return []
        
        recommendations = []
        top_winners = top_songs[:3]
        
        # 불참곡 중에서 추천
        candidates = [s for s in self.all_songs if s.id not in self.participated]
        
        for song in candidates[:n]:
            # 간단한 유사도: 같은 장르가 있으면 추천
            reason = "다양한 스타일 탐색"
            
            for winner in top_winners:
                if set(song.genres) & set(winner.genres):
                    reason = f"{winner} 와 유사한 장르"
                    break
            
            recommendations.append((song, reason))
        
        return recommendations[:n]
    
    def show_recommendations(self, recommendations: List[Tuple[Song, str]]):
        """추천 결과 출력"""
        print("\n" + "="*60)
        print("💡 추천 곡 목록")
        print("="*60)
        
        if not recommendations:
            print("추천할 곡이 없습니다.")
            return
        
        for i, (song, reason) in enumerate(recommendations, 1):
            print(f"\n{i}. {song}")
            print(f"   이유: {reason}")
            print(f"   링크: {song.youtube_url}")

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
        
        # 4. 브래킷 생성
        print("\n4️⃣ 토너먼트 브래킷 생성 중...")
        bracket_gen = BracketGenerator()
        bracket = bracket_gen.create_bracket(self.candidates)
        print(f"✓ {len(bracket[0])}개 매치로 구성된 브래킷 생성 완료")
        
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
        recommender = RecommendationEngine(self.songs, self.candidates)
        recommendations = recommender.generate_recommendations(report['top_songs'])
        recommender.show_recommendations(recommendations)
        
        # 종료
        print("\n" + "="*60)
        print("✨ 테스트 완료! 음악을 즐기세요 🎵")
        print("="*60)

# ============================================================================
# GUI 애플리케이션
# ============================================================================

class MusicTournamentGUI:
    GENRE_PAIRS = [
        ("Rock", "Pop"),
        ("Hip-Hop", "Electronic"),
        ("Jazz", "Classical"),
        ("K-Pop", "Indie")
    ]

    ERA_OPTIONS = [
        ("1970s-1980s", '1'),
        ("1990s-2000s", '2'),
        ("2010s 이후", '3'),
        ("상관없음", '4')
    ]

    ENERGY_OPTIONS = [
        ("차분한 무드", '1'),
        ("보통 에너지", '2'),
        ("활기찬 느낌", '3'),
        ("강렬한 사운드", '4')
    ]

    POPULARITY_OPTIONS = [
        ("유명한 히트곡", '1'),
        ("적당히 알려진 곡", '2'),
        ("숨은 명곡", '3')
    ]

    LANGUAGE_OPTIONS = [
        ("한국어", '1'),
        ("영어", '2'),
        ("기타 언어", '3'),
        ("상관없음", '4')
    ]

    def __init__(self, songs_file: str):
        self.songs_file = songs_file
        self.root = tk.Tk()
        self.root.title("Whats My Music Flavor · 토너먼트 취향 테스트")
        self.root.geometry("1024x720")
        self.root.minsize(960, 680)
        self.root.configure(bg="#eef2ff")

        self.style = ttk.Style(self.root)
        self.setup_styles()

        self.valid = True
        loader = DataLoader()
        self.songs = loader.load_songs(self.songs_file)

        if not self.songs or not loader.validate_songs(self.songs):
            messagebox.showerror("데이터 오류", "곡 데이터를 불러오지 못했습니다. songs.json 파일을 확인해주세요.")
            self.root.destroy()
            self.valid = False
            return

        self.build_base_layout()
        self.reset_state()
        self.status_bar_var.set(f"{len(self.songs)}곡 데이터를 성공적으로 불러왔어요.")

    def setup_styles(self):
        self.style.theme_use("clam")
        self.style.configure("Primary.TFrame", background="#eef2ff")
        self.style.configure("Hero.TFrame", background="#ffffff")
        self.style.configure("Card.TFrame", background="#ffffff", relief="flat", borderwidth=0)
        self.style.configure("Highlight.TFrame", background="#312e81", relief="flat", borderwidth=0)
        self.style.configure("Title.TLabel", background="#eef2ff", foreground="#1f2937", font=("Pretendard", 26, "bold"))
        self.style.configure("HeroTitle.TLabel", background="#ffffff", foreground="#1f2937", font=("Pretendard", 28, "bold"))
        self.style.configure("Brand.TLabel", background="#eef2ff", foreground="#4c1d95", font=("Pretendard", 18, "bold"))
        self.style.configure("Subtitle.TLabel", background="#eef2ff", foreground="#4b5563", font=("Pretendard", 14))
        self.style.configure("Body.TLabel", background="#ffffff", foreground="#374151", font=("Pretendard", 12))
        self.style.configure("BodyPrimary.TLabel", background="#eef2ff", foreground="#374151", font=("Pretendard", 12))
        self.style.configure("Subtle.TLabel", background="#ffffff", foreground="#6b7280", font=("Pretendard", 11))
        self.style.configure("Badge.TLabel", background="#eef2ff", foreground="#4c1d95", font=("Pretendard", 11, "bold"))
        self.style.configure("Footer.TLabel", background="#eef2ff", foreground="#6b7280", font=("Pretendard", 10))
        self.style.configure("CardTitle.TLabel", background="#ffffff", foreground="#111827", font=("Pretendard", 18, "bold"))
        self.style.configure("CardSubtitle.TLabel", background="#ffffff", foreground="#c7d2fe", font=("Pretendard", 12))
        self.style.configure("CardHighlight.TLabel", background="#312e81", foreground="#ede9fe", font=("Pretendard", 24, "bold"))
        self.style.configure("CardHighlightBody.TLabel", background="#312e81", foreground="#e0e7ff", font=("Pretendard", 12))

        self.style.configure("Accent.TButton", padding=12, font=("Pretendard", 12, "bold"), foreground="#ffffff", background="#6366f1")
        self.style.map("Accent.TButton", background=[("active", "#4f46e5"), ("pressed", "#4338ca")])
        self.style.configure("Soft.TButton", padding=12, font=("Pretendard", 12), foreground="#ffffff", background="#0ea5e9")
        self.style.map("Soft.TButton", background=[("active", "#0284c7"), ("pressed", "#0369a1")])
        self.style.configure("Ghost.TButton", padding=12, font=("Pretendard", 12), foreground="#4b5563", background="#ffffff")
        self.style.map("Ghost.TButton", background=[("active", "#e5e7eb"), ("pressed", "#d1d5db")])

    def build_base_layout(self):
        self.main_frame = ttk.Frame(self.root, style="Primary.TFrame", padding=32)
        self.main_frame.pack(fill="both", expand=True)

        header = ttk.Frame(self.main_frame, style="Primary.TFrame")
        header.pack(fill="x", pady=(0, 24))
        ttk.Label(header, text="Whats My Music Flavor", style="Brand.TLabel").pack(anchor="w")
        ttk.Label(header, text="나만의 음악 토너먼트", style="Title.TLabel").pack(anchor="w", pady=(8, 0))

        self.content_frame = ttk.Frame(self.main_frame, style="Primary.TFrame")
        self.content_frame.pack(fill="both", expand=True)

        self.status_bar_var = tk.StringVar(value="")
        self.status_bar = ttk.Label(self.main_frame, textvariable=self.status_bar_var, style="Footer.TLabel", anchor="w")
        self.status_bar.pack(fill="x", pady=(24, 0))

    def reset_state(self):
        self.survey_profile = {}
        self.candidates = []
        self.engine: Optional[TournamentEngine] = None
        self.bracket: List[List[Match]] = []
        self.current_round_number = 1
        self.current_round_matches: List[Match] = []
        self.current_round_winners: List[Song] = []
        self.current_match_index = 0
        self.active_match: Optional[Match] = None
        self.total_matches = 0
        self.champion: Optional[Song] = None
        self.report = {}
        self.recommendations: List[Tuple[Song, str]] = []

    def clear_content(self):
        for child in self.content_frame.winfo_children():
            child.destroy()

    def show_start_view(self):
        self.reset_state()
        self.clear_content()

        hero = ttk.Frame(self.content_frame, style="Hero.TFrame", padding=48)
        hero.pack(expand=True, fill="both", pady=12)

        ttk.Label(hero, text="당신의 음악 취향을 시각적으로 발견해보세요", style="HeroTitle.TLabel", wraplength=680).pack(anchor="w")
        ttk.Label(
            hero,
            text="장르 선호부터 토너먼트 챔피언 선정, 추천곡까지 한 번에 경험할 수 있는 인터랙티브 테스트입니다.",
            style="Body.TLabel",
            wraplength=700,
            padding=(0, 20)
        ).pack(anchor="w")

        highlights = ttk.Frame(hero, style="Hero.TFrame")
        highlights.pack(anchor="w", pady=(0, 24))
        for text in [
            "🎧 간단한 설문으로 나만의 음악 DNA 분석",
            "⚔️ 두 곡 중 하나를 선택하며 즐기는 토너먼트",
            "✨ 토너먼트 기록 기반 맞춤 추천 리스트"
        ]:
            row = ttk.Frame(highlights, style="Hero.TFrame")
            row.pack(anchor="w", pady=6)
            ttk.Label(row, text=text, style="Body.TLabel").pack(anchor="w")

        ttk.Button(hero, text="지금 시작하기", style="Accent.TButton", command=self.show_survey_view).pack(anchor="w", pady=(12, 0))
        self.status_bar_var.set("간단한 설문부터 시작해볼까요?")

    def show_survey_view(self):
        self.clear_content()

        container = ttk.Frame(self.content_frame, style="Primary.TFrame")
        container.pack(fill="both", expand=True)

        card = ttk.Frame(container, style="Card.TFrame", padding=32)
        card.pack(fill="both", expand=True, padx=12, pady=12)

        ttk.Label(card, text="나의 음악 스타일 진단", style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(card, text="선호에 가장 가까운 선택지를 골라주세요. 토너먼트에 활용됩니다.", style="Subtle.TLabel").pack(anchor="w", pady=(4, 24))

        genre_section = ttk.Frame(card, style="Card.TFrame")
        genre_section.pack(fill="x", pady=(0, 24))
        ttk.Label(genre_section, text="장르 밸런스", style="Body.TLabel").pack(anchor="w", pady=(0, 8))

        self.genre_vars = []
        for idx, (g1, g2) in enumerate(self.GENRE_PAIRS, 1):
            row = ttk.Frame(genre_section, style="Card.TFrame")
            row.pack(fill="x", pady=6)
            ttk.Label(row, text=f"{idx}. {g1} vs {g2}", style="Subtle.TLabel").pack(anchor="w")
            var = tk.StringVar(value="")
            self.genre_vars.append((var, (g1, g2)))
            options = ttk.Frame(row, style="Card.TFrame")
            options.pack(anchor="w", pady=(6, 0))
            ttk.Radiobutton(options, text=f"{g1} 선호", variable=var, value='1', style="Body.TLabel").pack(side="left", padx=(0, 16))
            ttk.Radiobutton(options, text=f"{g2} 선호", variable=var, value='2', style="Body.TLabel").pack(side="left", padx=(0, 16))
            ttk.Radiobutton(options, text="잘 모르겠음", variable=var, value='s', style="Body.TLabel").pack(side="left")

        def build_radio_section(parent, title, options, var):
            section = ttk.Frame(parent, style="Card.TFrame")
            section.pack(fill="x", pady=12)
            ttk.Label(section, text=title, style="Body.TLabel").pack(anchor="w")
            radios = ttk.Frame(section, style="Card.TFrame")
            radios.pack(anchor="w", pady=(6, 0))
            for text, value in options:
                ttk.Radiobutton(radios, text=text, variable=var, value=value, style="Body.TLabel").pack(side="left", padx=(0, 16))

        self.era_var = tk.StringVar(value='2')
        self.energy_var = tk.StringVar(value='3')
        self.popularity_var = tk.StringVar(value='2')
        self.language_var = tk.StringVar(value='4')

        build_radio_section(card, "가장 마음에 드는 음악 시대", self.ERA_OPTIONS, self.era_var)
        build_radio_section(card, "에너지 레벨", self.ENERGY_OPTIONS, self.energy_var)
        build_radio_section(card, "인지도 선호", self.POPULARITY_OPTIONS, self.popularity_var)
        build_radio_section(card, "가사 언어", self.LANGUAGE_OPTIONS, self.language_var)

        ttk.Button(card, text="토너먼트 시작", style="Accent.TButton", command=self.begin_tournament).pack(anchor="e", pady=(24, 0))
        self.status_bar_var.set("설문 응답을 바탕으로 맞춤 토너먼트를 준비합니다.")

    def begin_tournament(self):
        genre_scores = defaultdict(int)
        for var, (g1, g2) in self.genre_vars:
            choice = var.get()
            if choice == '1':
                genre_scores[g1] += 1
            elif choice == '2':
                genre_scores[g2] += 1

        era_map = {'1': 1980, '2': 2000, '3': 2015, '4': None}
        energy_map = {'1': 0.2, '2': 0.5, '3': 0.7, '4': 0.9}
        pop_map = {'1': 0.8, '2': 0.5, '3': 0.2}
        lang_map = {'1': 'ko', '2': 'en', '3': 'other', '4': None}

        self.survey_profile = {
            'genre_scores': dict(genre_scores),
            'preferred_era': era_map.get(self.era_var.get()),
            'preferred_energy': energy_map.get(self.energy_var.get(), 0.5),
            'preferred_popularity': pop_map.get(self.popularity_var.get(), 0.5),
            'preferred_language': lang_map.get(self.language_var.get())
        }

        selector = CandidateSelector(self.songs, self.survey_profile)
        self.candidates = selector.select_candidates(k=min(32, len(self.songs)))

        if len(self.candidates) < 2:
            messagebox.showwarning("후보 부족", "토너먼트를 진행하기에 곡이 부족합니다. 데이터를 확인해주세요.")
            self.show_start_view()
            return

        if len(self.candidates) % 2 == 1:
            self.candidates = self.candidates[:-1]

        self.engine = TournamentEngine()
        bracket_gen = BracketGenerator()
        self.bracket = bracket_gen.create_bracket(self.candidates)
        self.current_round_number = 1
        self.current_round_matches = self.bracket[0] if self.bracket else []
        self.current_round_winners = []
        self.current_match_index = 0
        self.total_matches = max(1, len(self.candidates) - 1)
        self.progress_value = 0

        self.status_bar_var.set("토너먼트를 준비 중입니다.")
        self.show_match_view()

    def show_match_view(self):
        self.clear_content()

        container = ttk.Frame(self.content_frame, style="Primary.TFrame")
        container.pack(fill="both", expand=True)

        ttk.Label(container, text="토너먼트 진행", style="Title.TLabel").pack(anchor="w")
        self.status_var = tk.StringVar(value="")
        ttk.Label(container, textvariable=self.status_var, style="BodyPrimary.TLabel").pack(anchor="w", pady=(6, 16))

        self.progress_bar = ttk.Progressbar(container, maximum=100, value=0, length=520)
        self.progress_bar.pack(fill="x", pady=(0, 24))

        cards = ttk.Frame(container, style="Primary.TFrame")
        cards.pack(fill="both", expand=True)
        cards.columnconfigure(0, weight=1)
        cards.columnconfigure(1, weight=1)

        self.card_a = self.create_song_card(cards, "A 곡")
        self.card_a["frame"].grid(row=0, column=0, sticky="nsew", padx=(0, 12))

        self.card_b = self.create_song_card(cards, "B 곡")
        self.card_b["frame"].grid(row=0, column=1, sticky="nsew", padx=(12, 0))

        self.helper_var = tk.StringVar(value="마음에 드는 곡을 선택하세요.")
        ttk.Label(container, textvariable=self.helper_var, style="BodyPrimary.TLabel").pack(anchor="center", pady=(24, 12))

        button_frame = ttk.Frame(container, style="Primary.TFrame")
        button_frame.pack(pady=(0, 24))
        button_frame.columnconfigure(0, weight=1)
        button_frame.columnconfigure(1, weight=1)

        ttk.Button(button_frame, text="A 곡 선택", style="Accent.TButton", command=lambda: self.on_choice('A')).grid(row=0, column=0, padx=8, pady=6, sticky="ew")
        ttk.Button(button_frame, text="B 곡 선택", style="Accent.TButton", command=lambda: self.on_choice('B')).grid(row=0, column=1, padx=8, pady=6, sticky="ew")
        ttk.Button(button_frame, text="둘 다 좋아요", style="Soft.TButton", command=lambda: self.on_choice('T')).grid(row=1, column=0, padx=8, pady=6, sticky="ew")
        ttk.Button(button_frame, text="건너뛰기", style="Ghost.TButton", command=lambda: self.on_choice('S')).grid(row=1, column=1, padx=8, pady=6, sticky="ew")

        self.status_bar_var.set("토너먼트가 진행 중입니다. 클릭 한 번으로 선택하세요!")
        self.display_current_match()

    def create_song_card(self, parent, label_text: str):
        frame = ttk.Frame(parent, style="Card.TFrame", padding=24)
        ttk.Label(frame, text=label_text, style="Badge.TLabel").pack(anchor="w")

        title_var = tk.StringVar(value="")
        ttk.Label(frame, textvariable=title_var, style="CardTitle.TLabel", wraplength=360).pack(anchor="w", pady=(12, 4))

        meta_var = tk.StringVar(value="")
        ttk.Label(frame, textvariable=meta_var, style="Body.TLabel", wraplength=360).pack(anchor="w")

        tag_var = tk.StringVar(value="")
        ttk.Label(frame, textvariable=tag_var, style="Subtle.TLabel", wraplength=360).pack(anchor="w", pady=(8, 0))

        link_label = tk.Label(frame, text="", font=("Pretendard", 11, "underline"), fg="#2563eb", bg="#ffffff", cursor="hand2")
        link_label.pack(anchor="w", pady=(12, 0))

        return {
            "frame": frame,
            "title": title_var,
            "meta": meta_var,
            "tag": tag_var,
            "link": link_label
        }

    def update_song_card(self, card, song: Song):
        card["title"].set(song.title)
        rating = song.rating if song.rating else 1500
        card["meta"].set(f"{song.artist} · 예상 레이팅 {rating:.0f}")

        details = []
        if song.tags.get('era_year'):
            details.append(f"{song.tags['era_year']}년대")
        if song.tags.get('energy') is not None:
            details.append(f"에너지 {song.tags['energy']*100:.0f}%")
        if song.genres:
            details.append(f"장르 코드 {', '.join(map(str, song.genres[:3]))}")
        card["tag"].set(" · ".join(details))

        link_label = card["link"]
        link_label.unbind("<Button-1>")
        if song.youtube_url:
            link_label.configure(text="YouTube에서 듣기 ↗", fg="#2563eb", cursor="hand2")
            link_label.bind("<Button-1>", lambda _event, url=song.youtube_url: webbrowser.open(url))
        else:
            link_label.configure(text="링크 정보가 없습니다", fg="#9ca3af", cursor="arrow")

    def display_current_match(self):
        if not self.current_round_matches:
            self.finish_tournament(self.current_round_winners[0] if self.current_round_winners else None)
            return

        if self.current_match_index >= len(self.current_round_matches):
            self.prepare_next_round()
            return

        self.active_match = self.current_round_matches[self.current_match_index]
        match = self.active_match
        self.status_var.set(f"라운드 {self.current_round_number} · 매치 {self.current_match_index + 1}/{len(self.current_round_matches)}")
        self.helper_var.set(f"{match.song_a.artist} vs {match.song_b.artist}")
        self.update_song_card(self.card_a, match.song_a)
        self.update_song_card(self.card_b, match.song_b)

        progress_ratio = len(self.engine.match_history) / self.total_matches if self.total_matches else 0
        self.progress_bar.configure(value=progress_ratio * 100)

    def on_choice(self, choice: str):
        if not self.active_match or not self.engine:
            return

        winner = self.engine.resolve_match(self.active_match, choice)
        if winner:
            self.current_round_winners.append(winner)

        self.current_match_index += 1
        progress_ratio = len(self.engine.match_history) / self.total_matches if self.total_matches else 0
        self.progress_bar.configure(value=progress_ratio * 100)
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
        next_round = []
        for i in range(0, len(winners), 2):
            if i + 1 < len(winners):
                match = Match(
                    round_num=self.current_round_number,
                    match_id=f"R{self.current_round_number}-M{i//2 + 1}",
                    song_a=winners[i],
                    song_b=winners[i + 1]
                )
                next_round.append(match)

        self.current_round_matches = next_round
        self.current_round_winners = []
        self.current_match_index = 0
        self.display_current_match()

    def finish_tournament(self, champion: Optional[Song]):
        self.champion = champion
        self.show_results_view()

    def show_results_view(self):
        self.clear_content()

        container = ttk.Frame(self.content_frame, style="Primary.TFrame")
        container.pack(fill="both", expand=True)

        if not self.champion or not self.engine:
            ttk.Label(container, text="토너먼트 결과가 존재하지 않습니다.", style="BodyPrimary.TLabel").pack(pady=24)
            ttk.Button(container, text="처음으로", style="Ghost.TButton", command=self.show_start_view).pack()
            return

        analyzer = ResultAnalyzer(self.engine.match_history, self.candidates)
        self.report = analyzer.generate_report(self.champion)
        recommender = RecommendationEngine(self.songs, self.candidates)
        self.recommendations = recommender.generate_recommendations(self.report['top_songs'])

        highlight = ttk.Frame(container, style="Highlight.TFrame", padding=32)
        highlight.pack(fill="x", padx=12, pady=(0, 24))

        ttk.Label(highlight, text="우승 곡", style="CardSubtitle.TLabel").pack(anchor="w")
        ttk.Label(highlight, text=str(self.champion), style="CardHighlight.TLabel").pack(anchor="w", pady=(8, 6))
        ttk.Label(
            highlight,
            text=f"최종 레이팅 {self.champion.rating:.1f} · 전적 {self.champion.wins}승 {self.champion.losses}패",
            style="CardHighlightBody.TLabel"
        ).pack(anchor="w")

        link = tk.Label(highlight, text="YouTube에서 우승 곡 감상하기 ↗", font=("Pretendard", 12, "underline"),
                        fg="#c4b5fd", bg="#312e81", cursor="hand2")
        link.pack(anchor="w", pady=(12, 0))
        if self.champion.youtube_url:
            link.bind("<Button-1>", lambda _event, url=self.champion.youtube_url: webbrowser.open(url))
        else:
            link.configure(text="YouTube 링크 정보가 없습니다", fg="#a78bfa", cursor="arrow")

        grid = ttk.Frame(container, style="Primary.TFrame")
        grid.pack(fill="both", expand=True)
        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)

        top_card = ttk.Frame(grid, style="Card.TFrame", padding=24)
        top_card.grid(row=0, column=0, sticky="nsew", padx=(0, 12), pady=(0, 24))
        ttk.Label(top_card, text="상위 플레이리스트", style="CardTitle.TLabel").pack(anchor="w")

        for i, song in enumerate(self.report['top_songs'], 1):
            item = ttk.Frame(top_card, style="Card.TFrame")
            item.pack(fill="x", pady=6)
            ttk.Label(item, text=f"{i}. {song}", style="Body.TLabel").pack(anchor="w")
            ttk.Label(item, text=f"레이팅 {song.rating:.1f} · 전적 {song.wins}승 {song.losses}패", style="Subtle.TLabel").pack(anchor="w")

        stats_card = ttk.Frame(grid, style="Card.TFrame", padding=24)
        stats_card.grid(row=0, column=1, sticky="nsew", padx=(12, 0), pady=(0, 24))
        ttk.Label(stats_card, text="매치 통계", style="CardTitle.TLabel").pack(anchor="w")

        stats = self.report['choice_distribution']
        ttk.Label(stats_card, text=f"총 매치: {self.report['total_matches']}", style="Body.TLabel").pack(anchor="w", pady=(8, 2))
        ttk.Label(stats_card, text=f"A 선택: {stats.get('A', 0)}", style="Subtle.TLabel").pack(anchor="w")
        ttk.Label(stats_card, text=f"B 선택: {stats.get('B', 0)}", style="Subtle.TLabel").pack(anchor="w")
        ttk.Label(stats_card, text=f"둘 다: {stats.get('T', 0)}", style="Subtle.TLabel").pack(anchor="w")
        ttk.Label(stats_card, text=f"건너뛰기: {stats.get('S', 0)}", style="Subtle.TLabel").pack(anchor="w")

        recommend_card = ttk.Frame(container, style="Card.TFrame", padding=24)
        recommend_card.pack(fill="both", expand=True, padx=12, pady=(0, 24))
        ttk.Label(recommend_card, text="맞춤 추천", style="CardTitle.TLabel").pack(anchor="w")

        if not self.recommendations:
            ttk.Label(recommend_card, text="추천할 곡이 없습니다.", style="Subtle.TLabel").pack(anchor="w", pady=12)
        else:
            for i, (song, reason) in enumerate(self.recommendations, 1):
                item = ttk.Frame(recommend_card, style="Card.TFrame")
                item.pack(fill="x", pady=8)
                ttk.Label(item, text=f"{i}. {song}", style="Body.TLabel").pack(anchor="w")
                ttk.Label(item, text=reason, style="Subtle.TLabel").pack(anchor="w")
                link_label = tk.Label(item, text="YouTube에서 듣기 ↗", font=("Pretendard", 11, "underline"),
                                     fg="#2563eb", bg="#ffffff", cursor="hand2")
                link_label.pack(anchor="w", pady=(4, 0))
                if song.youtube_url:
                    link_label.bind("<Button-1>", lambda _event, url=song.youtube_url: webbrowser.open(url))
                else:
                    link_label.configure(text="링크 정보가 없습니다", fg="#9ca3af", cursor="arrow")

        ttk.Button(container, text="처음으로 돌아가기", style="Ghost.TButton", command=self.show_start_view).pack(pady=(0, 12))
        self.status_bar_var.set("결과를 확인하고 추천곡을 감상해보세요.")

    def run(self):
        if not self.valid:
            return
        self.show_start_view()
        self.root.mainloop()
# ============================================================================
# 실행
# ============================================================================

def main():
    songs_file = Path("songs.json")

    if not songs_file.exists():
        print("✗ songs.json 파일을 찾을 수 없습니다. 프로젝트 루트에 파일을 추가해주세요.")
        return

    gui = MusicTournamentGUI(str(songs_file))
    gui.run()


if __name__ == "__main__":
    main()
    
