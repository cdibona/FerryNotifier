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

    # Test root endpoint (simulator frontend) has both integration tabs
    response = client.get('/')
    assert response.status_code == 200
    assert b'Ferry Status Simulator' in response.data
    assert b'data-tab="trmnl"' in response.data
    assert b'data-tab="vestaboard"' in response.data
    assert b'Fetch Preview' in response.data
    assert b'Push to Board' in response.data

    # Test API info endpoint
    response = client.get('/api/info')
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
    assert b'FerryTrmnl' in response.data
    assert b'Test Ferry' in response.data


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


@patch.dict(os.environ, {
    'WSDOT_API_KEY': 'test_key_12345',
    'FLASK_PORT': '5050'
})
def test_format_vestaboard_message():
    """Test that ferry data lays out onto a valid 6x22 Vestaboard grid."""
    from app import format_vestaboard_message, VB_ROWS, VB_COLS

    formatted = {
        "route_name": "Seattle / Bainbridge",
        "vessels": [
            {"name": "Wenatchee", "status": "Sailing", "location": "", "eta": ""},
            {"name": "Tacoma", "status": "Docked", "location": "", "eta": ""},
        ],
        "terminal_spaces": {"Seattle": {"drive_up": 45}, "Bainbridge Island": {"drive_up": 120}},
        "update_time": "3:15 PM",
    }
    grid = format_vestaboard_message(formatted)

    # Grid must be exactly 6 rows of 22 codes, each a valid Vestaboard code.
    assert len(grid) == VB_ROWS
    for row in grid:
        assert len(row) == VB_COLS
        assert all(isinstance(code, int) and 0 <= code <= 71 for code in row)


@patch.dict(os.environ, {
    'WSDOT_API_KEY': 'test_key_12345',
    'FLASK_PORT': '5050'
})
def test_format_vestaboard_message_error():
    """Test that error data still produces a valid grid."""
    from app import format_vestaboard_message, VB_ROWS, VB_COLS

    grid = format_vestaboard_message({"error": "API key not configured"})
    assert len(grid) == VB_ROWS
    assert all(len(row) == VB_COLS for row in grid)


@patch.dict(os.environ, {
    'WSDOT_API_KEY': 'test_key_12345',
    'FLASK_PORT': '5050'
})
@patch('app.requests.get')
def test_vestaboard_preview_endpoint(mock_get):
    """Test the /api/vestaboard preview returns a grid without sending."""
    from app import app

    mock_response = MagicMock()
    mock_response.json.return_value = [{'VesselName': 'Test Ferry', 'InService': True}]
    mock_response.raise_for_status = MagicMock()
    mock_get.return_value = mock_response

    client = app.test_client()
    response = client.get('/api/vestaboard?preview=true')

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['sent'] is False
    assert len(data['characters']) == 6


@patch.dict(os.environ, {
    'WSDOT_API_KEY': 'env_key',
    'FLASK_PORT': '5050'
})
@patch('app.requests.get')
def test_wsdot_key_override(mock_get):
    """A wsdot_key posted to the endpoint overrides the configured env key."""
    from app import app

    mock_response = MagicMock()
    mock_response.json.return_value = []
    mock_response.raise_for_status = MagicMock()
    mock_get.return_value = mock_response

    client = app.test_client()
    resp = client.post('/api/trmnl/preview', json={'route_id': 'sea-bi', 'wsdot_key': 'override_key'})
    assert resp.status_code == 200

    # The override key, not the env key, must be sent to WSDOT.
    used_keys = [call.kwargs.get('params', {}).get('apiaccesscode') for call in mock_get.call_args_list]
    assert 'override_key' in used_keys
    assert 'env_key' not in used_keys


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
