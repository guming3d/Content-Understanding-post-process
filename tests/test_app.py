"""Unit tests for app.py FastAPI application"""
import os
import unittest
from unittest.mock import patch, MagicMock, AsyncMock, mock_open
import json
import asyncio
from pathlib import Path
import tempfile
from fastapi.testclient import TestClient
from fastapi import UploadFile
import io

# Add parent directory to path for imports
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock environment variables before importing app
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

with patch.dict(os.environ, test_env):
    from app import (
        app, extract_selling_points, match_selling_points_with_timestamps,
        merge_segments_by_selling_points, analyze_video, create_segments_visualization,
        generate_thumbnail, get_video_duration, process_video_async,
        update_status, manager, processing_status, ConnectionManager
    )


class TestFastAPIApp(unittest.TestCase):
    """Test cases for FastAPI application"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.client = TestClient(app)
        processing_status.clear()
        
        # Create temporary directories
        self.temp_dir = tempfile.mkdtemp()
        self.inputs_dir = Path(self.temp_dir) / "inputs"
        self.inputs_dir.mkdir(exist_ok=True)
        self.thumbnails_dir = Path(self.temp_dir) / "thumbnails"
        self.thumbnails_dir.mkdir(exist_ok=True)
    
    def tearDown(self):
        """Clean up test fixtures"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @patch('openai.AzureOpenAI')
    def test_extract_selling_points_success(self, mock_openai_class):
        """Test successful extraction of selling points"""
        # Mock OpenAI response
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps({
            "selling_points": [
                "Magical pockets set me free!",
                "So soft and super stretchy",
                "Built-in shorts"
            ]
        })
        mock_client.chat.completions.create.return_value = mock_response
        
        transcription = "These pants have magical pockets that set me free! They're so soft and super stretchy with built-in shorts."
        result = extract_selling_points(transcription)
        
        self.assertEqual(len(result), 3)
        self.assertIn("Magical pockets set me free!", result)
    
    @patch('openai.AzureOpenAI')
    def test_extract_selling_points_error(self, mock_openai_class):
        """Test error handling in selling points extraction"""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        mock_client.chat.completions.create.side_effect = Exception("API Error")
        
        result = extract_selling_points("Test transcription")
        self.assertEqual(result, [])
    
    def test_match_selling_points_with_timestamps(self):
        """Test matching selling points with word timestamps"""
        word_segments = [
            (0.0, 0.5, "These"),
            (0.5, 1.0, "magical"),
            (1.0, 1.5, "pockets"),
            (1.5, 2.0, "are"),
            (2.0, 2.5, "super"),
            (2.5, 3.0, "stretchy")
        ]
        
        selling_points = ["magical pockets", "super stretchy"]
        
        result = match_selling_points_with_timestamps(word_segments, selling_points)
        
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["content"], "magical pockets")
        self.assertEqual(result[0]["startTime"], 0.5)
        self.assertEqual(result[0]["endTime"], 1.5)
        self.assertEqual(result[1]["content"], "super stretchy")
        self.assertEqual(result[1]["startTime"], 2.0)
        self.assertEqual(result[1]["endTime"], 3.0)
    
    def test_match_selling_points_no_match(self):
        """Test selling points matching when no match is found"""
        word_segments = [
            (0.0, 0.5, "Hello"),
            (0.5, 1.0, "World")
        ]
        
        selling_points = ["magical pockets"]
        
        result = match_selling_points_with_timestamps(word_segments, selling_points)
        
        self.assertEqual(len(result), 1)
        self.assertIsNone(result[0]["startTime"])
        self.assertIsNone(result[0]["endTime"])
    
    def test_merge_segments_by_selling_points(self):
        """Test merging video segments with selling points"""
        content_json = {
            "result": {
                "contents": [
                    {
                        "startTimeMs": 500,
                        "endTimeMs": 1500,
                        "fields": {
                            "sellingPoint": {"valueString": "pockets"},
                            "description": {"valueString": "showing pockets"}
                        }
                    }
                ]
            }
        }
        
        selling_points_json = {
            "selling_points": [
                {
                    "startTime": 0.5,
                    "endTime": 1.5,
                    "content": "magical pockets"
                }
            ]
        }
        
        result = merge_segments_by_selling_points(
            content_json, 
            selling_points_json,
            time_deviation_ms=100,
            min_overlap_percentage=0.8
        )
        
        self.assertIn("merged_segments", result)
        self.assertIn("unmerged_segments", result)
        self.assertIn("final_segments", result)
        self.assertEqual(len(result["merged_segments"]), 1)
        self.assertEqual(result["merged_segments"][0]["content"], "magical pockets")
    
    def test_merge_segments_no_timestamps(self):
        """Test merging when selling points have no timestamps"""
        content_json = {"result": {"contents": []}}
        selling_points_json = {
            "selling_points": [
                {"startTime": None, "endTime": None, "content": "test"}
            ]
        }
        
        result = merge_segments_by_selling_points(content_json, selling_points_json)
        
        self.assertEqual(len(result["merged_segments"]), 1)
        self.assertIsNone(result["merged_segments"][0]["startTimeMs"])
    
    @patch('subprocess.run')
    def test_generate_thumbnail_success(self, mock_run):
        """Test successful thumbnail generation"""
        mock_run.return_value = MagicMock(returncode=0)
        
        result = generate_thumbnail("video.mp4", "thumb.jpg", timestamp=5.0)
        
        self.assertTrue(result)
        mock_run.assert_called_once()
        
        # Verify ffmpeg command structure
        cmd = mock_run.call_args[0][0]
        self.assertEqual(cmd[0], 'ffmpeg')
        self.assertIn('-i', cmd)
        self.assertIn('-ss', cmd)
        self.assertIn('5.0', cmd)
    
    @patch('subprocess.run')
    def test_generate_thumbnail_failure(self, mock_run):
        """Test thumbnail generation failure"""
        mock_run.return_value = MagicMock(returncode=1, stderr="Error")
        
        result = generate_thumbnail("video.mp4", "thumb.jpg")
        
        self.assertFalse(result)
    
    @patch('subprocess.run')
    def test_get_video_duration_success(self, mock_run):
        """Test successful video duration retrieval"""
        mock_run.return_value = MagicMock(returncode=0, stdout="120.5\n")
        
        result = get_video_duration("video.mp4")
        
        self.assertEqual(result, 120.5)
        mock_run.assert_called_once()
        
        # Verify ffprobe command
        cmd = mock_run.call_args[0][0]
        self.assertEqual(cmd[0], 'ffprobe')
    
    @patch('subprocess.run')
    def test_get_video_duration_failure(self, mock_run):
        """Test video duration retrieval failure"""
        mock_run.return_value = MagicMock(returncode=1, stderr="Error")
        
        result = get_video_duration("video.mp4")
        
        self.assertIsNone(result)
    
    @patch('pathlib.Path.glob')
    @patch('pathlib.Path.exists')
    @patch('pathlib.Path.stat')
    @patch('app.get_video_duration')
    @patch('app.generate_thumbnail')
    def test_list_videos_endpoint(self, mock_gen_thumb, mock_duration, 
                                 mock_stat, mock_exists, mock_glob):
        """Test /api/videos endpoint"""
        # Mock video files
        mock_video = MagicMock()
        mock_video.name = "test_video.mp4"
        mock_video.with_suffix.return_value = Path("inputs/test_video")
        mock_glob.return_value = [mock_video]
        
        mock_exists.return_value = True
        mock_stat.return_value = MagicMock(st_size=1024*1024*10)  # 10 MB
        mock_duration.return_value = 60.0
        mock_gen_thumb.return_value = True
        
        response = self.client.get("/api/videos")
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["name"], "test_video.mp4")
        self.assertEqual(data[0]["size_mb"], 10.0)
        self.assertEqual(data[0]["duration"], 60.0)
    
    def test_upload_video_endpoint(self):
        """Test /api/upload endpoint"""
        # Create a mock video file
        file_content = b"fake video content"
        file = io.BytesIO(file_content)
        
        with patch('builtins.open', mock_open()) as mock_file:
            with patch('pathlib.Path.exists', return_value=False):
                with patch('pathlib.Path.stat') as mock_stat:
                    mock_stat.return_value = MagicMock(st_size=len(file_content))
                    
                    with patch('app.get_video_duration', return_value=30.0):
                        with patch('app.generate_thumbnail', return_value=True):
                            with patch('app.manager.broadcast', new_callable=AsyncMock):
                                response = self.client.post(
                                    "/api/upload",
                                    files={"file": ("test.mp4", file, "video/mp4")}
                                )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["message"], "Video uploaded successfully")
        self.assertEqual(data["original_filename"], "test.mp4")
    
    def test_upload_video_invalid_type(self):
        """Test video upload with invalid file type"""
        file = io.BytesIO(b"fake content")
        
        response = self.client.post(
            "/api/upload",
            files={"file": ("test.txt", file, "text/plain")}
        )
        
        self.assertEqual(response.status_code, 400)
        self.assertIn("not allowed", response.json()["detail"])
    
    @patch('app.process_video_async')
    def test_process_video_endpoint(self, mock_process):
        """Test /api/process endpoint"""
        with patch('os.path.exists', return_value=True):
            response = self.client.post(
                "/api/process",
                json={"video_name": "test_video.mp4"}
            )
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["message"], "Processing started")
    
    def test_process_video_not_found(self):
        """Test processing non-existent video"""
        with patch('os.path.exists', return_value=False):
            response = self.client.post(
                "/api/process",
                json={"video_name": "nonexistent.mp4"}
            )
        
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "Video not found")
    
    @patch('app.process_video_async')
    def test_process_batch_endpoint(self, mock_process):
        """Test /api/process-batch endpoint"""
        with patch('os.path.exists', side_effect=[True, False, True]):
            response = self.client.post(
                "/api/process-batch",
                json={
                    "video_names": ["video1.mp4", "video2.mp4", "video3.mp4"],
                    "enable_content_understanding": True
                }
            )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["processed_videos"]), 2)
        self.assertEqual(len(data["not_found_videos"]), 1)
    
    def test_get_status_endpoint(self):
        """Test /api/status/{video_name} endpoint"""
        # Add status to processing_status
        processing_status["test_video.mp4"] = {
            "status": "processing",
            "progress": 50,
            "message": "Processing..."
        }
        
        response = self.client.get("/api/status/test_video.mp4")
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "processing")
        self.assertEqual(data["progress"], 50)
    
    def test_get_status_not_started(self):
        """Test status for unprocessed video"""
        response = self.client.get("/api/status/unknown_video.mp4")
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "not_started")
    
    def test_get_all_status_endpoint(self):
        """Test /api/status-all endpoint"""
        processing_status["video1.mp4"] = {"status": "completed"}
        processing_status["video2.mp4"] = {"status": "processing"}
        
        response = self.client.get("/api/status-all")
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 2)
        self.assertIn("video1.mp4", data)
        self.assertIn("video2.mp4", data)
    
    def test_get_results_endpoint(self):
        """Test /api/results/{video_name} endpoint"""
        with patch('os.path.exists', return_value=True):
            with patch('builtins.open', mock_open(read_data='{"test": "data"}')):
                response = self.client.get("/api/results/test_video.mp4")
        
        self.assertEqual(response.status_code, 200)
        # Results processing is complex, just verify structure
        self.assertIsInstance(response.json(), dict)
    
    def test_get_visualization_endpoint(self):
        """Test /api/visualization/{video_name} endpoint"""
        with patch('os.path.exists', return_value=True):
            with patch('fastapi.responses.FileResponse') as mock_response:
                mock_response.return_value = MagicMock()
                response = self.client.get("/api/visualization/test_video.mp4")
        
        # FileResponse is mocked, so just check it was called
        mock_response.assert_called_once()
    
    def test_get_visualization_not_found(self):
        """Test visualization endpoint when file doesn't exist"""
        with patch('os.path.exists', return_value=False):
            response = self.client.get("/api/visualization/test_video.mp4")
        
        self.assertEqual(response.status_code, 404)
    
    @patch('app.generate_thumbnail')
    def test_get_thumbnail_endpoint(self, mock_gen_thumb):
        """Test /api/thumbnail/{video_name} endpoint"""
        mock_gen_thumb.return_value = True
        
        with patch('pathlib.Path.exists', side_effect=[True]):
            with patch('fastapi.responses.FileResponse') as mock_response:
                mock_response.return_value = MagicMock()
                response = self.client.get("/api/thumbnail/test_video.mp4")
        
        mock_response.assert_called_once()
    
    @patch('pathlib.Path.unlink')
    @patch('pathlib.Path.exists')
    @patch('app.manager.broadcast')
    def test_delete_video_endpoint(self, mock_broadcast, mock_exists, mock_unlink):
        """Test /api/videos/{video_name} DELETE endpoint"""
        mock_exists.return_value = True
        mock_broadcast.return_value = AsyncMock()
        
        response = self.client.delete("/api/videos/test_video.mp4")
        
        self.assertEqual(response.status_code, 200)
        self.assertIn("deleted successfully", response.json()["message"])
        
        # Verify file deletion was attempted
        self.assertTrue(mock_unlink.called)
    
    def test_delete_video_not_found(self):
        """Test deleting non-existent video"""
        with patch('pathlib.Path.exists', return_value=False):
            response = self.client.delete("/api/videos/nonexistent.mp4")
        
        self.assertEqual(response.status_code, 404)
    
    def test_serve_video_endpoint(self):
        """Test /inputs/{filename} endpoint"""
        with patch('pathlib.Path.exists', return_value=True):
            with patch('fastapi.responses.FileResponse') as mock_response:
                mock_response.return_value = MagicMock()
                response = self.client.get("/inputs/test_video.mp4")
        
        mock_response.assert_called_once()
        # Verify headers are set correctly
        call_kwargs = mock_response.call_args[1]
        self.assertIn("Accept-Ranges", call_kwargs["headers"])
    
    def test_serve_video_not_found(self):
        """Test serving non-existent video"""
        with patch('pathlib.Path.exists', return_value=False):
            response = self.client.get("/inputs/nonexistent.mp4")
        
        self.assertEqual(response.status_code, 404)


