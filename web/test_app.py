#!/usr/bin/env python3
"""
Simple tests for FerryTrmnl application
These tests verify basic functionality without requiring an actual API key.
"""

import os
import json
from unittest.mock import patch, MagicMock


# Mock environment variables before importing app
@patch.dict(os.environ, {
    'WSDOT_API_KEY': 'test_key_12345',
    'FLASK_PORT': '5050',
    'FLASK_DEBUG': 'False'
})
def test_app_imports():
    """Test that the application imports successfully."""
    from app import app, MAX_VESSELS_DISPLAY, MAX_DEPARTURES_DISPLAY
    assert app is not None
    assert MAX_VESSELS_DISPLAY == 5
    assert MAX_DEPARTURES_DISPLAY == 10


@patch.dict(os.environ, {
    'WSDOT_API_KEY': 'test_key_12345',
    'FLASK_PORT': '5050'
})
def test_app_routes():
    """Test that all expected routes are registered."""
    from app import app
    
    client = app.test_client()
    
    # Test root endpoint
    response = client.get('/')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert 'service' in data
    assert 'endpoints' in data
    
    # Test health endpoint
    response = client.get('/health')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['status'] == 'healthy'
    assert 'timestamp' in data


@patch.dict(os.environ, {
    'WSDOT_API_KEY': 'test_key_12345',
    'FLASK_PORT': '5050'
})
@patch('app.requests.get')
def test_webhook_with_mock_data(mock_get):
    """Test webhook endpoint with mocked API response."""
    from app import app
    
    # Mock successful API response
    mock_response = MagicMock()
    mock_response.json.return_value = [
        {
            'VesselName': 'Test Ferry',
            'InService': 'True',
            'AtDock': 'Seattle Terminal',
            'LeftDock': ''
        }
    ]
    mock_response.raise_for_status = MagicMock()
    mock_get.return_value = mock_response
    
    client = app.test_client()
    response = client.get('/webhook')
    
    assert response.status_code == 200
    assert b'WA State Ferry Status' in response.data


@patch.dict(os.environ, {
    'WSDOT_API_KEY': 'test_key_12345',
    'FLASK_PORT': '5050'
})
@patch('app.requests.get')
def test_api_ferry_status(mock_get):
    """Test JSON API endpoint."""
    from app import app
    
    # Mock successful API response
    mock_response = MagicMock()
    mock_response.json.return_value = [
        {
            'VesselName': 'Test Ferry',
            'InService': 'True'
        }
    ]
    mock_response.raise_for_status = MagicMock()
    mock_get.return_value = mock_response
    
    client = app.test_client()
    response = client.get('/api/ferry-status')
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert 'vessels' in data or 'error' in data


@patch.dict(os.environ, {
    'WSDOT_API_KEY': 'test_key_12345',
    'FLASK_PORT': '5050'
})
def test_format_ferry_data():
    """Test the ferry data formatting function."""
    from app import format_ferry_data
    
    # Test with error data
    error_data = {"error": "Test error"}
    result = format_ferry_data(error_data)
    assert "error" in result
    
    # Test with valid data
    valid_data = {
        "vessels": [
            {
                "VesselName": "Test Ferry",
                "InService": "True",
                "AtDock": "Seattle",
                "LeftDock": "10:00"
            }
        ],
        "route_info": {},
        "timestamp": "2024-01-01T10:00:00"
    }
    result = format_ferry_data(valid_data)
    assert "route_name" in result
    assert "vessels" in result
    assert len(result["vessels"]) == 1
    assert result["vessels"][0]["name"] == "Test Ferry"


if __name__ == '__main__':
    print("Running basic tests...")
    
    # Run tests manually
    test_app_imports()
    print("✓ App imports test passed")
    
    test_app_routes()
    print("✓ App routes test passed")
    
    test_webhook_with_mock_data()
    print("✓ Webhook with mock data test passed")
    
    test_api_ferry_status()
    print("✓ API ferry status test passed")
    
    test_format_ferry_data()
    print("✓ Format ferry data test passed")
    
    print("\nAll tests passed!")
