#!/usr/bin/env python3
"""
Washington State Ferry Status Webhook for Trmnl Display
This Flask application provides a webhook server that fetches ferry status data
from the WSDOT Ferries API and formats it for display on Trmnl e-ink devices.
"""

import os
import re
import logging
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

# Display configuration constants
MAX_VESSELS_DISPLAY = 5  # Maximum number of vessels to display
MAX_DEPARTURES_DISPLAY = 10  # Maximum number of departures to display

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
        * {
            box-sizing: border-box;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            margin: 0;
            padding: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
        }
        .simulator-container {
            max-width: 900px;
            margin: 0 auto;
        }
        .header {
            text-align: center;
            color: white;
            margin-bottom: 30px;
        }
        .header h1 {
            margin: 0 0 10px 0;
            font-size: 28px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.2);
        }
        .header p {
            margin: 0;
            opacity: 0.9;
            font-size: 16px;
        }
        .controls {
            background: white;
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        }
        .controls h2 {
            margin: 0 0 15px 0;
            font-size: 18px;
            color: #333;
        }
        .form-row {
            display: flex;
            gap: 15px;
            flex-wrap: wrap;
            align-items: flex-end;
        }
        .form-group {
            flex: 1;
            min-width: 200px;
        }
        .form-group label {
            display: block;
            margin-bottom: 5px;
            font-size: 14px;
            color: #666;
            font-weight: 500;
        }
        .form-group input, .form-group select {
            width: 100%;
            padding: 10px 12px;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            font-size: 14px;
            transition: border-color 0.2s;
            background-color: white;
        }
        .form-group input:focus, .form-group select:focus {
            outline: none;
            border-color: #667eea;
        }
        .btn {
            padding: 12px 24px;
            border: none;
            border-radius: 8px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
        }
        .btn-primary {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        .btn-primary:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
        }
        .btn-primary:disabled {
            opacity: 0.6;
            cursor: not-allowed;
            transform: none;
        }
        .btn-secondary {
            background: #f0f0f0;
            color: #333;
        }
        .btn-secondary:hover {
            background: #e0e0e0;
        }
        .webhook-url {
            background: #f8f9fa;
            border-radius: 8px;
            padding: 12px;
            margin-top: 15px;
            font-family: 'Monaco', 'Menlo', monospace;
            font-size: 13px;
            color: #666;
            word-break: break-all;
        }
        .webhook-url strong {
            color: #333;
        }
        .trmnl-frame {
            background: #2a2a2a;
            border-radius: 20px;
            padding: 20px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.3);
        }
        .trmnl-bezel {
            background: #1a1a1a;
            border-radius: 12px;
            padding: 8px;
        }
        .trmnl-screen {
            background: #f5f5f0;
            border-radius: 4px;
            min-height: 480px;
            position: relative;
            overflow: hidden;
        }
        .trmnl-screen iframe {
            width: 100%;
            height: 480px;
            border: none;
            background: white;
        }
        .trmnl-placeholder {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            height: 480px;
            color: #999;
            text-align: center;
            padding: 40px;
        }
        .trmnl-placeholder svg {
            width: 80px;
            height: 80px;
            margin-bottom: 20px;
            opacity: 0.5;
        }
        .trmnl-placeholder h3 {
            margin: 0 0 10px 0;
            color: #666;
        }
        .trmnl-placeholder p {
            margin: 0;
            font-size: 14px;
        }
        .trmnl-label {
            text-align: center;
            color: #666;
            font-size: 12px;
            margin-top: 15px;
            letter-spacing: 2px;
            text-transform: uppercase;
        }
        .loading-overlay {
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(255,255,255,0.9);
            display: none;
            align-items: center;
            justify-content: center;
            flex-direction: column;
        }
        .loading-overlay.active {
            display: flex;
        }
        .spinner {
            width: 40px;
            height: 40px;
            border: 4px solid #e0e0e0;
            border-top-color: #667eea;
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
        .loading-text {
            margin-top: 15px;
            color: #666;
            font-size: 14px;
        }
        .status-bar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-top: 15px;
            padding: 10px 15px;
            background: white;
            border-radius: 8px;
            font-size: 13px;
        }
        .status-indicator {
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .status-dot {
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background: #ccc;
        }
        .status-dot.success { background: #4caf50; }
        .status-dot.error { background: #f44336; }
        .status-dot.loading { background: #ff9800; animation: pulse 1s infinite; }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        .response-time {
            color: #999;
        }
        .info-section {
            background: white;
            border-radius: 12px;
            padding: 20px;
            margin-top: 20px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        }
        .info-section h3 {
            margin: 0 0 15px 0;
            font-size: 16px;
            color: #333;
        }
        .endpoint-list {
            display: grid;
            gap: 10px;
        }
        .endpoint-item {
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 10px;
            background: #f8f9fa;
            border-radius: 6px;
        }
        .endpoint-method {
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: 600;
            background: #e3f2fd;
            color: #1976d2;
        }
        .endpoint-path {
            font-family: monospace;
            font-size: 14px;
            color: #333;
        }
        .endpoint-desc {
            color: #666;
            font-size: 13px;
            margin-left: auto;
        }
        @media (max-width: 600px) {
            .form-row {
                flex-direction: column;
            }
            .form-group {
                min-width: 100%;
            }
        }
    </style>
</head>
<body>
    <div class="simulator-container">
        <div class="header">
            <h1>TRMNL Webhook Simulator</h1>
            <p>Test how your WA State Ferry Status webhook renders on a TRMNL e-ink display</p>
        </div>

        <div class="controls">
            <h2>Webhook Configuration</h2>
            <div class="form-row">
                <div class="form-group">
                    <label for="siteUrl">Site URL</label>
                    <input type="text" id="siteUrl" placeholder="https://your-domain.com" value="{{ site_url }}">
                </div>
                <div class="form-group">
                    <label for="routeId">Route (optional)</label>
                    <select id="routeId">
                        <option value="">All Routes</option>
                        <option value="sea-bi"{% if route_id == 'sea-bi' %} selected{% endif %}>Seattle / Bainbridge Island</option>
                        <option value="sea-br"{% if route_id == 'sea-br' %} selected{% endif %}>Seattle / Bremerton</option>
                        <option value="ed-king"{% if route_id == 'ed-king' %} selected{% endif %}>Edmonds / Kingston</option>
                        <option value="muk-cl"{% if route_id == 'muk-cl' %} selected{% endif %}>Mukilteo / Clinton</option>
                        <option value="f-v-s"{% if route_id == 'f-v-s' %} selected{% endif %}>Fauntleroy / Vashon</option>
                        <option value="f-s"{% if route_id == 'f-s' %} selected{% endif %}>Fauntleroy / Southworth</option>
                        <option value="s-v"{% if route_id == 's-v' %} selected{% endif %}>Southworth / Vashon</option>
                        <option value="pt-key"{% if route_id == 'pt-key' %} selected{% endif %}>Port Townsend / Coupeville</option>
                        <option value="pd-tal"{% if route_id == 'pd-tal' %} selected{% endif %}>Pt. Defiance / Tahlequah</option>
                        <option value="ana-sj"{% if route_id == 'ana-sj' %} selected{% endif %}>Anacortes / San Juan Islands</option>
                    </select>
                </div>
                <button class="btn btn-primary" id="fetchBtn" onclick="fetchWebhook()">
                    Fetch Webhook
                </button>
                <button class="btn btn-secondary" onclick="clearScreen()">
                    Clear
                </button>
            </div>
            <div class="webhook-url" id="webhookUrl">
                <strong>Webhook URL:</strong> <span id="urlDisplay">Configure site URL above</span>
            </div>
        </div>

        <div class="trmnl-frame">
            <div class="trmnl-bezel">
                <div class="trmnl-screen" id="screenContainer">
                    <div class="trmnl-placeholder" id="placeholder">
                        <svg viewBox="0 0 24 24" fill="currentColor">
                            <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/>
                            <polyline points="3.27 6.96 12 12.01 20.73 6.96" fill="none" stroke="white" stroke-width="1.5"/>
                            <line x1="12" y1="22.08" x2="12" y2="12" fill="none" stroke="white" stroke-width="1.5"/>
                        </svg>
                        <h3>TRMNL Display Preview</h3>
                        <p>Click "Fetch Webhook" to simulate a TRMNL device<br>calling your webhook endpoint</p>
                    </div>
                    <iframe id="displayFrame" style="display: none;"></iframe>
                    <div class="loading-overlay" id="loadingOverlay">
                        <div class="spinner"></div>
                        <div class="loading-text">Calling webhook...</div>
                    </div>
                </div>
            </div>
            <div class="trmnl-label">TRMNL E-Ink Display Simulator</div>
        </div>

        <div class="status-bar">
            <div class="status-indicator">
                <div class="status-dot" id="statusDot"></div>
                <span id="statusText">Ready</span>
            </div>
            <div class="response-time" id="responseTime"></div>
        </div>

        <div class="info-section">
            <h3>Available Endpoints</h3>
            <div class="endpoint-list">
                <div class="endpoint-item">
                    <span class="endpoint-method">GET</span>
                    <span class="endpoint-path">/api/trmnl</span>
                    <span class="endpoint-desc">TRMNL polling (JSON)</span>
                </div>
                <div class="endpoint-item">
                    <span class="endpoint-method">GET</span>
                    <span class="endpoint-path">/api/trmnl/preview</span>
                    <span class="endpoint-desc">TRMNL preview (HTML)</span>
                </div>
                <div class="endpoint-item">
                    <span class="endpoint-method">GET</span>
                    <span class="endpoint-path">/api/ferry-status</span>
                    <span class="endpoint-desc">Raw JSON API</span>
                </div>
                <div class="endpoint-item">
                    <span class="endpoint-method">GET</span>
                    <span class="endpoint-path">/health</span>
                    <span class="endpoint-desc">Health check</span>
                </div>
            </div>
        </div>
    </div>

    <script>
        // Initialize with current URL if no SITE_URL configured
        const defaultUrl = '{{ site_url }}' || window.location.origin;
        document.getElementById('siteUrl').value = defaultUrl;
        updateWebhookUrl();

        // Update webhook URL display when inputs change
        document.getElementById('siteUrl').addEventListener('input', updateWebhookUrl);
        document.getElementById('routeId').addEventListener('change', updateWebhookUrl);

        function updateWebhookUrl() {
            const siteUrl = document.getElementById('siteUrl').value.replace(/\\/$/, '');
            const routeId = document.getElementById('routeId').value.trim();

            let webhookUrl = siteUrl + '/api/trmnl';
            if (routeId) {
                webhookUrl += '?route_id=' + encodeURIComponent(routeId);
            }

            document.getElementById('urlDisplay').textContent = webhookUrl || 'Configure site URL above';
        }

        function setStatus(status, text, responseTime = null) {
            const dot = document.getElementById('statusDot');
            const statusText = document.getElementById('statusText');
            const responseTimeEl = document.getElementById('responseTime');

            dot.className = 'status-dot ' + status;
            statusText.textContent = text;

            if (responseTime !== null) {
                responseTimeEl.textContent = 'Response time: ' + responseTime + 'ms';
            } else {
                responseTimeEl.textContent = '';
            }
        }

        async function fetchWebhook() {
            const siteUrl = document.getElementById('siteUrl').value.replace(/\\/$/, '');
            const routeId = document.getElementById('routeId').value.trim();
            const fetchBtn = document.getElementById('fetchBtn');
            const loadingOverlay = document.getElementById('loadingOverlay');
            const placeholder = document.getElementById('placeholder');
            const displayFrame = document.getElementById('displayFrame');

            if (!siteUrl) {
                alert('Please enter a Site URL');
                return;
            }

            let webhookUrl = siteUrl + '/api/trmnl/preview';
            if (routeId) {
                webhookUrl += '?route_id=' + encodeURIComponent(routeId);
            }

            // Show loading state
            fetchBtn.disabled = true;
            loadingOverlay.classList.add('active');
            placeholder.style.display = 'none';
            displayFrame.style.display = 'none';
            setStatus('loading', 'Fetching webhook...');

            const startTime = performance.now();

            try {
                const response = await fetch(webhookUrl);
                const endTime = performance.now();
                const responseTime = Math.round(endTime - startTime);

                if (!response.ok) {
                    throw new Error('HTTP ' + response.status + ': ' + response.statusText);
                }

                const html = await response.text();

                // Display the response in the iframe
                displayFrame.style.display = 'block';
                displayFrame.srcdoc = html;

                setStatus('success', 'Webhook loaded successfully', responseTime);

            } catch (error) {
                console.error('Fetch error:', error);

                // Show error in the display
                displayFrame.style.display = 'block';
                displayFrame.srcdoc = `
                    <!DOCTYPE html>
                    <html>
                    <head>
                        <style>
                            body {
                                font-family: Arial, sans-serif;
                                padding: 40px;
                                text-align: center;
                                color: #cc0000;
                            }
                            h2 { margin-bottom: 20px; }
                            .error-details {
                                background: #fff5f5;
                                border: 1px solid #ffcccc;
                                padding: 20px;
                                border-radius: 8px;
                                margin-top: 20px;
                                text-align: left;
                            }
                            code {
                                background: #f0f0f0;
                                padding: 2px 6px;
                                border-radius: 4px;
                            }
                        </style>
                    </head>
                    <body>
                        <h2>Failed to Fetch Webhook</h2>
                        <p>${error.message}</p>
                        <div class="error-details">
                            <strong>Troubleshooting:</strong>
                            <ul>
                                <li>Check that the Site URL is correct</li>
                                <li>Ensure the webhook server is running</li>
                                <li>Verify CORS is enabled if accessing cross-origin</li>
                                <li>Check browser console for more details</li>
                            </ul>
                            <p><strong>Attempted URL:</strong> <code>${webhookUrl}</code></p>
                        </div>
                    </body>
                    </html>
                `;

                setStatus('error', 'Error: ' + error.message);

            } finally {
                fetchBtn.disabled = false;
                loadingOverlay.classList.remove('active');
            }
        }

        function clearScreen() {
            const placeholder = document.getElementById('placeholder');
            const displayFrame = document.getElementById('displayFrame');

            placeholder.style.display = 'flex';
            displayFrame.style.display = 'none';
            displayFrame.srcdoc = '';

            setStatus('', 'Ready');
            document.getElementById('responseTime').textContent = '';
        }

        // Allow Enter key to trigger fetch
        document.getElementById('siteUrl').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') fetchWebhook();
        });
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


def fetch_ferry_status(route_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Fetch ferry status from WSDOT API.

    Args:
        route_id: Optional specific route ID to fetch

    Returns:
        Dictionary containing ferry status data
    """
    if not WSDOT_API_KEY:
        logger.error("WSDOT_API_KEY not configured")
        return {"error": "API key not configured"}

    route = route_id or FERRY_ROUTE_ID
    params = {"apiaccesscode": WSDOT_API_KEY}

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

        # Fetch terminal space/parking data
        terminal_spaces = {}
        try:
            space_url = f"{WSDOT_API_BASE_URL.replace('/ferries/api', '/ferries/api/terminals')}/rest/terminalsailingspace"
            space_response = requests.get(space_url, params=params, timeout=10)
            space_response.raise_for_status()
            space_data = space_response.json()

            for terminal in space_data:
                terminal_name = terminal.get("TerminalName", "")
                if not terminals or terminal_name in terminals:
                    # Get the next departure's space info
                    departing_spaces = terminal.get("DepartingSpaces", [])
                    if departing_spaces:
                        next_departure = departing_spaces[0]
                        space_info = next_departure.get("SpaceForArrivalTerminals", [])
                        if space_info:
                            spaces = space_info[0]
                            terminal_spaces[terminal_name] = {
                                "drive_up": spaces.get("DriveUpSpaceCount", 0),
                                "max": spaces.get("MaxSpaceCount", 0),
                                "color": spaces.get("DriveUpSpaceHexColor", "#888888")
                            }
        except Exception as e:
            logger.warning(f"Could not fetch terminal space data: {e}")

        return {
            "vessels": vessels_data,
            "route_id": route,
            "route_name": ROUTE_NAMES.get(route, "Washington State Ferries") if route else "All Routes",
            "terminal_spaces": terminal_spaces,
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


def get_site_url() -> str:
    """Get the site URL, with fallback to constructing from request."""
    if SITE_URL:
        return SITE_URL.rstrip('/')
    # Fallback: construct from Flask config
    return f"http://{FLASK_HOST}:{FLASK_PORT}" if FLASK_HOST != '0.0.0.0' else ''


@app.route('/')
def index():
    """Root endpoint - serves the webhook simulator frontend."""
    site_url = get_site_url()
    return render_template_string(
        SIMULATOR_TEMPLATE,
        site_url=site_url,
        route_id=FERRY_ROUTE_ID
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
    route_id = request.args.get('route_id', FERRY_ROUTE_ID)

    # Fetch ferry data
    ferry_data = fetch_ferry_status(route_id)

    return jsonify(ferry_data)


@app.route('/api/trmnl', methods=['GET'])
def api_trmnl():
    """
    TRMNL polling endpoint.
    Returns JSON data formatted for TRMNL's Liquid templating.
    """
    logger.info("TRMNL polling endpoint called")

    # Get optional route_id from query parameters
    route_id = request.args.get('route_id', FERRY_ROUTE_ID)

    # Fetch and format ferry data
    ferry_data = fetch_ferry_status(route_id)
    formatted_data = format_ferry_data(ferry_data)

    # Return JSON for TRMNL polling
    return jsonify(formatted_data)


# TRMNL-style template (mimics what TRMNL renders with Liquid)
TRMNL_PREVIEW_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;350;375;400;450;600;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://usetrmnl.com/css/latest/plugins.css">
</head>
<body class="environment trmnl">
    <div class="screen">
        <div class="view view--full">
            <div class="layout">
                <div class="columns">
                    <div class="column">
                        <div class="markdown">
                            <div class="content">
                                <span class="title">{{ route_name }}</span>
                            </div>
                            {% for vessel in vessels %}
                            <div class="content" style="margin-top: 16px; padding: 12px; border: 2px solid #000;">
                                <span class="title" style="font-size: 24px;">{{ vessel.name }}</span>
                                <span class="label">{{ vessel.status }}</span>
                                {% if vessel.location %}
                                <p style="margin-top: 8px;">{{ vessel.location }}</p>
                                {% endif %}
                            </div>
                            {% endfor %}
                            <div class="content" style="margin-top: 16px;">
                                <span class="label">
                                    {% for terminal, space in terminal_spaces.items() %}
                                    {{ terminal }}: {{ space.drive_up }} spots{% if not loop.last %} | {% endif %}
                                    {% endfor %}
                                </span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            <div class="title_bar">
                <span class="title">FerryTrmnl</span>
                <span class="instance">Updated {{ update_time }}</span>
            </div>
        </div>
    </div>
</body>
</html>
"""


@app.route('/api/trmnl/preview', methods=['GET'])
def api_trmnl_preview():
    """
    TRMNL preview endpoint.
    Returns HTML rendered like TRMNL would display it.
    """
    logger.info("TRMNL preview endpoint called")

    # Get optional route_id from query parameters
    route_id = request.args.get('route_id', FERRY_ROUTE_ID)

    # Fetch and format ferry data
    ferry_data = fetch_ferry_status(route_id)
    formatted_data = format_ferry_data(ferry_data)

    # Render with TRMNL-style template
    html = render_template_string(TRMNL_PREVIEW_TEMPLATE, **formatted_data)
    return html


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
