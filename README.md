Calculador de Rutas con Tráfico en Tiempo Real:

Este proyecto es una aplicación web desarrollada en Python + Flask que permite calcular rutas vehiculares utilizando datos reales de OpenStreetMap mediante la librería OSMnx.
Incluye:

Visualización del mapa con Leaflet.

Cálculo de rutas con diferentes modos de tráfico.

Simulación de congestión dinámica.

Rutas normales, con parada o evitando un obstáculo.

Colores de tráfico basados en congestión.

POIs predefinidos asignados a nodos reales del grafo.

El sistema genera un grafo descargado desde OSM, lo guarda localmente y lo utiliza para calcular rutas optimizadas según el tráfico actual.

Características principales
1. Generación automática del grafo

Se define un polígono con coordenadas preestablecidas.

Se descarga el mapa de carreteras desde OpenStreetMap usando osmnx.

Se calculan distancias geodésicas para aristas sin longitud.

Se asignan pesos según:

Tráfico en hora pico

Tráfico normal

Hora libre

Se genera un archivo persistente grafo_guardado_v3.pkl.

2. Cálculo de rutas

El backend permite calcular tres tipos de rutas:

🔵 Ruta normal

Origen → Destino

Pondera pesos según el tipo de tráfico.

🟡 Ruta con parada

Origen → Punto C → Destino

🔴 Ruta evitando un obstáculo

Se elimina del grafo un área circular alrededor del punto indicado.

Si no es posible evitarlo, retorna ruta normal.

3. Simulación de tráfico

Cada arista tiene un nivel de congestión aleatorio, lo que permite:

Visualización en colores:

🟥 Muy pesado

🟧 Pesado

🟨 Moderado

🟩 Libre

Pesos dinámicos según:

Hora pico

Normal

Libre

El modo de tráfico se selecciona automáticamente según la hora, pero también puede sobreescribirse manualmente desde el panel.

4. Interfaz web avanzada (Leaflet)

El front-end incluye:

Visualización del mapa OSM.

Panel interactivo para seleccionar:

origen

destino

tipo de ruta

modo de tráfico

punto C

Dibujado de:

tráfico por color

POIs numerados

ruta óptima

Popup de distancia y tiempo formateado.


Endpoints:
GET /calcular_ruta

Parámetros:
Parámetro	Descripción
origen	POI origen 
destino	POI destino
modo	peso_horapico / peso_normal / peso_libre
tipo	normal / con_parada / con_obstaculo
punto_c	Punto de parada u obstáculo (opcional)
