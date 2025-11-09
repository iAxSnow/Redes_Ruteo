// Main JavaScript for the routing web interface

// Global variables
let map;
let threatsLayer;
let userMarker;
let threatsData = null;

// Routing variables
let startMarker = null;
let endMarker = null;
let routeLayers = {
    dijkstra_dist: null,
    dijkstra_prob: null,
    astar_prob: null,
    filtered_dijkstra: null
};
let clickMode = 'start'; // 'start' or 'end'

// Simulation variables
let failedThreats = [];
let showOnlyActive = false;

// Route colors
const routeColors = {
    dijkstra_dist: '#e74c3c',      // Red
    dijkstra_prob: '#3498db',      // Blue
    astar_prob: '#f39c12',         // Orange
    filtered_dijkstra: '#27ae60'   // Green
};

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
    
    // Add click handler for route point selection
    map.on('click', onMapClick);
    
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

// Map click handler for route point selection
function onMapClick(e) {
    const lat = e.latlng.lat;
    const lng = e.latlng.lng;
    
    if (clickMode === 'start') {
        // Set start point
        if (startMarker) {
            map.removeLayer(startMarker);
        }
        
        startMarker = L.marker([lat, lng], {
            icon: L.icon({
                iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-green.png',
                shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/0.7.7/images/marker-shadow.png',
                iconSize: [25, 41],
                iconAnchor: [12, 41],
                popupAnchor: [1, -34],
                shadowSize: [41, 41]
            })
        }).addTo(map);
        
        startMarker.bindPopup('<b>Punto de Inicio</b>').openPopup();
        clickMode = 'end';
        
        // Update instruction
        document.querySelector('.instruction-text').textContent = 'Haz clic en el mapa para seleccionar el punto final';
        
    } else if (clickMode === 'end') {
        // Set end point
        if (endMarker) {
            map.removeLayer(endMarker);
        }
        
        endMarker = L.marker([lat, lng], {
            icon: L.icon({
                iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-red.png',
                shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/0.7.7/images/marker-shadow.png',
                iconSize: [25, 41],
                iconAnchor: [12, 41],
                popupAnchor: [1, -34],
                shadowSize: [41, 41]
            })
        }).addTo(map);
        
        endMarker.bindPopup('<b>Punto Final</b>').openPopup();
        
        // Enable calculate button
        document.getElementById('calculate-route-btn').disabled = false;
        
        // Update instruction
        document.querySelector('.instruction-text').textContent = 'Haz clic en "Calcular Ruta Óptima"';
    }
}

// Calculate route using API
function calculateRoute() {
    if (!startMarker || !endMarker) {
        alert('Por favor selecciona puntos de inicio y fin');
        return;
    }
    
    const routeInfo = document.getElementById('route-info');
    routeInfo.innerHTML = '<p>Calculando rutas...</p>';
    routeInfo.classList.add('visible');
    
    // Get coordinates
    const startLatLng = startMarker.getLatLng();
    const endLatLng = endMarker.getLatLng();
    
    // Call API for all algorithms
    fetch('/api/calculate_route', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            start: { lat: startLatLng.lat, lng: startLatLng.lng },
            end: { lat: endLatLng.lat, lng: endLatLng.lng },
            algorithm: 'all'
        })
    })
    .then(response => {
        if (!response.ok) {
            return response.json().then(data => {
                throw new Error(data.error || 'Error al calcular rutas');
            });
        }
        return response.json();
    })
    .then(data => {
        // Clear previous routes
        Object.keys(routeLayers).forEach(key => {
            if (routeLayers[key]) {
                map.removeLayer(routeLayers[key]);
                routeLayers[key] = null;
            }
        });
        
        // Draw each route on map with different colors
        let allBounds = [];
        Object.keys(data).forEach(algorithmKey => {
            const routeData = data[algorithmKey];
            if (routeData && routeData.route_geojson) {
                const checkbox = document.getElementById(`show-${algorithmKey.replace(/_/g, '-')}`);
                const isVisible = checkbox ? checkbox.checked : true;
                
                const layer = L.geoJSON(routeData.route_geojson, {
                    style: {
                        color: routeColors[algorithmKey],
                        weight: 4,
                        opacity: isVisible ? 0.7 : 0
                    }
                });
                
                if (isVisible) {
                    layer.addTo(map);
                }
                
                routeLayers[algorithmKey] = layer;
                allBounds.push(layer.getBounds());
            }
        });
        
        // Fit map to all routes
        if (allBounds.length > 0) {
            const combinedBounds = allBounds.reduce((acc, bounds) => acc.extend(bounds), allBounds[0]);
            map.fitBounds(combinedBounds, { padding: [50, 50] });
        }
        
        // Display route info for all algorithms
        let routeInfoHtml = '<h4>Resultados de Ruteo</h4>';
        
        Object.keys(data).forEach(algorithmKey => {
            const routeData = data[algorithmKey];
            if (routeData && routeData.route_geojson) {
                const lengthKm = (routeData.route_geojson.properties.total_length_m / 1000).toFixed(2);
                const color = routeColors[algorithmKey];
                
                routeInfoHtml += `
                    <div class="route-metric">
                        <span class="metric-label" style="color: ${color}">⬤ ${routeData.algorithm}:</span>
                        <span class="metric-value">${lengthKm} km (${routeData.compute_time_ms.toFixed(2)} ms)</span>
                    </div>
                `;
            }
        });
        
        routeInfo.innerHTML = routeInfoHtml;
        
        console.log('Routes calculated successfully');
    })
    .catch(error => {
        console.error('Error calculating routes:', error);
        routeInfo.innerHTML = `<p style="color: red;">Error: ${error.message}</p>`;
    });
}

