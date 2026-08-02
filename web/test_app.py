#!/usr/bin/env python3
"""
Simple tests for FerryNotifier application
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
    assert b'FerryNotifier' in response.data
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


def _vb_text(grid):
    """Decode a Vestaboard grid back to a list of trimmed row strings."""
    import app
    codes = {v: k for k, v in app.VB_CHAR_MAP.items()}
    return [''.join(codes.get(c, ' ') for c in row).strip() for row in grid]


def _sea_bi_fixture(delay=False):
    """Formatted data + status for Bainbridge -> Seattle, optionally delayed."""
    import app
    from datetime import datetime, timedelta
    soon = datetime.now() + timedelta(minutes=30)
    raw = {
        "route_name": "Seattle / Bainbridge Island", "route_id": "sea-bi",
        "vessels": [{"VesselName": "Chimacum", "InService": True, "AtDock": True,
                     "DepartingTerminalName": "Bainbridge Island", "ArrivingTerminalName": "Seattle"}],
        "terminal_spaces": {"Bainbridge Island": {"drive_up": 106}},
        "terminal_departures": {"Bainbridge Island": [
            {"time": soon, "arrival": "Seattle", "vessel": "Wenatchee", "drive_up": 106}]},
        "alerts": ([{"title": "Sea/BI - vessel out of service - expect delays",
                     "route_ids": [5], "all_routes": False, "is_delay": True}] if delay else []),
    }
    st = app.compute_direction_status(raw, "sea-bi", "Bainbridge Island")
    return app.format_ferry_data(raw), st


@patch.dict(os.environ, {'WSDOT_API_KEY': 'test', 'FLASK_PORT': '5050'})
def test_board_template_conditional_delay_vs_vessel():
    """The headline example: delay text when delayed, next ship's name when not."""
    import app
    tpl = "{% if delay %}\nDELAYED {{ time }}\n{% else %}\n{{ vessel }}\n{% endif %}"

    fd, st = _sea_bi_fixture(delay=False)
    calm = _vb_text(app.format_vestaboard_message(fd, st, model="note", template=tpl))
    assert calm[0] == "WENATCHEE"

    fd, st = _sea_bi_fixture(delay=True)
    late = _vb_text(app.format_vestaboard_message(fd, st, model="note", template=tpl))
    assert late[0].startswith("DELAYED ") and late[0] != "DELAYED --"
    # A conditional on its own line must not emit a blank row before the content.
    assert calm[1] == "" and late[1] == ""


@patch.dict(os.environ, {'WSDOT_API_KEY': 'test', 'FLASK_PORT': '5050'})
def test_shipped_examples_fit_their_board():
    """The one-click examples must not lose their conditional line to truncation."""
    import app
    for model, rows_n in (("flagship", 6), ("note", 3)):
        tpl = app.BOARD_TEMPLATE_EXAMPLES[model]
        fd, st = _sea_bi_fixture(delay=False)
        calm = _vb_text(app.format_vestaboard_message(fd, st, model=model, template=tpl))
        fd, st = _sea_bi_fixture(delay=True)
        late = _vb_text(app.format_vestaboard_message(fd, st, model=model, template=tpl))
        assert len(calm) == rows_n
        assert "WENATCHEE" in calm, f"{model} example dropped the vessel line: {calm}"
        assert any(r.startswith("DELAYED") for r in late), f"{model} example dropped the delay line: {late}"
        # Nothing may be clipped mid-word by the column limit.
        assert all(len(r) <= app.vb_dimensions(model)[1] for r in calm + late)


