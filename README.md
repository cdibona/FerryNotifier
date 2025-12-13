# FerryTrmnl

A Washington State Ferry status display plugin for [Trmnl](https://usetrmnl.com/) e-ink displays. This webhook server fetches real-time ferry status information from the WSDOT Ferries API and displays it on your Trmnl device.

## Features

- **Real-time Ferry Status**: Displays current vessel locations and status
- **Route Information**: Shows specific ferry route details
- **Upcoming Departures**: Lists next departures for your chosen route
- **E-ink Optimized**: Display formatted for e-ink screens with clear, readable text
- **REST API**: Provides both HTML webhook and JSON API endpoints
- **Production Ready**: Designed to run behind nginx with systemd service management
- **CI/CD Ready**: Includes GitHub Actions workflows for automated testing and deployment

## Project Structure

```
FerryTrmnl/
├── web/                    # Web application code
│   ├── app.py              # Main Flask application
│   ├── test_app.py         # Unit tests
│   └── requirements.txt    # Python dependencies
├── deployment/             # Deployment configurations
│   ├── Dockerfile          # Docker container definition
│   ├── docker-compose.yml  # Docker Compose configuration
│   ├── ferrytrmnl.service  # Systemd service file
│   ├── nginx.conf.example  # Nginx reverse proxy config
│   └── run.sh              # Quick-start development script
├── .github/
│   └── workflows/          # GitHub Actions CI/CD
│       └── deploy.yml      # Deployment workflow
├── .env.template           # Environment variables template
├── .gitignore              # Git ignore rules
├── .dockerignore           # Docker ignore rules
├── LICENSE                 # MIT License
├── README.md               # This file
├── INSTALL.md              # Installation/deployment guide
├── TESTING.md              # Testing guide
└── CONTRIBUTING.md         # Contribution guidelines
```

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
   pip install -r web/requirements.txt
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
   python web/app.py
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

### Available Ferry Routes

Use these route IDs when configuring your webhook URL:

| Route ID | Route Name |
|----------|------------|
| `sea-bi` | Seattle / Bainbridge Island |
| `sea-br` | Seattle / Bremerton |
| `ed-king` | Edmonds / Kingston |
| `muk-cl` | Mukilteo / Clinton |
| `f-v-s` | Fauntleroy / Vashon |
| `f-s` | Fauntleroy / Southworth |
| `s-v` | Southworth / Vashon |
| `pt-key` | Port Townsend / Coupeville |
| `pd-tal` | Pt. Defiance / Tahlequah |
| `ana-sj` | Anacortes / San Juan Islands |

**Example**: To show Seattle/Bainbridge ferries, use:
```
https://your-domain.com/webhook?route_id=sea-bi
```

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

## Trmnl Plugin Configuration

This section provides detailed instructions for configuring FerryTrmnl as a plugin in the Trmnl dashboard.

### Step 1: Deploy Your Webhook Server

Before configuring Trmnl, you need your FerryTrmnl server running and accessible from the internet:

1. Deploy to a server with a public IP or domain name
2. Set up HTTPS using Let's Encrypt (see [INSTALL.md](INSTALL.md))
3. Verify your webhook is accessible: `curl https://your-domain.com/webhook`

### Step 2: Log in to Trmnl Dashboard

1. Go to [usetrmnl.com](https://usetrmnl.com/) and log in to your account
2. Navigate to your device dashboard

### Step 3: Create a New Private Plugin

1. Click on **"Plugins"** in the left sidebar
2. Click **"Create New Plugin"** or **"Add Plugin"**
3. Select **"Private Plugin"** (for custom polling plugins)

### Step 4: Configure Plugin Settings

Fill in the following fields:

| Setting | Value | Notes |
|---------|-------|-------|
| **Plugin Name** | `Washington State Ferries` | Or any name you prefer |
| **Strategy** | `Polling` | TRMNL fetches data from your server |
| **Polling URL** | `https://your-domain.com/webhook?route_id=sea-bi` | Your server URL with route |
| **Polling Verb** | `GET` | FerryTrmnl uses GET requests |
| **Polling Headers** | *(leave empty)* | No authentication required |
| **Refresh Rate** | `15 minutes` | Recommended: 15-30 minutes |

**Note:** This is a **Polling** plugin (TRMNL pulls data from your server), not a Webhook plugin (where TRMNL would push data to you).

### Step 5: Configure Polling URL with Route

To display a specific ferry route, add the `route_id` query parameter to your polling URL.

**Polling URL Examples:**

| Route | Polling URL |
|-------|-------------|
| Seattle / Bainbridge | `https://your-domain.com/webhook?route_id=sea-bi` |
| Seattle / Bremerton | `https://your-domain.com/webhook?route_id=sea-br` |
| Edmonds / Kingston | `https://your-domain.com/webhook?route_id=ed-king` |
| Mukilteo / Clinton | `https://your-domain.com/webhook?route_id=muk-cl` |
| Fauntleroy / Vashon | `https://your-domain.com/webhook?route_id=f-v-s` |
| Fauntleroy / Southworth | `https://your-domain.com/webhook?route_id=f-s` |
| Southworth / Vashon | `https://your-domain.com/webhook?route_id=s-v` |
| Port Townsend / Coupeville | `https://your-domain.com/webhook?route_id=pt-key` |
| Pt. Defiance / Tahlequah | `https://your-domain.com/webhook?route_id=pd-tal` |
| Anacortes / San Juan Islands | `https://your-domain.com/webhook?route_id=ana-sj` |

**Note:** If you omit `route_id`, the webhook will show all vessels (not recommended for e-ink display).

### Step 6: Save and Test

1. Click **"Save"** to create the plugin
2. Click **"Test Plugin"** or **"Preview"** to verify it works
3. You should see the ferry status HTML rendered

### Step 7: Assign to Device

1. Go to your device settings
2. Add the new plugin to your device's playlist
3. Configure the display duration and position

### Step 8: Verify Display

1. Wait for the next refresh cycle (or force a refresh on your device)
2. Verify the ferry status displays correctly on your Trmnl e-ink screen

### Troubleshooting Trmnl Integration

**Plugin shows "Error" or blank screen:**
- Verify your webhook URL is accessible from the internet
- Check that HTTPS is properly configured
- Test the URL manually: `curl https://your-domain.com/webhook`
- Check server logs for errors

**Data not updating:**
- Verify the polling interval is set correctly
- Check that your WSDOT API key is valid
- Review server logs for API errors

**Display formatting issues:**
- The HTML is optimized for Trmnl e-ink displays
- Ensure no CSS overrides are applied in Trmnl settings

## Production Deployment

### Running with Gunicorn

For production, use Gunicorn instead of the Flask development server:

```bash
cd web
gunicorn -w 4 -b 0.0.0.0:5050 app:app
```

### Docker Deployment

Build and run with Docker:

```bash
# Build from project root
docker build -f deployment/Dockerfile -t ferrytrmnl .

# Run
docker run -p 5050:5050 --env-file .env ferrytrmnl
```

Or use docker-compose:

```bash
cd deployment
docker-compose up -d
```

### Systemd Service

Copy the systemd service file:

```bash
sudo cp deployment/ferrytrmnl.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable ferrytrmnl
sudo systemctl start ferrytrmnl
```

### Nginx Configuration

Copy and configure nginx:

```bash
sudo cp deployment/nginx.conf.example /etc/nginx/sites-available/ferrytrmnl
# Edit and replace ferry.yourdomain.com with your domain
sudo ln -s /etc/nginx/sites-available/ferrytrmnl /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### SSL Certificate with Let's Encrypt

```bash
sudo apt-get install certbot python3-certbot-nginx
sudo certbot --nginx -d ferry.yourdomain.com
```

## CI/CD Deployment

This project includes GitHub Actions workflows for automated deployment. See `.github/workflows/deploy.yml` for the configuration.

### Setting Up CI/CD

1. **Configure GitHub Secrets** in your repository settings:
   - `STAGING_HOST`: Your staging server hostname
   - `STAGING_USER`: SSH username for staging
   - `STAGING_SSH_KEY`: SSH private key for staging
   - `PROD_HOST`: Your production server hostname
   - `PROD_USER`: SSH username for production
   - `PROD_SSH_KEY`: SSH private key for production
   - `WSDOT_API_KEY`: Your WSDOT API key

2. **Deployment Workflow**:
   - Push to `main` branch triggers staging deployment
   - Creating a release/tag triggers production deployment
   - Manual deployment via GitHub Actions UI

## Development

### Running in Development Mode

```bash
# Enable debug mode in .env
FLASK_DEBUG=True

# Run the development server
python web/app.py
```

Or use the quick start script:

```bash
./deployment/run.sh
```

### Running Tests

```bash
python web/test_app.py
```

### Testing the Webhook

```bash
# Test the HTML output
curl http://localhost:5050/webhook

# Test the JSON API
curl http://localhost:5050/api/ferry-status | jq

# Test with a specific route
curl "http://localhost:5050/webhook?route_id=YOUR_ROUTE_ID"
```

## Troubleshooting

### Common Issues

**"API key not configured" error**:
- Make sure you've copied `.env.template` to `.env`
- Verify your `WSDOT_API_KEY` is set correctly in `.env`
- Ensure the `.env` file is in the project root directory

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

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

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
