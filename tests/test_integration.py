"""Integration tests for the video analysis pipeline"""
import os
import unittest
from unittest.mock import patch, MagicMock
import tempfile
import shutil
from pathlib import Path
import json
import asyncio

# Add parent directory to path for imports
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock environment variables
test_env = {
    'AZURE_SPEECH_KEY': 'test_speech_key',
    'AZURE_SPEECH_ENDPOINT': 'https://test.speech.endpoint',
    'AZURE_OPENAI_API_KEY': 'test_openai_key',
    'AZURE_OPENAI_API_VERSION': '2024-01-01',
    'AZURE_OPENAI_ENDPOINT': 'https://test.openai.endpoint',
    'AZURE_OPENAI_DEPLOYMENT': 'test-deployment',
    'AZURE_CONTENT_UNDERSTANDING_ENDPOINT': 'https://test.cu.endpoint',
    'AZURE_CONTENT_UNDERSTANDING_API_VERSION': '2024-01-01',
    'AZURE_CONTENT_UNDERSTANDING_API_KEY': 'test_cu_key'
}


class TestIntegration(unittest.TestCase):
    """Integration tests for complete pipeline flow"""
    
    def setUp(self):
        """Set up test environment"""
        self.test_dir = tempfile.mkdtemp()
        self.inputs_dir = Path(self.test_dir) / "inputs"
        self.inputs_dir.mkdir()
        
        # Create a fake video file
        self.test_video = self.inputs_dir / "test_video.mp4"
        self.test_video.write_bytes(b"fake video content")
    
    def tearDown(self):
        """Clean up test environment"""
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    @patch.dict(os.environ, test_env)
    @patch('app.analyze_video')
    @patch('subprocess.run')
    @patch('azure.cognitiveservices.speech.SpeechRecognizer')
    @patch('openai.AzureOpenAI')
    @patch('matplotlib.pyplot.savefig')
    def test_full_pipeline_flow(self, mock_savefig, mock_openai_class, 
                               mock_recognizer_class, mock_subprocess, 
                               mock_analyze):
        """Test complete pipeline from video to final results"""
        from app import process_video_async
        
        # Mock content understanding analysis
        mock_analyze.return_value = self.test_video.parent / f"{self.test_video.name}.json"
        content_result = {
            "result": {
                "contents": [{
                    "startTimeMs": 1000,
                    "endTimeMs": 3000,
                    "fields": {
                        "sellingPoint": {"valueString": "Magical pockets"},
                        "description": {"valueString": "Showing pocket feature"}
                    }
                }]
            }
        }
        with open(mock_analyze.return_value, 'w', encoding='utf-8') as f:
            json.dump(content_result, f)
        
        # Mock ffmpeg for audio extraction and thumbnail
        mock_subprocess.return_value = MagicMock(returncode=0)
        
        # Mock speech recognition
        mock_recognizer = MagicMock()
        mock_recognizer_class.return_value = mock_recognizer
        
        # Mock word recognition
        word_event = MagicMock()
        word_event.result.reason = MagicMock(RecognizedSpeech=1)
        word_event.result.json = json.dumps({
            'NBest': [{
                'Words': [
                    {'Offset': 10000000, 'Duration': 5000000, 'Word': 'Magical'},
                    {'Offset': 15000000, 'Duration': 5000000, 'Word': 'pockets'}
                ]
            }]
        })
        
        # Mock sentence recognition
        sentence_event = MagicMock()
        sentence_event.result.reason = MagicMock(RecognizedSpeech=1)
        sentence_event.result.json = json.dumps({
            'NBest': [{
                'Lexical': 'Magical pockets',
                'Words': [
                    {'Offset': 10000000, 'Duration': 5000000, 'Word': 'Magical'},
                    {'Offset': 15000000, 'Duration': 5000000, 'Word': 'pockets'}
                ]
            }]
        })
        
        # Setup recognition callbacks
        def setup_recognizer(recognizer_mock, event):
            callbacks = {}
            
            def capture_callback(name):
                def wrapper(callback):
                    callbacks[name] = callback
                return wrapper
            
            recognizer_mock.recognized.connect = capture_callback('recognized')
            recognizer_mock.session_stopped.connect = capture_callback('stopped')
            recognizer_mock.canceled.connect = capture_callback('canceled')
            
            def start_recognition():
                # Simulate async recognition
                if 'recognized' in callbacks:
                    callbacks['recognized'](event)
                recognizer_mock.done = True
            
            recognizer_mock.start_continuous_recognition = start_recognition
            recognizer_mock.stop_continuous_recognition = MagicMock()
        
        # Apply different events for word and sentence recognition
        call_count = 0
        def side_effect(*args, **kwargs):
            nonlocal call_count
            recognizer = MagicMock()
            if call_count == 0:
                setup_recognizer(recognizer, word_event)
            else:
                setup_recognizer(recognizer, sentence_event)
            call_count += 1
            return recognizer
        
        mock_recognizer_class.side_effect = side_effect
        
        # Mock OpenAI selling points extraction
        mock_openai = MagicMock()
        mock_openai_class.return_value = mock_openai
        
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps({
            "selling_points": ["Magical pockets"]
        })
        mock_openai.chat.completions.create.return_value = mock_response
        
        # Mock visualization creation
        mock_savefig.return_value = None
        
        # Run the pipeline
        with patch('os.chdir', return_value=None):
            asyncio.run(process_video_async(str(self.test_video), "test_video.mp4"))
        
        # Verify outputs were created
        base_path = self.test_video.with_suffix('')
        
        # Check transcription files
        word_file = Path(f"{base_path}_word.txt")
        self.assertTrue(word_file.exists())
        self.assertIn("Magical", word_file.read_text(encoding='utf-8'))
        
        sentence_file = Path(f"{base_path}_sentence.txt")
        self.assertTrue(sentence_file.exists())
        self.assertIn("Magical pockets", sentence_file.read_text(encoding='utf-8'))
        
        # Check selling points file
        sp_file = Path(f"{base_path}_selling_points.json")
        self.assertTrue(sp_file.exists())
        sp_data = json.loads(sp_file.read_text(encoding='utf-8'))
        self.assertEqual(len(sp_data["selling_points"]), 1)
        self.assertEqual(sp_data["selling_points"][0]["content"], "Magical pockets")
        
        # Check merged segments file
        merged_file = Path(f"{base_path}_merged_segments.json")
        self.assertTrue(merged_file.exists())
        merged_data = json.loads(merged_file.read_text(encoding='utf-8'))
        self.assertIn("merged_segments", merged_data)
        self.assertIn("unmerged_segments", merged_data)
        self.assertIn("final_segments", merged_data)
    
    @patch.dict(os.environ, test_env)
    def test_pipeline_with_missing_azure_credentials(self):
        """Test pipeline behavior with missing Azure credentials"""
        # Remove required environment variables
        with patch.dict(os.environ, {'AZURE_SPEECH_KEY': '', 'AZURE_SPEECH_ENDPOINT': ''}):
            # Importing should fail
            with self.assertRaises(SystemExit):
                import importlib
                import transcribe_videos
                importlib.reload(transcribe_videos)
    
    @patch.dict(os.environ, test_env)
    @patch('subprocess.run')
    def test_pipeline_with_ffmpeg_failure(self, mock_subprocess):
        """Test pipeline handling of ffmpeg failures"""
        from app import process_video_async
        
        # Mock ffmpeg failure
        mock_subprocess.side_effect = Exception("FFmpeg not found")
        
        # Run the pipeline - should handle error gracefully
        asyncio.run(process_video_async(str(self.test_video), "test_video.mp4"))
        
        # Check that no output files were created (except maybe error status)
        base_path = self.test_video.with_suffix('')
        self.assertFalse(Path(f"{base_path}_word.txt").exists())
        self.assertFalse(Path(f"{base_path}_sentence.txt").exists())


