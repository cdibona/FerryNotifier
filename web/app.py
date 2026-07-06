#!/usr/bin/env python3
"""
Washington State Ferry Status Webhook for Trmnl Display
This Flask application provides a webhook server that fetches ferry status data
from the WSDOT Ferries API and formats it for display on Trmnl e-ink devices.
"""

import os
import re
import json
import logging
import threading
from datetime import datetime
from typing import Dict, Any, Optional

import requests
from flask import Flask, jsonify, render_template_string, request
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# Configuration from environment variables
WSDOT_API_KEY = os.getenv('WSDOT_API_KEY')
WSDOT_API_BASE_URL = os.getenv('WSDOT_API_BASE_URL', 'https://www.wsdot.wa.gov/ferries/api')
FERRY_ROUTE_ID = os.getenv('FERRY_ROUTE_ID', '')
FLASK_HOST = os.getenv('FLASK_HOST', '0.0.0.0')
FLASK_PORT = int(os.getenv('FLASK_PORT', 5050))
FLASK_DEBUG = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
SITE_URL = os.getenv('SITE_URL', '')
DISCORD_WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL', '')

# Vestaboard configuration (optional push target)
# Uses the Read/Write API: https://docs.vestaboard.com/docs/read-write-api/introduction
# Get a Read/Write key from the Vestaboard app (Settings > API) or web.vestaboard.com.
# The same key works for a Vestaboard Note device.
VESTABOARD_RW_KEY = os.getenv('VESTABOARD_RW_KEY', '')
VESTABOARD_RW_URL = os.getenv('VESTABOARD_RW_URL', 'https://rw.vestaboard.com/')

# Build/version metadata (injected at image build time via Docker build args).
APP_VERSION = os.getenv('APP_VERSION', 'dev')
GIT_SHA = os.getenv('GIT_SHA', '')
GITHUB_REPO_URL = os.getenv('GITHUB_REPO_URL', 'https://github.com/cdibona/FerryNotifier')

# Persisted settings saved from the web UI (route, keys, Vestaboard targets).
# Stored as a JSON file; mount a volume at this path to persist across restarts.
SETTINGS_PATH = os.getenv(
    'SETTINGS_PATH',
    os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'settings.json')
)
_settings_lock = threading.Lock()

# Display configuration constants
MAX_VESSELS_DISPLAY = 5  # Maximum number of vessels to display
MAX_DEPARTURES_DISPLAY = 10  # Maximum number of departures to display

# Vestaboard display dimensions (split-flap grid)
VB_ROWS = 6
VB_COLS = 22


def send_discord_notification(endpoint: str, route_id: str, ip_address: str, user_agent: str):
    """Send a notification to Discord webhook if configured."""
    if not DISCORD_WEBHOOK_URL:
        return

    try:
        payload = {
            "embeds": [{
                "title": "FerryTrmnl API Request",
                "color": 3447003,  # Blue
                "fields": [
                    {"name": "Endpoint", "value": endpoint, "inline": True},
                    {"name": "Route", "value": route_id or "All", "inline": True},
                    {"name": "IP Address", "value": ip_address, "inline": True},
                    {"name": "User Agent", "value": user_agent[:100] if user_agent else "Unknown", "inline": False},
                ],
                "timestamp": datetime.now().isoformat()
            }]
        }
        requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=5)
    except Exception as e:
        logger.warning(f"Failed to send Discord notification: {e}")

