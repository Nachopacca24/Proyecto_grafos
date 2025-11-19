import osmnx as ox
import folium
import math
from shapely.geometry import Point, Polygon
from shapely.ops import unary_union

# ============================
# 1. COORDENADAS ORIGINALES (lat, lon)
# ============================
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

# ============================
# 2. ORDENAR POLÍGONO
# ============================
pts = [Point(lon, lat) for (lon, lat) in coor]

# centroide
cx = sum(p.x for p in pts) / len(pts)
cy = sum(p.y for p in pts) / len(pts)
centroide = Point(cx, cy)

# función de ángulo
def angle(p):
    return math.atan2(p.y - cy, p.x - cx)

pts_sorted = sorted(pts, key=angle)

# ============================
# 3. CREAR POLÍGONO VALIDO (lon, lat)
# ============================
poly = Polygon([(p.x, p.y) for p in pts_sorted])

# reparar si tiene self-intersections
poly = poly.buffer(0)

if not poly.is_valid:
    raise Exception("Poligono inválido incluso después de reparar")

print("Polígono creado correctamente.\n")

# ============================
# 4. DESCARGAR GRAFO REAL
# ============================
print("Descargando grafo desde OpenStreetMap...")

G = ox.graph_from_polygon(poly, network_type="drive")

print("\nGrafo descargado con éxito.")
print("Nodos:", len(G.nodes))
print("Aristas:", len(G.edges))

# ============================
# 5. CREAR MAPA FOLIUM
# ============================
m = folium.Map(location=[cy, cx], zoom_start=15)

# Dibujar grafo
for u, v, data in G.edges(data=True):
    if "geometry" in data:
        xs, ys = data["geometry"].xy
        coords = list(zip(ys, xs))
    else:
        x1, y1 = G.nodes[u]["x"], G.nodes[u]["y"]
        x2, y2 = G.nodes[v]["x"], G.nodes[v]["y"]
        coords = [(y1, x1), (y2, x2)]
    folium.PolyLine(coords, weight=2).add_to(m)

# Dibujar polígono
folium.Polygon([(p.y, p.x) for p in pts_sorted],
               color="red", weight=3, fill=False).add_to(m)

m.save("mapa_grafo.html")
print("\nMapa guardado en mapa_grafo.html")
