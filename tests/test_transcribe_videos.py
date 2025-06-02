"""Unit tests for transcribe_videos.py module"""
import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock, call
from pathlib import Path
import json

# Add parent directory to path for imports
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from transcribe_videos import (
    extract_audio_from_video,
    transcribe_audio_with_word_timestamps,
    transcribe_audio_with_sentence_timestamps,
    main
)


class TestTranscribeVideos(unittest.TestCase):
    """Test cases for video transcription functions"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.test_video_path = "test_video.mp4"
        self.test_audio_path = "test_audio.wav"
        self.test_speech_key = "test_key"
        self.test_speech_endpoint = "https://test.endpoint.com"
    
    @patch('subprocess.run')
    def test_extract_audio_from_video_success(self, mock_run):
        """Test successful audio extraction from video"""
        mock_run.return_value = MagicMock(returncode=0)
        
        # Should not raise exception
        extract_audio_from_video(self.test_video_path, self.test_audio_path)
        
        # Verify ffmpeg command
        expected_cmd = [
            "ffmpeg", "-y", "-i", self.test_video_path, "-vn", 
            "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1", 
            self.test_audio_path
        ]
        mock_run.assert_called_once()
        actual_cmd = mock_run.call_args[0][0]
        self.assertEqual(actual_cmd, expected_cmd)
    
    @patch('subprocess.run')
    def test_extract_audio_from_video_failure(self, mock_run):
        """Test audio extraction failure handling"""
        mock_run.side_effect = Exception("FFmpeg error")
        
        with self.assertRaises(Exception) as context:
            extract_audio_from_video(self.test_video_path, self.test_audio_path)
        
        self.assertIn("FFmpeg error", str(context.exception))
    
    @patch('azure.cognitiveservices.speech.SpeechRecognizer')
    @patch('azure.cognitiveservices.speech.AudioConfig')
    @patch('azure.cognitiveservices.speech.SpeechConfig')
    def test_transcribe_audio_with_word_timestamps(self, mock_speech_config, 
                                                   mock_audio_config, 
                                                   mock_recognizer_class):
        """Test word-level transcription"""
        # Mock the recognizer
        mock_recognizer = MagicMock()
        mock_recognizer_class.return_value = mock_recognizer
        
        # Mock recognition result
        mock_event = MagicMock()
        mock_event.result.reason = MagicMock(RecognizedSpeech=1)
        mock_event.result.json = json.dumps({
            'NBest': [{
                'Words': [
                    {'Offset': 10000000, 'Duration': 5000000, 'Word': 'Hello'},
                    {'Offset': 20000000, 'Duration': 5000000, 'Word': 'World'}
                ]
            }]
        })
        
        # Simulate recognition callback
        recognized_callback = None
        def capture_callback(callback):
            nonlocal recognized_callback
            recognized_callback = callback
        
        mock_recognizer.recognized.connect = capture_callback
        mock_recognizer.session_stopped.connect = MagicMock()
        mock_recognizer.canceled.connect = MagicMock()
        
        # Start the function in a thread to test async behavior
        import threading
        results = []
        def run_transcribe():
            nonlocal results
            results = transcribe_audio_with_word_timestamps(
                self.test_audio_path, 
                self.test_speech_key, 
                self.test_speech_endpoint
            )
        
        thread = threading.Thread(target=run_transcribe)
        thread.start()
        
        # Give time for setup
        import time
        time.sleep(0.1)
        
        # Simulate recognition event
        if recognized_callback:
            recognized_callback(mock_event)
        
        # Signal completion
        mock_recognizer.done = True
        
        thread.join(timeout=2)
        
        # Verify results
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0], (1.0, 1.5, 'Hello'))
        self.assertEqual(results[1], (2.0, 2.5, 'World'))
    
    @patch('azure.cognitiveservices.speech.SpeechRecognizer')
    @patch('azure.cognitiveservices.speech.AudioConfig')
    @patch('azure.cognitiveservices.speech.SpeechConfig')
    def test_transcribe_audio_with_sentence_timestamps(self, mock_speech_config, 
                                                       mock_audio_config, 
                                                       mock_recognizer_class):
        """Test sentence-level transcription"""
        # Mock the recognizer
        mock_recognizer = MagicMock()
        mock_recognizer_class.return_value = mock_recognizer
        
        # Mock recognition result
        mock_event = MagicMock()
        mock_event.result.reason = MagicMock(RecognizedSpeech=1)
        mock_event.result.json = json.dumps({
            'NBest': [{
                'Lexical': 'hello world how are you',
                'Words': [
                    {'Offset': 10000000, 'Duration': 5000000, 'Word': 'hello'},
                    {'Offset': 20000000, 'Duration': 5000000, 'Word': 'world'},
                    {'Offset': 30000000, 'Duration': 5000000, 'Word': 'how'},
                    {'Offset': 40000000, 'Duration': 5000000, 'Word': 'are'},
                    {'Offset': 50000000, 'Duration': 5000000, 'Word': 'you'}
                ]
            }]
        })
        
        # Simulate recognition callback
        recognized_callback = None
        def capture_callback(callback):
            nonlocal recognized_callback
            recognized_callback = callback
        
        mock_recognizer.recognized.connect = capture_callback
        mock_recognizer.session_stopped.connect = MagicMock()
        mock_recognizer.canceled.connect = MagicMock()
        
        # Start the function in a thread
        import threading
        results = []
        def run_transcribe():
            nonlocal results
            results = transcribe_audio_with_sentence_timestamps(
                self.test_audio_path, 
                self.test_speech_key, 
                self.test_speech_endpoint
            )
        
        thread = threading.Thread(target=run_transcribe)
        thread.start()
        
        # Give time for setup
        import time
        time.sleep(0.1)
        
        # Simulate recognition event
        if recognized_callback:
            recognized_callback(mock_event)
        
        # Signal completion
        mock_recognizer.done = True
        
        thread.join(timeout=2)
        
        # Verify results
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0][0], 1.0)  # start time
        self.assertEqual(results[0][1], 5.5)  # end time
        self.assertEqual(results[0][2], 'hello world how are you')
    
    @patch('transcribe_videos.transcribe_audio_with_sentence_timestamps')
    @patch('transcribe_videos.transcribe_audio_with_word_timestamps')
    @patch('transcribe_videos.extract_audio_from_video')
    @patch('glob.glob')
    @patch('os.path.exists')
    @patch('os.remove')
    @patch('builtins.open', create=True)
    @patch.dict(os.environ, {
        'AZURE_SPEECH_KEY': 'test_key',
        'AZURE_SPEECH_ENDPOINT': 'https://test.endpoint.com'
    })
    def test_main_function(self, mock_open, mock_remove, mock_exists, 
                          mock_glob, mock_extract, mock_word_transcribe, 
                          mock_sentence_transcribe):
        """Test main function flow"""
        # Setup mocks
        mock_glob.return_value = ["inputs/test_video.mp4"]
        mock_exists.return_value = True
        mock_extract.return_value = None
        mock_word_transcribe.return_value = [
            (0.0, 0.5, "Hello"),
            (0.6, 1.0, "World")
        ]
        mock_sentence_transcribe.return_value = [
            (0.0, 1.0, "Hello World")
        ]
        
        # Mock file operations
        mock_file = MagicMock()
        mock_open.return_value.__enter__.return_value = mock_file
        
        # Run main
        main()
        
        # Verify calls
        mock_glob.assert_called_once_with(os.path.join("inputs", "*.mp4"))
        mock_extract.assert_called_once()
        mock_word_transcribe.assert_called_once()
        mock_sentence_transcribe.assert_called_once()
        
        # Verify file writes
        self.assertEqual(mock_file.write.call_count, 3)  # 2 words + 1 sentence
        
        # Verify cleanup
        mock_remove.assert_called_once()
    
    @patch('glob.glob')
    @patch('builtins.open', create=True)
    @patch.dict(os.environ, {
        'AZURE_SPEECH_KEY': 'test_key',
        'AZURE_SPEECH_ENDPOINT': 'https://test.endpoint.com'
    })
    def test_main_no_videos(self, mock_open, mock_glob):
        """Test main function when no videos are found"""
        mock_glob.return_value = []
        
        # Should complete without errors
        main()
        
        # Verify no file operations occurred
        mock_open.assert_not_called()


if __name__ == '__main__':
    unittest.main()