// Clear route and markers
function clearRoute() {
    // Remove markers
    if (startMarker) {
        map.removeLayer(startMarker);
        startMarker = null;
    }
    
    if (endMarker) {
        map.removeLayer(endMarker);
        endMarker = null;
    }
    
    // Remove all routes
    Object.keys(routeLayers).forEach(key => {
        if (routeLayers[key]) {
            map.removeLayer(routeLayers[key]);
            routeLayers[key] = null;
        }
    });
    
    // Reset click mode
    clickMode = 'start';
    
    // Disable calculate button
    document.getElementById('calculate-route-btn').disabled = true;
    
    // Hide route info
    const routeInfo = document.getElementById('route-info');
    routeInfo.classList.remove('visible');
    
    // Reset instruction
    document.querySelector('.instruction-text').textContent = 'Haz clic en el mapa para seleccionar inicio y fin';
}

// Toggle route visibility
function toggleRouteVisibility(algorithmKey, visible) {
    const layer = routeLayers[algorithmKey];
    if (layer) {
        if (visible) {
            layer.addTo(map);
            layer.setStyle({ opacity: 0.7 });
        } else {
            map.removeLayer(layer);
        }
    }
}

// Simulate failures
function simulateFailures() {
    const simulationInfo = document.getElementById('simulation-info');
    simulationInfo.innerHTML = '<p>Simulando fallas...</p>';
    simulationInfo.classList.add('visible');
    
    fetch('/api/simulate_failures', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        }
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Error al simular fallas');
        }
        return response.json();
    })
    .then(data => {
        failedThreats = data.failed_edges || [];
        
        simulationInfo.innerHTML = `
            <div class="route-metric">
                <span class="metric-label">Elementos fallados:</span>
                <span class="metric-value">${data.total_failed}</span>
            </div>
            <div class="route-metric">
                <span class="metric-label">Arcos:</span>
                <span class="metric-value">${data.failed_edges.length}</span>
            </div>
            <div class="route-metric">
                <span class="metric-label">Nodos:</span>
                <span class="metric-value">${data.failed_nodes.length}</span>
            </div>
        `;
        
        // Highlight failed threats on map
        highlightFailedThreats();
        
        console.log(`Simulation: ${data.total_failed} elements failed`);
    })
    .catch(error => {
        console.error('Error simulating failures:', error);
        simulationInfo.innerHTML = `<p style="color: red;">Error: ${error.message}</p>`;
    });
}

// Highlight failed threats
function highlightFailedThreats() {
    // This would ideally highlight the specific threats that failed
    // For now, we'll update the display based on the showOnlyActive flag
    if (showOnlyActive) {
        displayThreats(threatsData);
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
    
    // Route calculation buttons
    document.getElementById('calculate-route-btn').addEventListener('click', calculateRoute);
    document.getElementById('clear-route-btn').addEventListener('click', clearRoute);
    
    // Route visibility checkboxes
    document.querySelectorAll('.route-checkbox').forEach(checkbox => {
        checkbox.addEventListener('change', function(e) {
            const algorithmKey = e.target.id.replace('show-', '').replace(/-/g, '_');
            toggleRouteVisibility(algorithmKey, e.target.checked);
        });
    });
    
    // Simulation checkboxes
    document.getElementById('simulate-failures').addEventListener('change', function(e) {
        if (e.target.checked) {
            simulateFailures();
        } else {
            // Clear simulation
            failedThreats = [];
            const simulationInfo = document.getElementById('simulation-info');
            simulationInfo.classList.remove('visible');
            highlightFailedThreats();
        }
    });
    
    document.getElementById('show-only-active-threats').addEventListener('change', function(e) {
        showOnlyActive = e.target.checked;
        displayThreats(threatsData);
    });
});
