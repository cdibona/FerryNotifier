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


@app.route('/')
def index():
    """Root endpoint - provides basic information about the webhook."""
    return jsonify({
        "service": "Washington State Ferry Status Webhook",
        "version": "1.0.0",
        "endpoints": {
            "/webhook": "Main webhook endpoint for Trmnl (GET)",
            "/api/ferry-status": "JSON API endpoint (GET)",
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