@patch.dict(os.environ, {'WSDOT_API_KEY': 'test', 'FLASK_PORT': '5050'})
def test_board_template_shape_and_alignment():
    """One line per row, `|` splits left/right, overflow drops, short output pads."""
    import app
    fd, st = _sea_bi_fixture()

    rows = app.format_vestaboard_message(fd, st, model="note",
                                         template="SPACES | {{ spaces }}\n{{ origin }} TO {{ dest }}")
    text = _vb_text(rows)
    assert len(rows) == 3 and all(len(r) == 15 for r in rows)
    assert text[0].startswith("SPACES") and text[0].endswith("106")   # right-aligned
    assert text[1] == "BAIN TO SEA"
    assert text[2] == ""                                             # padded blank row

    # More lines than the board has rows: the extras are dropped, not wrapped.
    many = app.format_vestaboard_message(fd, st, model="note", template="\n".join("R%d" % i for i in range(9)))
    assert _vb_text(many) == ["R0", "R1", "R2"]

    # Blank template falls through to the built-in layout.
    assert app.render_board_template("  \n ", fd, st, "note") is None
    assert app.format_vestaboard_message(fd, st, model="note", template="") == \
           app.format_vestaboard_message(fd, st, model="note")


@patch.dict(os.environ, {'WSDOT_API_KEY': 'test', 'FLASK_PORT': '5050'})
def test_board_template_errors_and_sandbox():
    """Broken templates show an on-board error; the sandbox blocks attribute escapes."""
    import app
    fd, st = _sea_bi_fixture()

    broken = _vb_text(app.format_vestaboard_message(fd, st, model="flagship",
                                                    template="{% if delay %}OOPS"))
    assert broken[0] == "TEMPLATE ERROR"

    unsafe = _vb_text(app.format_vestaboard_message(
        fd, st, model="flagship", template="{{ ''.__class__.__mro__ }}"))
    assert unsafe[0] == "TEMPLATE ERROR"

    # An unknown variable is blank, not an error.
    assert _vb_text(app.format_vestaboard_message(
        fd, st, model="note", template="A{{ nope }}B"))[0] == "AB"


@patch.dict(os.environ, {'WSDOT_API_KEY': 'test', 'FLASK_PORT': '5050'})
def test_board_template_persists(tmp_path):
    """A board's template round-trips through /api/settings and is capped."""
    import app
    with patch.object(app, 'SETTINGS_PATH', str(tmp_path / 's.json')):
        client = app.app.test_client()
        client.post('/api/settings', json={'vestaboard': {'boards': [
            {'name': 'Hall', 'model': 'note', 'template': '{{ vessel }}'},
            {'name': 'Big', 'template': 'X' * (app.BOARD_TEMPLATE_MAX + 500)}]}})
        boards = client.get('/api/settings').get_json()['vestaboard']['boards']
        assert boards[0]['template'] == '{{ vessel }}'
        assert len(boards[1]['template']) == app.BOARD_TEMPLATE_MAX


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
        # A real future Seattle->Bainbridge departure, so the push isn't skipped
        # as a WSDOT blackout (see test_ferry_data_is_stale).
        from datetime import datetime, timedelta
        dep_ms = int((datetime.now() + timedelta(minutes=30)).timestamp() * 1000)
        sailing_space = [{
            "TerminalName": "Seattle",
            "DepartingSpaces": [{
                "Departure": f"/Date({dep_ms}-0800)/", "VesselName": "Tacoma",
                "SpaceForArrivalTerminals": [{
                    "TerminalName": "Bainbridge Island", "VesselName": "Tacoma",
                    "DriveUpSpaceCount": 90, "MaxSpaceCount": 200}],
            }],
        }]

        def _wsdot_get(url, *a, **k):
            r = MagicMock(); r.raise_for_status = MagicMock()
            r.json.return_value = sailing_space if "terminalsailingspace" in url else []
            return r

        with patch('app.requests.get', side_effect=_wsdot_get) as mg, patch('app.requests.post') as mp:
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
    from datetime import datetime, timezone
    utc = timezone.utc
    sch = app._normalize_schedule({'enabled': True, 'mode': 'aligned', 'align_period_min': 15, 'align_offset_min': 13})
    assert app._aligned_due(sch, {}, datetime(2026, 7, 6, 10, 13, 0, tzinfo=utc)) is True
    assert app._aligned_due(sch, {}, datetime(2026, 7, 6, 10, 14, 0, tzinfo=utc)) is False
    # once per window
    just = {'last_push': datetime(2026, 7, 6, 10, 13, 0, tzinfo=utc).isoformat()}
    assert app._aligned_due(sch, just, datetime(2026, 7, 6, 10, 13, 30, tzinfo=utc)) is False
    assert app._aligned_due(sch, just, datetime(2026, 7, 6, 10, 28, 0, tzinfo=utc)) is True


