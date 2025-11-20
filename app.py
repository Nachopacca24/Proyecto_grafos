import pickle
import os
import osmnx as ox
import folium
import math
import random
from collections import deque
from shapely.geometry import Point, Polygon
import networkx as nx
from flask import Flask, render_template_string, jsonify, request

app = Flask(__name__)

GRAFO_FILE = "grafo_guardado.pkl"

def cargar_grafo():
    if os.path.exists(GRAFO_FILE):
        print("Cargando grafo desde archivo...")
        with open(GRAFO_FILE, 'rb') as f:
            return pickle.load(f)
    return None

def guardar_grafo(grafo):
    print("Guardando grafo...")
    with open(GRAFO_FILE, 'wb') as f:
        pickle.dump(grafo, f)

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
    poly = Polygon([(p.x, p.y) for p in pts_sorted]).buffer(0)

    print("Descargando grafo desde OSM...")
    G = ox.graph_from_polygon(poly, network_type="drive")
    print(f"Grafo descargado: {len(G.nodes)} nodos, {len(G.edges)} aristas")

    nodos = list(G.nodes)
    num_seeds = max(3, len(nodos) // 20)
    seeds = random.sample(nodos, num_seeds)

    node_congestion = {n: float('inf') for n in nodos}
    for s in seeds:
        node_congestion[s] = 0

    q = deque(seeds)
    while q:
        actual = q.popleft()
        for vecino in G.neighbors(actual):
            if node_congestion[vecino] == float('inf'):
                node_congestion[vecino] = node_congestion[actual] + 1
                q.append(vecino)

    for u, v, data in G.edges(data=True):
        if "length" not in data:
            if "geometry" in data:
                data["length"] = data["geometry"].length
            else:
                x1, y1 = G.nodes[u]["x"], G.nodes[u]["y"]
                x2, y2 = G.nodes[v]["x"], G.nodes[v]["y"]
                data["length"] = math.dist((x1, y1), (x2, y2))

        d = data["length"]

        data["peso_normal"] = d

        dist_u = node_congestion[u]
        dist_v = node_congestion[v]
        dist_prom = min(dist_u, dist_v)

        if dist_prom == 0:
            factor = 3.5
            color = "#b30000"
            nivel = "TRÁFICO MUY PESADO"
        else:
            factor = 2.2
            color = "#ff6600"
            nivel = "TRÁFICO PESADO"

        data["peso_horapico"] = d * factor
        data["tr_color"] = color
        data["tr_nivel"] = nivel
        data["peso_libre"] = d * 0.7

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

    print("Añadiendo POIs...")
    poi_mapping = {}

    for i, (lat, lon) in enumerate(POIS_USUARIO, start=1):
        nombre = f"POI_{i}"
        nearest = ox.distance.nearest_nodes(G, X=lon, Y=lat)
        poi_mapping[nombre] = nearest

        dist = math.dist((lon, lat), (G.nodes[nearest]['x'], G.nodes[nearest]['y']))

        G.add_node(nombre, x=lon, y=lat, tipo="POI")

        for edge_data in [(nombre, nearest), (nearest, nombre)]:
            G.add_edge(
                edge_data[0],
                edge_data[1],
                length=dist,
                peso_normal=dist,
                peso_horapico=dist,
                peso_libre=dist,
                tr_color="gray",
                tr_nivel="CONEXIÓN POI"
            )

    print(f"POIs añadidos: {len(POIS_USUARIO)}")
    return G, poi_mapping

def distancia_geodesica(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

    return R * c

def calcular_ruta(G, origen, destino, modo_trafico="peso_horapico"):
    try:
        ruta = nx.shortest_path(G, origen, destino, weight=modo_trafico)

        distancia_total = 0
        for i in range(len(ruta) - 1):
            u = ruta[i]
            v = ruta[i + 1]
            if G.has_edge(u, v):
                edge_data = G[u][v]
                if "length" in edge_data and edge_data["length"] > 0:
                    distancia_total += edge_data["length"]
                else:
                    lat_u = G.nodes[u].get('y', 0)
                    lon_u = G.nodes[u].get('x', 0)
                    lat_v = G.nodes[v].get('y', 0)
                    lon_v = G.nodes[v].get('x', 0)
                    if lat_u != 0 and lon_u != 0 and lat_v != 0 and lon_v != 0:
                        dist_geodesica = distancia_geodesica(lat_u, lon_u, lat_v, lon_v)
                        distancia_total += dist_geodesica

        velocidad_promedio = 30
        if modo_trafico == "peso_horapico":
            velocidad_promedio = 15
        elif modo_trafico == "peso_libre":
            velocidad_promedio = 50

        tiempo_segundos = (distancia_total / 1000) / (velocidad_promedio / 3600)
        tiempo_minutos = tiempo_segundos / 60

        coords_ruta = []
        for i in range(len(ruta) - 1):
            u = ruta[i]
            v = ruta[i + 1]
            
            if G.has_edge(u, v):
                edge_data = G[u][v]
                
                if "geometry" in edge_data:
                    xs, ys = edge_data["geometry"].xy
                    segmento = list(zip(ys, xs))
                    coords_ruta.extend(segmento)
                else:
                    lat_u = G.nodes[u].get('y', 0)
                    lon_u = G.nodes[u].get('x', 0)
                    lat_v = G.nodes[v].get('y', 0)
                    lon_v = G.nodes[v].get('x', 0)
                    
                    if lat_u != 0 and lon_u != 0:
                        coords_ruta.append([lat_u, lon_u])
                    if lat_v != 0 and lon_v != 0:
                        coords_ruta.append([lat_v, lon_v])

        return {
            "ruta": ruta,
            "coordenadas": coords_ruta,
            "distancia_metros": distancia_total,
            "distancia_km": distancia_total / 1000,
            "tiempo_minutos": tiempo_minutos
        }
    except nx.NetworkXNoPath:
        return None
    except Exception as e:
        print(f"Error calculando ruta: {e}")
        return None

def generar_mapa_base(G):
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
    
    m = folium.Map(location=[cy, cx], zoom_start=15)
    
    layer_normal = folium.FeatureGroup(name="Tráfico normal", show=False).add_to(m)
    layer_horapico = folium.FeatureGroup(name="Hora pico", show=True).add_to(m)
    layer_libre = folium.FeatureGroup(name="Hora libre", show=False).add_to(m)
    layer_pois = folium.FeatureGroup(name="POIs", show=True).add_to(m)
    layer_ruta = folium.FeatureGroup(name="Ruta", show=True).add_to(m)
    
    for u, v, data in G.edges(data=True):
        if "geometry" in data:
            xs, ys = data["geometry"].xy
            coords = list(zip(ys, xs))
        else:
            x1, y1 = G.nodes[u]["y"], G.nodes[u]["x"]
            x2, y2 = G.nodes[v]["y"], G.nodes[v]["x"]
            coords = [(x1, y1), (x2, y2)]
        
        popup = f"""
        <b>Normal:</b> {data.get('peso_normal', 0):.2f}<br>
        <b>Hora pico:</b> {data.get('peso_horapico', 0):.2f}<br>
        <b>Nivel:</b> {data.get('tr_nivel', 'N/A')}<br>
        """
        
        folium.PolyLine(coords, color="blue", weight=3, popup=popup).add_to(layer_normal)
        folium.PolyLine(coords, color=data.get("tr_color", "gray"), weight=5, popup=popup).add_to(layer_horapico)
        folium.PolyLine(coords, color="green", weight=3, popup=popup).add_to(layer_libre)
    
    for i, (lat, lon) in enumerate(POIS_USUARIO, start=1):
        html_icon = f'''
        <div style="
            background-color: #ff0000;
            width: 35px;
            height: 35px;
            border-radius: 50%;
            border: 3px solid white;
            box-shadow: 0 2px 5px rgba(0,0,0,0.5);
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: bold;
            font-size: 16px;
        ">{i}</div>
        '''
        icon = folium.DivIcon(
            html=html_icon,
            icon_size=(35, 35),
            icon_anchor=(17, 17)
        )
        folium.Marker(
            location=[lat, lon],
            popup=f"<b>Punto de Interés {i}</b><br>POI_{i}",
            tooltip=f"POI {i}",
            icon=icon
        ).add_to(layer_pois)
    
    folium.LayerControl().add_to(m)
    
    return m

G = cargar_grafo()
if G is None:
    G, poi_mapping = crear_grafo()
    guardar_grafo(G)
else:
    print("Grafo cargado desde archivo")
    poi_mapping = {f"POI_{i}": None for i in range(1, 11)}

@app.route('/')
def index():
    m = generar_mapa_base(G)
    html_string = m.get_root().render()
    
    panel_html = '''
    <div id="panel" style="position: absolute; top: 10px; left: 10px; z-index: 1000; background: white; padding: 15px; border-radius: 5px; box-shadow: 0 2px 5px rgba(0,0,0,0.3); font-family: Arial, sans-serif; max-width: 250px;">
        <h3 style="margin-top: 0;">Calcular Ruta</h3>
        <p style="font-size: 11px; color: #666; margin: 0 0 10px 0;">POI = Punto de Interés</p>
        <label><strong>Origen:</strong></label><br>
        <select id="origen" style="margin: 5px 0; padding: 8px; width: 100%;">
            <option value="POI_1">Punto 1</option>
            <option value="POI_2">Punto 2</option>
            <option value="POI_3">Punto 3</option>
            <option value="POI_4">Punto 4</option>
            <option value="POI_5">Punto 5</option>
            <option value="POI_6">Punto 6</option>
            <option value="POI_7">Punto 7</option>
            <option value="POI_8">Punto 8</option>
            <option value="POI_9">Punto 9</option>
            <option value="POI_10">Punto 10</option>
        </select><br>
        <label><strong>Destino:</strong></label><br>
        <select id="destino" style="margin: 5px 0; padding: 8px; width: 100%;">
            <option value="POI_1">Punto 1</option>
            <option value="POI_2">Punto 2</option>
            <option value="POI_3">Punto 3</option>
            <option value="POI_4">Punto 4</option>
            <option value="POI_5" selected>Punto 5</option>
            <option value="POI_6">Punto 6</option>
            <option value="POI_7">Punto 7</option>
            <option value="POI_8">Punto 8</option>
            <option value="POI_9">Punto 9</option>
            <option value="POI_10">Punto 10</option>
        </select><br>
        <label><strong>Modo de Tráfico:</strong></label><br>
        <select id="modo" style="margin: 5px 0; padding: 8px; width: 100%;">
            <option value="peso_normal">Normal</option>
            <option value="peso_horapico" selected>Hora Pico</option>
            <option value="peso_libre">Hora Libre</option>
        </select><br>
        <button onclick="calcularRuta()" style="margin: 10px 0; padding: 10px; width: 100%; background: #007bff; color: white; border: none; cursor: pointer; border-radius: 3px; font-weight: bold;">Calcular Ruta</button>
        <div id="info" style="margin-top: 10px; padding: 10px; background: #f0f0f0; border-radius: 3px; font-size: 14px;"></div>
    </div>
    '''
    
    script = '''
    <script>
        var rutaLayer = null;
        var foliumMap = null;
        
        function getFoliumMap() {
            if (foliumMap) return foliumMap;
            if (window.foliumMap) {
                foliumMap = window.foliumMap;
                return foliumMap;
            }
            var scripts = document.getElementsByTagName('script');
            for (var i = 0; i < scripts.length; i++) {
                var script = scripts[i];
                if (script.innerHTML) {
                    var match = script.innerHTML.match(/var (map_[a-zA-Z0-9]+)\s*=/);
                    if (match) {
                        try {
                            var varName = match[1];
                            foliumMap = eval(varName);
                            if (foliumMap && foliumMap instanceof L.Map) {
                                window.foliumMap = foliumMap;
                                return foliumMap;
                            }
                        } catch(e) {
                            console.log('Error evaluando mapa:', e);
                        }
                    }
                }
            }
            var mapDiv = document.querySelector('.folium-map');
            if (mapDiv && mapDiv._leaflet_id) {
                try {
                    foliumMap = L.Map.prototype._getMap(mapDiv._leaflet_id);
                    if (foliumMap) {
                        window.foliumMap = foliumMap;
                        return foliumMap;
                    }
                } catch(e) {
                    console.log('Error obteniendo mapa del div:', e);
                }
            }
            return null;
        }
        
        function calcularRuta() {
            var origen = document.getElementById('origen').value;
            var destino = document.getElementById('destino').value;
            var modo = document.getElementById('modo').value;
            
            document.getElementById('info').innerHTML = '<p style="margin: 0; color: #666;">Calculando ruta...</p>';
            
            if (origen === destino) {
                document.getElementById('info').innerHTML = '<p style="color: red; margin: 0;">Selecciona origen y destino diferentes</p>';
                return;
            }
            
            fetch('/calcular_ruta?origen=' + origen + '&destino=' + destino + '&modo=' + modo)
                .then(response => {
                    if (!response.ok) {
                        throw new Error('Error en la respuesta del servidor');
                    }
                    return response.json();
                })
                .then(data => {
                    if (data.error) {
                        document.getElementById('info').innerHTML = '<p style="color: red; margin: 0;">' + data.error + '</p>';
                        return;
                    }
                    
                    var intentos = 0;
                    var maxIntentos = 10;
                    
                    function intentarDibujarRuta() {
                        intentos++;
                        var map = getFoliumMap();
                        
                        if (!map && intentos < maxIntentos) {
                            setTimeout(intentarDibujarRuta, 200);
                            return;
                        }
                        
                        if (!map) {
                            document.getElementById('info').innerHTML = '<p style="color: red; margin: 0;">Error: No se pudo acceder al mapa. Recarga la página.</p>';
                            return;
                        }
                        
                        if (rutaLayer) {
                            map.removeLayer(rutaLayer);
                            rutaLayer = null;
                        }
                        
                        var coords = data.coordenadas.map(c => [c[0], c[1]]);
                        rutaLayer = L.polyline(coords, {color: '#00ff00', weight: 8, opacity: 0.8}).addTo(map);
                        
                        try {
                            map.fitBounds(rutaLayer.getBounds());
                        } catch(e) {
                            console.log('Error ajustando vista:', e);
                        }
                        
                        document.getElementById('info').innerHTML = 
                            '<p style="margin: 5px 0;"><strong>Distancia:</strong> ' + data.distancia_km.toFixed(2) + ' km (' + data.distancia_metros.toFixed(0) + ' m)</p>' +
                            '<p style="margin: 5px 0;"><strong>Tiempo estimado:</strong> ' + data.tiempo_minutos.toFixed(2) + ' minutos</p>';
                    }
                    
                    intentarDibujarRuta();
                })
                .catch(error => {
                    console.error('Error:', error);
                    document.getElementById('info').innerHTML = '<p style="color: red; margin: 0;">Error: ' + error.message + '</p>';
                });
        }
        
        window.addEventListener('load', function() {
            setTimeout(function() {
                getFoliumMap();
            }, 1000);
        });
    </script>
    '''
    
    html_string = html_string.replace('</body>', panel_html + script + '</body>')
    html_string = html_string.replace('</head>', '<style>body { margin: 0; padding: 0; }</style></head>')
    
    import re
    match = re.search(r'var (map_[a-zA-Z0-9]+)\s*=', html_string)
    if match:
        var_name = match.group(1)
        html_string = re.sub(
            rf'({var_name}\.addTo\([^)]+\))',
            rf'window.foliumMap = {var_name};\n            \1',
            html_string,
            count=1
        )
    
    return html_string

@app.route('/calcular_ruta')
def calcular_ruta_endpoint():
    origen = request.args.get('origen')
    destino = request.args.get('destino')
    modo = request.args.get('modo', 'peso_horapico')
    
    if not origen or not destino:
        return jsonify({"error": "Faltan parámetros"}), 400
    
    resultado = calcular_ruta(G, origen, destino, modo)
    
    if resultado is None:
        return jsonify({"error": "No se encontró ruta"}), 404
    
    return jsonify(resultado)

if __name__ == '__main__':
    app.run(debug=True, port=5001)

