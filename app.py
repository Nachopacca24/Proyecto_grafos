import pickle
import os
import osmnx as ox
import folium
import math
import random
from collections import deque
from shapely.geometry import Point, Polygon
import networkx as nx
from flask import Flask, jsonify, request
from datetime import datetime
import json

app = Flask(__name__)

GRAFO_FILE = "grafo_guardado_v3.pkl"

def obtener_modo_trafico_actual():
    hora_actual = datetime.now().hour
    if 6 <= hora_actual < 9 or 17 <= hora_actual < 20:
        return "peso_horapico", "Hora Pico"
    elif 9 <= hora_actual < 17:
        return "peso_normal", "Tráfico Normal"
    else:
        return "peso_libre", "Hora Libre"

def cargar_grafo():
    if os.path.exists(GRAFO_FILE):
        print("Cargando grafo desde archivo...")
        with open(GRAFO_FILE, 'rb') as f:
            return pickle.load(f)
    return None

def guardar_grafo(data):
    print("Guardando grafo...")
    with open(GRAFO_FILE, 'wb') as f:
        pickle.dump(data, f)

def distancia_geodesica(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(delta_lambda/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

def crear_grafo():
    coor_latlon = [
        (14.595992916589651, -90.45998036866868),
        (14.595125835501939, -90.4612230889126),
        (14.596128175354478, -90.46895110645838),
        (14.594658980099597, -90.47868828889479),
        (14.595038649909512, -90.48309807332323),
        (14.60135625944328, -90.49847739249991),
        (14.60425684591137, -90.48940590688885),
        (14.608938645353811, -90.4916152886364),
        (14.613813239360029, -90.49218024329048),
        (14.610335736317806, -90.49927356176848),
        (14.607070781643843, -90.49988559587275),
        (14.607192269188966, -90.50537820975624),
        (14.620813635477512, -90.49349847057412),
        (14.62025716603483, -90.47364421713812),
        (14.617402360485203, -90.47436610351755),
        (14.611636886631626, -90.475081016863),
        (14.60604519507612, -90.46863390250498),
        (14.599059515184518, -90.46270187944435)
    ]

    coor = [(lon, lat) for lat, lon in coor_latlon]
    pts = [Point(lon, lat) for (lon, lat) in coor]
    cx = sum(p.x for p in pts) / len(pts)
    cy = sum(p.y for p in pts) / len(pts)

    def angle(p):
        return math.atan2(p.y - cy, p.x - cx)

    pts_sorted = sorted(pts, key=angle)
    poly = Polygon([(p.x, p.y) for p in pts_sorted]).buffer(0.002)

    print("Descargando grafo desde OSM...")
    G = ox.graph_from_polygon(poly, network_type="drive")
    G = G.to_undirected()
    G = nx.Graph(G)
    print(f"Grafo descargado: {len(G.nodes)} nodos, {len(G.edges)} aristas")

    # Datos de aristas para el frontend
    edges_data = []

    for u, v, data in G.edges(data=True):
        if "length" not in data or data["length"] == 0:
            lat1, lon1 = G.nodes[u]["y"], G.nodes[u]["x"]
            lat2, lon2 = G.nodes[v]["y"], G.nodes[v]["x"]
            data["length"] = distancia_geodesica(lat1, lon1, lat2, lon2)
        
        d = data["length"]
        data["peso_normal"] = d
        congestion = random.uniform(1.5, 3.5)
        data["peso_horapico"] = d * congestion
        data["peso_libre"] = d * 0.7
        data["congestion"] = congestion
        
        # Guardar para frontend
        lat1, lon1 = G.nodes[u]["y"], G.nodes[u]["x"]
        lat2, lon2 = G.nodes[v]["y"], G.nodes[v]["x"]
        edges_data.append({
            "coords": [[lat1, lon1], [lat2, lon2]],
            "congestion": congestion
        })

    POIS_USUARIO = [
        (14.61119100485585, -90.48580778897217),
        (14.618944838124076, -90.48081377973796),
        (14.618582412910866, -90.48420743608744),
        (14.612142341881135, -90.49900242733989),
        (14.614371861881606, -90.49132981324811),
        (14.600884567886517, -90.47892424008336),
        (14.596326378463905, -90.48123964433496),
        (14.597073268975551, -90.48314644782701),
        (14.60100190653431, -90.48819584711718),
        (14.608097113251654, -90.4832018378643)
    ]

    poi_mapping = {}
    for i, (lat, lon) in enumerate(POIS_USUARIO, start=1):
        nombre = f"POI_{i}"
        nearest = ox.distance.nearest_nodes(G, X=lon, Y=lat)
        poi_mapping[nombre] = nearest

    print(f"POIs mapeados: {len(poi_mapping)}")
    return G, poi_mapping, edges_data

def formato_tiempo(minutos):
    if minutos < 1:
        return f"{int(minutos * 60)} segundos"
    elif minutos < 60:
        mins = int(minutos)
        segs = int((minutos - mins) * 60)
        return f"{mins} min {segs} seg" if segs > 0 else f"{mins} minutos"
    else:
        return f"{int(minutos // 60)} h {int(minutos % 60)} min"

def calcular_ruta(G, poi_mapping, origen, destino, modo_trafico="peso_horapico"):
    try:
        nodo_origen = poi_mapping.get(origen)
        nodo_destino = poi_mapping.get(destino)
        
        if nodo_origen is None or nodo_destino is None:
            return None
        
        ruta = nx.shortest_path(G, nodo_origen, nodo_destino, weight=modo_trafico)
        
        distancia_total = 0
        coords_ruta = []
        
        for i, nodo in enumerate(ruta):
            lat = G.nodes[nodo].get("y")
            lon = G.nodes[nodo].get("x")
            if lat is not None and lon is not None:
                coords_ruta.append([float(lat), float(lon)])
            
            if i < len(ruta) - 1:
                siguiente = ruta[i + 1]
                if G.has_edge(nodo, siguiente):
                    edge_data = G.get_edge_data(nodo, siguiente)
                    if edge_data and "length" in edge_data:
                        distancia_total += edge_data["length"]

        if len(coords_ruta) < 2:
            return None

        velocidades = {"peso_horapico": 15, "peso_normal": 30, "peso_libre": 50}
        velocidad = velocidades.get(modo_trafico, 30)
        tiempo_minutos = (distancia_total / 1000) / velocidad * 60

        return {
            "coordenadas": coords_ruta,
            "distancia_metros": distancia_total,
            "distancia_km": distancia_total / 1000,
            "tiempo_minutos": tiempo_minutos,
            "tiempo_formato": formato_tiempo(tiempo_minutos)
        }
    except:
        return None

def calcular_ruta_con_parada(G, poi_mapping, origen, parada, destino, modo_trafico):
    try:
        ruta1 = calcular_ruta(G, poi_mapping, origen, parada, modo_trafico)
        ruta2 = calcular_ruta(G, poi_mapping, parada, destino, modo_trafico)
        
        if ruta1 is None or ruta2 is None:
            return None
        
        coords_combinadas = ruta1["coordenadas"][:-1] + ruta2["coordenadas"]
        distancia_total = ruta1["distancia_metros"] + ruta2["distancia_metros"]
        tiempo_total = ruta1["tiempo_minutos"] + ruta2["tiempo_minutos"]
        
        return {
            "coordenadas": coords_combinadas,
            "distancia_metros": distancia_total,
            "distancia_km": distancia_total / 1000,
            "tiempo_minutos": tiempo_total,
            "tiempo_formato": formato_tiempo(tiempo_total)
        }
    except:
        return None

def calcular_ruta_con_obstaculo(G, poi_mapping, origen, destino, obstaculo, modo_trafico, radio_metros=200):
    try:
        import math
        
        nodo_origen = poi_mapping.get(origen)
        nodo_destino = poi_mapping.get(destino)
        nodo_obstaculo = poi_mapping.get(obstaculo)
        
        if nodo_origen is None or nodo_destino is None or nodo_obstaculo is None:
            return calcular_ruta(G, poi_mapping, origen, destino, modo_trafico)
        
        lat_obs = G.nodes[nodo_obstaculo].get("y")
        lon_obs = G.nodes[nodo_obstaculo].get("x")
        
        if lat_obs is None or lon_obs is None:
            return calcular_ruta(G, poi_mapping, origen, destino, modo_trafico)
        
        G_temp = G.copy()
        
        nodos_a_evitar = []
        for nodo in G_temp.nodes():
            lat = G_temp.nodes[nodo].get("y")
            lon = G_temp.nodes[nodo].get("x")
            if lat is not None and lon is not None:
                dist_lat = (lat - lat_obs) * 111000
                dist_lon = (lon - lon_obs) * 111000 * math.cos(math.radians(lat_obs))
                dist = math.sqrt(dist_lat**2 + dist_lon**2)
                if dist < radio_metros and nodo != nodo_origen and nodo != nodo_destino:
                    nodos_a_evitar.append(nodo)
        
        for nodo in nodos_a_evitar:
            vecinos = list(G_temp.neighbors(nodo))
            for vecino in vecinos:
                if G_temp.has_edge(nodo, vecino):
                    G_temp.remove_edge(nodo, vecino)
                if G_temp.has_edge(vecino, nodo):
                    G_temp.remove_edge(vecino, nodo)
        
        ruta = nx.shortest_path(G_temp, nodo_origen, nodo_destino, weight=modo_trafico)
        
        distancia_total = 0
        coords_ruta = []
        
        for i, nodo in enumerate(ruta):
            lat = G_temp.nodes[nodo].get("y")
            lon = G_temp.nodes[nodo].get("x")
            if lat is not None and lon is not None:
                coords_ruta.append([float(lat), float(lon)])
            
            if i < len(ruta) - 1:
                siguiente = ruta[i + 1]
                if G_temp.has_edge(nodo, siguiente):
                    edge_data = G_temp.get_edge_data(nodo, siguiente)
                    if edge_data and "length" in edge_data:
                        distancia_total += edge_data["length"]
        
        if len(coords_ruta) < 2:
            return calcular_ruta(G, poi_mapping, origen, destino, modo_trafico)
        
        velocidades = {"peso_horapico": 15, "peso_normal": 30, "peso_libre": 50}
        velocidad = velocidades.get(modo_trafico, 30)
        tiempo_minutos = (distancia_total / 1000) / velocidad * 60
        
        return {
            "coordenadas": coords_ruta,
            "distancia_metros": distancia_total,
            "distancia_km": distancia_total / 1000,
            "tiempo_minutos": tiempo_minutos,
            "tiempo_formato": formato_tiempo(tiempo_minutos)
        }
    except:
        return calcular_ruta(G, poi_mapping, origen, destino, modo_trafico)


# Inicializar
print("Inicializando aplicación...")
data = cargar_grafo()
if data is None:
    G, poi_mapping, edges_data = crear_grafo()
    guardar_grafo((G, poi_mapping, edges_data))
else:
    G, poi_mapping, edges_data = data
    print("Grafo cargado desde archivo")

POIS_USUARIO = [
    (14.61119100485585, -90.48580778897217),
    (14.618944838124076, -90.48081377973796),
    (14.618582412910866, -90.48420743608744),
    (14.612142341881135, -90.49900242733989),
    (14.614371861881606, -90.49132981324811),
    (14.600884567886517, -90.47892424008336),
    (14.596326378463905, -90.48123964433496),
    (14.597073268975551, -90.48314644782701),
    (14.60100190653431, -90.48819584711718),
    (14.608097113251654, -90.4832018378643)
]

@app.route('/')
def index():
    modo_actual, nombre_modo = obtener_modo_trafico_actual()
    hora_actual = datetime.now().strftime("%H:%M")
    
    cx = sum(lon for lat, lon in POIS_USUARIO) / len(POIS_USUARIO)
    cy = sum(lat for lat, lon in POIS_USUARIO) / len(POIS_USUARIO)
    
    # Convertir edges_data a JSON para JavaScript
    edges_json = json.dumps(edges_data)
    pois_json = json.dumps(POIS_USUARIO)
    
    html = f'''
<!DOCTYPE html>
<html>
<head>
    <title>Calculador de Rutas</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <style>
        body {{ margin: 0; padding: 0; }}
        #map {{ position: absolute; top: 0; bottom: 0; width: 100%; }}
        #panel {{
            position: absolute; top: 10px; left: 10px; z-index: 1000;
            background: white; padding: 15px; border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.3); font-family: Arial;
            max-width: 260px;
        }}
        select, button {{ width: 100%; padding: 8px; margin: 4px 0; border-radius: 4px; }}
        select {{ border: 1px solid #ccc; }}
        button {{ background: #007bff; color: white; border: none; cursor: pointer; font-weight: bold; }}
        button:hover {{ background: #0056b3; }}
        #info {{ margin-top: 10px; padding: 10px; background: #f8f9fa; border-radius: 4px; display: none; }}
        .legend {{
            position: absolute; bottom: 20px; right: 10px; z-index: 1000;
            background: white; padding: 10px; border-radius: 5px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.3); font-family: Arial; font-size: 12px;
        }}
        .legend-item {{ display: flex; align-items: center; margin: 3px 0; }}
        .legend-color {{ width: 20px; height: 10px; margin-right: 8px; border-radius: 2px; }}
    </style>
</head>
<body>
    <div id="map"></div>
    
    <div id="panel">
        <h3 style="margin:0 0 5px;">🚗 Calculador de Rutas</h3>
        <p style="font-size:11px;color:#666;margin:0 0 8px;">
            Hora: <b>{hora_actual}</b> - <span id="modoActual" style="color:{"#cc0000" if "Pico" in nombre_modo else "#00aa00"}">{nombre_modo}</span>
        </p>
        <div style="background:#f5f5f5;padding:6px;border-radius:4px;margin-bottom:8px;font-size:10px;">
            🔴 Pico: 6-9h, 17-20h | 🟡 Normal: 9-17h | 🟢 Libre: 20-6h
        </div>
        
        <label style="font-size:12px;"><b>Origen:</b></label>
        <select id="origen">
            {"".join([f'<option value="POI_{i}">Punto {i}</option>' for i in range(1, 11)])}
        </select>
        
        <label style="font-size:12px;"><b>Destino:</b></label>
        <select id="destino">
            {"".join([f'<option value="POI_{i}" {"selected" if i==6 else ""}>Punto {i}</option>' for i in range(1, 11)])}
        </select>
        
        <label style="font-size:12px;"><b>Tipo de Ruta:</b></label>
        <select id="tipo_ruta" onchange="actualizarTipoRuta()">
            <option value="normal">Ruta Normal</option>
            <option value="con_parada">Ruta con Parada</option>
            <option value="con_obstaculo">Ruta con Obstáculo</option>
        </select>
        
        <div id="punto_c_container" style="display:none;">
            <label style="font-size:12px;"><b id="punto_c_label">Punto C:</b></label>
            <select id="punto_c">
                {"".join([f'<option value="POI_{i}">Punto {i}</option>' for i in range(1, 11)])}
            </select>
        </div>
        
        <label style="font-size:12px;"><b>Modo de Tráfico:</b></label>
        <select id="modo" onchange="cambiarModoTrafico()">
            <option value="peso_horapico" {"selected" if modo_actual=="peso_horapico" else ""}>🔴 Hora Pico</option>
            <option value="peso_normal" {"selected" if modo_actual=="peso_normal" else ""}>🟡 Normal</option>
            <option value="peso_libre" {"selected" if modo_actual=="peso_libre" else ""}>🟢 Libre</option>
        </select>
        
        <button onclick="calcularRuta()">📍 Calcular Ruta</button>
        <div id="info"></div>
    </div>
    
    <div class="legend" id="legend">
        <b>Nivel de Tráfico</b>
        <div class="legend-item"><div class="legend-color" style="background:#b30000"></div> Muy pesado</div>
        <div class="legend-item"><div class="legend-color" style="background:#ff6600"></div> Pesado</div>
        <div class="legend-item"><div class="legend-color" style="background:#ffcc00"></div> Moderado</div>
        <div class="legend-item"><div class="legend-color" style="background:#00cc00"></div> Libre</div>
    </div>

    <script>
        var map = L.map('map').setView([{cy}, {cx}], 15);
        
        L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
            attribution: '© OpenStreetMap'
        }}).addTo(map);
        
        var edgesData = {edges_json};
        var poisData = {pois_json};
        var trafficLayer = L.layerGroup().addTo(map);
        var rutaLayer = null;
        var poisLayer = L.layerGroup().addTo(map);
        
        // Función para obtener color según modo y congestión
        function getColor(congestion, modo) {{
            if (modo === 'peso_libre') {{
                return '#00cc00';  // Verde para todo
            }} else if (modo === 'peso_normal') {{
                if (congestion > 2.5) return '#ffcc00';
                return '#0066ff';  // Azul
            }} else {{  // hora pico
                if (congestion > 2.8) return '#b30000';  // Rojo oscuro
                if (congestion > 2.2) return '#ff6600';  // Naranja
                return '#ffcc00';  // Amarillo
            }}
        }}
        
        // Dibujar tráfico según modo
        function dibujarTrafico(modo) {{
            trafficLayer.clearLayers();
            
            edgesData.forEach(function(edge) {{
                var color = getColor(edge.congestion, modo);
                L.polyline(edge.coords, {{
                    color: color,
                    weight: 4,
                    opacity: 0.8
                }}).addTo(trafficLayer);
            }});
            
            // Actualizar leyenda
            var legend = document.getElementById('legend');
            if (modo === 'peso_libre') {{
                legend.innerHTML = '<b>🟢 Hora Libre</b><div class="legend-item"><div class="legend-color" style="background:#00cc00"></div> Tráfico fluido</div>';
            }} else if (modo === 'peso_normal') {{
                legend.innerHTML = '<b>🟡 Tráfico Normal</b><div class="legend-item"><div class="legend-color" style="background:#0066ff"></div> Normal</div><div class="legend-item"><div class="legend-color" style="background:#ffcc00"></div> Algo lento</div>';
            }} else {{
                legend.innerHTML = '<b>🔴 Hora Pico</b><div class="legend-item"><div class="legend-color" style="background:#b30000"></div> Muy pesado</div><div class="legend-item"><div class="legend-color" style="background:#ff6600"></div> Pesado</div><div class="legend-item"><div class="legend-color" style="background:#ffcc00"></div> Moderado</div>';
            }}
            
            // Actualizar texto del modo actual
            var modoTexto = document.getElementById('modoActual');
            if (modo === 'peso_horapico') {{
                modoTexto.textContent = 'Hora Pico';
                modoTexto.style.color = '#cc0000';
            }} else if (modo === 'peso_normal') {{
                modoTexto.textContent = 'Tráfico Normal';
                modoTexto.style.color = '#cc9900';
            }} else {{
                modoTexto.textContent = 'Hora Libre';
                modoTexto.style.color = '#00aa00';
            }}
        }}
        
        // Dibujar POIs
        function dibujarPOIs() {{
            poisData.forEach(function(poi, index) {{
                var i = index + 1;
                var icon = L.divIcon({{
                    html: '<div style="background:#ff0000;width:28px;height:28px;border-radius:50%;border:2px solid white;box-shadow:0 2px 5px rgba(0,0,0,0.5);display:flex;align-items:center;justify-content:center;color:white;font-weight:bold;font-size:12px;">' + i + '</div>',
                    iconSize: [28, 28],
                    iconAnchor: [14, 14],
                    className: ''
                }});
                L.marker([poi[0], poi[1]], {{icon: icon}})
                    .bindPopup('Punto ' + i)
                    .addTo(poisLayer);
            }});
        }}
        
        // Cambiar modo de tráfico
        function cambiarModoTrafico() {{
            var modo = document.getElementById('modo').value;
            dibujarTrafico(modo);
        }}
        
        // Actualizar tipo de ruta
        function actualizarTipoRuta() {{
            var tipo = document.getElementById('tipo_ruta').value;
            var container = document.getElementById('punto_c_container');
            var label = document.getElementById('punto_c_label');
            
            if (tipo === 'normal') {{
                container.style.display = 'none';
            }} else {{
                container.style.display = 'block';
                if (tipo === 'con_parada') {{
                    label.textContent = 'Punto de Parada:';
                }} else {{
                    label.textContent = 'Punto Obstáculo:';
                }}
            }}
        }}
        
        // Calcular ruta
        function calcularRuta() {{
            var origen = document.getElementById('origen').value;
            var destino = document.getElementById('destino').value;
            var modo = document.getElementById('modo').value;
            var tipo = document.getElementById('tipo_ruta').value;
            var punto_c = document.getElementById('punto_c').value;
            var info = document.getElementById('info');
            
            info.style.display = 'block';
            info.innerHTML = '⏳ Calculando...';
            
            if (origen === destino) {{
                info.innerHTML = '<span style="color:#cc0000">⚠️ Origen y destino deben ser diferentes</span>';
                return;
            }}
            
            if ((tipo === 'con_parada' || tipo === 'con_obstaculo') && punto_c === origen) {{
                info.innerHTML = '<span style="color:#cc0000">⚠️ El punto C debe ser diferente al origen</span>';
                return;
            }}
            
            if ((tipo === 'con_parada' || tipo === 'con_obstaculo') && punto_c === destino) {{
                info.innerHTML = '<span style="color:#cc0000">⚠️ El punto C debe ser diferente al destino</span>';
                return;
            }}
            
            var url = '/calcular_ruta?origen=' + origen + '&destino=' + destino + '&modo=' + modo + '&tipo=' + tipo;
            if (tipo !== 'normal') {{
                url += '&punto_c=' + punto_c;
            }}
            
            fetch(url)
                .then(function(r) {{ return r.json(); }})
                .then(function(data) {{
                    if (data.error) {{
                        info.innerHTML = '<span style="color:#cc0000">❌ ' + data.error + '</span>';
                        return;
                    }}
                    
                    if (rutaLayer) {{
                        map.removeLayer(rutaLayer);
                    }}
                    
                    if (data.coordenadas && data.coordenadas.length > 1) {{
                        rutaLayer = L.polyline(data.coordenadas, {{
                            color: '#00ff00',
                            weight: 7,
                            opacity: 0.9
                        }}).addTo(map);
                        
                        var bounds = rutaLayer.getBounds();
                        if (bounds.isValid()) {{
                            map.fitBounds(bounds, {{padding: [50, 50]}});
                        }}
                    }}
                    
                    info.innerHTML = 
                        '<div style="border-left:3px solid #00cc00;padding-left:8px;">' +
                        '<p style="margin:3px 0;"><b>📏 Distancia:</b> ' + data.distancia_km.toFixed(2) + ' km</p>' +
                        '<p style="margin:3px 0;"><b>⏱️ Tiempo:</b> ' + data.tiempo_formato + '</p>' +
                        '</div>';
                }})
                .catch(function(err) {{
                    info.innerHTML = '<span style="color:#cc0000">❌ Error de conexión</span>';
                }});
        }}
        
        // Inicializar
        dibujarTrafico('{modo_actual}');
        dibujarPOIs();
    </script>
</body>
</html>
'''
    return html

@app.route('/calcular_ruta')
def calcular_ruta_endpoint():
    origen = request.args.get('origen')
    destino = request.args.get('destino')
    modo = request.args.get('modo', 'peso_horapico')
    tipo_ruta = request.args.get('tipo', 'normal')
    punto_c = request.args.get('punto_c')
    
    if not origen or not destino:
        return jsonify({"error": "Faltan parámetros"}), 400
    
    if tipo_ruta == 'con_parada':
        if not punto_c:
            return jsonify({"error": "Falta el punto de parada"}), 400
        resultado = calcular_ruta_con_parada(G, poi_mapping, origen, punto_c, destino, modo)
    elif tipo_ruta == 'con_obstaculo':
        if not punto_c:
            return jsonify({"error": "Falta el punto obstáculo"}), 400
        resultado = calcular_ruta_con_obstaculo(G, poi_mapping, origen, destino, punto_c, modo)
    else:
        resultado = calcular_ruta(G, poi_mapping, origen, destino, modo)
    
    if resultado is None:
        return jsonify({"error": f"No se encontró ruta de {origen} a {destino}"}), 404
    
    return jsonify(resultado)

if __name__ == '__main__':
    if os.path.exists(GRAFO_FILE):
        os.remove(GRAFO_FILE)
        print("Regenerando grafo...")
    
    G, poi_mapping, edges_data = crear_grafo()
    guardar_grafo((G, poi_mapping, edges_data))
    
    print("\nIniciando servidor en http://localhost:5002")
    app.run(debug=True, port=5002)