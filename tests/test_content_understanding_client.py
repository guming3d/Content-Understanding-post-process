"""Unit tests for content_understanding_client.py module"""
import os
import unittest
from unittest.mock import patch, MagicMock, mock_open
import json
import requests
from pathlib import Path

# Add parent directory to path for imports
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from content_understanding_client import AzureContentUnderstandingClient


class TestAzureContentUnderstandingClient(unittest.TestCase):
    """Test cases for Azure Content Understanding Client"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.endpoint = "https://test.endpoint.com"
        self.api_version = "2024-01-01"
        self.api_key = "test_api_key"
        self.analyzer_id = "test_analyzer"
        
        self.client = AzureContentUnderstandingClient(
            endpoint=self.endpoint,
            api_version=self.api_version,
            api_key=self.api_key
        )
    
    def test_client_initialization_with_api_key(self):
        """Test client initialization with API key"""
        client = AzureContentUnderstandingClient(
            endpoint=self.endpoint,
            api_version=self.api_version,
            api_key=self.api_key
        )
        
        self.assertEqual(client._endpoint, self.endpoint)
        self.assertEqual(client._api_version, self.api_version)
        self.assertIn('Ocp-Apim-Subscription-Key', client._headers)
        self.assertEqual(client._headers['Ocp-Apim-Subscription-Key'], self.api_key)
    
    def test_client_initialization_with_subscription_key(self):
        """Test client initialization with subscription key"""
        client = AzureContentUnderstandingClient(
            endpoint=self.endpoint,
            api_version=self.api_version,
            subscription_key=self.api_key
        )
        
        self.assertIn('Ocp-Apim-Subscription-Key', client._headers)
    
    def test_client_initialization_with_token_provider(self):
        """Test client initialization with token provider"""
        token_provider = lambda: "test_token"
        client = AzureContentUnderstandingClient(
            endpoint=self.endpoint,
            api_version=self.api_version,
            token_provider=token_provider
        )
        
        self.assertIn('Authorization', client._headers)
        self.assertEqual(client._headers['Authorization'], 'Bearer test_token')
    
    def test_client_initialization_missing_credentials(self):
        """Test client initialization fails without credentials"""
        with self.assertRaises(ValueError) as context:
            AzureContentUnderstandingClient(
                endpoint=self.endpoint,
                api_version=self.api_version
            )
        
        self.assertIn("Either api_key, subscription_key, or token_provider", str(context.exception))
    
    def test_client_initialization_missing_api_version(self):
        """Test client initialization fails without API version"""
        with self.assertRaises(ValueError) as context:
            AzureContentUnderstandingClient(
                endpoint=self.endpoint,
                api_version="",
                api_key=self.api_key
            )
        
        self.assertIn("API version must be provided", str(context.exception))
    
    def test_client_initialization_missing_endpoint(self):
        """Test client initialization fails without endpoint"""
        with self.assertRaises(ValueError) as context:
            AzureContentUnderstandingClient(
                endpoint="",
                api_version=self.api_version,
                api_key=self.api_key
            )
        
        self.assertIn("Endpoint must be provided", str(context.exception))
    
    @patch('requests.get')
    def test_get_all_analyzers_success(self, mock_get):
        """Test successful retrieval of all analyzers"""
        mock_response = MagicMock()
        mock_response.json.return_value = {"analyzers": ["analyzer1", "analyzer2"]}
        mock_get.return_value = mock_response
        
        result = self.client.get_all_analyzers()
        
        expected_url = f"{self.endpoint}/contentunderstanding/analyzers?api-version={self.api_version}"
        mock_get.assert_called_once_with(url=expected_url, headers=self.client._headers)
        self.assertEqual(result, {"analyzers": ["analyzer1", "analyzer2"]})
    
    @patch('requests.get')
    def test_get_all_analyzers_failure(self, mock_get):
        """Test failed retrieval of all analyzers"""
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("404 Not Found")
        mock_get.return_value = mock_response
        
        with self.assertRaises(requests.exceptions.HTTPError):
            self.client.get_all_analyzers()
    
    @patch('requests.get')
    def test_get_analyzer_detail_by_id_success(self, mock_get):
        """Test successful retrieval of analyzer details"""
        mock_response = MagicMock()
        mock_response.json.return_value = {"id": self.analyzer_id, "status": "ready"}
        mock_get.return_value = mock_response
        
        result = self.client.get_analyzer_detail_by_id(self.analyzer_id)
        
        expected_url = f"{self.endpoint}/contentunderstanding/analyzers/{self.analyzer_id}?api-version={self.api_version}"
        mock_get.assert_called_once_with(url=expected_url, headers=self.client._headers)
        self.assertEqual(result["id"], self.analyzer_id)
    
    @patch('requests.put')
    def test_begin_create_analyzer_with_template(self, mock_put):
        """Test analyzer creation with template dict"""
        template = {"name": "test", "config": {"key": "value"}}
        mock_response = MagicMock()
        mock_put.return_value = mock_response
        
        result = self.client.begin_create_analyzer(self.analyzer_id, analyzer_template=template)
        
        expected_url = f"{self.endpoint}/contentunderstanding/analyzers/{self.analyzer_id}?api-version={self.api_version}"
        expected_headers = dict(self.client._headers)
        expected_headers['Content-Type'] = 'application/json'
        
        mock_put.assert_called_once_with(
            url=expected_url,
            headers=expected_headers,
            json=template
        )
        self.assertEqual(result, mock_response)
    
    @patch('builtins.open', new_callable=mock_open, read_data='{"name": "test"}')
    @patch('requests.put')
    def test_begin_create_analyzer_with_template_path(self, mock_put, mock_file):
        """Test analyzer creation with template file path"""
        template_path = "template.json"
        mock_response = MagicMock()
        mock_put.return_value = mock_response
        
        with patch('pathlib.Path.exists', return_value=True):
            result = self.client.begin_create_analyzer(
                self.analyzer_id, 
                analyzer_template_path=template_path
            )
        
        mock_file.assert_called_once_with(template_path, 'r')
        self.assertEqual(result, mock_response)
    
    @patch('requests.put')
    def test_begin_create_analyzer_with_training_data(self, mock_put):
        """Test analyzer creation with training data configuration"""
        template = {"name": "test"}
        sas_url = "https://storage.blob.core.windows.net/container?sas=token"
        path_prefix = "training/data"
        
        mock_response = MagicMock()
        mock_put.return_value = mock_response
        
        result = self.client.begin_create_analyzer(
            self.analyzer_id,
            analyzer_template=template,
            training_storage_container_sas_url=sas_url,
            training_storage_container_path_prefix=path_prefix
        )
        
        # Verify training data was added to template
        actual_json = mock_put.call_args[1]['json']
        self.assertIn('trainingData', actual_json)
        self.assertEqual(actual_json['trainingData']['containerUrl'], sas_url)
        self.assertEqual(actual_json['trainingData']['prefix'], path_prefix)
    
    def test_begin_create_analyzer_no_template(self):
        """Test analyzer creation fails without template"""
        with self.assertRaises(ValueError) as context:
            self.client.begin_create_analyzer(self.analyzer_id)
        
        self.assertIn("Analyzer schema must be provided", str(context.exception))
    
    @patch('requests.delete')
    def test_delete_analyzer_success(self, mock_delete):
        """Test successful analyzer deletion"""
        mock_response = MagicMock()
        mock_delete.return_value = mock_response
        
        result = self.client.delete_analyzer(self.analyzer_id)
        
        expected_url = f"{self.endpoint}/contentunderstanding/analyzers/{self.analyzer_id}?api-version={self.api_version}"
        mock_delete.assert_called_once_with(url=expected_url, headers=self.client._headers)
        self.assertEqual(result, mock_response)
    
    @patch('builtins.open', new_callable=mock_open, read_data=b'file content')
    @patch('requests.post')
    def test_begin_analyze_with_file(self, mock_post, mock_file):
        """Test analysis with local file"""
        file_path = "test_video.mp4"
        mock_response = MagicMock()
        mock_post.return_value = mock_response
        
        with patch('pathlib.Path.exists', return_value=True):
            result = self.client.begin_analyze(self.analyzer_id, file_path)
        
        expected_url = f"{self.endpoint}/contentunderstanding/analyzers/{self.analyzer_id}:analyze?api-version={self.api_version}"
        expected_headers = dict(self.client._headers)
        expected_headers['Content-Type'] = 'application/octet-stream'
        
        mock_post.assert_called_once_with(
            url=expected_url,
            headers=expected_headers,
            data=b'file content'
        )
        self.assertEqual(result, mock_response)
    
    @patch('requests.post')
    def test_begin_analyze_with_url(self, mock_post):
        """Test analysis with URL"""
        url = "https://example.com/video.mp4"
        mock_response = MagicMock()
        mock_post.return_value = mock_response
        
        result = self.client.begin_analyze(self.analyzer_id, url)
        
        expected_url = f"{self.endpoint}/contentunderstanding/analyzers/{self.analyzer_id}:analyze?api-version={self.api_version}"
        expected_headers = dict(self.client._headers)
        expected_headers['Content-Type'] = 'application/json'
        
        mock_post.assert_called_once_with(
            url=expected_url,
            headers=expected_headers,
            json={"url": url}
        )
        self.assertEqual(result, mock_response)
    
    def test_begin_analyze_invalid_location(self):
        """Test analysis fails with invalid file location"""
        with self.assertRaises(ValueError) as context:
            self.client.begin_analyze(self.analyzer_id, "invalid_path")
        
        self.assertIn("File location must be a valid path or URL", str(context.exception))
    
    @patch('requests.get')
    def test_get_image_from_analyze_operation(self, mock_get):
        """Test image retrieval from analysis operation"""
        mock_analyze_response = MagicMock()
        mock_analyze_response.headers = {
            'operation-location': f"{self.endpoint}/operations/12345?api-version={self.api_version}"
        }
        
        mock_image_response = MagicMock()
        mock_image_response.headers = {'Content-Type': 'image/jpeg'}
        mock_image_response.content = b'image data'
        mock_get.return_value = mock_image_response
        
        result = self.client.get_image_from_analyze_operation(mock_analyze_response, "image123")
        
        expected_url = f"{self.endpoint}/operations/12345/images/image123?api-version={self.api_version}"
        mock_get.assert_called_once_with(url=expected_url, headers=self.client._headers)
        self.assertEqual(result, b'image data')
    
    def test_get_image_no_operation_location(self):
        """Test image retrieval fails without operation location"""
        mock_response = MagicMock()
        mock_response.headers = {}
        
        with self.assertRaises(ValueError) as context:
            self.client.get_image_from_analyze_operation(mock_response, "image123")
        
        self.assertIn("Operation location not found", str(context.exception))
    
    @patch('time.sleep')
    @patch('requests.get')
    def test_poll_result_success(self, mock_get, mock_sleep):
        """Test successful polling of operation result"""
        mock_response = MagicMock()
        mock_response.headers = {'operation-location': 'https://test.com/operations/123'}
        
        # Mock progression: running -> succeeded
        mock_poll_responses = [
            MagicMock(json=lambda: {"status": "running"}),
            MagicMock(json=lambda: {"status": "succeeded", "result": "data"})
        ]
        mock_get.side_effect = mock_poll_responses
        
        result = self.client.poll_result(mock_response)
        
        self.assertEqual(mock_get.call_count, 2)
        self.assertEqual(result, {"status": "succeeded", "result": "data"})
    
    @patch('time.sleep')
    @patch('requests.get')
    def test_poll_result_failure(self, mock_get, mock_sleep):
        """Test polling when operation fails"""
        mock_response = MagicMock()
        mock_response.headers = {'operation-location': 'https://test.com/operations/123'}
        
        mock_poll_response = MagicMock(json=lambda: {"status": "failed", "error": "Processing failed"})
        mock_get.return_value = mock_poll_response
        
        with self.assertRaises(RuntimeError) as context:
            self.client.poll_result(mock_response)
        
        self.assertIn("Request failed", str(context.exception))
    
    @patch('time.time')
    @patch('time.sleep')
    @patch('requests.get')
    def test_poll_result_timeout(self, mock_get, mock_sleep, mock_time):
        """Test polling timeout"""
        mock_response = MagicMock()
        mock_response.headers = {'operation-location': 'https://test.com/operations/123'}
        
        # Mock time progression
        mock_time.side_effect = [0, 0, 130]  # Start at 0, then jump past timeout
        
        mock_poll_response = MagicMock(json=lambda: {"status": "running"})
        mock_get.return_value = mock_poll_response
        
        with self.assertRaises(TimeoutError) as context:
            self.client.poll_result(mock_response, timeout_seconds=120)
        
        self.assertIn("Operation timed out after 120", str(context.exception))
    
    def test_poll_result_no_operation_location(self):
        """Test polling fails without operation location"""
        mock_response = MagicMock()
        mock_response.headers = {}
        
        with self.assertRaises(ValueError) as context:
            self.client.poll_result(mock_response)
        
        self.assertIn("Operation location not found", str(context.exception))


if __name__ == '__main__':
    unittest.main()
