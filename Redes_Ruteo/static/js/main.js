// Main JavaScript for the routing web interface

// Global variables
let map;
let threatsLayer;
let userMarker;
let threatsData = null;

// Initialize the map
function initMap() {
    // Create map centered on Santiago, Chile
    map = L.map('map').setView([-33.45, -70.65], 12);
    
    // Add OpenStreetMap tile layer
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    }).addTo(map);
    
    // Initialize threats layer group
    threatsLayer = L.layerGroup().addTo(map);
    
    console.log('Map initialized');
}

// Get user's geolocation
function getUserLocation() {
    const locationInfo = document.getElementById('location-info');
    
    if (!navigator.geolocation) {
        locationInfo.innerHTML = '<p style="color: red;">Geolocalización no soportada</p>';
        locationInfo.classList.add('visible');
        return;
    }
    
    locationInfo.innerHTML = '<p>Obteniendo ubicación...</p>';
    locationInfo.classList.add('visible');
    
    navigator.geolocation.getCurrentPosition(
        (position) => {
            const lat = position.coords.latitude;
            const lng = position.coords.longitude;
            
            // Remove previous marker if exists
            if (userMarker) {
                map.removeLayer(userMarker);
            }
            
            // Add marker for user location
            userMarker = L.marker([lat, lng], {
                icon: L.icon({
                    iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-blue.png',
                    shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/0.7.7/images/marker-shadow.png',
                    iconSize: [25, 41],
                    iconAnchor: [12, 41],
                    popupAnchor: [1, -34],
                    shadowSize: [41, 41]
                })
            }).addTo(map);
            
            userMarker.bindPopup('<b>Mi Ubicación</b>').openPopup();
            
            // Center map on user location
            map.setView([lat, lng], 14);
            
            // Update location info
            locationInfo.innerHTML = `
                <p><strong>Latitud:</strong> ${lat.toFixed(6)}</p>
                <p><strong>Longitud:</strong> ${lng.toFixed(6)}</p>
            `;
        },
        (error) => {
            let errorMsg = 'Error desconocido';
            switch(error.code) {
                case error.PERMISSION_DENIED:
                    errorMsg = 'Permiso de geolocalización denegado';
                    break;
                case error.POSITION_UNAVAILABLE:
                    errorMsg = 'Información de ubicación no disponible';
                    break;
                case error.TIMEOUT:
                    errorMsg = 'Tiempo de espera agotado';
                    break;
            }
            locationInfo.innerHTML = `<p style="color: red;">${errorMsg}</p>`;
        }
    );
}

// Load threats data from API
function loadThreats() {
    const statsInfo = document.getElementById('stats-info');
    statsInfo.innerHTML = '<p>Cargando amenazas...</p>';
    
    fetch('/api/threats')
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            threatsData = data;
            displayThreats(data);
            updateStats(data);
            console.log(`Loaded ${data.features.length} threats`);
        })
        .catch(error => {
            console.error('Error loading threats:', error);
            statsInfo.innerHTML = '<p style="color: red;">Error al cargar amenazas</p>';
        });
}

// Display threats on the map
function displayThreats(data) {
    // Clear existing threats
    threatsLayer.clearLayers();
    
    if (!data || !data.features || data.features.length === 0) {
        console.log('No threats to display');
        return;
    }
    
    // Add GeoJSON layer with custom styling
    L.geoJSON(data, {
        pointToLayer: function(feature, latlng) {
            return createThreatMarker(feature, latlng);
        },
        style: function(feature) {
            return getThreatStyle(feature);
        },
        onEachFeature: function(feature, layer) {
            bindThreatPopup(feature, layer);
        }
    }).addTo(threatsLayer);
    
    // Fit map bounds to threats if possible
    try {
        const bounds = threatsLayer.getBounds();
        if (bounds.isValid()) {
            map.fitBounds(bounds, { maxZoom: 14, padding: [50, 50] });
        }
    } catch(e) {
        console.log('Could not fit bounds:', e);
    }
}

