[English README](README.en.md)

# WhatsMyMusicFlavor

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## 개요

WhatsMyMusicFlavor는 사용자를 설문 조사, 토너먼트 방식의 곡 선택 과정, 개인화된 음악 추천으로 안내하는 Python 기반 음악 취향 탐색 시스템입니다. 현대적인 GUI를 제공하는 PyQt6와 JSON 기반 곡 데이터베이스를 활용하여 사용자 선호도를 분석하고 맞춤형 곡 제안을 제공하며, 한국어 텍스트 렌더링과 세련된 그라디언트 테마 인터페이스를 지원합니다.

## 주요 기능

- **대화형 설문조사**: 장르, 시대, 에너지 수준, 인기도, 언어 중심 선호를 수집해 경험을 맞춤화합니다.
- **토너먼트 시스템**: Elo 레이팅 시스템을 사용해 곡을 1:1 매칭으로 비교하면서 음악 취향 프로필을 정교하게 다듬습니다.
- **개인화 추천**: 설문 응답과 토너먼트 결과를 기반으로 "core" 및 "fresh" 음악 추천을 제공합니다.
- **실시간 시각 피드백**: 토너먼트 진행 상황을 진행 바와 상세한 곡 정보로 보여 줍니다.
- **반응형 GUI**: 데스크톱 사용에 최적화된 터치 친화적 컨트롤과 현대적이고 사용자 친화적인 인터페이스를 제공합니다.
- **한국어 지원**: 곡 제목, 아티스트 이름, UI 요소에서 한국어 텍스트를 완전히 지원합니다.
- **확장 가능한 곡 데이터베이스**: 장르, 분위기, 악기 구성 등 상세한 메타데이터를 갖춘 JSON 기반 곡 카탈로그를 사용합니다.
- **오류 처리**: 곡 데이터와 사용자 입력을 꼼꼼하게 검증하여 안정적인 사용 경험을 보장합니다.

# 설치 방법

## Windows

1. 저장소를 클론합니다.

   ```powershell
   git clone https://github.com/cheesedongjin/WhatsMyMusicFlavor.git
   ```
2. 프로젝트 디렉터리로 이동합니다.

   ```powershell
   cd WhatsMyMusicFlavor
   ```