@patch.dict(os.environ, {'WSDOT_API_KEY': 'test', 'FLASK_PORT': '5050'})
def test_smart_schedule_triggers():
    import app
    from datetime import datetime, timedelta, timezone
    sch = app._normalize_schedule({'enabled': True, 'mode': 'smart', 'interval_min': 15, 'spaces_pct': 25})
    now = datetime(2026, 7, 6, 10, 0, 0, tzinfo=timezone.utc)
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


@patch.dict(os.environ, {'WSDOT_API_KEY': 'test', 'FLASK_PORT': '5050'})
def test_quiet_hours_window():
    import app
    from datetime import datetime
    q = app._normalize_quiet({'enabled': True, 'start': '22:00', 'end': '06:00'})
    assert app._in_quiet_hours(q, datetime(2026, 7, 6, 23, 0)) is True   # overnight
    assert app._in_quiet_hours(q, datetime(2026, 7, 6, 5, 0)) is True
    assert app._in_quiet_hours(q, datetime(2026, 7, 6, 14, 0)) is False
    # disabled -> never quiet
    q2 = app._normalize_quiet({'enabled': False, 'start': '22:00', 'end': '06:00'})
    assert app._in_quiet_hours(q2, datetime(2026, 7, 6, 23, 0)) is False


@patch.dict(os.environ, {'WSDOT_API_KEY': 'test', 'FLASK_PORT': '5050'})
def test_quiet_hours_sleep_lead():
    """The window opens sleep_lead_min early so the goodnight beats the board's own sleep."""
    import app
    from datetime import datetime
    q = app._normalize_quiet({'enabled': True, 'start': '22:00', 'end': '06:00'})
    assert q['sleep_lead_min'] == app.SLEEP_LEAD_DEFAULT_MIN == 3
    assert app._in_quiet_hours(q, datetime(2026, 7, 6, 21, 57)) is True   # lead edge
    assert app._in_quiet_hours(q, datetime(2026, 7, 6, 21, 56)) is False  # one minute earlier
    assert app._in_quiet_hours(q, datetime(2026, 7, 6, 6, 0)) is False    # end is unshifted
    # explicit lead, including 0 (fire exactly at the configured start)
    q10 = app._normalize_quiet({'enabled': True, 'start': '22:00', 'end': '06:00', 'sleep_lead_min': 10})
    assert app._in_quiet_hours(q10, datetime(2026, 7, 6, 21, 50)) is True
    q0 = app._normalize_quiet({'enabled': True, 'start': '22:00', 'end': '06:00', 'sleep_lead_min': 0})
    assert app._in_quiet_hours(q0, datetime(2026, 7, 6, 21, 59)) is False
    assert app._in_quiet_hours(q0, datetime(2026, 7, 6, 22, 0)) is True
    # a lead can't swallow the whole day: a 1438-minute window keeps one awake minute
    wide = app._normalize_quiet({'enabled': True, 'start': '06:02', 'end': '06:00', 'sleep_lead_min': 60})
    assert app._in_quiet_hours(wide, datetime(2026, 7, 6, 6, 0)) is False
    assert app._in_quiet_hours(wide, datetime(2026, 7, 6, 6, 1)) is True
    # garbage and out-of-range leads clamp
    assert app._normalize_quiet({'sleep_lead_min': 'abc'})['sleep_lead_min'] == 3
    assert app._normalize_quiet({'sleep_lead_min': 999})['sleep_lead_min'] == 60
    assert app._normalize_quiet({'sleep_lead_min': -5})['sleep_lead_min'] == 0


