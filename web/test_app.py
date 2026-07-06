#!/usr/bin/env python3
"""
Simple tests for FerryTrmnl application
These tests verify basic functionality without requiring an actual API key.
"""

import os
import sys
import json
import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture(autouse=True)
def _clear_ferry_cache():
    """Clear the WSDOT response cache between tests for determinism."""
    m = sys.modules.get('app')
    if m and hasattr(m, '_ferry_cache'):
        m._ferry_cache.clear()
    yield


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
    assert b'FerryNotifier Control Panel' in response.data
    assert b'data-tab="trmnl"' in response.data
    assert b'data-tab="vestaboard"' in response.data
    assert b'Fetch Preview' in response.data
    assert b'Push to Board' in response.data
    assert b'Scheduled Push Targets' in response.data

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


@patch.dict(os.environ, {
    'WSDOT_API_KEY': 'test_key_12345',
    'FLASK_PORT': '5050'
})
def test_settings_persistence_and_board(tmp_path):
    """Settings persist to disk and board ids are generated + resolved for pushes."""
    import app
    spath = str(tmp_path / 'settings.json')
    with patch.object(app, 'SETTINGS_PATH', spath):
        client = app.app.test_client()

        # Empty defaults on first read
        assert client.get('/api/settings').get_json()['vestaboard']['boards'] == []

        # Save a board (no id -> slugified from name)
        r = client.post('/api/settings', json={
            'route_id': 'sea-bi',
            'vestaboard': {'selected': '', 'boards': [{'name': 'Kitchen Board', 'key': 'kkey', 'url': ''}]}
        })
        saved = r.get_json()
        assert saved['vestaboard']['boards'][0]['id'] == 'kitchen-board'

        # Persisted across a fresh read
        again = client.get('/api/settings').get_json()
        assert again['route_id'] == 'sea-bi'
        assert again['vestaboard']['boards'][0]['key'] == 'kkey'

        # Push resolves the board_id to that board's key
        with patch('app.requests.get') as mg, patch('app.requests.post') as mp:
            gr = MagicMock(); gr.json.return_value = []; gr.raise_for_status = MagicMock(); mg.return_value = gr
            pr = MagicMock(); pr.content = b'{}'; pr.json.return_value = {}; pr.raise_for_status = MagicMock(); mp.return_value = pr
            resp = client.post('/api/vestaboard', json={'route_id': 'sea-bi', 'board_id': 'kitchen-board'})
            assert resp.status_code == 200 and resp.get_json()['sent'] is True
            assert mp.call_args.kwargs['headers']['X-Vestaboard-Read-Write-Key'] == 'kkey'


@patch.dict(os.environ, {'WSDOT_API_KEY': 'test', 'FLASK_PORT': '5050'})
def test_direction_status_and_layout():
    """Direction status computes next departure/spaces/delay and lays out correctly."""
    from app import compute_direction_status, format_vestaboard_message, format_ferry_data, VB_ROWS, VB_COLS
    from datetime import datetime, timedelta

    soon = datetime.now() + timedelta(minutes=30)
    raw = {
        "route_name": "Seattle / Bainbridge Island",
        "route_id": "sea-bi",
        "vessels": [],
        "terminal_spaces": {"Bainbridge Island": {"drive_up": 100}},
        "terminal_departures": {
            "Bainbridge Island": [
                {"time": soon, "arrival": "Seattle", "vessel": "Wenatchee", "drive_up": 106},
            ]
        },
        "alerts": [
            {"title": "Sea/BI - vessel out of service - expect delays", "route_ids": [5],
             "all_routes": False, "is_delay": True},
            {"title": "Sea/BI - elevator out of service", "route_ids": [5],
             "all_routes": False, "is_delay": False},
        ],
    }
    st = compute_direction_status(raw, "sea-bi", "Bainbridge Island")
    assert st["from_short"] == "BAIN" and st["to_short"] == "SEA"
    assert st["spaces"] == 106
    assert st["delay"] and "vessel out of service" in st["delay"].lower()

    grid = format_vestaboard_message(format_ferry_data(raw), st)
    assert len(grid) == VB_ROWS and all(len(r) == VB_COLS for r in grid)

    # No-delay route: informational alert must not be treated as a delay
    raw_info = dict(raw, alerts=[{"title": "Youth tickets valid six hours", "route_ids": [5],
                                  "all_routes": False, "is_delay": False}])
    st2 = compute_direction_status(raw_info, "sea-bi", "Bainbridge Island")
    assert st2["delay"] is None


@patch.dict(os.environ, {'WSDOT_API_KEY': 'test', 'FLASK_PORT': '5050'})
def test_note_model_dimensions():
    """A Note board renders a 3x15 grid; flagship renders 6x22."""
    from app import format_vestaboard_message, format_ferry_data, compute_direction_status
    from datetime import datetime, timedelta

    soon = datetime.now() + timedelta(minutes=30)
    raw = {
        "route_name": "Seattle / Bainbridge Island", "route_id": "sea-bi", "vessels": [],
        "terminal_spaces": {"Bainbridge Island": {"drive_up": 106}},
        "terminal_departures": {"Bainbridge Island": [
            {"time": soon, "arrival": "Seattle", "vessel": "Wenatchee", "drive_up": 106}]},
        "alerts": [],
    }
    st = compute_direction_status(raw, "sea-bi", "Bainbridge Island")
    fd = format_ferry_data(raw)

    flag = format_vestaboard_message(fd, st, model="flagship")
    note = format_vestaboard_message(fd, st, model="note")
    assert len(flag) == 6 and all(len(r) == 22 for r in flag)
    assert len(note) == 3 and all(len(r) == 15 for r in note)
    # All codes valid for both
    for grid in (flag, note):
        assert all(0 <= c <= 71 for row in grid for c in row)