3. (선택 사항) 가상환경을 생성하고 활성화합니다.

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\activate
   ```
4. 의존성을 설치합니다.

   ```powershell
   pip install PyQt6 PyQt6-WebEngine numpy scikit-learn
   ```
5. 프로젝트 루트에 `songs.json` 파일이 있는지 확인합니다.
6. 애플리케이션을 실행합니다.

   ```powershell
   python main.py
   ```

---

## macOS

1. 저장소를 클론합니다.

   ```bash
   git clone https://github.com/cheesedongjin/WhatsMyMusicFlavor.git
   ```
2. 프로젝트 디렉터리로 이동합니다.

   ```bash
   cd WhatsMyMusicFlavor
   ```
3. (선택 사항) 가상환경을 생성하고 활성화합니다.

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
4. 의존성을 설치합니다.

   ```bash
   pip install PyQt6 PyQt6-WebEngine numpy scikit-learn
   ```
5. 프로젝트 루트에 `songs.json` 파일이 있는지 확인합니다.
6. 애플리케이션을 실행합니다.

   ```bash
   python main.py
   ```

---

## Linux (Ubuntu/Debian 예시)

1. Python과 pip가 설치되어 있는지 확인합니다.

   ```bash
   sudo apt update
   sudo apt install python3 python3-pip python3-venv git
   ```
2. 저장소를 클론합니다.

   ```bash
   git clone https://github.com/cheesedongjin/WhatsMyMusicFlavor.git
   ```
3. 프로젝트 디렉터리로 이동합니다.

   ```bash
   cd WhatsMyMusicFlavor
   ```
4. (선택 사항) 가상환경을 생성하고 활성화합니다.

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
5. 의존성을 설치합니다.

   ```bash
   pip install PyQt6 PyQt6-WebEngine numpy scikit-learn
   ```
6. 프로젝트 루트에 `songs.json` 파일이 있는지 확인합니다.
7. 애플리케이션을 실행합니다.

   ```bash
   python main.py
   ```

**참고**: 애플리케이션은 정상 동작을 위해 올바른 `songs.json` 파일이 필요합니다. 파일 포맷에 대한 자세한 내용은 아래 JSON 구조를 참고하세요.

## 사용 방법

1. **애플리케이션 실행**: `python main.py`를 실행하여 GUI를 시작합니다.
2. **설문 완료**: 장르, 음악 시대, 에너지 수준, 인기도, 언어 선호, 지역 선호에 대한 질문에 답합니다.
3. **토너먼트 참여**: 토너먼트 형식으로 제시되는 곡 쌍에서 선호하는 곡을 선택합니다. 두 곡 모두 선택하거나 건너뛸 수도 있습니다.
4. **결과 확인**: 토너먼트 종료 후 우승 곡, 최고 평점 곡, 음악 취향 요약을 확인합니다.
5. **추천 탐색**: "core"(취향에 부합)와 "fresh"(새로운 발견) 카테고리로 나뉜 맞춤 추천을 받아 봅니다.
6. **곡과 상호작용**: 곡 카드와 추천 목록의 "미리 듣기" 버튼으로 앱 내부에서 YouTube 프리뷰를 재생할 수 있습니다. PyQt6-WebEngine이 설치되지 않은 환경에서는 버튼이 자동으로 비활성화되고 대체 안내 문구가 표시됩니다.

## 미리 듣기 기능 안내

- **필수 의존성**: 앱 내부에서 YouTube 임베드를 재생하려면 `PyQt6-WebEngine` 모듈이 필요합니다. 이 모듈이 없는 환경에서는 미리 듣기 버튼이 비활성화되며, 설치 안내 메시지가 표시됩니다.
- **지원 링크 형식**: 현재는 `songs.json`의 `youtube_url` 필드를 사용해 YouTube 동영상을 임베드합니다. 표준 `watch` 혹은 `youtu.be` 링크가 자동으로 `embed` 형식으로 변환됩니다.
- **대체 시나리오**: 사내 네트워크 정책이나 패키지 미지원 등으로 인해 `PyQt6-WebEngine`을 사용할 수 없는 경우, 버튼을 통해 외부 링크 대신 안내 문구를 확인하게 되며 앱이 비정상 종료되지 않습니다.

## JSON 구조

애플리케이션은 곡 데이터를 불러오기 위해 `songs.json` 파일을 사용합니다. 각 곡 항목은 다음 구조를 따라야 합니다.

```json
{
  "id": "song_001",
  "artist": "Artist Name",
  "title": "Song Title",
  "youtube_url": "https://www.youtube.com/watch?v=example",
  "title_kor": "Korean Title (optional)",
  "genres": [2, 14],
  "tags": {
    "subgenres": [0, 19],
    "mood": [13, 23],
    "energy": 0.7,
    "valence": 0.6,
    "tempo_bpm": 120,
    "era_year": 2020,
    "language": 4,
    "instrumentation": [4, 13, 15]
  },
  "popularity": {
    "awareness_idx": 0.5,
    "yt_views": 1000000,
    "regionality": [6, 4]
  },
  "meta": {
    "duration_sec": 180,
    "loudness_lufs": -8.5
  }
}
```

### 인덱스 매핑
- **genres**: `GENRE_CODE_TABLE`의 코드를 사용합니다(예: 2: Pop, 14: Alternative Rock).
- **tags.subgenres**: `SUBGENRES`의 코드입니다(예: 0: alt_pop, 19: electropop).
- **tags.mood**: `MOODS`의 코드입니다(예: 13: danceable, 23: energetic).
- **tags.language**: `LANGUAGES`의 코드입니다(예: 4: ko).
- **tags.instrumentation**: `INSTRUMENTATIONS`의 코드입니다(예: 4: guitar, 15: vocals).
- **popularity.regionality**: `REGIONALITIES`의 코드입니다(예: 6: kr, 4: global).

전체 코드 목록은 소스 코드 주석을 참고하세요.

## 의존성

- **Python 3.8+**
- **PyQt6**: 그래픽 사용자 인터페이스용.
- **PyQt6-WebEngine**: 앱 내 YouTube 미리 듣기 재생용.
- **NumPy**: 추천 알고리즘의 수치 계산용.
- **scikit-learn**: 선호도 분석에서 KMeans 클러스터링에 사용.
- **JSON**: 곡 데이터베이스 로드 및 파싱에 사용.

의존성 설치 명령:
```bash
pip install PyQt6 PyQt6-WebEngine numpy scikit-learn
```

## 라이선스

이 프로젝트는 [MIT License](LICENSE)를 따릅니다.

## 기여하기

기여를 환영합니다! 특히 `songs.json` 파일을 개선하기 위한 기여를 장려합니다. 예를 들어 기존 곡 데이터의 오류를 수정하거나 음악 카탈로그를 확장하기 위해 새로운 곡을 추가할 수 있습니다. 다음 절차를 따라 주세요.

1. 저장소를 포크합니다.
2. 새 브랜치를 생성합니다(`git checkout -b feature/your-feature`).
3. 변경 사항을 적용하고 커밋합니다(`git commit -m "Add your feature or song update"`).
   - `songs.json`을 업데이트할 경우 [JSON 구조](#json-구조)에서 제시한 포맷을 준수하세요.
   - 새로 추가하거나 수정한 곡 항목이 필수 필드(`id`, `artist`, `title`)를 포함하고 올바른 인덱스 코드를 사용했는지 확인하세요.
4. 브랜치를 푸시합니다(`git push origin feature/your-feature`).
5. Pull Request를 생성합니다.

## 문의

이슈나 제안 사항이 있다면 [GitHub 저장소](https://github.com/cheesedongjin/WhatsMyMusicFlavor/issues)에 이슈를 등록해 주세요.