class TestConnectionManager(unittest.TestCase):
    """Test cases for WebSocket connection manager"""
    
    def test_connection_manager_init(self):
        """Test ConnectionManager initialization"""
        cm = ConnectionManager()
        self.assertEqual(len(cm.active_connections), 0)
    
    async def test_connect(self):
        """Test WebSocket connection"""
        cm = ConnectionManager()
        mock_websocket = AsyncMock()
        
        await cm.connect(mock_websocket)
        
        mock_websocket.accept.assert_called_once()
        self.assertEqual(len(cm.active_connections), 1)
    
    def test_disconnect(self):
        """Test WebSocket disconnection"""
        cm = ConnectionManager()
        mock_websocket = MagicMock()
        cm.active_connections.append(mock_websocket)
        
        cm.disconnect(mock_websocket)
        
        self.assertEqual(len(cm.active_connections), 0)
    
    async def test_broadcast(self):
        """Test broadcasting to all connections"""
        cm = ConnectionManager()
        mock_ws1 = AsyncMock()
        mock_ws2 = AsyncMock()
        cm.active_connections = [mock_ws1, mock_ws2]
        
        message = {"type": "test", "data": "value"}
        await cm.broadcast(message)
        
        mock_ws1.send_json.assert_called_once_with(message)
        mock_ws2.send_json.assert_called_once_with(message)