@patch.dict(os.environ, {'WSDOT_API_KEY': 'test', 'FLASK_PORT': '5050'})
def test_scheduler_quiet_pushes_sleep_then_suppresses(tmp_path):
    import app
    from datetime import datetime
    with patch.object(app, 'SETTINGS_PATH', str(tmp_path / 's.json')), \
         patch.object(app, 'SCHEDULE_STATE_PATH', str(tmp_path / 'st.json')):
        client = app.app.test_client()
        client.post('/api/settings', json={'wsdot_key': 'wk', 'vestaboard': {'boards': [{
            'name': 'Bed', 'model': 'note', 'route': 'sea-bi', 'direction': 'Seattle', 'key': 'k',
            'schedule': {'enabled': True, 'mode': 'interval', 'interval_min': 15},
            'quiet': {'enabled': True, 'start': '22:00', 'end': '06:00', 'sleep_text': 'NIGHT'}}]}})
        with patch('app.push_sleep_message', return_value={'status': 'sent'}) as sleep_m, \
             patch('app.push_vestaboard_target', return_value={'status': 'sent'}) as ferry_m:
            with patch('app._now', return_value=datetime(2026, 7, 6, 23, 0, 0)):
                app._scheduler_tick(); app._scheduler_tick()
            assert sleep_m.call_count == 1 and ferry_m.call_count == 0
            with patch('app._now', return_value=datetime(2026, 7, 6, 7, 0, 0)):
                app._scheduler_tick()
            assert ferry_m.call_count == 1  # wake push


@patch.dict(os.environ, {'WSDOT_API_KEY': 'test', 'FLASK_PORT': '5050'})
def test_scheduler_sleeps_early_by_lead(tmp_path):
    """At start-minus-lead the sleep message goes out and ferry pushes already stop."""
    import app
    from datetime import datetime
    with patch.object(app, 'SETTINGS_PATH', str(tmp_path / 's.json')), \
         patch.object(app, 'SCHEDULE_STATE_PATH', str(tmp_path / 'st.json')):
        client = app.app.test_client()
        client.post('/api/settings', json={'wsdot_key': 'wk', 'vestaboard': {'boards': [{
            'name': 'Bed', 'model': 'note', 'route': 'sea-bi', 'direction': 'Seattle', 'key': 'k',
            'schedule': {'enabled': True, 'mode': 'interval', 'interval_min': 15},
            'quiet': {'enabled': True, 'start': '22:00', 'end': '06:00',
                      'sleep_lead_min': 3, 'sleep_text': 'NIGHT'}}]}})
        with patch('app.push_sleep_message', return_value={'status': 'sent'}) as sleep_m, \
             patch('app.push_vestaboard_target', return_value={'status': 'sent'}) as ferry_m:
            with patch('app._now', return_value=datetime(2026, 7, 6, 21, 58, 0)):
                app._scheduler_tick()
            assert sleep_m.call_count == 1 and ferry_m.call_count == 0
            # still quiet once the configured start actually arrives — no second sleep push
            with patch('app._now', return_value=datetime(2026, 7, 6, 22, 0, 0)):
                app._scheduler_tick()
            assert sleep_m.call_count == 1 and ferry_m.call_count == 0


@patch.dict(os.environ, {'WSDOT_API_KEY': 'test', 'FLASK_PORT': '5050'})
def test_ferry_data_is_stale():
    """Only the total 'no departure AND no spaces' blackout counts as stale."""
    import app
    routed = {'departure_time': '2026-08-02T11:30:00', 'spaces': 100}
    assert app._ferry_data_is_stale({'terminal_departures': {'x': [1]}}, routed) is False
    # a real departure with unknown spaces still pushes
    assert app._ferry_data_is_stale({}, {'departure_time': '2026-08-02T11:30:00', 'spaces': None}) is False
    # spaces known but no next departure still pushes
    assert app._ferry_data_is_stale({}, {'departure_time': None, 'spaces': 42}) is False
    # the blackout: both missing -> stale
    assert app._ferry_data_is_stale({'terminal_spaces': {}}, {'departure_time': None, 'spaces': None}) is True
    # hard fetch error -> stale
    assert app._ferry_data_is_stale({'error': 'boom'}, routed) is True
    # route-less board: vessels present -> not stale; nothing -> stale
    assert app._ferry_data_is_stale({'vessels': [{'VesselName': 'Tacoma'}]}, None) is False
    assert app._ferry_data_is_stale({'vessels': [], 'terminal_spaces': {}}, None) is True