# HTML template for Trmnl display
TRMNL_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 15px;
            background-color: white;
        }
        .container {
            max-width: 800px;
            margin: 0 auto;
        }
        .header {
            font-size: 22px;
            font-weight: bold;
            margin-bottom: 8px;
            padding-bottom: 8px;
            border-bottom: 3px solid black;
        }
        .header-brand {
            color: #333;
        }
        .header-route {
            color: #000;
        }
        .vessels-section {
            margin-top: 10px;
        }
        .vessel-info {
            margin: 12px 0;
            padding: 12px;
            border: 2px solid black;
            border-radius: 4px;
        }
        .vessel-name {
            font-size: 18px;
            font-weight: bold;
            margin-bottom: 6px;
        }
        .vessel-status {
            font-size: 15px;
            display: flex;
            gap: 8px;
            align-items: center;
        }
        .status-badge {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 3px;
            font-weight: bold;
            font-size: 13px;
        }
        .status-sailing {
            background: #000;
            color: #fff;
        }
        .status-docked {
            background: #666;
            color: #fff;
        }
        .vessel-location {
            font-size: 14px;
            margin-top: 4px;
            color: #333;
        }
        .footer {
            display: flex;
            justify-content: space-between;
            align-items: flex-end;
            margin-top: 15px;
            padding-top: 10px;
            border-top: 1px solid #ccc;
            font-size: 12px;
            color: #555;
        }
        .parking-info {
            display: flex;
            gap: 15px;
        }
        .terminal-space {
            display: flex;
            align-items: center;
            gap: 4px;
        }
        .terminal-name {
            font-weight: 500;
        }
        .space-count {
            font-weight: bold;
        }
        .update-time {
            text-align: right;
        }
        .error {
            color: #cc0000;
            font-size: 16px;
            padding: 10px;
            border: 1px solid #cc0000;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <span class="header-brand">FerryTrmnl:</span> <span class="header-route">{{ route_name }}</span>
        </div>

        {% if error %}
        <div class="error">{{ error }}</div>
        {% else %}

        <div class="vessels-section">
            {% for vessel in vessels %}
            <div class="vessel-info">
                <div class="vessel-name">{{ vessel.name }}</div>
                <div class="vessel-status">
                    <span class="status-badge {% if vessel.status == 'Sailing' %}status-sailing{% else %}status-docked{% endif %}">{{ vessel.status }}</span>
                </div>
                {% if vessel.location %}
                <div class="vessel-location">{{ vessel.location }}</div>
                {% endif %}
            </div>
            {% endfor %}
        </div>

        <div class="footer">
            <div class="parking-info">
                {% for terminal, space in terminal_spaces.items() %}
                <div class="terminal-space">
                    <span class="terminal-name">{{ terminal }}:</span>
                    <span class="space-count">{{ space.drive_up }}</span> spots
                </div>
                {% endfor %}
            </div>
            <div class="update-time">
                Updated {{ update_time }}
            </div>
        </div>
        {% endif %}
    </div>
</body>
</html>
"""

# HTML template for webhook simulator frontend
SIMULATOR_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TRMNL Webhook Simulator - WA Ferry Status</title>
    <style>
        * { box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            margin: 0; padding: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
        }
        .simulator-container { max-width: 900px; margin: 0 auto; }
        .header { text-align: center; color: white; margin-bottom: 24px; }
        .header h1 { margin: 0 0 10px 0; font-size: 28px; text-shadow: 2px 2px 4px rgba(0,0,0,0.2); }
        .header p { margin: 0; opacity: 0.9; font-size: 16px; }

        .tabs { display: flex; gap: 8px; }
        .tab { flex: 1; padding: 14px 20px; border: none; border-radius: 12px 12px 0 0;
            background: rgba(255,255,255,0.35); color: #2a2250; font-size: 16px; font-weight: 600; cursor: pointer; transition: all 0.2s; }
        .tab:hover { background: rgba(255,255,255,0.55); }
        .tab.active { background: white; color: #333; }
        .tab-panel { display: none; }
        .tab-panel.active { display: block; }

        .controls { background: white; border-radius: 0 12px 12px 12px; padding: 20px; margin-bottom: 20px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); }
        .controls h2 { margin: 0 0 6px 0; font-size: 18px; color: #333; }
        .controls .hint { margin: 0 0 16px 0; font-size: 13px; color: #888; }
        .controls .hint a { color: #667eea; }
        .form-row { display: flex; gap: 15px; flex-wrap: wrap; align-items: flex-end; }
        .form-group { flex: 1; min-width: 180px; }
        .form-group.wide { flex-basis: 100%; }
        .form-group label { display: block; margin-bottom: 5px; font-size: 14px; color: #666; font-weight: 500; }
        .form-group .badge { font-size: 11px; font-weight: 600; color: #2e7d32; margin-left: 6px; }
        .help-link { font-size: 12px; font-weight: 500; color: #667eea; margin-left: 8px; text-decoration: none; }
        .help-link:hover { text-decoration: underline; }
        .form-group input, .form-group select { width: 100%; padding: 10px 12px; border: 2px solid #e0e0e0; border-radius: 8px; font-size: 14px; transition: border-color 0.2s; background-color: white; }
        .form-group input:focus, .form-group select:focus { outline: none; border-color: #667eea; }
        .btn { padding: 12px 24px; border: none; border-radius: 8px; font-size: 14px; font-weight: 600; cursor: pointer; transition: all 0.2s; }
        .btn-primary { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; }
        .btn-primary:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4); }
        .btn-primary:disabled { opacity: 0.6; cursor: not-allowed; transform: none; }
        .btn-secondary { background: #f0f0f0; color: #333; }
        .btn-secondary:hover { background: #e0e0e0; }
        .btn-ghost { background: transparent; color: #c0392b; padding: 12px 8px; }
        .btn-ghost:hover { text-decoration: underline; }
        .board-editor { margin-top: 16px; padding: 16px; background: #f8f9fb; border: 1px solid #e6e8f0; border-radius: 10px; }
        .board-editor h4 { margin: 0 0 12px 0; font-size: 14px; color: #555; }
        .webhook-url { background: #f8f9fa; border-radius: 8px; padding: 12px; margin-top: 15px; font-family: 'Monaco', 'Menlo', monospace; font-size: 13px; color: #666; word-break: break-all; }
        .webhook-url strong { color: #333; }

        .trmnl-frame { background: #2a2a2a; border-radius: 20px; padding: 20px; box-shadow: 0 10px 40px rgba(0,0,0,0.3); }
        .trmnl-bezel { background: #1a1a1a; border-radius: 12px; padding: 8px; }
        .trmnl-screen { background: #f5f5f0; border-radius: 4px; min-height: 480px; position: relative; overflow: hidden; }
        .trmnl-screen iframe { width: 100%; height: 480px; border: none; background: white; }
        .trmnl-placeholder { display: flex; flex-direction: column; align-items: center; justify-content: center; height: 480px; color: #999; text-align: center; padding: 40px; }
        .trmnl-placeholder svg { width: 80px; height: 80px; margin-bottom: 20px; opacity: 0.5; }
        .trmnl-placeholder h3 { margin: 0 0 10px 0; color: #666; }
        .trmnl-placeholder p { margin: 0; font-size: 14px; }
        .device-label { text-align: center; color: #666; font-size: 12px; margin-top: 15px; letter-spacing: 2px; text-transform: uppercase; }
        .loading-overlay { position: absolute; top: 0; left: 0; right: 0; bottom: 0; background: rgba(255,255,255,0.9); display: none; align-items: center; justify-content: center; flex-direction: column; }
        .loading-overlay.active { display: flex; }
        .spinner { width: 40px; height: 40px; border: 4px solid #e0e0e0; border-top-color: #667eea; border-radius: 50%; animation: spin 1s linear infinite; }
        @keyframes spin { to { transform: rotate(360deg); } }
        .loading-text { margin-top: 15px; color: #666; font-size: 14px; }

        .vb-frame { background: #2a2a2a; border-radius: 16px; padding: 18px; box-shadow: 0 10px 40px rgba(0,0,0,0.3); }
        .vb-board-scroll { overflow-x: auto; }
        .vb-grid { display: grid; grid-template-columns: repeat(22, 1fr); gap: 3px; min-width: 640px; background: #000; padding: 8px; border-radius: 6px; }
        .vb-cell { aspect-ratio: 3 / 4; background: #1c1c1c; color: #f5f5f0; display: flex; align-items: center; justify-content: center; font-family: 'Courier New', monospace; font-weight: 700; font-size: 15px; border-radius: 3px; border: 1px solid #050505; box-shadow: inset 0 -6px 8px -6px rgba(0,0,0,0.8); }
        .vb-placeholder { padding: 60px 20px; text-align: center; color: #888; }

        .status-bar { display: flex; justify-content: space-between; align-items: center; margin-top: 15px; padding: 10px 15px; background: white; border-radius: 8px; font-size: 13px; }
        .status-indicator { display: flex; align-items: center; gap: 8px; }
        .status-dot { width: 10px; height: 10px; border-radius: 50%; background: #ccc; }
        .status-dot.success { background: #4caf50; }
        .status-dot.error { background: #f44336; }
        .status-dot.loading { background: #ff9800; animation: pulse 1s infinite; }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
        .response-time { color: #999; }

        .info-section { background: white; border-radius: 12px; padding: 20px; margin-top: 20px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); }
        .info-section h3 { margin: 0 0 15px 0; font-size: 16px; color: #333; }
        .info-section .note { font-size: 12px; color: #999; margin-top: 14px; }
        .save-indicator { font-weight: 600; }
        .save-indicator.saving { color: #ff9800; }
        .save-indicator.saved { color: #2e7d32; }
        .save-indicator.error { color: #c0392b; }
        .endpoint-list { display: grid; gap: 10px; }
        .endpoint-item { display: flex; align-items: center; gap: 10px; padding: 10px; background: #f8f9fa; border-radius: 6px; }
        .endpoint-method { padding: 4px 8px; border-radius: 4px; font-size: 12px; font-weight: 600; background: #e3f2fd; color: #1976d2; }
        .endpoint-path { font-family: monospace; font-size: 14px; color: #333; }
        .endpoint-desc { color: #666; font-size: 13px; margin-left: auto; }
        .app-footer { text-align: center; color: rgba(255,255,255,0.85); font-size: 12px; margin-top: 22px; }
        .app-footer a { color: #fff; font-family: 'Monaco', 'Menlo', monospace; text-decoration: underline; }
        @media (max-width: 600px) { .form-row { flex-direction: column; } .form-group { min-width: 100%; } }
    </style>
</head>
<body>
    <div class="simulator-container">
        <div class="header">
            <h1>Ferry Status Simulator</h1>
            <p>Preview and push WA State Ferry status to TRMNL and Vestaboard</p>
        </div>

        <div class="tabs">
            <button class="tab active" data-tab="trmnl" onclick="showTab('trmnl')">TRMNL</button>
            <button class="tab" data-tab="vestaboard" onclick="showTab('vestaboard')">Vestaboard</button>
        </div>

        {% set routes = [
            ['', 'All Routes'],
            ['sea-bi', 'Seattle / Bainbridge Island'],
            ['sea-br', 'Seattle / Bremerton'],
            ['ed-king', 'Edmonds / Kingston'],
            ['muk-cl', 'Mukilteo / Clinton'],
            ['f-v-s', 'Fauntleroy / Vashon'],
            ['f-s', 'Fauntleroy / Southworth'],
            ['s-v', 'Southworth / Vashon'],
            ['pt-key', 'Port Townsend / Coupeville'],
            ['pd-tal', 'Pt. Defiance / Tahlequah'],
            ['ana-sj', 'Anacortes / San Juan Islands']
        ] %}

        <!-- ===================== TRMNL TAB ===================== -->
        <div class="tab-panel active" data-tab="trmnl">
            <div class="controls">
                <h2>TRMNL Configuration</h2>
                <p class="hint">TRMNL polls your server for JSON; this previews how the e-ink display renders.
                    Set up the polling plugin and find your device API key in your
                    <a href="https://usetrmnl.com/" target="_blank" rel="noopener">TRMNL dashboard &#8599;</a>.</p>
                <div class="form-row">
                    <div class="form-group">
                        <label>Site URL</label>
                        <input type="text" data-sync="site_url" placeholder="https://your-domain.com">
                    </div>
                    <div class="form-group">
                        <label>Route</label>
                        <select data-sync="route_id" onchange="refreshTrmnlDir()">
                            {% for r in routes %}<option value="{{ r[0] }}">{{ r[1] }}</option>{% endfor %}
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Direction</label>
                        <select id="trmnlDir" onchange="onTrmnlDir()"></select>
                    </div>
                </div>
                <div class="form-row" style="margin-top: 15px;">
                    <div class="form-group wide">
                        <label>WSDOT API Key
                            {% if wsdot_env_set %}<span class="badge">server key configured</span>{% endif %}
                            <a class="help-link" href="https://wsdot.wa.gov/traffic/api/" target="_blank" rel="noopener">get a key &#8599;</a>
                        </label>
                        <input type="password" data-sync="wsdot_key" placeholder="Leave blank to use the server's configured key" autocomplete="off">
                    </div>
                </div>
                <div class="form-row" style="margin-top: 15px;">
                    <button class="btn btn-primary" id="trmnlFetchBtn" onclick="fetchTrmnl()">Fetch Preview</button>
                    <button class="btn btn-secondary" onclick="clearTrmnl()">Clear</button>
                </div>
                <div class="webhook-url"><strong>Polling URL:</strong> <span id="trmnlUrlDisplay">Configure site URL above</span></div>
            </div>

            <div class="trmnl-frame">
                <div class="trmnl-bezel">
                    <div class="trmnl-screen" id="trmnlScreen">
                        <div class="trmnl-placeholder" id="trmnlPlaceholder">
                            <svg viewBox="0 0 24 24" fill="currentColor"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/></svg>
                            <h3>TRMNL Display Preview</h3>
                            <p>Click "Fetch Preview" to render the ferry status<br>as it would appear on a TRMNL e-ink device</p>
                        </div>
                        <iframe id="trmnlFrame" style="display: none;"></iframe>
                        <div class="loading-overlay" id="trmnlLoading"><div class="spinner"></div><div class="loading-text">Rendering preview...</div></div>
                    </div>
                </div>
                <div class="device-label">TRMNL E-Ink Display Simulator</div>
            </div>

            <div class="status-bar">
                <div class="status-indicator"><div class="status-dot" id="trmnlDot"></div><span id="trmnlStatus">Ready</span></div>
                <div class="response-time" id="trmnlTime"></div>
            </div>
        </div>

        <!-- ===================== VESTABOARD TAB ===================== -->
        <div class="tab-panel" data-tab="vestaboard">
            <div class="controls">
                <h2>Vestaboard Configuration</h2>
                <p class="hint">Each board has its own Read/Write key, model, route and direction. Add a board,
                    choose its route/direction, then preview or push. Enable the Read/Write API and copy the key from
                    <a href="https://web.vestaboard.com/" target="_blank" rel="noopener">web.vestaboard.com &#8599;</a>
                    (<a href="https://docs.vestaboard.com/docs/read-write-api/introduction" target="_blank" rel="noopener">docs</a>).</p>
                <div class="form-row">
                    <div class="form-group">
                        <label>WSDOT API Key
                            {% if wsdot_env_set %}<span class="badge">server key configured</span>{% endif %}
                            <a class="help-link" href="https://wsdot.wa.gov/traffic/api/" target="_blank" rel="noopener">get a key &#8599;</a>
                        </label>
                        <input type="password" data-sync="wsdot_key" placeholder="Leave blank to use the server's key" autocomplete="off">
                    </div>
                    <div class="form-group">
                        <label>Target Board</label>
                        <select id="vbBoardSelect" onchange="onBoardSelect()"></select>
                    </div>
                </div>

                <div class="board-editor" id="boardEditor" style="display: none;">
                    <h4 id="boardEditorTitle">Board</h4>
                    <div class="form-row">
                        <div class="form-group">
                            <label>Board Name</label>
                            <input type="text" id="beName" placeholder="e.g. Living Room">
                        </div>
                        <div class="form-group">
                            <label>Model</label>
                            <select id="beModel">
                                <option value="flagship">Vestaboard (Flagship)</option>
                                <option value="note">Vestaboard Note</option>
                            </select>
                        </div>
                    </div>
                    <div class="form-row" style="margin-top: 15px;">
                        <div class="form-group">
                            <label>Route</label>
                            <select id="beRoute" onchange="refreshBoardDir()">
                                {% for r in routes %}<option value="{{ r[0] }}">{{ r[1] }}</option>{% endfor %}
                            </select>
                        </div>
                        <div class="form-group">
                            <label>Direction</label>
                            <select id="beDir"></select>
                        </div>
                    </div>
                    <div class="form-row" style="margin-top: 15px;">
                        <div class="form-group">
                            <label>Read/Write Key
                                <a class="help-link" href="https://web.vestaboard.com/" target="_blank" rel="noopener">find your key &#8599;</a>
                            </label>
                            <input type="password" id="beKey" placeholder="This board's Read/Write key" autocomplete="off">
                        </div>
                        <div class="form-group">
                            <label>API URL (optional)</label>
                            <input type="text" id="beUrl" placeholder="https://rw.vestaboard.com/" autocomplete="off">
                        </div>
                    </div>
                    <div class="form-row" style="margin-top: 15px;">
                        <button class="btn btn-secondary" onclick="saveBoard()">Save Board</button>
                        <button class="btn btn-ghost" id="beDeleteBtn" onclick="deleteBoard()">Delete</button>
                    </div>
                </div>

                <div class="form-row" style="margin-top: 15px;">
                    <button class="btn btn-secondary" id="vbPreviewBtn" onclick="previewVesta()">Preview Grid</button>
                    <button class="btn btn-primary" id="vbPushBtn" onclick="pushVesta()">Push to Board</button>
                </div>
            </div>

            <div class="vb-frame">
                <div class="vb-board-scroll">
                    <div id="vbBoard"><div class="vb-placeholder">Click "Preview Grid" to render the split-flap layout</div></div>
                </div>
                <div class="device-label">Vestaboard 6 &times; 22 Split-Flap</div>
            </div>

            <div class="status-bar">
                <div class="status-indicator"><div class="status-dot" id="vbDot"></div><span id="vbStatus">Ready</span></div>
                <div class="response-time" id="vbTime"></div>
            </div>
        </div>

        <div class="info-section">
            <h3>Available Endpoints</h3>
            <div class="endpoint-list">
                <div class="endpoint-item"><span class="endpoint-method">GET</span><span class="endpoint-path">/api/trmnl</span><span class="endpoint-desc">TRMNL polling (JSON)</span></div>
                <div class="endpoint-item"><span class="endpoint-method">POST</span><span class="endpoint-path">/api/vestaboard</span><span class="endpoint-desc">Push to Vestaboard</span></div>
                <div class="endpoint-item"><span class="endpoint-method">GET</span><span class="endpoint-path">/api/settings</span><span class="endpoint-desc">Saved options</span></div>
                <div class="endpoint-item"><span class="endpoint-method">GET</span><span class="endpoint-path">/api/ferry-status</span><span class="endpoint-desc">Raw JSON API</span></div>
            </div>
            <p class="note">
                Options (including API keys) are saved on the <strong>server</strong> so they persist across
                restarts and devices &mdash; keep this server on your tailnet, not the public web.
                <span class="save-indicator" id="saveInd"></span>
                &nbsp;<a href="#" onclick="resetSettings(); return false;">Reset all saved settings</a>
            </p>
        </div>

        <div class="app-footer">
            FerryNotifier {{ app_version }}{% if git_sha %} &middot; <a href="{{ repo_url }}/commit/{{ git_sha }}" target="_blank" rel="noopener">{{ git_sha[:7] }}</a>{% endif %}
        </div>
    </div>

    <script>
        const VB_CODE_TO_CHAR = {{ vb_code_to_char|tojson }};
        const VB_COLOR = {63:'#ef4444',64:'#f97316',65:'#eab308',66:'#22c55e',67:'#3b82f6',68:'#8b5cf6',69:'#f5f5f0',70:'#111111',71:'#f5f5f0'};
        const VB_ENV_SET = {{ vestaboard_env_set|tojson }};
        const ROUTE_DIRECTIONS = {{ route_directions|tojson }};

        const SETTINGS_DEFAULT = { site_url: '', route_id: '', direction: '', wsdot_key: '', vestaboard: { selected: '', boards: [] } };
        let SETTINGS = JSON.parse(JSON.stringify(SETTINGS_DEFAULT));
        let editingNew = false;
        let saveTimer = null;

        function noTrailingSlash(s) { while (s.endsWith('/')) s = s.slice(0, -1); return s; }
        function siteBase() { return noTrailingSlash(SETTINGS.site_url || window.location.origin); }
        function val(id) { const e = document.getElementById(id); return e ? e.value.trim() : ''; }
        function slug(s) { return (s.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '')) || 'board'; }
        function boardById(id) { return SETTINGS.vestaboard.boards.filter(function (b) { return b.id === id; })[0] || null; }

        function normalizeSettings(s) {
            s = Object.assign({}, SETTINGS_DEFAULT, s || {});
            if (!s.vestaboard) s.vestaboard = { selected: '', boards: [] };
            if (!Array.isArray(s.vestaboard.boards)) s.vestaboard.boards = [];
            return s;
        }

        // Fill a <select> with the directions for a route, keeping `chosen` if valid.
        function populateDirSelect(sel, route, chosen) {
            const opts = ROUTE_DIRECTIONS[route] || [];
            sel.innerHTML = '';
            if (!opts.length) {
                const e = document.createElement('option'); e.value = ''; e.textContent = '(all directions)'; sel.appendChild(e);
                return '';
            }
            let matched = '';
            opts.forEach(function (o) {
                const e = document.createElement('option'); e.value = o.value; e.textContent = o.label;
                if (o.value === chosen) { e.selected = true; matched = chosen; }
                sel.appendChild(e);
            });
            if (!matched) sel.value = opts[0].value;
            return sel.value;
        }

        // ---- persistence (server) ----
        async function loadSettings() {
            try { const r = await fetch('/api/settings'); if (r.ok) SETTINGS = normalizeSettings(await r.json()); } catch (e) {}
            applySettingsToFields();
            SETTINGS.direction = populateDirSelect(document.getElementById('trmnlDir'), SETTINGS.route_id, SETTINGS.direction);
            renderBoardOptions();
            updateTrmnlUrl();
        }
        function applySettingsToFields() {
            document.querySelectorAll('[data-sync]').forEach(function (el) { el.value = SETTINGS[el.dataset.sync] || ''; });
            document.querySelectorAll('[data-sync="site_url"]').forEach(function (el) { if (!el.value) el.value = window.location.origin; });
        }
        function setSaveIndicator(state) {
            const el = document.getElementById('saveInd');
            const labels = { saving: 'Saving…', saved: 'Saved ✓', error: 'Save failed' };
            el.className = 'save-indicator ' + (state || ''); el.textContent = labels[state] || '';
        }
        async function saveSettingsNow() {
            setSaveIndicator('saving');
            try {
                const r = await fetch('/api/settings', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(SETTINGS) });
                if (r.ok) { SETTINGS = normalizeSettings(await r.json()); setSaveIndicator('saved'); return true; }
                setSaveIndicator('error'); return false;
            } catch (e) { setSaveIndicator('error'); return false; }
        }
        function saveSettingsDebounced() { clearTimeout(saveTimer); setSaveIndicator('saving'); saveTimer = setTimeout(saveSettingsNow, 500); }
        function bindSync() {
            document.querySelectorAll('[data-sync]').forEach(function (el) {
                const handler = function () {
                    const k = el.dataset.sync;
                    SETTINGS[k] = el.value;
                    document.querySelectorAll('[data-sync="' + k + '"]').forEach(function (o) { if (o !== el) o.value = el.value; });
                    if (k === 'site_url' || k === 'route_id') updateTrmnlUrl();
                    saveSettingsDebounced();
                };
                el.addEventListener('input', handler);
                el.addEventListener('change', handler);
            });
        }
        async function resetSettings() {
            SETTINGS = JSON.parse(JSON.stringify(SETTINGS_DEFAULT));
            await saveSettingsNow();
            applySettingsToFields();
            SETTINGS.direction = populateDirSelect(document.getElementById('trmnlDir'), SETTINGS.route_id, SETTINGS.direction);
            renderBoardOptions(); updateTrmnlUrl();
        }

        function showTab(name) {
            document.querySelectorAll('.tab').forEach(function (t) { t.classList.toggle('active', t.dataset.tab === name); });
            document.querySelectorAll('.tab-panel').forEach(function (p) { p.classList.toggle('active', p.dataset.tab === name); });
        }
        function setStatus(dotId, textId, timeId, state, text, ms) {
            document.getElementById(dotId).className = 'status-dot ' + (state || '');
            document.getElementById(textId).textContent = text;
            document.getElementById(timeId).textContent = (ms != null) ? ('Response time: ' + ms + 'ms') : '';
        }

        // ---- TRMNL direction ----
        function refreshTrmnlDir() {
            SETTINGS.route_id = val('route_id') || document.querySelector('[data-sync="route_id"]').value;
            SETTINGS.direction = populateDirSelect(document.getElementById('trmnlDir'), SETTINGS.route_id, '');
            updateTrmnlUrl(); saveSettingsDebounced();
        }
        function onTrmnlDir() { SETTINGS.direction = document.getElementById('trmnlDir').value; updateTrmnlUrl(); saveSettingsDebounced(); }
        function updateTrmnlUrl() {
            let url = siteBase() + '/api/trmnl';
            const q = [];
            if (SETTINGS.route_id) q.push('route_id=' + encodeURIComponent(SETTINGS.route_id));
            if (SETTINGS.direction) q.push('direction=' + encodeURIComponent(SETTINGS.direction));
            if (q.length) url += '?' + q.join('&');
            document.getElementById('trmnlUrlDisplay').textContent = url;
        }

        // ---- Vestaboard board management ----
        function renderBoardOptions() {
            const sel = document.getElementById('vbBoardSelect');
            const cur = SETTINGS.vestaboard.selected || '';
            const opts = [];
            if (VB_ENV_SET) opts.push({ v: '', label: 'Server default (.env key)' });
            SETTINGS.vestaboard.boards.forEach(function (b) { opts.push({ v: b.id, label: b.name + ' — ' + (b.model === 'note' ? 'Note' : 'Flagship') }); });
            opts.push({ v: '__add__', label: '＋ Add new board…' });
            sel.innerHTML = '';
            opts.forEach(function (o) { const e = document.createElement('option'); e.value = o.v; e.textContent = o.label; if (o.v === cur) e.selected = true; sel.appendChild(e); });
            const b = boardById(cur);
            if (b) showEditor(b); else hideEditor();
        }
        function refreshBoardDir() { populateDirSelect(document.getElementById('beDir'), val('beRoute'), ''); }
        function showEditor(b) {
            editingNew = false;
            document.getElementById('boardEditorTitle').textContent = 'Edit board';
            document.getElementById('beName').value = b.name || '';
            document.getElementById('beModel').value = (b.model === 'note') ? 'note' : 'flagship';
            document.getElementById('beRoute').value = b.route || '';
            populateDirSelect(document.getElementById('beDir'), b.route || '', b.direction || '');
            document.getElementById('beKey').value = b.key || '';
            document.getElementById('beUrl').value = b.url || '';
            document.getElementById('beDeleteBtn').style.display = '';
            document.getElementById('boardEditor').style.display = '';
        }
        function showEditorBlank() {
            editingNew = true;
            document.getElementById('boardEditorTitle').textContent = 'Add board';
            document.getElementById('beName').value = '';
            document.getElementById('beModel').value = 'flagship';
            document.getElementById('beRoute').value = '';
            populateDirSelect(document.getElementById('beDir'), '', '');
            document.getElementById('beKey').value = '';
            document.getElementById('beUrl').value = '';
            document.getElementById('beDeleteBtn').style.display = 'none';
            document.getElementById('boardEditor').style.display = '';
        }
        function hideEditor() { document.getElementById('boardEditor').style.display = 'none'; }
        function currentBoardConfig() {
            // Values from the open editor (covers unsaved edits), else the selected board.
            if (document.getElementById('boardEditor').style.display !== 'none') {
                return { route: val('beRoute'), direction: val('beDir'), key: val('beKey'), url: val('beUrl'), model: val('beModel') };
            }
            const b = boardById(SETTINGS.vestaboard.selected);
            return b ? { route: b.route, direction: b.direction, key: b.key, url: b.url, model: b.model } : { route: '', direction: '', key: '', url: '', model: 'flagship' };
        }
        function onBoardSelect() {
            const v = document.getElementById('vbBoardSelect').value;
            if (v === '__add__') { showEditorBlank(); return; }
            SETTINGS.vestaboard.selected = v;
            const b = boardById(v);
            if (b) showEditor(b); else hideEditor();
            saveSettingsNow();
        }
        async function saveBoard() {
            const name = val('beName') || 'Board';
            const fields = { name: name, model: val('beModel') || 'flagship', route: val('beRoute'), direction: val('beDir'), key: val('beKey'), url: val('beUrl') };
            if (editingNew) {
                const id = slug(name) + '-' + Date.now().toString(36).slice(-4);
                SETTINGS.vestaboard.boards.push(Object.assign({ id: id }, fields));
                SETTINGS.vestaboard.selected = id;
            } else {
                const b = boardById(SETTINGS.vestaboard.selected);
                if (b) Object.assign(b, fields);
            }
            await saveSettingsNow();
            renderBoardOptions();
            setStatus('vbDot', 'vbStatus', 'vbTime', 'success', 'Board saved');
        }
        async function deleteBoard() {
            const id = SETTINGS.vestaboard.selected;
            SETTINGS.vestaboard.boards = SETTINGS.vestaboard.boards.filter(function (b) { return b.id !== id; });
            SETTINGS.vestaboard.selected = VB_ENV_SET ? '' : (SETTINGS.vestaboard.boards[0] ? SETTINGS.vestaboard.boards[0].id : '');
            await saveSettingsNow();
            renderBoardOptions();
            setStatus('vbDot', 'vbStatus', 'vbTime', '', 'Board deleted');
        }

        // ---- TRMNL preview ----
        async function fetchTrmnl() {
            const btn = document.getElementById('trmnlFetchBtn'), loading = document.getElementById('trmnlLoading');
            const placeholder = document.getElementById('trmnlPlaceholder'), frame = document.getElementById('trmnlFrame');
            const body = { route_id: SETTINGS.route_id, direction: SETTINGS.direction, wsdot_key: SETTINGS.wsdot_key };
            btn.disabled = true; loading.classList.add('active'); placeholder.style.display = 'none'; frame.style.display = 'none';
            setStatus('trmnlDot', 'trmnlStatus', 'trmnlTime', 'loading', 'Rendering preview...');
            const start = performance.now();
            try {
                const resp = await fetch(siteBase() + '/api/trmnl/preview', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
                const ms = Math.round(performance.now() - start);
                if (!resp.ok) throw new Error('HTTP ' + resp.status + ': ' + resp.statusText);
                const html = await resp.text();
                frame.style.display = 'block'; frame.srcdoc = html;
                setStatus('trmnlDot', 'trmnlStatus', 'trmnlTime', 'success', 'Preview rendered', ms);
            } catch (err) {
                placeholder.style.display = 'flex';
                setStatus('trmnlDot', 'trmnlStatus', 'trmnlTime', 'error', 'Error: ' + err.message);
            } finally { btn.disabled = false; loading.classList.remove('active'); }
        }
        function clearTrmnl() {
            document.getElementById('trmnlPlaceholder').style.display = 'flex';
            const frame = document.getElementById('trmnlFrame'); frame.style.display = 'none'; frame.srcdoc = '';
            setStatus('trmnlDot', 'trmnlStatus', 'trmnlTime', '', 'Ready');
        }

        // ---- Vestaboard preview/push ----
        function renderVestaGrid(chars) {
            const board = document.getElementById('vbBoard'); board.innerHTML = '';
            const grid = document.createElement('div'); grid.className = 'vb-grid';
            chars.forEach(function (row) { row.forEach(function (code) {
                const cell = document.createElement('div'); cell.className = 'vb-cell';
                if (VB_COLOR[code] !== undefined) { cell.style.background = VB_COLOR[code]; }
                else { const ch = VB_CODE_TO_CHAR[code]; cell.textContent = (ch && ch !== ' ') ? ch : ''; }
                grid.appendChild(cell);
            }); });
            board.appendChild(grid);
        }
        async function vestaRequest(send) {
            const btn = document.getElementById(send ? 'vbPushBtn' : 'vbPreviewBtn');
            const cfg = currentBoardConfig();
            const body = { route_id: cfg.route, direction: cfg.direction, wsdot_key: SETTINGS.wsdot_key };
            if (send) {
                body.board_id = SETTINGS.vestaboard.selected || '';
                if (cfg.key) { body.vestaboard_key = cfg.key; body.vestaboard_url = cfg.url; }
            }
            const url = siteBase() + '/api/vestaboard' + (send ? '' : '?preview=true');
            btn.disabled = true;
            setStatus('vbDot', 'vbStatus', 'vbTime', 'loading', send ? 'Pushing to board...' : 'Building preview...');
            const start = performance.now();
            try {
                const resp = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
                const ms = Math.round(performance.now() - start);
                const data = await resp.json();
                if (data.characters) renderVestaGrid(data.characters);
                if (send) {
                    if (data.sent) setStatus('vbDot', 'vbStatus', 'vbTime', 'success', 'Pushed to Vestaboard', ms);
                    else setStatus('vbDot', 'vbStatus', 'vbTime', 'error', data.error || 'Push failed', ms);
                } else { setStatus('vbDot', 'vbStatus', 'vbTime', 'success', 'Preview rendered (not sent)', ms); }
            } catch (err) { setStatus('vbDot', 'vbStatus', 'vbTime', 'error', 'Error: ' + err.message); }
            finally { btn.disabled = false; }
        }
        function previewVesta() { vestaRequest(false); }
        function pushVesta() {
            const b = boardById(SETTINGS.vestaboard.selected);
            const target = b ? b.name : (VB_ENV_SET ? 'the server default board' : null);
            if (!target) { setStatus('vbDot', 'vbStatus', 'vbTime', 'error', 'Add and select a board first'); return; }
            if (!confirm('Push live ferry status to ' + target + '? This changes the physical display.')) return;
            vestaRequest(true);
        }

        // ---- init ----
        bindSync();
        loadSettings();
    </script>
</body>
</html>
"""


# Route to terminals mapping
ROUTE_TERMINALS = {
    "sea-bi": ["Seattle", "Bainbridge Island"],
    "sea-br": ["Seattle", "Bremerton"],
    "ed-king": ["Edmonds", "Kingston"],
    "muk-cl": ["Mukilteo", "Clinton"],
    "f-v-s": ["Fauntleroy", "Vashon Island"],
    "f-s": ["Fauntleroy", "Southworth"],
    "s-v": ["Southworth", "Vashon Island"],
    "pt-key": ["Port Townsend", "Coupeville"],
    "pd-tal": ["Point Defiance", "Tahlequah"],
    "ana-sj": ["Anacortes", "Friday Harbor", "Orcas Island", "Lopez Island", "Shaw Island"],
}

ROUTE_NAMES = {
    "sea-bi": "Seattle / Bainbridge Island",
    "sea-br": "Seattle / Bremerton",
    "ed-king": "Edmonds / Kingston",
    "muk-cl": "Mukilteo / Clinton",
    "f-v-s": "Fauntleroy / Vashon",
    "f-s": "Fauntleroy / Southworth",
    "s-v": "Southworth / Vashon",
    "pt-key": "Port Townsend / Coupeville",
    "pd-tal": "Pt. Defiance / Tahlequah",
    "ana-sj": "Anacortes / San Juan Islands",
}

# WSDOT numeric route IDs (from schedule/rest/routes), used to match alerts.
ROUTE_WSDOT_IDS = {
    "sea-bi": 5, "sea-br": 3, "ed-king": 6, "muk-cl": 7, "f-v-s": 14,
    "f-s": 13, "s-v": 15, "pt-key": 8, "pd-tal": 1, "ana-sj": 9,
}

# Short terminal labels for the Vestaboard's narrow rows.
TERMINAL_SHORT = {
    "Seattle": "SEA", "Bainbridge Island": "BAIN", "Bremerton": "BREM",
    "Edmonds": "EDM", "Kingston": "KING", "Mukilteo": "MUK", "Clinton": "CLIN",
    "Fauntleroy": "FAUN", "Vashon Island": "VASH", "Southworth": "SOUTH",
    "Port Townsend": "PTWN", "Coupeville": "COUP", "Point Defiance": "PDEF",
    "Tahlequah": "TAH", "Anacortes": "ANA", "Friday Harbor": "FRI",
    "Orcas Island": "ORC", "Lopez Island": "LOP", "Shaw Island": "SHAW",
}


def _terminal_short(name: str) -> str:
    """Short uppercase label for a terminal, for narrow displays."""
    return TERMINAL_SHORT.get(name, (name or "")[:4].upper())


def route_direction_options(route: Optional[str]) -> list:
    """
    Return selectable directions for a route as a list of dicts:
    {value, label, from, to}. ``value`` is the departing terminal name.
    """
    terminals = ROUTE_TERMINALS.get(route or "", [])
    options = []
    if len(terminals) == 2:
        a, b = terminals
        options.append({"value": a, "label": f"{a} → {b}", "from": a, "to": b})
        options.append({"value": b, "label": f"{b} → {a}", "from": b, "to": a})
    else:
        # Multi-terminal (e.g. San Juans): pick the departing terminal only.
        for t in terminals:
            options.append({"value": t, "label": f"Depart {t}", "from": t, "to": None})
    return options


def compute_direction_status(data: Dict[str, Any], route: Optional[str],
                             direction: Optional[str]) -> Optional[Dict[str, Any]]:
    """
    Build the next-departure / spaces / alert summary for a route + direction.

    ``direction`` is the departing terminal name (see route_direction_options).
    Returns None if route/direction can't be resolved.
    """
    opts = route_direction_options(route)
    if not opts:
        return None
    chosen = next((o for o in opts if o["value"] == direction), opts[0])
    from_t, to_t = chosen["from"], chosen["to"]

    now = datetime.now()
    departures = data.get("terminal_departures", {}).get(from_t, [])
    # Next future departure toward the arrival terminal (or any, if to_t is None).
    upcoming = [
        d for d in departures
        if d.get("time") and d["time"] >= now and (to_t is None or d.get("arrival") == to_t)
    ]
    upcoming.sort(key=lambda d: d["time"])
    nxt = upcoming[0] if upcoming else None

    # Spaces: from the chosen departure, else the terminal's headline space count.
    if nxt is not None:
        spaces = nxt.get("drive_up")
    else:
        spaces = data.get("terminal_spaces", {}).get(from_t, {}).get("drive_up")

    alerts = data.get("alerts", [])
    dep_time = nxt["time"] if nxt else None
    return {
        "route_id": route,
        "from": from_t,
        "to": to_t,
        "from_short": _terminal_short(from_t),
        "to_short": _terminal_short(to_t) if to_t else "",
        "departure_time": dep_time.isoformat() if dep_time else None,
        "time_str": _fmt_time(dep_time),
        "vessel": nxt.get("vessel") if nxt else None,
        "spaces": spaces,
        "delay": route_alert(route, alerts, delays_only=True),
        "alert": route_alert(route, alerts),
    }


# Keywords that mark an alert as a sailing delay/disruption (vs. informational).
DELAY_KEYWORDS = (
    "delay", "cancel", "reduced", "suspend", "no service", "not sailing",
    "no sailings", "standby", "behind schedule", "one boat", "vessel out of service",
)
# If any of these appear, it's infrastructure/info, not a sailing delay,
# even when it says "out of service" (e.g. an elevator).
NON_DELAY_KEYWORDS = (
    "elevator", "restroom", "ada ", "wifi", "wi-fi", "website", "galley",
    "food", "app ", "ticket", "reservation", "fare", "survey", "parking lot",
)


def _is_delay_alert(title: str) -> bool:
    """True if an alert title describes a sailing delay/disruption rather than info."""
    t = (title or "").lower()
    if any(kw in t for kw in NON_DELAY_KEYWORDS):
        return False
    if "out of service" in t and ("vessel" in t or "boat" in t or "expect delays" in t):
        return True
    return any(kw in t for kw in DELAY_KEYWORDS)


def _alert_affects_route(alert: Dict[str, Any], route: Optional[str]) -> bool:
    wsdot_id = ROUTE_WSDOT_IDS.get(route or "")
    return bool(alert.get("all_routes") or (wsdot_id and wsdot_id in alert.get("route_ids", [])))


def route_alert(route: Optional[str], alerts: list, delays_only: bool = False) -> Optional[str]:
    """Return the title of the first (delay) alert affecting this route, else None."""
    for alert in alerts or []:
        if delays_only and not alert.get("is_delay"):
            continue
        if _alert_affects_route(alert, route):
            return alert.get("title") or "Service alert"
    return None


def parse_wsdot_date(date_str: Optional[str]) -> Optional[datetime]:
    """Parse WSDOT API date format like /Date(1765655700000-0800)/"""
    if not date_str or date_str == "None":
        return None
    try:
        # Extract timestamp from /Date(1234567890000-0800)/
        match = re.search(r'/Date\((\d+)([+-]\d{4})?\)/', str(date_str))
        if match:
            timestamp_ms = int(match.group(1))
            return datetime.fromtimestamp(timestamp_ms / 1000)
    except Exception:
        pass
    return None


def fetch_ferry_status(route_id: Optional[str] = None, api_key: Optional[str] = None) -> Dict[str, Any]:
    """
    Fetch ferry status from WSDOT API.

    Args:
        route_id: Optional specific route ID to fetch
        api_key: Optional WSDOT API key override (falls back to WSDOT_API_KEY)

    Returns:
        Dictionary containing ferry status data
    """
    effective_key = api_key or WSDOT_API_KEY
    if not effective_key:
        logger.error("WSDOT_API_KEY not configured")
        return {"error": "API key not configured"}

    route = route_id or FERRY_ROUTE_ID
    params = {"apiaccesscode": effective_key}

    try:
        # Fetch vessel locations
        vessels_url = f"{WSDOT_API_BASE_URL}/vessels/rest/vessellocations"

        logger.info(f"Fetching vessel locations from WSDOT API for route: {route or 'all'}")
        response = requests.get(vessels_url, params=params, timeout=10)
        response.raise_for_status()

        vessels_data = response.json()

        # Filter vessels by route if specified
        terminals = []
        if route and route in ROUTE_TERMINALS:
            terminals = ROUTE_TERMINALS[route]
            filtered_vessels = []
            for vessel in vessels_data:
                dep_terminal = vessel.get("DepartingTerminalName", "")
                arr_terminal = vessel.get("ArrivingTerminalName", "")
                # Vessel is on this route if BOTH terminals are in the route's terminal list
                if dep_terminal in terminals and arr_terminal in terminals:
                    filtered_vessels.append(vessel)
            vessels_data = filtered_vessels

        # Fetch terminal space/parking data (headline spaces + full departure list)
        terminal_spaces = {}
        terminal_departures = {}
        try:
            space_url = f"{WSDOT_API_BASE_URL.replace('/ferries/api', '/ferries/api/terminals')}/rest/terminalsailingspace"
            space_response = requests.get(space_url, params=params, timeout=10)
            space_response.raise_for_status()
            space_data = space_response.json()

            for terminal in space_data:
                terminal_name = terminal.get("TerminalName", "")
                if terminals and terminal_name not in terminals:
                    continue
                departing_spaces = terminal.get("DepartingSpaces", [])

                # Headline space count (next departure) for backward compatibility.
                if departing_spaces:
                    space_info = departing_spaces[0].get("SpaceForArrivalTerminals", [])
                    if space_info:
                        spaces = space_info[0]
                        terminal_spaces[terminal_name] = {
                            "drive_up": spaces.get("DriveUpSpaceCount", 0),
                            "max": spaces.get("MaxSpaceCount", 0),
                            "color": spaces.get("DriveUpSpaceHexColor", "#888888"),
                        }

                # Full list of upcoming departures, one row per arrival terminal.
                deps = []
                for dep in departing_spaces:
                    dep_time = parse_wsdot_date(dep.get("Departure"))
                    for arr in dep.get("SpaceForArrivalTerminals", []):
                        deps.append({
                            "time": dep_time,
                            "arrival": arr.get("TerminalName", ""),
                            "vessel": arr.get("VesselName") or dep.get("VesselName"),
                            "drive_up": arr.get("DriveUpSpaceCount"),
                            "max": arr.get("MaxSpaceCount"),
                        })
                if deps:
                    terminal_departures[terminal_name] = deps
        except Exception as e:
            logger.warning(f"Could not fetch terminal space data: {e}")

        # Fetch service alerts (normalized to {title, route_ids, all_routes})
        alerts = []
        try:
            alerts_url = f"{WSDOT_API_BASE_URL}/schedule/rest/alerts"
            alerts_response = requests.get(alerts_url, params=params, timeout=10)
            alerts_response.raise_for_status()
            for alert in alerts_response.json():
                title = alert.get("AlertFullTitle", "")
                alerts.append({
                    "title": title,
                    "route_ids": alert.get("AffectedRouteIDs") or [],
                    "all_routes": bool(alert.get("AllRoutesFlag")),
                    "type": alert.get("AlertType", ""),
                    "is_delay": _is_delay_alert(title),
                })
        except Exception as e:
            logger.warning(f"Could not fetch alerts: {e}")

        return {
            "vessels": vessels_data,
            "route_id": route,
            "route_name": ROUTE_NAMES.get(route, "Washington State Ferries") if route else "All Routes",
            "terminal_spaces": terminal_spaces,
            "terminal_departures": terminal_departures,
            "alerts": alerts,
            "timestamp": datetime.now().isoformat()
        }

    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching ferry data: {e}")
        return {"error": f"Failed to fetch ferry data: {str(e)}"}
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return {"error": f"Unexpected error: {str(e)}"}


def format_ferry_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format ferry data for display on Trmnl.

    Args:
        data: Raw ferry data from API

    Returns:
        Formatted data dictionary for template rendering
    """
    if "error" in data:
        return {"error": data["error"]}

    formatted = {
        "route_name": data.get("route_name", "Washington State Ferries"),
        "route_description": "",
        "vessels": [],
        "departures": [],
        "terminal_spaces": data.get("terminal_spaces", {}),
        "update_time": datetime.now().strftime("%I:%M %p").lstrip("0")
    }

    # Process vessel data
    vessels = data.get("vessels", [])
    if isinstance(vessels, list):
        for vessel in vessels[:MAX_VESSELS_DISPLAY]:
            vessel_name = vessel.get("VesselName", "Unknown")
            in_service = vessel.get("InService", False)
            at_dock = vessel.get("AtDock", False)
            dep_terminal = vessel.get("DepartingTerminalName", "")
            arr_terminal = vessel.get("ArrivingTerminalName", "")
            speed = vessel.get("Speed", 0)

            # Build status text
            if not in_service:
                status = "Out of service"
                location = ""
            elif at_dock:
                status = "Docked"
                location = f"At {dep_terminal}"
                # Add scheduled departure if available
                sched_dep = parse_wsdot_date(vessel.get("ScheduledDeparture"))
                if sched_dep:
                    location += f", departs {sched_dep.strftime('%I:%M %p').lstrip('0')}"
            else:
                status = "Sailing"
                location = f"{dep_terminal} → {arr_terminal}"
                # Add ETA if available
                eta = parse_wsdot_date(vessel.get("Eta"))
                if eta:
                    location += f" (ETA {eta.strftime('%I:%M %p').lstrip('0')})"
                elif speed:
                    location += f" ({speed:.1f} kts)"

            vessel_info = {
                "name": vessel_name,
                "status": status,
                "location": location,
                "eta": ""
            }
            formatted["vessels"].append(vessel_info)

    # If no vessels found, add a message
    if not formatted["vessels"]:
        formatted["vessels"].append({
            "name": "No vessels",
            "status": "No active vessels found for this route",
            "location": "",
            "eta": ""
        })

    return formatted


# --- Vestaboard support ---------------------------------------------------

# Vestaboard character code map (blank, A-Z, digits, and common punctuation).
# See https://docs.vestaboard.com/docs/characterCodes
VB_CHAR_MAP: Dict[str, int] = {' ': 0}
for _i, _c in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ", start=1):
    VB_CHAR_MAP[_c] = _i
for _i, _c in enumerate("123456789", start=27):
    VB_CHAR_MAP[_c] = _i
VB_CHAR_MAP['0'] = 36
VB_CHAR_MAP.update({
    '!': 37, '@': 38, '#': 39, '$': 40, '(': 41, ')': 42, '-': 44, '+': 46,
    '&': 47, '=': 48, ';': 49, ':': 50, "'": 52, '"': 53, '%': 54, ',': 55,
    '.': 56, '/': 59, '?': 60, '°': 62,
})

# Short status tokens so a vessel line fits within 22 columns.
VB_STATUS_SHORT = {
    "Sailing": "SAIL",
    "Docked": "DOCK",
    "Out of service": "OOS",
}

# Short route labels (<= 22 chars) for the Vestaboard header row.
VB_ROUTE_LABEL = {
    "sea-bi": "SEATTLE-BAINBRIDGE", "sea-br": "SEATTLE-BREMERTON",
    "ed-king": "EDMONDS-KINGSTON", "muk-cl": "MUKILTEO-CLINTON",
    "f-v-s": "FAUNTLEROY-VASHON", "f-s": "FAUNTLEROY-SOUTHWRTH",
    "s-v": "SOUTHWORTH-VASHON", "pt-key": "PT TOWNSEND-COUPEVL",
    "pd-tal": "PT DEFIANCE-TAHLEQAH", "ana-sj": "ANACORTES-SAN JUANS",
}


def _vb_char(ch: str) -> int:
    """Map a single character to its Vestaboard code (unknown -> blank)."""
    return VB_CHAR_MAP.get(ch.upper(), 0)


def _vb_row(left: str = "", right: str = "", center: Optional[str] = None) -> list:
    """
    Build a single 22-cell Vestaboard row.

    If ``center`` is given, that text is centered. Otherwise ``left`` is placed
    left-aligned and ``right`` right-aligned on the same row, with ``left``
    truncated first if the two would collide.
    """
    if center is not None:
        codes = [_vb_char(c) for c in str(center)[:VB_COLS]]
        pad = VB_COLS - len(codes)
        left_pad = pad // 2
        return [0] * left_pad + codes + [0] * (pad - left_pad)

    left = str(left)
    right = str(right)
    # Reserve at least one blank between left and right tokens.
    max_left = VB_COLS - len(right) - (1 if right else 0)
    if len(left) > max_left:
        left = left[:max(max_left, 0)]

    left_codes = [_vb_char(c) for c in left]
    right_codes = [_vb_char(c) for c in right]
    middle = VB_COLS - len(left_codes) - len(right_codes)
    return left_codes + [0] * middle + right_codes


def _fmt_time(t: Optional[datetime]) -> str:
    """Format a time like '11:30 AM' (no leading zero)."""
    return t.strftime("%I:%M %p").lstrip("0") if t else "--"


def _wrap_center_rows(text: str, max_rows: int) -> list:
    """Word-wrap text into up to max_rows centered Vestaboard rows."""
    words = str(text).upper().split()
    lines, line = [], ""
    for word in words:
        candidate = f"{line} {word}".strip()
        if len(candidate) > VB_COLS:
            if line:
                lines.append(line)
            line = word[:VB_COLS]
            if len(lines) >= max_rows:
                line = ""
                break
        else:
            line = candidate
    if line and len(lines) < max_rows:
        lines.append(line)
    return [_vb_row(center=l) for l in lines[:max_rows]]


def format_vestaboard_message(data: Dict[str, Any],
                              status: Optional[Dict[str, Any]] = None) -> list:
    """
    Lay ferry data out onto a 6-row x 22-column Vestaboard grid.

    Args:
        data: Output of :func:`format_ferry_data`.
        status: Optional output of :func:`compute_direction_status`. When given,
            renders the focused "next departure / spaces / delay" layout for the
            chosen route + direction. Otherwise falls back to a vessel list.

    Returns:
        A list of 6 rows, each a list of 22 Vestaboard character codes.
    """
    rows = []

    if "error" in data:
        rows.append(_vb_row(center="FERRY ERROR"))
        rows += _wrap_center_rows(data["error"], VB_ROWS - 1)
    elif status is not None:
        # Focused layout: route, direction + next departure, spaces, delay.
        header = VB_ROUTE_LABEL.get(status.get("route_id", ""), data.get("route_name", "FERRIES"))
        rows.append(_vb_row(center=header))

        # The Vestaboard has no ">" glyph, so use "TO" for the direction.
        when = status.get("time_str", "--")
        if status.get("to_short"):
            heading = f"{status['from_short']} TO {status['to_short']} {when}"
        else:
            heading = f"DEP {status['from_short']} {when}"
        rows.append(_vb_row(center=heading))

        sp = status.get("spaces")
        rows.append(_vb_row(center=f"SPACES: {sp if sp is not None else 'N/A'}"))

        delay = status.get("delay")
        if delay:
            rows.append(_vb_row(center="DELAYS:"))
            rows += _wrap_center_rows(delay, VB_ROWS - len(rows))
        else:
            rows.append(_vb_row(center="NO DELAYS"))
    else:
        rows.append(_vb_row(center=data.get("route_name", "FERRIES")))

        vessels = [v for v in data.get("vessels", []) if v.get("name") != "No vessels"]
        if not vessels:
            rows.append(_vb_row(center="NO ACTIVE VESSELS"))
        else:
            for vessel in vessels[:VB_ROWS - 2]:
                vstatus = vessel.get("status", "")
                short = VB_STATUS_SHORT.get(vstatus, vstatus[:4])
                rows.append(_vb_row(left=vessel.get("name", ""), right=short))

        spaces = data.get("terminal_spaces", {})
        if spaces:
            parts = [f"{term[:3]} {info.get('drive_up', 0)}" for term, info in spaces.items()]
            rows.append(_vb_row(center="  ".join(parts)))
        else:
            rows.append(_vb_row(right=data.get("update_time", "")))

    # Pad or truncate to exactly VB_ROWS rows.
    while len(rows) < VB_ROWS:
        rows.append([0] * VB_COLS)
    return rows[:VB_ROWS]


def send_to_vestaboard(characters: list, key: Optional[str] = None,
                       url: Optional[str] = None) -> Dict[str, Any]:
    """
    Push a 6x22 character grid to a Vestaboard via the Read/Write API.

    Args:
        characters: 6x22 grid of Vestaboard character codes.
        key: Optional Read/Write key override (falls back to VESTABOARD_RW_KEY).
        url: Optional endpoint override (falls back to VESTABOARD_RW_URL).

    Returns a result dict with either ``status`` or ``error``.
    """
    rw_key = key or VESTABOARD_RW_KEY
    rw_url = url or VESTABOARD_RW_URL
    if not rw_key:
        return {"error": "Vestaboard Read/Write key not configured"}

    try:
        response = requests.post(
            rw_url,
            headers={
                "X-Vestaboard-Read-Write-Key": rw_key,
                "Content-Type": "application/json",
            },
            json={"characters": characters},
            timeout=10,
        )
        response.raise_for_status()
        body = response.json() if response.content else {}
        return {"status": "sent", "response": body}
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to send to Vestaboard: {e}")
        return {"error": f"Failed to send to Vestaboard: {str(e)}"}


def _param(name: str, default: str = '') -> str:
    """
    Read a request parameter from the JSON body, then query string / form.

    Lets the simulator (and API clients) pass optional overrides such as
    ``wsdot_key`` or ``vestaboard_key`` on a per-request basis.
    """
    body = request.get_json(silent=True) if request.is_json else None
    if isinstance(body, dict) and body.get(name) not in (None, ''):
        return str(body[name])
    val = request.values.get(name)
    return val if val not in (None, '') else default


def get_site_url() -> str:
    """Get the site URL, with fallback to constructing from request."""
    if SITE_URL:
        return SITE_URL.rstrip('/')
    # Fallback: construct from Flask config
    return f"http://{FLASK_HOST}:{FLASK_PORT}" if FLASK_HOST != '0.0.0.0' else ''


def _slugify(text: str) -> str:
    """Turn a board name into a stable id fragment."""
    slug = re.sub(r'[^a-z0-9]+', '-', str(text).lower()).strip('-')
    return slug or 'board'


def _normalize_settings(data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Coerce arbitrary input into the canonical settings shape."""
    data = data or {}
    vb = data.get('vestaboard') or {}
    boards = []
    seen_ids = set()
    for entry in (vb.get('boards') or []):
        if not isinstance(entry, dict):
            continue
        name = str(entry.get('name') or '').strip() or 'Board'
        bid = str(entry.get('id') or '').strip() or _slugify(name)
        # Ensure ids are unique.
        base_id, n = bid, 2
        while bid in seen_ids:
            bid = f"{base_id}-{n}"
            n += 1
        seen_ids.add(bid)
        model = str(entry.get('model') or 'flagship').strip().lower()
        if model not in ('flagship', 'note'):
            model = 'flagship'
        boards.append({
            'id': bid,
            'name': name,
            'key': str(entry.get('key') or '').strip(),
            'url': str(entry.get('url') or '').strip(),
            'model': model,
            'route': str(entry.get('route') or '').strip(),
            'direction': str(entry.get('direction') or '').strip(),
        })
    selected = str(vb.get('selected') or '').strip()
    if selected and selected not in seen_ids:
        selected = ''
    return {
        'site_url': str(data.get('site_url') or '').strip(),
        'route_id': str(data.get('route_id') or '').strip(),
        'wsdot_key': str(data.get('wsdot_key') or '').strip(),
        'vestaboard': {'selected': selected, 'boards': boards},
    }


def load_settings() -> Dict[str, Any]:
    """Load persisted settings, returning normalized defaults if missing/invalid."""
    try:
        with open(SETTINGS_PATH, 'r') as f:
            return _normalize_settings(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return _normalize_settings({})


def save_settings(data: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize and atomically persist settings; returns the stored value."""
    normalized = _normalize_settings(data)
    with _settings_lock:
        os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
        tmp = SETTINGS_PATH + '.tmp'
        with open(tmp, 'w') as f:
            json.dump(normalized, f, indent=2)
        os.replace(tmp, SETTINGS_PATH)
    return normalized


def _effective_wsdot_key() -> Optional[str]:
    """Resolve the WSDOT key: request override, then saved settings (env is the final fallback)."""
    return _param('wsdot_key') or (load_settings().get('wsdot_key') or None)


def _resolve_vestaboard_target() -> Dict[str, Any]:
    """
    Resolve the push target, honoring explicit request params first, then the
    selected saved board's stored fields. Returns key/url/route/direction/model.
    """
    vb_key = _param('vestaboard_key')
    vb_url = _param('vestaboard_url')
    route = _param('route_id')
    direction = _param('direction')
    model = _param('model')
    board_id = _param('board_id')

    if board_id:
        for board in load_settings()['vestaboard']['boards']:
            if board['id'] == board_id:
                vb_key = vb_key or board.get('key', '')
                vb_url = vb_url or board.get('url', '')
                route = route or board.get('route', '')
                direction = direction or board.get('direction', '')
                model = model or board.get('model', '')
                break

    return {
        'key': vb_key or None,
        'url': vb_url or None,
        'route': route or None,
        'direction': direction or None,
        'model': model or 'flagship',
    }


@app.route('/')
def index():
    """Root endpoint - serves the webhook simulator frontend."""
    site_url = get_site_url()
    # Reverse map (code -> character) so the browser can render a Vestaboard grid.
    vb_code_to_char = {code: char for char, code in VB_CHAR_MAP.items()}
    # route -> selectable directions, for the dynamic direction dropdowns.
    route_directions = {
        r: [{"value": o["value"], "label": o["label"]} for o in route_direction_options(r)]
        for r in ROUTE_TERMINALS
    }
    return render_template_string(
        SIMULATOR_TEMPLATE,
        site_url=site_url,
        route_id=FERRY_ROUTE_ID,
        vb_code_to_char=vb_code_to_char,
        route_directions=route_directions,
        wsdot_env_set=bool(WSDOT_API_KEY),
        vestaboard_env_set=bool(VESTABOARD_RW_KEY),
        app_version=APP_VERSION,
        git_sha=GIT_SHA,
        repo_url=GITHUB_REPO_URL,
    )


@app.route('/api/info')
def api_info():
    """API info endpoint - provides basic information about the webhook."""
    return jsonify({
        "service": "Washington State Ferry Status Webhook",
        "version": "1.0.0",
        "endpoints": {
            "/": "Webhook simulator frontend",
            "/webhook": "Main webhook endpoint for Trmnl (GET)",
            "/api/ferry-status": "JSON API endpoint (GET)",
            "/api/vestaboard": "Push ferry status to a Vestaboard device (GET/POST)",
            "/api/settings": "Read/write persisted web UI settings (GET/POST)",
            "/api/info": "API information (GET)",
            "/health": "Health check endpoint"
        },
        "documentation": "https://github.com/cdibona/FerryTrmnl"
    })


@app.route('/health')
def health():
    """Health check endpoint."""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    })


@app.route('/api/settings', methods=['GET', 'POST'])
def api_settings():
    """
    Read or write the web UI's persisted settings.

    GET returns the stored settings (route, WSDOT key, Vestaboard targets).
    POST replaces them with the normalized posted body and returns the result.

    Note: keys are stored and returned in plaintext, so keep this server on a
    trusted network (e.g. tailnet-only), not the public internet.
    """
    if request.method == 'POST':
        incoming = request.get_json(silent=True) or {}
        return jsonify(save_settings(incoming))
    return jsonify(load_settings())


@app.route('/webhook', methods=['GET'])
def webhook():
    """
    Main webhook endpoint for Trmnl display.
    Returns HTML formatted ferry status for display.
    """
    logger.info("Webhook called")
    
    # Get optional route_id from query parameters
    route_id = request.args.get('route_id', FERRY_ROUTE_ID)
    
    # Fetch ferry data
    ferry_data = fetch_ferry_status(route_id)
    
    # Format data for display
    formatted_data = format_ferry_data(ferry_data)
    
    # Render HTML template
    html = render_template_string(TRMNL_TEMPLATE, **formatted_data)
    
    return html


@app.route('/api/ferry-status', methods=['GET'])
def api_ferry_status():
    """
    JSON API endpoint for ferry status.
    Returns raw ferry status data in JSON format.
    """
    logger.info("API endpoint called")

    # Get optional route_id from query parameters
    route_id = _param('route_id', FERRY_ROUTE_ID)

    # Fetch ferry data
    ferry_data = fetch_ferry_status(route_id, api_key=_effective_wsdot_key())

    return jsonify(ferry_data)


@app.route('/api/trmnl', methods=['GET'])
def api_trmnl():
    """
    TRMNL polling endpoint.
    Returns JSON data formatted for TRMNL's Liquid templating.
    """
    logger.info("TRMNL polling endpoint called")

    # Get optional route_id from query parameters
    route_id = _param('route_id', FERRY_ROUTE_ID)

    # Send Discord notification if configured
    ip_address = request.headers.get('X-Forwarded-For', request.remote_addr)
    user_agent = request.headers.get('User-Agent', '')
    send_discord_notification('/api/trmnl', route_id, ip_address, user_agent)

    # Fetch and format ferry data
    direction = _param('direction')
    ferry_data = fetch_ferry_status(route_id, api_key=_effective_wsdot_key())
    formatted_data = format_ferry_data(ferry_data)
    formatted_data["status"] = compute_direction_status(ferry_data, route_id, direction) if route_id else None

    # Return JSON for TRMNL polling
    return jsonify(formatted_data)


# Inline ferry icon (self-contained, black/white for e-ink).
FERRY_ICON_SVG = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" aria-hidden="true">
  <path d="M20 180 L40 210 L216 210 L236 180 L220 180 L220 140 L36 140 L36 180 Z" fill="black"/>
  <path d="M30 210 Q50 220, 70 210 Q90 200, 110 210 Q130 220, 150 210 Q170 200, 190 210 Q210 220, 226 210"
        fill="none" stroke="black" stroke-width="6" stroke-linecap="round"/>
  <rect x="55" y="100" width="146" height="40" fill="black"/>
  <rect x="90" y="65" width="76" height="35" fill="black"/>
  <rect x="170" y="45" width="25" height="55" fill="black"/>
  <rect x="65" y="110" width="15" height="20" fill="white"/>
  <rect x="90" y="110" width="15" height="20" fill="white"/>
  <rect x="115" y="110" width="15" height="20" fill="white"/>
  <rect x="140" y="110" width="15" height="20" fill="white"/>
  <rect x="165" y="110" width="15" height="20" fill="white"/>
  <rect x="100" y="73" width="20" height="18" fill="white"/>
  <rect x="130" y="73" width="20" height="18" fill="white"/>
  <rect x="50" y="150" width="35" height="25" fill="white"/>
  <rect x="95" y="150" width="35" height="25" fill="white"/>
  <rect x="140" y="150" width="35" height="25" fill="white"/>
  <rect x="185" y="150" width="25" height="25" fill="white"/>
</svg>
"""

# Self-contained TRMNL e-ink preview (no external CDN, so it always renders).
TRMNL_PREVIEW_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        * { box-sizing: border-box; }
        html, body { height: 100%; margin: 0; }
        body { font-family: 'Helvetica Neue', Arial, sans-serif; background: #fff; color: #000; }
        .screen { height: 100%; padding: 20px 24px; display: flex; flex-direction: column; }
        .hdr { font-size: 30px; font-weight: 800; letter-spacing: -0.5px; padding-bottom: 10px; border-bottom: 4px solid #000; }
        .body { display: flex; gap: 22px; flex: 1; padding-top: 16px; min-height: 0; }
        .ferry { flex: 0 0 148px; display: flex; align-items: flex-start; justify-content: center; }
        .ferry svg { width: 148px; height: 148px; }
        .info { flex: 1; display: flex; flex-direction: column; gap: 12px; min-width: 0; }
        .dir { font-size: 21px; font-weight: 800; }
        .next { font-size: 40px; font-weight: 800; line-height: 1; }
        .next small { font-size: 15px; font-weight: 600; color: #444; letter-spacing: 0.5px; text-transform: uppercase; }
        .spaces { font-size: 22px; font-weight: 700; }
        .delay-ok { display: inline-block; font-size: 15px; font-weight: 700; padding: 3px 12px; border: 2px solid #000; border-radius: 4px; }
        .delay-bad { font-size: 15px; font-weight: 700; border-left: 5px solid #000; padding-left: 10px; }
        .vessels { margin-top: 4px; display: flex; flex-direction: column; gap: 5px; }
        .vessel { font-size: 14px; color: #222; }
        .vessel b { font-size: 15px; color: #000; }
        .foot { display: flex; justify-content: space-between; align-items: baseline; border-top: 1px solid #999; padding-top: 8px; font-size: 13px; color: #333; margin-top: 12px; }
    </style>
</head>
<body>
    <div class="screen">
        <div class="hdr">{{ route_name }}</div>
        <div class="body">
            <div class="ferry">{{ ferry_icon|safe }}</div>
            <div class="info">
                {% if status %}
                <div class="dir">{{ status.from }}{% if status.to %} &#8594; {{ status.to }}{% endif %}</div>
                <div class="next">{{ status.time_str or '—' }} <small>next departure</small></div>
                <div class="spaces">{{ status.spaces if status.spaces is not none else '—' }} drive-up spaces</div>
                {% if status.delay %}
                <div class="delay-bad">&#9888; {{ status.delay }}</div>
                {% else %}
                <span class="delay-ok">No delays</span>
                {% endif %}
                {% endif %}
                {% if vessels %}
                <div class="vessels">
                    {% for v in vessels %}
                    <div class="vessel"><b>{{ v.name }}</b>{% if v.status %} — {{ v.status }}{% endif %}{% if v.location %} &middot; {{ v.location }}{% endif %}</div>
                    {% endfor %}
                </div>
                {% endif %}
            </div>
        </div>
        <div class="foot"><span>FerryTrmnl</span><span>Updated {{ update_time }}</span></div>
    </div>
</body>
</html>
"""


@app.route('/api/trmnl/preview', methods=['GET', 'POST'])
def api_trmnl_preview():
    """
    TRMNL preview endpoint.
    Returns HTML rendered like TRMNL would display it.

    Accepts optional ``route_id`` and ``wsdot_key`` overrides (query or JSON body).
    """
    logger.info("TRMNL preview endpoint called")

    route_id = _param('route_id', FERRY_ROUTE_ID)
    direction = _param('direction')

    # Send Discord notification if configured
    ip_address = request.headers.get('X-Forwarded-For', request.remote_addr)
    user_agent = request.headers.get('User-Agent', '')
    send_discord_notification('/api/trmnl/preview', route_id, ip_address, user_agent)

    # Fetch and format ferry data
    ferry_data = fetch_ferry_status(route_id, api_key=_effective_wsdot_key())
    status = compute_direction_status(ferry_data, route_id, direction) if route_id else None
    formatted_data = format_ferry_data(ferry_data)

    # Render the self-contained e-ink preview
    html = render_template_string(
        TRMNL_PREVIEW_TEMPLATE, ferry_icon=FERRY_ICON_SVG, status=status, **formatted_data
    )
    return html


@app.route('/api/vestaboard', methods=['GET', 'POST'])
def api_vestaboard():
    """
    Push current ferry status to a Vestaboard (or Vestaboard Note) device.

    Query parameters:
        route_id: Optional route to display (defaults to FERRY_ROUTE_ID).
        preview:  If truthy, return the character grid without sending it.
    """
    logger.info("Vestaboard endpoint called")

    preview = _param('preview').lower() in ('1', 'true', 'yes')
    target = _resolve_vestaboard_target()
    route_id = target['route'] or FERRY_ROUTE_ID
    direction = target['direction']
    vb_key = target['key'] or VESTABOARD_RW_KEY
    vb_url = target['url'] or VESTABOARD_RW_URL

    # Send Discord notification if configured
    ip_address = request.headers.get('X-Forwarded-For', request.remote_addr)
    user_agent = request.headers.get('User-Agent', '')
    send_discord_notification('/api/vestaboard', route_id, ip_address, user_agent)

    # Fetch, format, and lay out for the split-flap grid
    ferry_data = fetch_ferry_status(route_id, api_key=_effective_wsdot_key())
    status = compute_direction_status(ferry_data, route_id, direction) if route_id else None
    formatted_data = format_ferry_data(ferry_data)
    characters = format_vestaboard_message(formatted_data, status)

    if preview:
        return jsonify({"characters": characters, "sent": False})

    if not vb_key:
        return jsonify({
            "error": "Vestaboard Read/Write key not configured",
            "characters": characters,
            "sent": False,
        }), 503

    result = send_to_vestaboard(characters, key=vb_key, url=vb_url)
    status_code = 200 if "error" not in result else 502
    return jsonify({**result, "characters": characters, "sent": "error" not in result}), status_code


def main():
    """Main entry point for running the Flask application."""
    if not WSDOT_API_KEY:
        logger.error("WSDOT_API_KEY environment variable is not set!")
        logger.error("Please copy .env.template to .env and configure your API key")
        return
    
    logger.info(f"Starting Washington State Ferry Webhook Server")
    logger.info(f"Server will run on {FLASK_HOST}:{FLASK_PORT}")
    logger.info(f"Debug mode: {FLASK_DEBUG}")
    
    app.run(
        host=FLASK_HOST,
        port=FLASK_PORT,
        debug=FLASK_DEBUG
    )


if __name__ == '__main__':
    main()
