#!/usr/bin/env python3
"""
Washington State Ferry Status Webhook for Trmnl Display
This Flask application provides a webhook server that fetches ferry status data
from the WSDOT Ferries API and formats it for display on Trmnl e-ink devices.
"""

import os
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
            padding: 20px;
            background-color: white;
        }
        .container {
            max-width: 800px;
            margin: 0 auto;
        }
        h1 {
            font-size: 24px;
            margin-bottom: 10px;
            border-bottom: 2px solid black;
            padding-bottom: 10px;
        }
        .route-info {
            font-size: 18px;
            margin: 15px 0;
        }
        .vessel-info {
            margin: 20px 0;
            padding: 15px;
            border: 1px solid black;
        }
        .vessel-name {
            font-size: 20px;
            font-weight: bold;
            margin-bottom: 10px;
        }
        .status {
            font-size: 16px;
            margin: 5px 0;
        }
        .schedule {
            margin-top: 20px;
        }
        .departure {
            font-size: 14px;
            padding: 8px;
            margin: 5px 0;
            border-left: 3px solid black;
            padding-left: 10px;
        }
        .update-time {
            font-size: 12px;
            color: #666;
            margin-top: 20px;
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
        <h1>WA State Ferry Status</h1>
        {% if error %}
        <div class="error">{{ error }}</div>
        {% else %}
        <div class="route-info">
            <strong>Route:</strong> {{ route_name }}<br>
            {% if route_description %}
            <strong>Description:</strong> {{ route_description }}
            {% endif %}
        </div>
        
        {% if vessels %}
        <div class="schedule">
            <h2>Current Vessels</h2>
            {% for vessel in vessels %}
            <div class="vessel-info">
                <div class="vessel-name">{{ vessel.name }}</div>
                <div class="status">
                    <strong>Status:</strong> {{ vessel.status }}<br>
                    {% if vessel.location %}
                    <strong>Location:</strong> {{ vessel.location }}<br>
                    {% endif %}
                    {% if vessel.eta %}
                    <strong>ETA:</strong> {{ vessel.eta }}
                    {% endif %}
                </div>
            </div>
            {% endfor %}
        </div>
        {% endif %}
        
        {% if departures %}
        <div class="schedule">
            <h2>Upcoming Departures</h2>
            {% for departure in departures %}
            <div class="departure">
                <strong>{{ departure.time }}</strong> - {{ departure.departing_terminal }} to {{ departure.arriving_terminal }}
                {% if departure.vessel %}
                <br>Vessel: {{ departure.vessel }}
                {% endif %}
            </div>
            {% endfor %}
        </div>
        {% endif %}
        
        <div class="update-time">
            Last updated: {{ update_time }}
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
        .form-group input {
            width: 100%;
            padding: 10px 12px;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            font-size: 14px;
            transition: border-color 0.2s;
        }
        .form-group input:focus {
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
                    <label for="routeId">Route ID (optional)</label>
                    <input type="text" id="routeId" placeholder="e.g., sea-bi for Seattle-Bainbridge" value="{{ route_id }}">
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
                    <span class="endpoint-path">/webhook</span>
                    <span class="endpoint-desc">Main TRMNL webhook (HTML)</span>
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
        document.getElementById('routeId').addEventListener('input', updateWebhookUrl);

        function updateWebhookUrl() {
            const siteUrl = document.getElementById('siteUrl').value.replace(/\\/$/, '');
            const routeId = document.getElementById('routeId').value.trim();

            let webhookUrl = siteUrl + '/webhook';
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

            let webhookUrl = siteUrl + '/webhook';
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
        document.getElementById('routeId').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') fetchWebhook();
        });
    </script>
</body>
</html>
"""


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
    
    try:
        # Fetch vessel locations
        vessels_url = f"{WSDOT_API_BASE_URL}/vessels/rest/vessellocations"
        params = {"apiaccesscode": WSDOT_API_KEY}
        
        logger.info(f"Fetching vessel locations from WSDOT API")
        response = requests.get(vessels_url, params=params, timeout=10)
        response.raise_for_status()
        
        vessels_data = response.json()
        
        # If route_id is specified, fetch route-specific information
        route_info = {}
        if route:
            try:
                route_url = f"{WSDOT_API_BASE_URL}/schedule/rest/schedule/{route}"
                route_response = requests.get(route_url, params=params, timeout=10)
                route_response.raise_for_status()
                route_info = route_response.json()
            except Exception as e:
                logger.warning(f"Could not fetch route-specific data: {e}")
        
        return {
            "vessels": vessels_data,
            "route_info": route_info,
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
        "route_name": "Washington State Ferries",
        "route_description": "",
        "vessels": [],
        "departures": [],
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    # Process vessel data
    vessels = data.get("vessels", [])
    if isinstance(vessels, list):
        for vessel in vessels[:MAX_VESSELS_DISPLAY]:
            vessel_info = {
                "name": vessel.get("VesselName", "Unknown"),
                "status": vessel.get("InService", "Unknown"),
                "location": vessel.get("AtDock", ""),
                "eta": vessel.get("LeftDock", "")
            }
            formatted["vessels"].append(vessel_info)
    
    # Process route info if available
    route_info = data.get("route_info", {})
    if route_info:
        formatted["route_name"] = route_info.get("RouteName", formatted["route_name"])
        formatted["route_description"] = route_info.get("Description", "")
        
        # Process schedule/departures
        schedule = route_info.get("Schedule", [])
        if isinstance(schedule, list):
            for dept in schedule[:MAX_DEPARTURES_DISPLAY]:
                departure_info = {
                    "time": dept.get("DepartingTime", ""),
                    "departing_terminal": dept.get("DepartingTerminal", ""),
                    "arriving_terminal": dept.get("ArrivingTerminal", ""),
                    "vessel": dept.get("VesselName", "")
                }
                formatted["departures"].append(departure_info)
    
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
