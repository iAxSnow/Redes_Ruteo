# Web Interface for Routing Project

This directory contains the Flask-based web interface for the routing project.

## Structure

```
Redes_Ruteo/
├── app.py                  # Flask server with main routes and API
├── templates/
│   └── index.html         # Main HTML template
├── static/
│   ├── css/
│   │   └── style.css      # Styling for map and control panel
│   └── js/
│       └── main.js        # Frontend logic for map and threats
├── requirements.txt        # Python dependencies including Flask
└── .env                   # Environment variables (not in repo)
```

## Features

1. **Interactive Map**: Leaflet-based map centered on Santiago, Chile
2. **Geolocation**: Button to center map on user's location
3. **Threat Visualization**: Display threats from multiple sources (Waze, Traffic Calming, Weather)
4. **Layer Control**: Checkbox to show/hide threat markers
5. **Threat Details**: Click on markers to see detailed information in popups
6. **Statistics**: Real-time count of threats by source

## Installation

1. Install Python dependencies:
```bash
cd Redes_Ruteo
pip install -r requirements.txt
```

2. Set up environment variables (create `.env` file):
```
PGHOST=localhost
PGPORT=5432
PGDATABASE=rr
PGUSER=postgres
PGPASSWORD=postgres
```

3. Ensure PostgreSQL database is running with the schema loaded:
```bash
docker-compose up -d
```

## Running the Application

Start the Flask development server:
```bash
cd Redes_Ruteo
python app.py
```

The application will be available at http://localhost:5000

## API Endpoints

### GET /
Returns the main web interface.

### GET /api/threats
Returns all threats from the database as GeoJSON FeatureCollection.

**Response format:**
```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "properties": {
        "ext_id": "...",
        "kind": "incident",
        "subtype": "CLOSURE",
        "severity": 3,
        "source": "waze",
        ...
      },
      "geometry": {
        "type": "Point",
        "coordinates": [-70.65, -33.45]
      }
    }
  ]
}
```

## Development

The application uses:
- **Flask 3.0.0**: Web framework
- **Leaflet 1.9.4**: Interactive map library
- **PostgreSQL + PostGIS**: Spatial database
- **psycopg2**: PostgreSQL adapter for Python

## Next Steps

Future enhancements will include:
- Route calculation interface
- Failure simulation controls
- Real-time route updates based on threats
- Cost function visualization
