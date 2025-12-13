# FerryTrmnl

A Washington State Ferry status display plugin for [Trmnl](https://usetrmnl.com/) e-ink displays. This webhook server fetches real-time ferry status information from the WSDOT Ferries API and displays it on your Trmnl device.

## Features

- **Real-time Ferry Status**: Displays current vessel locations and status
- **Route Information**: Shows specific ferry route details
- **Upcoming Departures**: Lists next departures for your chosen route
- **E-ink Optimized**: Display formatted for e-ink screens with clear, readable text
- **REST API**: Provides both HTML webhook and JSON API endpoints
- **Production Ready**: Designed to run behind nginx with systemd service management

## Quick Start

### Prerequisites

- Python 3.8 or higher
- WSDOT Ferries API key (free from [WSDOT](https://www.wsdot.wa.gov/traffic/api/))
- A Trmnl device or account

### Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/cdibona/FerryTrmnl.git
   cd FerryTrmnl
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment variables**:
   ```bash
   cp .env.template .env
   # Edit .env with your favorite editor
   nano .env
   ```

4. **Add your WSDOT API key** to the `.env` file:
   ```bash
   WSDOT_API_KEY=your_actual_api_key_here
   ```

5. **Run the server**:
   ```bash
   python app.py
   ```

The server will start on `http://localhost:5050` by default.

## Configuration

### Environment Variables

Edit the `.env` file to configure the webhook server:

| Variable | Description | Default |
|----------|-------------|---------|
| `FLASK_HOST` | Host to bind the server to | `0.0.0.0` |
| `FLASK_PORT` | Port to run the server on | `5050` |
| `FLASK_DEBUG` | Enable Flask debug mode | `False` |
| `WSDOT_API_KEY` | Your WSDOT API access key | *Required* |
| `WSDOT_API_BASE_URL` | WSDOT API base URL | `https://www.wsdot.wa.gov/ferries/api` |
| `FERRY_ROUTE_ID` | Specific ferry route ID (optional) | `` |
| `TRMNL_DEVICE_ID` | Your Trmnl device ID (optional) | `` |

### Getting a WSDOT API Key

1. Visit the [WSDOT Traveler Information API page](https://www.wsdot.wa.gov/traffic/api/)
2. Request an API access code (it's free!)
3. You'll receive an API key via email
4. Add it to your `.env` file

### Finding Ferry Route IDs

Common Washington State Ferry routes:

- **Seattle - Bainbridge Island**: Check WSDOT API documentation
- **Mukilteo - Clinton**: Check WSDOT API documentation
- **Edmonds - Kingston**: Check WSDOT API documentation
- **Fauntleroy - Vashon - Southworth**: Check WSDOT API documentation

You can find all route IDs by calling the WSDOT API or checking their documentation.

## API Endpoints

### `GET /webhook`

Main webhook endpoint for Trmnl. Returns HTML formatted for e-ink display.

**Query Parameters**:
- `route_id` (optional): Specific ferry route to display

**Example**:
```bash
curl http://localhost:5050/webhook
```

### `GET /api/ferry-status`

JSON API endpoint returning raw ferry status data.

**Query Parameters**:
- `route_id` (optional): Specific ferry route to query

**Example**:
```bash
curl http://localhost:5050/api/ferry-status
```

**Response**:
```json
{
  "vessels": [...],
  "route_info": {...},
  "timestamp": "2024-01-15T10:30:00"
}
```

### `GET /health`

Health check endpoint for monitoring.

**Example**:
```bash
curl http://localhost:5050/health
```

### `GET /`

Root endpoint providing service information and available endpoints.

## Production Deployment

### Running with Gunicorn

For production, use Gunicorn instead of the Flask development server:

```bash
gunicorn -w 4 -b 0.0.0.0:5050 app:app
```

### Systemd Service

Create a systemd service file at `/etc/systemd/system/ferrytrmnl.service`:

```ini
[Unit]
Description=FerryTrmnl Webhook Server
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/FerryTrmnl
Environment="PATH=/opt/FerryTrmnl/venv/bin"
ExecStart=/opt/FerryTrmnl/venv/bin/gunicorn -w 4 -b 127.0.0.1:5050 app:app
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start the service:

```bash
sudo systemctl enable ferrytrmnl
sudo systemctl start ferrytrmnl
sudo systemctl status ferrytrmnl
```

### Nginx Configuration

Create an nginx configuration at `/etc/nginx/sites-available/ferrytrmnl`:

```nginx
server {
    listen 80;
    server_name ferry.yourdomain.com;

    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name ferry.yourdomain.com;

    # SSL configuration
    ssl_certificate /etc/letsencrypt/live/ferry.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/ferry.yourdomain.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "SAMEORIGIN" always;

    # Logging
    access_log /var/log/nginx/ferrytrmnl_access.log;
    error_log /var/log/nginx/ferrytrmnl_error.log;

    location / {
        proxy_pass http://127.0.0.1:5050;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
}
```

Enable the site:

```bash
sudo ln -s /etc/nginx/sites-available/ferrytrmnl /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### SSL Certificate with Let's Encrypt

```bash
sudo apt-get install certbot python3-certbot-nginx
sudo certbot --nginx -d ferry.yourdomain.com
```

## Trmnl Setup

1. **Log in to your Trmnl account** at [usetrmnl.com](https://usetrmnl.com/)

2. **Create a new Plugin**:
   - Go to your dashboard
   - Click "Add Plugin" or "Create Custom Plugin"
   - Choose "Webhook" type

3. **Configure the webhook**:
   - **Webhook URL**: `https://ferry.yourdomain.com/webhook`
   - **Refresh Interval**: Set to your preference (e.g., 15 minutes)
   - **Method**: GET

4. **Save and test** the plugin

5. **Assign to your device** to start displaying ferry status

## Development

### Running in Development Mode

```bash
# Enable debug mode in .env
FLASK_DEBUG=True

# Run the development server
python app.py
```

### Testing the Webhook

Test the webhook locally:

```bash
# Test the HTML output
curl http://localhost:5050/webhook

# Test the JSON API
curl http://localhost:5050/api/ferry-status | jq

# Test with a specific route
curl "http://localhost:5050/webhook?route_id=YOUR_ROUTE_ID"
```

### Project Structure

```
FerryTrmnl/
├── app.py              # Main Flask application
├── requirements.txt    # Python dependencies
├── .env.template      # Environment variables template
├── .env               # Your local configuration (not in git)
├── .gitignore         # Git ignore rules
└── README.md          # This file
```

## Troubleshooting

### Common Issues

**"API key not configured" error**:
- Make sure you've copied `.env.template` to `.env`
- Verify your `WSDOT_API_KEY` is set correctly in `.env`
- Ensure the `.env` file is in the same directory as `app.py`

**"Failed to fetch ferry data" error**:
- Check your internet connection
- Verify your WSDOT API key is valid and active
- Check WSDOT API status at their website

**Port 5050 already in use**:
- Change `FLASK_PORT` in your `.env` file to a different port
- Or stop the process using port 5050: `sudo lsof -ti:5050 | xargs kill -9`

**Nginx 502 Bad Gateway**:
- Ensure the Flask/Gunicorn service is running: `sudo systemctl status ferrytrmnl`
- Check that the port in nginx config matches your Flask port
- Review logs: `sudo journalctl -u ferrytrmnl -f`

### Logs

View application logs:

```bash
# If running with systemd
sudo journalctl -u ferrytrmnl -f

# If running directly
# Logs will appear in the terminal
```

View nginx logs:

```bash
sudo tail -f /var/log/nginx/ferrytrmnl_error.log
sudo tail -f /var/log/nginx/ferrytrmnl_access.log
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is open source and available under the MIT License.

## Acknowledgments

- WSDOT for providing the Ferries API
- Trmnl for their e-ink display platform
- The Washington State Ferry system for their excellent service

## Support

For issues, questions, or contributions, please visit the [GitHub repository](https://github.com/cdibona/FerryTrmnl).

## Related Links

- [WSDOT Traveler Information API](https://www.wsdot.wa.gov/traffic/api/)
- [Trmnl Platform](https://usetrmnl.com/)
- [Washington State Ferries](https://www.wsdot.wa.gov/ferries/)
