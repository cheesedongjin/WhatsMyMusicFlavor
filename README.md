# WhatsMyMusicFlavor

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## Overview

WhatsMyMusicFlavor is a Python-based music taste discovery system that guides users through a survey, a tournament-style song selection process, and personalized music recommendations. Built with PyQt6 for a modern GUI, it leverages a JSON-based song database to analyze user preferences and deliver tailored song suggestions, supporting Korean text rendering and a sleek, gradient-themed interface.

## Features

- **Interactive Survey**: Collects user preferences on genres, eras, energy levels, popularity, and language focus to tailor the experience.
- **Tournament System**: Engages users in head-to-head song matchups to refine their music taste profile using an Elo rating system.
- **Personalized Recommendations**: Generates "core" and "fresh" song recommendations based on survey responses and tournament outcomes.
- **Real-Time Visual Feedback**: Displays progress with a progress bar and detailed song information during the tournament.
- **Responsive GUI**: Modern, user-friendly interface with touch-friendly controls, optimized for desktop use.
- **Korean Language Support**: Fully supports Korean text for song titles, artist names, and UI elements.
- **Extensible Song Database**: Uses a JSON-based song catalog with detailed metadata (genres, moods, instrumentation, etc.).
- **Error Handling**: Robust validation of song data and user inputs to ensure a smooth experience.

## Installation

To run WhatsMyMusicFlavor locally:

1. Clone the repository:
   ```bash
   git clone https://github.com/cheesedongjin/WhatsMyMusicFlavor.git
   ```
2. Navigate to the project directory:
   ```bash
   cd WhatsMyMusicFlavor
   ```
3. Install dependencies:
   ```bash
   pip install PyQt6 numpy scikit-learn
   ```
4. Ensure a `songs.json` file exists in the project root with the required song data structure (see [JSON Structure](#json-structure)).
5. Run the application:
   ```bash
   python main.py
   ```

**Note**: The application requires a valid `songs.json` file to function. Refer to the JSON structure below for details on how to format this file.

## Usage

1. **Launch the Application**: Run `python main.py` to start the GUI.
2. **Complete the Survey**: Answer questions about genre preferences, music era, energy level, popularity, language focus, and regional preferences.
3. **Participate in the Tournament**: Choose between pairs of songs in a bracket-style competition. Options include selecting one song, choosing both, or skipping.
4. **View Results**: After the tournament, review the winning song, top-rated songs, and a summary of your music taste.
5. **Explore Recommendations**: Receive tailored song recommendations split into "core" (aligned with your taste) and "fresh" (new discoveries) categories.
6. **Interact with Songs**: Click YouTube links (if available) to listen to songs directly from the interface.

## JSON Structure

The application relies on a `songs.json` file to load song data. Below is the required structure for each song entry:

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

### Index Mappings
- **genres**: Use codes from `GENRE_CODE_TABLE` (e.g., 2: Pop, 14: Alternative Rock).
- **tags.subgenres**: Codes from `SUBGENRES` (e.g., 0: alt_pop, 19: electropop).
- **tags.mood**: Codes from `MOODS` (e.g., 13: danceable, 23: energetic).
- **tags.language**: Codes from `LANGUAGES` (e.g., 4: ko).
- **tags.instrumentation**: Codes from `INSTRUMENTATIONS` (e.g., 4: guitar, 15: vocals).
- **popularity.regionality**: Codes from `REGIONALITIES` (e.g., 6: kr, 4: global).

See the source code comments for the full list of codes.

## Dependencies

- **Python 3.8+**
- **PyQt6**: For the graphical user interface.
- **NumPy**: For numerical computations in recommendation algorithms.
- **scikit-learn**: For KMeans clustering in preference analysis.
- **JSON**: For loading and parsing the song database.

Install dependencies using:
```bash
pip install PyQt6 numpy scikit-learn
```

## License

This project is licensed under the [MIT License](LICENSE).

## Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository.
2. Create a new branch (`git checkout -b feature/your-feature`).
3. Make your changes and commit (`git commit -m "Add your feature"`).
4. Push to the branch (`git push origin feature/your-feature`).
5. Open a Pull Request.

## Contact

For issues or suggestions, please open an issue on the [GitHub repository](https://github.com/cheesedongjin/WhatsMyMusicFlavor/issues).