@patch.dict(os.environ, {'WSDOT_API_KEY': 'test', 'FLASK_PORT': '5050'})
def test_push_skips_on_stale_wsdot():
    """A blackout read returns skipped and never touches the board."""
    import app
    from datetime import datetime, timedelta
    board = {'name': 'B', 'model': 'note', 'route': 'sea-bi', 'direction': 'Bainbridge Island', 'key': 'k'}
    empty = {'route_id': 'sea-bi', 'vessels': [], 'terminal_spaces': {}, 'terminal_departures': {}, 'alerts': []}
    with patch('app.fetch_ferry_status', return_value=empty), \
         patch('app.send_to_vestaboard') as send_m:
        result = app.push_vestaboard_target(board, 'wk')
    assert result.get('skipped') and send_m.call_count == 0

    # A good read still pushes: a real departure -> send is called, no skip.
    good = dict(empty, terminal_departures={'Bainbridge Island': [
        {'time': datetime.now() + timedelta(minutes=20), 'arrival': 'Seattle',
         'vessel': 'Tacoma', 'drive_up': 90}]})
    with patch('app.fetch_ferry_status', return_value=good), \
         patch('app.send_to_vestaboard', return_value={'status': 'sent'}) as send_ok:
        result = app.push_vestaboard_target(board, 'wk')
    assert 'skipped' not in result and send_ok.call_count == 1


@patch.dict(os.environ, {'WSDOT_API_KEY': 'test', 'FLASK_PORT': '5050'})
def test_trmnl_push_skips_on_stale_wsdot():
    """A blackout read skips the TRMNL webhook too, so the device keeps its screen."""
    import app
    dev = {'name': 'D', 'route': 'sea-bi', 'direction': 'Bainbridge Island',
           'webhook_url': 'https://usetrmnl.com/api/custom_plugins/x'}
    empty = {'route_id': 'sea-bi', 'vessels': [], 'terminal_spaces': {}, 'terminal_departures': {}, 'alerts': []}
    with patch('app.fetch_ferry_status', return_value=empty), \
         patch('app.send_to_trmnl') as send_m:
        result = app.push_trmnl_target(dev, 'wk')
    assert result.get('skipped') and send_m.call_count == 0


@patch.dict(os.environ, {'WSDOT_API_KEY': 'test', 'FLASK_PORT': '5050'})
def test_scheduler_skip_keeps_last_message_and_retries(tmp_path):
    """When WSDOT is glitching the scheduler leaves the board and retries next tick."""
    import app
    from datetime import datetime, timezone, timedelta
    with patch.object(app, 'SETTINGS_PATH', str(tmp_path / 's.json')), \
         patch.object(app, 'SCHEDULE_STATE_PATH', str(tmp_path / 'st.json')):
        client = app.app.test_client()
        client.post('/api/settings', json={'wsdot_key': 'wk', 'vestaboard': {'boards': [{
            'name': 'Hall', 'model': 'note', 'route': 'sea-bi', 'direction': 'Bainbridge Island', 'key': 'k',
            'schedule': {'enabled': True, 'mode': 'interval', 'interval_min': 15}}]}})
        bid = client.get('/api/settings').get_json()['vestaboard']['boards'][0]['id']

        # Seed a real last push an interval ago (the scheduler's interval clock is
        # wall-clock UTC, not _now()). This is the board's last good message.
        first_push = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        st = app._load_state()
        st['vestaboard'][bid] = {'last_push': first_push, 'ok': True, 'message': 'sent'}
        app._save_state(st)

        # Tick with WSDOT down: push returns skipped, board left alone.
        with patch('app.push_vestaboard_target', return_value={'skipped': 'WSDOT data unavailable'}) as skip_m:
            app._scheduler_tick()
        assert skip_m.call_count == 1
        entry = app._load_state()['vestaboard'][bid]
        # last_push did NOT advance -> the last good message sits and it stays due.
        assert entry['last_push'] == first_push
        assert 'skipped' in entry['message'] and entry['ok'] is True

        # Next tick: WSDOT recovers -> it pushes without waiting another interval.
        with patch('app.push_vestaboard_target', return_value={'status': 'sent'}) as back_m:
            app._scheduler_tick()
        assert back_m.call_count == 1
        assert app._load_state()['vestaboard'][bid]['last_push'] != first_push


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