// Create marker for threat based on type
function createThreatMarker(feature, latlng) {
    const props = feature.properties;
    let color, radius;
    
    // Determine color and size based on threat type and severity
    if (props.source === 'waze') {
        if (props.subtype === 'CLOSURE') {
            color = '#d73027';
            radius = 6;
        } else if (props.subtype === 'TRAFFIC_JAM') {
            color = '#fc8d59';
            radius = 5;
        } else {
            color = '#fee090';
            radius = 4;
        }
    } else if (props.source === 'traffic_calming') {
        color = '#4575b4';
        radius = 5;
    } else if (props.source === 'weather') {
        color = '#91bfdb';
        radius = 8;
    } else {
        color = '#999999';
        radius = 4;
    }
    
    return L.circleMarker(latlng, {
        radius: radius,
        fillColor: color,
        color: color,
        weight: 1,
        opacity: 1,
        fillOpacity: 0.7
    });
}

// Get style for line features
function getThreatStyle(feature) {
    const props = feature.properties;
    
    if (feature.geometry.type === 'LineString') {
        if (props.subtype === 'TRAFFIC_JAM') {
            return {
                color: '#fee090',
                weight: 4,
                opacity: 0.8
            };
        }
    }
    
    return {};
}

// Bind popup to threat feature
function bindThreatPopup(feature, layer) {
    const props = feature.properties;
    
    // Determine title based on threat type
    let title = 'Amenaza';
    if (props.source === 'waze') {
        if (props.subtype === 'CLOSURE') {
            title = 'Cierre (Waze)';
        } else if (props.subtype === 'TRAFFIC_JAM') {
            title = 'Tráfico (Waze)';
        } else {
            title = 'Incidente (Waze)';
        }
    } else if (props.source === 'traffic_calming') {
        title = `Reductor de Velocidad (${props.subtype || 'unknown'})`;
    } else if (props.source === 'weather') {
        title = 'Amenaza Climática';
    }
    
    // Build popup content
    let popupContent = `<div class="threat-popup">`;
    popupContent += `<h4>${title}</h4>`;
    
    if (props.description) {
        popupContent += `<p>${props.description}</p>`;
    }
    
    if (props.street) {
        popupContent += `<p><strong>Calle:</strong> ${props.street}</p>`;
    }
    
    if (props.severity !== undefined && props.severity !== null) {
        let severityClass = 'severity-low';
        if (props.severity >= 3) {
            severityClass = 'severity-high';
        } else if (props.severity >= 2) {
            severityClass = 'severity-medium';
        }
        popupContent += `<span class="threat-severity ${severityClass}">Severidad: ${props.severity}</span>`;
    }
    
    popupContent += `</div>`;
    
    layer.bindPopup(popupContent);
}

// Update statistics display
function updateStats(data) {
    const statsInfo = document.getElementById('stats-info');
    
    if (!data || !data.features) {
        statsInfo.innerHTML = '<p>No hay datos disponibles</p>';
        return;
    }
    
    // Count threats by source
    const counts = {
        waze: 0,
        traffic_calming: 0,
        weather: 0,
        total: data.features.length
    };
    
    data.features.forEach(feature => {
        const source = feature.properties.source;
        if (counts[source] !== undefined) {
            counts[source]++;
        }
    });
    
    // Build stats HTML
    let statsHtml = '<div class="stat-item"><span class="stat-label">Total:</span><span class="stat-value">' + counts.total + '</span></div>';
    
    if (counts.waze > 0) {
        statsHtml += '<div class="stat-item"><span class="stat-label">Waze:</span><span class="stat-value">' + counts.waze + '</span></div>';
    }
    
    if (counts.traffic_calming > 0) {
        statsHtml += '<div class="stat-item"><span class="stat-label">Reductores:</span><span class="stat-value">' + counts.traffic_calming + '</span></div>';
    }
    
    if (counts.weather > 0) {
        statsHtml += '<div class="stat-item"><span class="stat-label">Clima:</span><span class="stat-value">' + counts.weather + '</span></div>';
    }
    
    statsInfo.innerHTML = statsHtml;
}

// Toggle threats visibility
function toggleThreats(show) {
    if (show) {
        if (threatsData) {
            displayThreats(threatsData);
        }
    } else {
        threatsLayer.clearLayers();
    }
}

// Event listeners
document.addEventListener('DOMContentLoaded', function() {
    // Initialize map
    initMap();
    
    // Load threats data
    loadThreats();
    
    // Location button
    document.getElementById('locate-btn').addEventListener('click', getUserLocation);
    
    // Show/hide threats checkbox
    document.getElementById('show-threats').addEventListener('change', function(e) {
        toggleThreats(e.target.checked);
    });
});
