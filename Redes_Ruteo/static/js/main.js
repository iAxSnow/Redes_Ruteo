// Main JavaScript for the routing web interface

// Global variables
let map;
let threatsLayer;
let hydrantsLayer;
let userMarker;
let threatsData = null;
let hydrantsData = null;
let hydrantsVisible = false;
let threatVisibility = {
    waze: true,
    weather: true,
    calming: true
};

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
    
    // Initialize hydrants layer group (not added to map initially)
    hydrantsLayer = L.layerGroup();
    
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
            
            // Remove previous user marker if exists
            if (userMarker) {
                map.removeLayer(userMarker);
            }
            
            // Remove previous start marker if exists (we'll replace it with user location)
            if (startMarker) {
                map.removeLayer(startMarker);
            }
            
            // Set user location as start point for routing
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
            
            startMarker.bindPopup('<b>Mi Ubicación (Inicio)</b>').openPopup();
            
            // Set click mode to 'end' so next click sets the destination
            clickMode = 'end';
            
            // Update instruction text
            document.querySelector('.instruction-text').textContent = 'Haz clic en el mapa para seleccionar el punto final';
            
            // Center map on user location
            map.setView([lat, lng], 14);
            
            // Update location info
            locationInfo.innerHTML = `
                <p><strong>Latitud:</strong> ${lat.toFixed(6)}</p>
                <p><strong>Longitud:</strong> ${lng.toFixed(6)}</p>
                <p style="color: green;"><strong>✓ Establecido como punto de inicio</strong></p>
            `;
            
            console.log(`User location set as start point: ${lat.toFixed(6)}, ${lng.toFixed(6)}`);
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
            displayThreats(); // No longer pass data directly
            updateStats(data);
            console.log(`Loaded ${data.features.length} threats`);
        })
        .catch(error => {
            console.error('Error loading threats:', error);
            statsInfo.innerHTML = '<p style="color: red;">Error al cargar amenazas</p>';
        });
}

