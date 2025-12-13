# Testing Guide for FerryTrmnl

This guide explains how to test the FerryTrmnl webhook server.

## Running Tests

### Automated Tests

Run the included test suite:

```bash
python3 test_app.py
```

The test suite includes:
- Import and initialization tests
- Route registration tests
- Webhook endpoint tests with mock data
- API endpoint tests
- Data formatting tests

### Manual Testing

#### 1. Start the Development Server

```bash
# Make sure .env is configured with your API key
python3 app.py
```

Or use the quick start script:

```bash
./run.sh
```

#### 2. Test Basic Endpoints

**Health Check:**
```bash
curl http://localhost:5050/health
```

Expected response:
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00.123456"
}
```

**Service Information:**
```bash
curl http://localhost:5050/
```

Expected response:
```json
{
  "service": "Washington State Ferry Status Webhook",
  "version": "1.0.0",
  "endpoints": {
    "/webhook": "Main webhook endpoint for Trmnl (GET)",
    "/api/ferry-status": "JSON API endpoint (GET)",
    "/health": "Health check endpoint"
  },
  "documentation": "https://github.com/cdibona/FerryTrmnl"
}
```

#### 3. Test Webhook Endpoint

**HTML Output (for Trmnl):**
```bash
curl http://localhost:5050/webhook
```

This returns HTML formatted for e-ink display.

**Save to file for inspection:**
```bash
curl http://localhost:5050/webhook > ferry_output.html
# Open ferry_output.html in a browser
```

**With specific route:**
```bash
curl "http://localhost:5050/webhook?route_id=YOUR_ROUTE_ID"
```

#### 4. Test JSON API Endpoint

```bash
curl http://localhost:5050/api/ferry-status | jq
```

Or with a specific route:
```bash
curl "http://localhost:5050/api/ferry-status?route_id=YOUR_ROUTE_ID" | jq
```

## Testing with Docker

### Build and Run

```bash
# Build the Docker image
docker build -t ferrytrmnl .

# Run with .env file
docker run -p 5050:5050 --env-file .env ferrytrmnl
```

Or use docker-compose:

```bash
docker-compose up --build
```

### Test Health Check

```bash
# Check if container is healthy
docker ps

# Should show "healthy" in the STATUS column
```

### View Logs

```bash
docker-compose logs -f
```

## Testing API Integration

### Test WSDOT API Connection

```bash
# Test that your API key works
curl "https://www.wsdot.wa.gov/ferries/api/vessels/rest/vessellocations?apiaccesscode=YOUR_API_KEY"
```

### Mock API Responses

For development without hitting the WSDOT API, you can modify `app.py` temporarily:

```python
def fetch_ferry_status(route_id: Optional[str] = None) -> Dict[str, Any]:
    """Mock version for testing."""
    return {
        "vessels": [
            {
                "VesselName": "Test Ferry",
                "InService": "True",
                "AtDock": "Seattle Terminal",
                "LeftDock": "10:00 AM"
            }
        ],
        "route_info": {
            "RouteName": "Seattle - Bainbridge",
            "Description": "Test Route"
        },
        "timestamp": datetime.now().isoformat()
    }
```

## Testing Production Deployment

### Test Gunicorn

```bash
gunicorn -w 4 -b 127.0.0.1:5050 app:app
```

Then test endpoints as above.

### Test with Nginx Proxy

After setting up nginx:

```bash
# Test through nginx
curl https://ferry.yourdomain.com/health

# Check nginx logs
sudo tail -f /var/log/nginx/ferrytrmnl_access.log
```

### Test Systemd Service

```bash
# Start service
sudo systemctl start ferrytrmnl

# Check status
sudo systemctl status ferrytrmnl

# View logs
sudo journalctl -u ferrytrmnl -f

# Test endpoints
curl http://localhost:5050/health
```

## Load Testing (Optional)

For production systems, consider load testing:

### Using Apache Bench (ab)

```bash
# Install ab
sudo apt-get install apache2-utils

# Test 100 requests with 10 concurrent
ab -n 100 -c 10 http://localhost:5050/health
```

### Using wrk

```bash
# Install wrk
sudo apt-get install wrk

# Test for 30 seconds with 10 threads and 100 connections
wrk -t10 -c100 -d30s http://localhost:5050/health
```

## Testing Trmnl Integration

### 1. Set Up Trmnl Webhook

1. Log in to your Trmnl account
2. Create a new webhook plugin
3. Enter your webhook URL
4. Set refresh interval

### 2. Test Webhook Manually

Before connecting to Trmnl, test that your webhook returns proper HTML:

```bash
curl http://localhost:5050/webhook > test.html
open test.html  # macOS
xdg-open test.html  # Linux
start test.html  # Windows
```

Verify the HTML displays correctly in a browser.

### 3. Test Trmnl Connection

Use Trmnl's "Test Plugin" feature to verify the webhook works from their servers.

### 4. Monitor Logs

Watch for Trmnl requests:

```bash
sudo journalctl -u ferrytrmnl -f
# or
sudo tail -f /var/log/ferrytrmnl/access.log
```

## Troubleshooting Tests

### Tests Fail to Import App

Make sure you're in the correct directory:
```bash
cd /path/to/FerryTrmnl
python3 test_app.py
```

### API Connection Errors

1. Verify your API key is correct in `.env`
2. Test API key directly with curl
3. Check internet connectivity
4. Verify WSDOT API is operational

### Port Already in Use

```bash
# Find process using port 5050
sudo lsof -i :5050

# Kill the process
kill -9 <PID>

# Or use a different port in .env
FLASK_PORT=5051
```

### Docker Tests Fail

```bash
# Check Docker logs
docker-compose logs

# Rebuild without cache
docker-compose build --no-cache

# Check if port is available
netstat -tlnp | grep 5050
```

## Continuous Testing

For ongoing development, consider:

1. **Watch mode**: Use a tool like `watchdog` to run tests on file changes
2. **Pre-commit hooks**: Run tests before commits
3. **CI/CD**: Set up GitHub Actions for automated testing

## Test Checklist

Before deploying to production:

- [ ] All automated tests pass
- [ ] Manual endpoint tests successful
- [ ] WSDOT API integration works
- [ ] HTML output displays correctly
- [ ] JSON API returns valid data
- [ ] Health check responds
- [ ] Docker container builds and runs
- [ ] Gunicorn serves requests
- [ ] Nginx proxy works (if used)
- [ ] Systemd service starts and restarts
- [ ] Logs are being written
- [ ] Trmnl can fetch webhook successfully
- [ ] Display updates on Trmnl device

## Need Help?

If tests fail or you encounter issues:

1. Check the logs for error messages
2. Review the TROUBLESHOOTING section in README.md
3. Open an issue on GitHub with:
   - Test output
   - Log messages
   - Your environment details
