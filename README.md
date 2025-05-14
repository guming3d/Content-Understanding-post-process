# Video Speech Transcription and Analysis

This repository contains tools for transcribing speech from video files using Azure Speech-to-Text service and analyzing timestamp data.

## Requirements

- Python 3.6+
- FFmpeg installed and available in PATH
- Azure Speech Service subscription (key and endpoint)

## Setup

1. Install required dependencies:
   ```zsh
   pip install -r requirements.txt
   ```

2. Create a `.env` file in the project root with your Azure Speech Service credentials:
   ```
   AZURE_SPEECH_KEY=your_azure_speech_key_here
   AZURE_SPEECH_ENDPOINT=your_azure_speech_endpoint_here
   ```

## Using the Transcription Tool (`transcribe_videos.py`)

The transcription tool processes all `.mp4` video files in the `inputs/` directory and generates transcript files with timestamps.

### Features:
- Extracts audio from video using FFmpeg
- Transcribes using Azure Speech-to-Text service
- Generates both word-level and sentence-level transcriptions
- Includes accurate timestamps for each word and sentence

### Running the tool:

```zsh
python transcribe_videos.py
```

### Output:

For each video file (e.g., `inputs/example.mp4`), the script produces:
- `inputs/example_word.txt`: Word-level transcription with timestamps for each word
- `inputs/example_sentence.txt`: Sentence-level transcription with timestamps for each sentence

Example output format:
```
[0.07 - 0.67] word1
[0.70 - 1.30] word2
...
```

## Using the Timestamp Plotting Tool (`plot_timestamp.py`)

This script visualizes timestamp data, potentially comparing original timestamps with processed ones.

### Running the tool:

```zsh
python plot_timestamp.py
```

The script will generate visualizations in the `outputs/` directory based on timestamp data.

## Workflow Example

1. Place your `.mp4` video files in the `inputs/` directory
2. Run the transcription tool:
   ```zsh
   python transcribe_videos.py
   ```
3. Examine the generated transcript files
4. Run the plotting tool to visualize the timestamp data:
   ```zsh
   python plot_timestamp.py
   ```
5. View the generated plots in the `outputs/` directory

## Troubleshooting

- **FFmpeg not found**: Ensure FFmpeg is installed and added to your PATH
- **Azure credentials error**: Verify your `.env` file contains valid credentials
- **No transcriptions generated**: Check Azure Speech Service subscription status and network connectivity

## File Structure

```
├── .env                       # Azure Speech Service credentials
├── requirements.txt           # Python dependencies
├── transcribe_videos.py       # Video transcription script
├── plot_timestamp.py          # Timestamp analysis script
├── README.md                  # This documentation
├── inputs/                    # Directory for input videos
│   └── *.mp4                  # Video files
│   └── *_word.txt             # Generated word-level transcripts
│   └── *_sentence.txt         # Generated sentence-level transcripts
└── outputs/                   # Directory for generated plots
    └── *.png                  # Plot images
```

## Contributing

Feel free to submit issues or pull requests with improvements or bug fixes.
