"""Unit tests for frontend JavaScript functionality using Selenium"""
import os
import unittest
import tempfile
import shutil
import time
import json
from pathlib import Path
from unittest.mock import patch, MagicMock
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException
import multiprocessing
import uvicorn

# Add parent directory to path
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestFrontend(unittest.TestCase):
    """Test frontend functionality using Selenium"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test server and browser"""
        # Set up test environment
        cls.test_dir = tempfile.mkdtemp()
        cls.old_cwd = os.getcwd()
        os.chdir(cls.test_dir)
        
        # Create required directories
        Path("inputs").mkdir()
        Path("thumbnails").mkdir()
        Path("static").mkdir()
        
        # Copy static files (assuming they exist in the project)
        static_source = Path(cls.old_cwd) / "static"
        if static_source.exists():
            shutil.copytree(static_source, Path("static"), dirs_exist_ok=True)
        else:
            # Create minimal HTML for testing
            html_content = '''
            <!DOCTYPE html>
            <html>
            <head>
                <title>Video Segmentation Dashboard</title>
            </head>
            <body>
                <div id="app">
                    <h1>Video Segmentation Dashboard</h1>
                    <div id="videoGrid"></div>
                    <div id="uploadSection">
                        <input type="file" id="fileInput" accept="video/*">
                        <button id="uploadBtn">Upload</button>
                    </div>
                    <div id="statusSection"></div>
                </div>
                <script>
                    // Minimal JavaScript for testing
                    const API_BASE = '';
                    let ws = null;
                    
                    async function loadVideos() {
                        const response = await fetch(`${API_BASE}/api/videos`);
                        const videos = await response.json();
                        const grid = document.getElementById('videoGrid');
                        grid.innerHTML = videos.map(v => `
                            <div class="video-card" data-video="${v.name}">
                                <h3>${v.name}</h3>
                                <button class="process-btn" data-video="${v.name}">Process</button>
                                <button class="delete-btn" data-video="${v.name}">Delete</button>
                            </div>
                        `).join('');
                    }
                    
                    async function processVideo(videoName) {
                        const response = await fetch(`${API_BASE}/api/process`, {
                            method: 'POST',
                            headers: {'Content-Type': 'application/json'},
                            body: JSON.stringify({video_name: videoName})
                        });
                        return response.json();
                    }
                    
                    function connectWebSocket() {
                        ws = new WebSocket(`ws://localhost:8001/ws`);
                        ws.onmessage = (event) => {
                            const data = JSON.parse(event.data);
                            if (data.type === 'status_update') {
                                updateStatus(data.video_name, data.status, data.progress);
                            }
                        };
                    }
                    
                    function updateStatus(videoName, status, progress) {
                        const statusDiv = document.getElementById('statusSection');
                        statusDiv.innerHTML = `${videoName}: ${status} (${progress}%)`;
                    }
                    
                    // Event listeners
                    document.addEventListener('click', async (e) => {
                        if (e.target.classList.contains('process-btn')) {
                            await processVideo(e.target.dataset.video);
                        } else if (e.target.classList.contains('delete-btn')) {
                            await fetch(`${API_BASE}/api/videos/${e.target.dataset.video}`, {
                                method: 'DELETE'
                            });
                            await loadVideos();
                        }
                    });
                    
                    document.getElementById('uploadBtn')?.addEventListener('click', async () => {
                        const fileInput = document.getElementById('fileInput');
                        if (fileInput.files.length > 0) {
                            const formData = new FormData();
                            formData.append('file', fileInput.files[0]);
                            await fetch(`${API_BASE}/api/upload`, {
                                method: 'POST',
                                body: formData
                            });
                            await loadVideos();
                        }
                    });
                    
                    // Initialize
                    loadVideos();
                    connectWebSocket();
                </script>
            </body>
            </html>
            '''
            with open("static/index.html", 'w', encoding='utf-8') as f:
                f.write(html_content)
        
        # Mock environment variables
        test_env = {
            'AZURE_SPEECH_KEY': 'test_key',
            'AZURE_SPEECH_ENDPOINT': 'https://test.endpoint',
            'AZURE_OPENAI_API_KEY': 'test_key',
            'AZURE_OPENAI_API_VERSION': '2024-01-01',
            'AZURE_OPENAI_ENDPOINT': 'https://test.endpoint',
            'AZURE_OPENAI_DEPLOYMENT': 'test-deployment',
            'AZURE_CONTENT_UNDERSTANDING_ENDPOINT': 'https://test.endpoint',
            'AZURE_CONTENT_UNDERSTANDING_API_VERSION': '2024-01-01',
            'AZURE_CONTENT_UNDERSTANDING_API_KEY': 'test_key'
        }
        
        # Start test server in a separate process
        def run_server():
            with patch.dict(os.environ, test_env):
                from app import app
                uvicorn.run(app, host="127.0.0.1", port=8001, log_level="error")
        
        cls.server_process = multiprocessing.Process(target=run_server)
        cls.server_process.start()
        time.sleep(2)  # Wait for server to start
        
        # Set up Chrome driver with headless option
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        
        try:
            cls.driver = webdriver.Chrome(options=chrome_options)
            cls.driver.implicitly_wait(10)
        except Exception:
            # If Chrome is not available, skip tests
            cls.driver = None
    
    @classmethod
    def tearDownClass(cls):
        """Clean up test server and browser"""
        if hasattr(cls, 'driver') and cls.driver:
            cls.driver.quit()
        
        if hasattr(cls, 'server_process'):
            cls.server_process.terminate()
            cls.server_process.join()
        
        os.chdir(cls.old_cwd)
        shutil.rmtree(cls.test_dir, ignore_errors=True)
    
    def setUp(self):
        """Set up each test"""
        if not self.driver:
            self.skipTest("Chrome WebDriver not available")
        
        # Create a test video file
        self.test_video = Path("inputs") / "test_video.mp4"
        self.test_video.write_bytes(b"fake video content")
    
    def tearDown(self):
        """Clean up after each test"""
        # Remove test files
        for video in Path("inputs").glob("*.mp4"):
            video.unlink()
    
    def test_page_loads(self):
        """Test that the page loads successfully"""
        self.driver.get("http://localhost:8001")
        
        # Check page title
        self.assertIn("Video Analysis", self.driver.title)
        
        # Check main elements exist
        app_div = self.driver.find_element(By.ID, "app")
        self.assertIsNotNone(app_div)
        
        video_grid = self.driver.find_element(By.ID, "videoGrid")
        self.assertIsNotNone(video_grid)
    
    def test_video_list_display(self):
        """Test that videos are displayed in the grid"""
        self.driver.get("http://localhost:8001")
        
        # Wait for video grid to load
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "video-card"))
        )
        
        # Check that test video is displayed
        video_cards = self.driver.find_elements(By.CLASS_NAME, "video-card")
        self.assertEqual(len(video_cards), 1)
        
        # Check video name is displayed
        video_name = video_cards[0].find_element(By.TAG_NAME, "h3").text
        self.assertEqual(video_name, "test_video.mp4")
    
    def test_video_processing(self):
        """Test video processing functionality"""
        self.driver.get("http://localhost:8001")
        
        # Wait for video card to load
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "process-btn"))
        )
        
        # Mock the process_video_async function
        with patch('app.process_video_async') as mock_process:
            # Click process button
            process_btn = self.driver.find_element(By.CLASS_NAME, "process-btn")
            process_btn.click()
            
            # Wait a bit for the request to be sent
            time.sleep(1)
            
            # Check status section for updates
            status_section = self.driver.find_element(By.ID, "statusSection")
            # Status might be updated via WebSocket
    
    def test_video_deletion(self):
        """Test video deletion functionality"""
        self.driver.get("http://localhost:8001")
        
        # Wait for delete button
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "delete-btn"))
        )
        
        # Click delete button
        delete_btn = self.driver.find_element(By.CLASS_NAME, "delete-btn")
        delete_btn.click()
        
        # Wait for video grid to update
        time.sleep(1)
        
        # Check that video is removed from grid
        video_cards = self.driver.find_elements(By.CLASS_NAME, "video-card")
        self.assertEqual(len(video_cards), 0)
        
        # Check that file is deleted
        self.assertFalse(self.test_video.exists())
    
    def test_file_upload(self):
        """Test file upload functionality"""
        self.driver.get("http://localhost:8001")
        
        # Create a temporary file to upload
        upload_file = Path("test_upload.mp4")
        upload_file.write_bytes(b"upload video content")
        
        try:
            # Find file input and upload button
            file_input = self.driver.find_element(By.ID, "fileInput")
            upload_btn = self.driver.find_element(By.ID, "uploadBtn")
            
            # Send file path to input
            file_input.send_keys(str(upload_file.absolute()))
            
            # Click upload button
            upload_btn.click()
            
            # Wait for upload to complete and grid to update
            time.sleep(2)
            
            # Check that new video appears in grid
            video_cards = self.driver.find_elements(By.CLASS_NAME, "video-card")
            self.assertEqual(len(video_cards), 2)  # Original test video + uploaded
            
            # Check uploaded file exists in inputs directory
            uploaded_files = list(Path("inputs").glob("test_upload*.mp4"))
            self.assertTrue(len(uploaded_files) > 0)
            
        finally:
            # Clean up
            upload_file.unlink()
    
    def test_websocket_connection(self):
        """Test WebSocket connection and status updates"""
        self.driver.get("http://localhost:8001")
        
        # Execute JavaScript to check WebSocket state
        ws_state = self.driver.execute_script("return ws ? ws.readyState : -1")
        
        # WebSocket states: 0=CONNECTING, 1=OPEN, 2=CLOSING, 3=CLOSED
        self.assertIn(ws_state, [0, 1])  # Should be connecting or open
        
        # Wait a bit for connection to establish
        time.sleep(1)
        
        # Check again
        ws_state = self.driver.execute_script("return ws ? ws.readyState : -1")
        self.assertEqual(ws_state, 1)  # Should be open
    
    def test_responsive_design(self):
        """Test that the page is responsive"""
        # Test different viewport sizes
        viewports = [
            (1920, 1080),  # Desktop
            (768, 1024),   # Tablet
            (375, 667)     # Mobile
        ]
        
        for width, height in viewports:
            self.driver.set_window_size(width, height)
            self.driver.get("http://localhost:8001")
            
            # Check that main elements are visible
            app_div = self.driver.find_element(By.ID, "app")
            self.assertTrue(app_div.is_displayed())
            
            video_grid = self.driver.find_element(By.ID, "videoGrid")
            self.assertTrue(video_grid.is_displayed())


if __name__ == '__main__':
    unittest.main()