class TestAsyncFunctions(unittest.IsolatedAsyncioTestCase):
    """Test cases for async functions"""
    
    async def test_update_status(self):
        """Test status update function"""
        with patch('app.manager.broadcast', new_callable=AsyncMock) as mock_broadcast:
            await update_status("test.mp4", "processing", 50, "Testing")
            
            self.assertIn("test.mp4", processing_status)
            self.assertEqual(processing_status["test.mp4"]["status"], "processing")
            self.assertEqual(processing_status["test.mp4"]["progress"], 50)
            
            mock_broadcast.assert_called_once()
            broadcast_msg = mock_broadcast.call_args[0][0]
            self.assertEqual(broadcast_msg["type"], "status_update")
            self.assertEqual(broadcast_msg["video_name"], "test.mp4")
    
    @patch('app.analyze_video')
    @patch('app.extract_audio_from_video')
    @patch('app.transcribe_audio_with_word_timestamps')
    @patch('app.transcribe_audio_with_sentence_timestamps')
    @patch('app.extract_selling_points')
    @patch('app.match_selling_points_with_timestamps')
    @patch('app.merge_segments_by_selling_points')
    @patch('app.create_segments_visualization')
    @patch('app.generate_thumbnail')
    @patch('os.path.exists')
    @patch('os.remove')
    @patch('builtins.open', new_callable=mock_open)
    @patch('app.update_status')
    async def test_process_video_async_full_flow(
        self, mock_update_status, mock_file, mock_remove, mock_exists,
        mock_gen_thumb, mock_create_viz, mock_merge, mock_match,
        mock_extract_sp, mock_transcribe_sent, mock_transcribe_word,
        mock_extract_audio, mock_analyze
    ):
        """Test complete video processing flow"""
        # Setup mocks
        mock_update_status.return_value = AsyncMock()
        mock_exists.side_effect = [True, True]  # content json exists, audio exists
        mock_transcribe_word.return_value = [(0, 0.5, "Hello"), (0.5, 1, "World")]
        mock_transcribe_sent.return_value = [(0, 1, "Hello World")]
        mock_extract_sp.return_value = ["Hello World"]
        mock_match.return_value = [{"startTime": 0, "endTime": 1, "content": "Hello World"}]
        mock_merge.return_value = {"merged_segments": [], "unmerged_segments": [], "final_segments": []}
        
        # Mock file reads for merge operation
        mock_file.return_value.__enter__.return_value.read.side_effect = [
            '{"result": {"contents": []}}',  # content json
            '{"selling_points": []}'  # selling points json
        ]
        
        await process_video_async("test_video.mp4", "test_video.mp4")
        
        # Verify all steps were called
        mock_analyze.assert_called_once()
        mock_extract_audio.assert_called_once()
        mock_transcribe_word.assert_called_once()
        mock_transcribe_sent.assert_called_once()
        mock_extract_sp.assert_called_once()
        mock_match.assert_called_once()
        mock_merge.assert_called_once()
        mock_create_viz.assert_called_once()
        mock_gen_thumb.assert_called_once()
        
        # Verify cleanup
        mock_remove.assert_called_once()
    
    @patch('app.update_status')
    async def test_process_video_async_error_handling(self, mock_update_status):
        """Test error handling in video processing"""
        mock_update_status.return_value = AsyncMock()
        
        with patch('app.extract_audio_from_video', side_effect=Exception("Test error")):
            await process_video_async("test_video.mp4", "test_video.mp4")
        
        # Verify error status was set
        last_call = mock_update_status.call_args_list[-1]
        self.assertEqual(last_call[0][1], "error")
        self.assertIn("Test error", last_call[0][3])


if __name__ == '__main__':
    unittest.main()