@patch.dict(os.environ, {'WSDOT_API_KEY': 'test', 'FLASK_PORT': '5050'})
def test_scheduler_pushes_due_targets(tmp_path):
    """The scheduler pushes enabled targets, records state, and respects intervals."""
    import app
    with patch.object(app, 'SETTINGS_PATH', str(tmp_path / 'settings.json')), \
         patch.object(app, 'SCHEDULE_STATE_PATH', str(tmp_path / 'state.json')):
        client = app.app.test_client()
        client.post('/api/settings', json={
            'wsdot_key': 'wk',
            'vestaboard': {'boards': [{'name': 'K', 'model': 'note', 'route': 'sea-bi',
                                       'direction': 'Seattle', 'key': 'vbkey',
                                       'schedule': {'enabled': True, 'interval_min': 30}}]},
            'trmnl': {'devices': [{'name': 'O', 'route': 'sea-bi', 'direction': 'Seattle',
                                   'webhook_url': 'https://usetrmnl.com/api/custom_plugins/x',
                                   'schedule': {'enabled': True, 'interval_min': 15}}]},
        })
        with patch('app.requests.get') as mg, patch('app.requests.post') as mp:
            gr = MagicMock(); gr.json.return_value = []; gr.raise_for_status = MagicMock(); mg.return_value = gr
            pr = MagicMock(); pr.status_code = 200; pr.content = b'{}'; pr.json.return_value = {}; pr.raise_for_status = MagicMock(); mp.return_value = pr
            app._scheduler_tick()
            posts = [c.args[0] for c in mp.call_args_list]
            assert 'https://rw.vestaboard.com/' in posts
            assert 'https://usetrmnl.com/api/custom_plugins/x' in posts
            # A second immediate tick pushes nothing (intervals not elapsed)
            mp.reset_mock()
            app._scheduler_tick()
            assert mp.call_count == 0

        status = client.get('/api/schedule/status').get_json()
        assert status['vestaboard']['k']['ok'] is True
        assert status['trmnl']['o']['ok'] is True


@patch.dict(os.environ, {'WSDOT_API_KEY': 'test', 'FLASK_PORT': '5050'})
def test_aligned_schedule_minute_13_of_15():
    import app
    from datetime import datetime
    sch = app._normalize_schedule({'enabled': True, 'mode': 'aligned', 'align_period_min': 15, 'align_offset_min': 13})
    assert app._aligned_due(sch, {}, datetime(2026, 7, 6, 10, 13, 0)) is True
    assert app._aligned_due(sch, {}, datetime(2026, 7, 6, 10, 14, 0)) is False
    # once per window
    just = {'last_push': datetime(2026, 7, 6, 10, 13, 0).isoformat()}
    assert app._aligned_due(sch, just, datetime(2026, 7, 6, 10, 13, 30)) is False
    assert app._aligned_due(sch, just, datetime(2026, 7, 6, 10, 28, 0)) is True


@patch.dict(os.environ, {'WSDOT_API_KEY': 'test', 'FLASK_PORT': '5050'})
def test_smart_schedule_triggers():
    import app
    from datetime import datetime, timedelta
    sch = app._normalize_schedule({'enabled': True, 'mode': 'smart', 'interval_min': 15, 'spaces_pct': 25})
    now = datetime(2026, 7, 6, 10, 0, 0)
    data = {'vessels': [{'VesselName': 'Tacoma', 'AtDock': True, 'InService': True}],
            'terminal_spaces': {'Seattle': {'max': 200, 'drive_up': 100}}}
    status = {'from': 'Seattle', 'spaces': 100}
    base = {'last_push': now.isoformat(), 'observed_docked': ['Tacoma'], 'pushed_spaces': 100}

    assert app._smart_evaluate(None, sch, base, data, status, now + timedelta(minutes=5))[0] is False
    # new vessel docks -> arrival
    data2 = {'vessels': data['vessels'] + [{'VesselName': 'Wenatchee', 'AtDock': True, 'InService': True}],
             'terminal_spaces': data['terminal_spaces']}
    assert 'arrival' in app._smart_evaluate(None, sch, base, data2, status, now + timedelta(minutes=5))[1]
    # >25% of 200 = >50 change
    assert 'spaces' in app._smart_evaluate(None, sch, base, data, {'from': 'Seattle', 'spaces': 40}, now + timedelta(minutes=5))[1]
    assert app._smart_evaluate(None, sch, base, data, {'from': 'Seattle', 'spaces': 80}, now + timedelta(minutes=5))[0] is False
    # time trigger after interval
    assert 'time' in app._smart_evaluate(None, sch, base, data, status, now + timedelta(minutes=16))[1]


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
