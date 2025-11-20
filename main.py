import osmnx as ox
import folium
import math
import random
from collections import deque
from shapely.geometry import Point, Polygon
import networkx as nx

# ===============================================================
# 1. COORDENADAS DEL POLÍGONO
# ===============================================================
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

# Convertir a (lon, lat)
coor = [(lon, lat) for lat, lon in coor_latlon]
pts = [Point(lon, lat) for (lon, lat) in coor]

# Centroide para ordenarlos y formar polígono válido
cx = sum(p.x for p in pts) / len(pts)
cy = sum(p.y for p in pts) / len(pts)

def angle(p):
    return math.atan2(p.y - cy, p.x - cx)

pts_sorted = sorted(pts, key=angle)
poly = Polygon([(p.x, p.y) for p in pts_sorted]).buffer(0)

# ===============================================================
# 2. DESCARGA DEL GRAFO (OSMNX 1.9+)
# ===============================================================
print("Descargando grafo desde OSM...")

G = ox.graph_from_polygon(
    poly,
    network_type="drive"
)

print(f"Grafo descargado: {len(G.nodes)} nodos, {len(G.edges)} aristas")

# ===============================================================
# 3. SIMULACIÓN DE TRÁFICO TIPO WAZE (2 NIVELES)
# ===============================================================
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

# ===============================================================
# 4. ASIGNACIÓN DE PESOS
# ===============================================================
for u, v, data in G.edges(data=True):

    # Distancia real
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

    # Hora pico (2 niveles)
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

# ===============================================================
# 5. TUS 10 PUNTOS DE INTERÉS (POIs)
# ===============================================================
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

# PRIMERO: Encontrar nodos cercanos ANTES de añadir POIs
print("Añadiendo POIs...")
poi_mapping = {}  # Diccionario para guardar POI -> nodo cercano

for i, (lat, lon) in enumerate(POIS_USUARIO, start=1):
    nombre = f"POI_{i}"
    
    # Buscar nodo real más cercano ANTES de añadir el POI
    nearest = ox.distance.nearest_nodes(G, X=lon, Y=lat)
    poi_mapping[nombre] = nearest
    
    # Distancia euclidiana
    dist = math.dist((lon, lat), (G.nodes[nearest]['x'], G.nodes[nearest]['y']))
    
    # AHORA SÍ añadir el nodo POI
    G.add_node(nombre, x=lon, y=lat, tipo="POI")
    
    # Crear aristas bidireccionales con todos los pesos
    for edge_data in [(nombre, nearest), (nearest, nombre)]:
        G.add_edge(
            edge_data[0], 
            edge_data[1], 
            length=dist,
            peso_normal=dist,
            peso_horapico=dist,  # Los POIs no tienen tráfico
            peso_libre=dist,
            tr_color="gray",
            tr_nivel="CONEXIÓN POI"
        )

print(f"POIs añadidos: {len(POIS_USUARIO)}")
print("Nodos conectados a:")
for poi, nodo in poi_mapping.items():
    print(f"  {poi} -> Nodo {nodo}")

# ===============================================================
# 6. MAPA FOLIUM
# ===============================================================
m = folium.Map(location=[cy, cx], zoom_start=15)

layer_normal = folium.FeatureGroup(name="Tráfico normal").add_to(m)
layer_horapico = folium.FeatureGroup(name="Hora pico").add_to(m)
layer_libre = folium.FeatureGroup(name="Hora libre").add_to(m)
layer_pois = folium.FeatureGroup(name="POIs", show=True).add_to(m)

# Dibujar calles
for u, v, data in G.edges(data=True):

    if "geometry" in data:
        xs, ys = data["geometry"].xy
        coords = list(zip(ys, xs))
    else:
        x1, y1 = G.nodes[u]["y"], G.nodes[u]["x"]
        x2, y2 = G.nodes[v]["y"], G.nodes[v]["x"]
        coords = [(x1, y1), (x2, y2)]

    popup = f"""
    <b>Normal:</b> {data['peso_normal']:.2f}<br>
    <b>Hora pico:</b> {data['peso_horapico']:.2f}<br>
    <b>Nivel:</b> {data['tr_nivel']}<br>
    """

    folium.PolyLine(coords, color="blue", weight=3, popup=popup).add_to(layer_normal)
    folium.PolyLine(coords, color=data["tr_color"], weight=5, popup=popup).add_to(layer_horapico)
    folium.PolyLine(coords, color="green", weight=3, popup=popup).add_to(layer_libre)

# Dibujar POIs
for i, (lat, lon) in enumerate(POIS_USUARIO, start=1):
    folium.Marker(
        location=[lat, lon],
        popup=f"<b>POI_{i}</b>",
        icon=folium.Icon(color="red", icon="info-sign")
    ).add_to(layer_pois)

folium.LayerControl().add_to(m)

# ===============================================================
# 7. CALCULAR RUTA ENTRE POIs
# ===============================================================
def distancia_geodesica(lat1, lon1, lat2, lon2):
    """
    Calcula la distancia geodésica entre dos puntos en metros.
    Usa la formula de haversine.
    """
    R = 6371000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    
    a = math.sin(delta_phi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    
    return R * c

def calcular_ruta(origen, destino, modo_trafico="peso_horapico"):
    """
    Calcula la ruta mas corta entre dos POIs.
    
    Args:
        origen: nombre del POI origen (ej: 'POI_1')
        destino: nombre del POI destino (ej: 'POI_5')
        modo_trafico: 'peso_normal', 'peso_horapico', o 'peso_libre'
    
    Returns:
        ruta: lista de nodos de la ruta
        distancia_total: distancia total en metros
        tiempo_estimado: tiempo estimado en minutos
    """
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
        
        return ruta, distancia_total, tiempo_minutos
    except nx.NetworkXNoPath:
        return None, 0, 0

def dibujar_ruta(mapa, ruta, color="#00ff00", weight=8):
    """
    Dibuja la ruta en el mapa usando las geometrias reales de las calles.
    """
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
    
    if len(coords_ruta) > 1:
        folium.PolyLine(
            coords_ruta,
            color=color,
            weight=weight,
            opacity=0.8,
            popup="Ruta calculada"
        ).add_to(mapa)

# Ejemplo: calcular ruta de POI_1 a POI_5 con trafico hora pico
print("\n" + "="*50)
print("CALCULANDO RUTA DE EJEMPLO")
print("="*50)

origen_ejemplo = "POI_1"
destino_ejemplo = "POI_5"
modo_ejemplo = "peso_horapico"

ruta_calculada, distancia, tiempo = calcular_ruta(
    origen_ejemplo,
    destino_ejemplo,
    modo_ejemplo
)

if ruta_calculada:
    print(f"\nRuta de {origen_ejemplo} a {destino_ejemplo}:")
    print(f"  Distancia total: {distancia:.2f} metros ({distancia/1000:.2f} km)")
    print(f"  Tiempo estimado: {tiempo:.2f} minutos")
    print(f"  Nodos en la ruta: {len(ruta_calculada)}")
    
    dibujar_ruta(m, ruta_calculada, color="#00ff00", weight=8)
else:
    print(f"\nNo se encontro ruta entre {origen_ejemplo} y {destino_ejemplo}")

# ===============================================================
# 8. GUARDAR
# ===============================================================
m.save("mapa_grafo.html")
print("\nArchivo generado: mapa_grafo.html")
print("\nPara calcular otras rutas, usa:")
print("  ruta, distancia, tiempo = calcular_ruta('POI_1', 'POI_5', 'peso_horapico')")
print("  dibujar_ruta(m, ruta)")