class TestEndToEndAPI(unittest.TestCase):
    """End-to-end tests for the API"""
    
    def setUp(self):
        """Set up test environment"""
        from fastapi.testclient import TestClient
        
        self.test_dir = tempfile.mkdtemp()
        self.old_cwd = os.getcwd()
        os.chdir(self.test_dir)
        
        # Create required directories
        Path("inputs").mkdir()
        Path("thumbnails").mkdir()
        Path("static").mkdir()
        
        # Create analyzer template
        Path("analyzer_templates").mkdir()
        template = {
            "name": "test_analyzer",
            "description": "Test analyzer"
        }
        with open("analyzer_templates/video_content_understanding.json", 'w', encoding='utf-8') as f:
            json.dump(template, f)
        
        with patch.dict(os.environ, test_env):
            from app import app
            self.client = TestClient(app)
    
    def tearDown(self):
        """Clean up test environment"""
        os.chdir(self.old_cwd)
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_video_upload_process_results_flow(self):
        """Test complete flow: upload -> process -> get results"""
        # Step 1: Upload video
        video_content = b"fake video content"
        response = self.client.post(
            "/api/upload",
            files={"file": ("test.mp4", io.BytesIO(video_content), "video/mp4")}
        )
        self.assertEqual(response.status_code, 200)
        video_name = response.json()["video"]["name"]
        
        # Step 2: List videos - should include uploaded video
        response = self.client.get("/api/videos")
        self.assertEqual(response.status_code, 200)
        videos = response.json()
        self.assertTrue(any(v["name"] == video_name for v in videos))
        
        # Step 3: Get initial status - should be not_started
        response = self.client.get(f"/api/status/{video_name}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "not_started")
        
        # Step 4: Start processing
        with patch('app.process_video_async') as mock_process:
            response = self.client.post(
                "/api/process",
                json={"video_name": video_name}
            )
            self.assertEqual(response.status_code, 200)
            mock_process.assert_called_once()
        
        # Step 5: Delete video
        response = self.client.delete(f"/api/videos/{video_name}")
        self.assertEqual(response.status_code, 200)
        
        # Step 6: Verify video is deleted
        response = self.client.get("/api/videos")
        videos = response.json()
        self.assertFalse(any(v["name"] == video_name for v in videos))
    
    def test_batch_processing_flow(self):
        """Test batch processing of multiple videos"""
        # Create multiple test videos
        video_names = []
        for i in range(3):
            video_path = Path("inputs") / f"test_video_{i}.mp4"
            video_path.write_bytes(b"fake video content")
            video_names.append(video_path.name)
        
        # Process batch
        with patch('app.process_video_async') as mock_process:
            response = self.client.post(
                "/api/process-batch",
                json={
                    "video_names": video_names + ["nonexistent.mp4"],
                    "enable_content_understanding": True
                }
            )
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(len(data["processed_videos"]), 3)
            self.assertEqual(len(data["not_found_videos"]), 1)
            self.assertEqual(mock_process.call_count, 3)
    
    async def test_websocket_status_updates(self):
        """Test WebSocket status updates"""
        from fastapi.testclient import TestClient
        from app import app, update_status
        
        with TestClient(app) as client:
            with client.websocket_connect("/ws") as websocket:
                # Update status
                await update_status("test.mp4", "processing", 50, "Processing...")
                
                # Should receive update via WebSocket
                data = websocket.receive_json()
                self.assertEqual(data["type"], "status_update")
                self.assertEqual(data["video_name"], "test.mp4")
                self.assertEqual(data["status"], "processing")
                self.assertEqual(data["progress"], 50)


if __name__ == '__main__':
    unittest.main()
