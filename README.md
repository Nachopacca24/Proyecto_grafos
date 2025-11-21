# Calculador de Rutas con Tráfico en Tiempo Real

Este proyecto es una aplicación web creada con Python y Flask que calcula rutas vehiculares utilizando datos reales de OpenStreetMap mediante la librería OSMnx.  
Genera un grafo de calles, lo almacena localmente y calcula rutas optimizadas según distintos niveles de tráfico.  
Incluye visualización mediante Leaflet, simulación de tráfico y diferentes tipos de rutas.

---

## Características Principales

### 1. Generación Automática del Grafo
- Se define un polígono que delimita el área de interés.
- Se descarga la red vial desde OpenStreetMap usando OSMnx.
- Se calculan distancias geodésicas para las aristas sin longitud.
- Se asignan pesos según el modo de tráfico:
  - Hora pico  
  - Tráfico normal  
  - Hora libre  
- El grafo generado se guarda en "grafo_guardado_v3.pkl" para mayor eficiencia en futuras ejecuciones.

---

### 2. Cálculo de Rutas

El sistema permite calcular tres tipos principales de rutas:

#### 2.1 Ruta Normal
- Origen → Destino  
- Utiliza los pesos asociados al modo de tráfico seleccionado.

#### 2.2 Ruta con Parada
- Origen → Punto C → Destino  
- Para rutas que requieren realizar una escala intermedia.

#### 2.3 Ruta Evitando un Obstáculo
- Se elimina del grafo una zona circular alrededor del punto marcado como obstáculo.
- Si no existe alternativa viable, se retorna una ruta normal.

---

### 3. Simulación de Tráfico

- Cada arista del grafo recibe un nivel de congestión aleatorio.
- Se visualiza mediante colores que representan el nivel de tráfico:
  - Muy pesado  
  - Pesado  
  - Moderado  
  - Libre  
- Los modos de tráfico modifican directamente los pesos utilizados en el cálculo.
- El modo puede establecerse automáticamente según la hora o seleccionarse manualmente desde la interfaz.

---

### 4. Interfaz Web Interactiva (Leaflet)

La aplicación web permite:

- Visualizar el mapa con capas de tráfico coloreadas.
- Seleccionar:
  - Origen  
  - Destino  
  - Tipo de ruta  
  - Modo de tráfico  
  - Punto de parada u obstáculo  
- Ver:
  - POIs numerados  
  - La ruta óptima generada  
  - Distancia total y tiempo estimado  

---

## Endpoint Principal

### GET /calcular_ruta

Genera una ruta según los parámetros enviados.

#### Parámetros

| Parámetro | Descripción |
|----------|-------------|
| `origen` | Punto inicial (POI destino) |
| `destino` | Punto final (POI destino) |
| `modo` | Tipo de tráfico: `peso_horapico`, `peso_normal`, `peso_libre` |
| `tipo` | Tipo de ruta: `normal`, `con_parada`, `con_obstaculo` |
| `punto_c` | Punto intermedio u obstáculo |