// Display threats on the map based on visibility state
function displayThreats() {
    // Clear existing threats
    threatsLayer.clearLayers();
    
    if (!threatsData || !threatsData.features || threatsData.features.length === 0) {
        console.log('No threats to display');
        return;
    }

    // Filter features based on current visibility settings
    const visibleFeatures = threatsData.features.filter(feature => {
        const source = feature.properties.source;
        if (source === 'waze' && threatVisibility.waze) return true;
        if (source === 'weather' && threatVisibility.weather) return true;
        if (source === 'traffic_calming' && threatVisibility.calming) return true;
        return false;
    });

    const visibleThreats = {
        type: "FeatureCollection",
        features: visibleFeatures
    };
    
    // Count threats by type for debugging
    const counts = {
        waze: 0,
        traffic_calming: 0,
        weather: 0,
        other: 0
    };
    
    visibleFeatures.forEach(feature => {
        const source = feature.properties.source;
        if (counts[source] !== undefined) {
            counts[source]++;
        } else {
            counts.other++;
        }
    });
    
    console.log(`Displaying threats - Total: ${visibleFeatures.length}, Waze: ${counts.waze}, Traffic Calming: ${counts.traffic_calming}, Weather: ${counts.weather}`);
    
    // Add GeoJSON layer with custom styling
    L.geoJSON(visibleThreats, {
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
}

// Create marker for threat based on type
function createThreatMarker(feature, latlng) {
    const props = feature.properties;
    let color, radius;
    
    // Determine color and size based on threat type and severity
    if (props.source === 'waze') {
        if (props.subtype === 'CLOSURE') {
            color = '#d73027';  // Red for closures
            radius = 6;
        } else if (props.subtype === 'TRAFFIC_JAM') {
            color = '#fc8d59';  // Orange for traffic jams
            radius = 5;
        } else {
            color = '#fee090';  // Yellow for other incidents
            radius = 4;
        }
    } else if (props.source === 'traffic_calming') {
        // Make traffic calming more visible with blue color and larger size
        color = '#4575b4';  // Blue for traffic calming (speed reducers)
        radius = 6;  // Increased from 5 to make more visible
    } else if (props.source === 'weather') {
        color = '#91bfdb';  // Light blue for weather
        radius = 8;
    } else {
        color = '#999999';  // Gray for unknown
        radius = 4;
    }
    
    return L.circleMarker(latlng, {
        radius: radius,
        fillColor: color,
        color: color,
        weight: 2,  // Increased border weight for better visibility
        opacity: 1,
        fillOpacity: 0.8  // Increased from 0.7 for better visibility
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

// Load hydrants data from API
function loadHydrants() {
    const hydrantsInfo = document.getElementById('hydrants-info');
    hydrantsInfo.innerHTML = '<p style="font-size: 12px; color: #666;">Cargando hidrantes...</p>';
    
    fetch('/api/hydrants')
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            hydrantsData = data;
            displayHydrants();
            updateHydrantsInfo(data);
            console.log(`Loaded ${data.features.length} hydrants`);
        })
        .catch(error => {
            console.error('Error loading hydrants:', error);
            hydrantsInfo.innerHTML = '<p style="font-size: 12px; color: red;">Error al cargar hidrantes</p>';
        });
}

// Display hydrants on the map
function displayHydrants() {
    // Clear existing hydrants
    hydrantsLayer.clearLayers();
    
    if (!hydrantsData || !hydrantsData.features || hydrantsData.features.length === 0) {
        console.log('No hydrants to display');
        return;
    }
    
    // Count by status
    const counts = {
        functional: 0,
        not_functional: 0,
        unknown: 0
    };
    
    // Add GeoJSON layer with custom styling
    L.geoJSON(hydrantsData, {
        pointToLayer: function(feature, latlng) {
            const props = feature.properties;
            const functionalStatus = props.functional_status || 'unknown';
            
            // Count by status
            counts[functionalStatus]++;
            
            // Determine color based on status
            let color;
            if (functionalStatus === 'functional') {
                color = '#2ecc71';  // Green for functional
            } else if (functionalStatus === 'not_functional') {
                color = '#e74c3c';  // Red for not functional
            } else {
                color = '#95a5a6';  // Gray for unknown
            }
            
            return L.circleMarker(latlng, {
                radius: 6,
                fillColor: color,
                color: color,
                weight: 2,
                opacity: 0.9,
                fillOpacity: 0.7
            });
        },
        onEachFeature: function(feature, layer) {
            const props = feature.properties;
            
            // Build popup content
            let popupContent = `<div class="hydrant-popup">`;
            popupContent += `<h4>Hidrante</h4>`;
            
            if (props.ext_id) {
                popupContent += `<p><strong>ID:</strong> ${props.ext_id}</p>`;
            }
            
            if (props.status) {
                const statusClass = props.functional_status === 'functional' ? 'status-functional' : 
                                   props.functional_status === 'not_functional' ? 'status-not-functional' : 
                                   'status-unknown';
                popupContent += `<p><strong>Estado:</strong> <span class="${statusClass}">${props.status}</span></p>`;
            }
            
            if (props.provider) {
                popupContent += `<p><strong>Proveedor:</strong> ${props.provider}</p>`;
            }
            
            // Add other relevant properties from the props object
            if (props.UBICACION) {
                popupContent += `<p><strong>Ubicación:</strong> ${props.UBICACION}</p>`;
            }
            
            if (props.MODELO) {
                popupContent += `<p><strong>Modelo:</strong> ${props.MODELO}</p>`;
            }
            
            if (props.DIAMETRO_NOMINAL) {
                popupContent += `<p><strong>Diámetro:</strong> ${props.DIAMETRO_NOMINAL}</p>`;
            }
            
            popupContent += `</div>`;
            
            layer.bindPopup(popupContent);
        }
    }).addTo(hydrantsLayer);
    
    console.log(`Displayed hydrants - Functional: ${counts.functional}, Not Functional: ${counts.not_functional}, Unknown: ${counts.unknown}`);
}

// Update hydrants info display
function updateHydrantsInfo(data) {
    const hydrantsInfo = document.getElementById('hydrants-info');
    
    if (!data || !data.features) {
        hydrantsInfo.innerHTML = '<p style="font-size: 12px; color: #666;">No hay datos disponibles</p>';
        return;
    }
    
    // Count by functional status
    const counts = {
        functional: 0,
        not_functional: 0,
        unknown: 0,
        total: data.features.length
    };
    
    data.features.forEach(feature => {
        const functionalStatus = feature.properties.functional_status || 'unknown';
        if (counts[functionalStatus] !== undefined) {
            counts[functionalStatus]++;
        }
    });
    
    // Build info HTML
    let infoHtml = '<div style="font-size: 12px; color: #666; margin-top: 5px;">';
    infoHtml += `<div>Total: ${counts.total}</div>`;
    infoHtml += `<div><span style="color: #2ecc71;">●</span> Funcionales: ${counts.functional}</div>`;
    infoHtml += `<div><span style="color: #e74c3c;">●</span> No funcionales: ${counts.not_functional}</div>`;
    if (counts.unknown > 0) {
        infoHtml += `<div><span style="color: #95a5a6;">●</span> Desconocido: ${counts.unknown}</div>`;
    }
    infoHtml += '</div>';
    
    hydrantsInfo.innerHTML = infoHtml;
}

// Toggle hydrants visibility
function toggleHydrants() {
    const btn = document.getElementById('toggle-hydrants-btn');
    const legend = document.getElementById('hydrants-legend');
    
    if (hydrantsVisible) {
        // Hide hydrants
        map.removeLayer(hydrantsLayer);
        hydrantsVisible = false;
        btn.textContent = '🚰 Mostrar Hidrantes';
        legend.style.display = 'none';
        console.log('Hydrants hidden');
    } else {
        // Show hydrants
        if (!hydrantsData) {
            // Load hydrants if not already loaded
            loadHydrants();
        }
        map.addLayer(hydrantsLayer);
        hydrantsVisible = true;
        btn.textContent = '🚰 Ocultar Hidrantes';
        legend.style.display = 'block';
        console.log('Hydrants shown');
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
    
    // Check if simulation is requested
    const simulateFailures = document.getElementById('simulate-failures').checked;

    // Call API for all algorithms
    fetch('/api/calculate_route', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            start: { lat: startLatLng.lat, lng: startLatLng.lng },
            end: { lat: endLatLng.lat, lng: endLatLng.lng },
            algorithm: 'all',
            simulate_failures: simulateFailures // Pass simulation flag to backend
        })
    })
    .then(response => {
        if (!response.ok) {
            return response.json().then(data => {
                throw new Error(data.error || 'Error al calcular rutas');
            }).catch(err => {
                // If response is not JSON, throw generic error
                if (err instanceof SyntaxError) {
                    throw new Error('Error al calcular rutas (código: ' + response.status + ')');
                }
                throw err;
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
            // Check if we have valid route data with geometry
            if (routeData && routeData.route_geojson && routeData.route_geojson.geometry) {
                const checkbox = document.getElementById(`show-${algorithmKey.replace(/_/g, '-')}`);
                const isVisible = checkbox ? checkbox.checked : true;
                
                try {
                    const layer = L.geoJSON(routeData.route_geojson, {
                        style: {
                            color: routeColors[algorithmKey],
                            weight: 4,
                            opacity: isVisible ? 0.7 : 0
                        }
                    });
                    
                    if (isVisible) {
                        layer.addTo(map);
                        // Only add bounds for visible routes
                        const bounds = layer.getBounds();
                        if (bounds.isValid()) {
                            allBounds.push(bounds);
                        }
                    }
                    
                    routeLayers[algorithmKey] = layer;
                } catch (error) {
                    console.error(`Error rendering ${algorithmKey} route:`, error);
                }
            }
        });
        
        // Fit map to visible routes if we have valid bounds
        if (allBounds.length > 0) {
            try {
                const combinedBounds = allBounds.reduce((acc, bounds) => acc.extend(bounds), allBounds[0]);
                if (combinedBounds.isValid()) {
                    map.fitBounds(combinedBounds, { padding: [50, 50] });
                }
            } catch (error) {
                console.warn('Could not fit map bounds:', error);
            }
        } else {
            // If no valid routes, fit to start and end markers
            if (startMarker && endMarker) {
                const markerBounds = L.latLngBounds([startMarker.getLatLng(), endMarker.getLatLng()]);
                map.fitBounds(markerBounds, { padding: [50, 50] });
            }
        }
        
        // Display route info only for selected algorithms
        let routeInfoHtml = '<h4>Resultados de Ruteo</h4>';
        let routesDisplayed = 0;
        
        Object.keys(data).forEach(algorithmKey => {
            const routeData = data[algorithmKey];
            if (routeData && routeData.route_geojson && routeData.route_geojson.properties) {
                const checkbox = document.getElementById(`show-${algorithmKey.replace(/_/g, '-')}`);
                const isVisible = checkbox ? checkbox.checked : true;
                
                if (isVisible) {
                    const lengthKm = (routeData.route_geojson.properties.total_length_m / 1000).toFixed(2);
                    const color = routeColors[algorithmKey];
                    
                    routeInfoHtml += `
                        <div class="route-metric">
                            <span class="metric-label" style="color: ${color}">⬤ ${routeData.algorithm}:</span>
                            <span class="metric-value">${lengthKm} km (${routeData.compute_time_ms.toFixed(2)} ms)</span>
                        </div>
                    `;
                    routesDisplayed++;
                }
            }
        });
        
        if (routesDisplayed === 0) {
            routeInfoHtml += '<p style="color: orange;">No se encontraron rutas o todas están ocultas</p>';
        }
        
        routeInfo.innerHTML = routeInfoHtml;
        
        console.log('Routes calculated successfully');
    })
    .catch(error => {
        console.error('Error calculating routes:', error);
        routeInfo.innerHTML = `<p style="color: red;"><strong>Error:</strong> ${error.message}</p>`;
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

// Highlight failed threats
function highlightFailedThreats() {
    // This would ideally highlight the specific threats that failed
    // For now, we'll update the display based on the showOnlyActive flag
    if (showOnlyActive) {
        displayThreats();
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
    
    // Hydrants button
    document.getElementById('toggle-hydrants-btn').addEventListener('click', toggleHydrants);
    
    // Threat layer checkboxes
    document.querySelectorAll('.threat-checkbox').forEach(checkbox => {
        checkbox.addEventListener('change', function(e) {
            const threatType = e.target.dataset.threat; // 'waze', 'weather', 'calming'
            threatVisibility[threatType] = e.target.checked;
            displayThreats(); // Re-render threats with new visibility
        });
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
    
    // Simulation checkbox - now just triggers a recalculation
    document.getElementById('simulate-failures').addEventListener('change', function(e) {
        // If start and end points are set, recalculate the route with the new simulation setting
        if (startMarker && endMarker) {
            calculateRoute();
        }
    });
    
    document.getElementById('show-only-active-threats').addEventListener('change', function(e) {
        showOnlyActive = e.target.checked;
        displayThreats();
    });
});
