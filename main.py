import fastapi
import psycopg2
import psycopg2.extras
import time
import json
from pydantic import BaseModel

# --- Configuración ------------------------------------------------
app = fastapi.FastAPI()

DB_CONFIG = {
    "host": "localhost", # O el nombre de tu servicio de Docker (ej. 'postgis_db')
    "dbname": "tu_base_de_datos",
    "user": "tu_usuario",
    "password": "tu_contraseña",
    "port": "5432"
}

# --- Modelos de Datos (Validación de entrada) ----------------------

class RouteRequest(BaseModel):
    """Define lo que la API espera recibir del frontend."""
    start_lon: float
    start_lat: float
    end_lon: float
    end_lat: float
    vehicle_width: float = 2.5  # Ancho del carro bomba (default 2.5m)

# --- Funciones de Ayuda (Helpers) ----------------------------------

def get_db_conn():
    """Se conecta a la base de datos PostGIS."""
    try:
        conn_str = " ".join([f"{k}='{v}'" for k, v in DB_CONFIG.items()])
        conn = psycopg2.connect(conn_str)
        # Habilita que las respuestas sean diccionarios
        conn.cursor_factory = psycopg2.extras.DictCursor
        return conn
    except Exception as e:
        print(f"Error de conexión a BD: {e}")
        return None

def find_nearest_node(conn, lon, lat):
    """
    Encuentra el ID del nodo de ruteo más cercano a un punto (lon, lat).
    Usa la tabla 'rr.ways_vertices_pgr' creada por pgr_createTopology.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id
            FROM rr.ways_vertices_pgr
            ORDER BY
                geom <-> ST_SetSRID(ST_MakePoint(%s, %s), 4326)
            LIMIT 1;
            """,
            (lon, lat)
        )
        result = cur.fetchone()
        return result['id'] if result else None

def get_route_geojson_from_path(conn, path_data):
    """
    Toma una lista de nodos de pgr_dijkstra y devuelve un 
    GeoJSON unificado de la ruta y el costo total.
    """
    if not path_data:
        return (None, 0)
    
    # Extrae los IDs de las aristas (calles) usadas en la ruta
    edge_ids = [row['edge'] for row in path_data if row['edge'] != -1]
    
    if not edge_ids:
        return (None, 0)

    # Suma el costo total de la ruta
    total_cost = sum(row['cost'] for row in path_data)
    
    # Consulta para unir todas las geometrías de las aristas en una sola
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT json_build_object(
                'type', 'Feature',
                'geometry', ST_AsGeoJSON(ST_Union(geom))::json,
                'properties', %s
            ) AS geojson
            FROM rr.ways
            WHERE id = ANY(%s);
            """,
            (json.dumps({'cost': total_cost}), edge_ids)
        )
        result = cur.fetchone()
        return (result['geojson'] if result else None, total_cost)

# --- Funciones de Cálculo de Rutas (Requisito #5) -----------------

def calc_dijkstra_distancia(conn, start_node, end_node, width_m):
    """5a: Pgr_dijkstra usando solo la distancia (length_m) como costo."""
    print(f"Calculando Ruta 5a: Dijkstra (distancia) para ancho {width_m}m")
    
    # Esta es la consulta SQL que define el grafo para pgRouting.
    # ¡Filtramos las calles que son muy angostas!
    sql_grafo = f"""
    SELECT
        id,
        source,
        target,
        length_m AS cost, -- Costo es la distancia
        CASE -- Costo reverso según 'oneway'
            WHEN oneway = 'yes' THEN -1
            WHEN oneway = '-1' THEN length_m
            ELSE length_m
        END AS reverse_cost
    FROM rr.ways
    WHERE
        length_m > 0
        AND (maxwidth_m IS NULL OR maxwidth_m >= {width_m})
    """
    
    sql_dijkstra = """
    SELECT * FROM pgr_dijkstra(
        %s, -- El SQL del grafo
        %s, -- Nodo inicio
        %s, -- Nodo fin
        TRUE  -- 'directed' es TRUE por 'oneway'
    );
    """
    
    with conn.cursor() as cur:
        cur.execute(sql_dijkstra, (sql_grafo, start_node, end_node))
        path = cur.fetchall()
        return get_route_geojson_from_path(conn, path)

def calc_dijkstra_ponderado(conn, start_node, end_node, width_m):
    """5c: Pgr_dijkstra usando el costo_combinado (distancia + riesgo)."""
    print(f"Calculando Ruta 5c: Dijkstra (ponderado) para ancho {width_m}m")

    # El grafo es idéntico al anterior, pero cambia la columna 'cost'
    sql_grafo = f"""
    SELECT
        id,
        source,
        target,
        costo_combinado AS cost, -- Costo es el ponderado (dist + riesgo)
        CASE -- Costo reverso (asumimos que el riesgo es bidireccional)
            WHEN oneway = 'yes' THEN -1
            WHEN oneway = '-1' THEN costo_combinado
            ELSE costo_combinado
        END AS reverse_cost
    FROM rr.ways
    WHERE
        costo_combinado IS NOT NULL AND costo_combinado > 0
        AND (maxwidth_m IS NULL OR maxwidth_m >= {width_m})
    """
    
    sql_dijkstra = """
    SELECT * FROM pgr_dijkstra(%s, %s, %s, TRUE);
    """
    
    with conn.cursor() as cur:
        cur.execute(sql_dijkstra, (sql_grafo, start_node, end_node))
        path = cur.fetchall()
        return get_route_geojson_from_path(conn, path)

def calc_cplex_optimizado(conn, start_node, end_node, req: RouteRequest):
    """
    5b: (Stub) Modelamiento formal con CPLEX/GUROBI.
    
    Detalle del Funcionamiento (como pide la rúbrica):
    1. Variables: 
       - x_ij: Variable binaria (0 o 1). 1 si se usa la arista (calle) 'ij'.
    2. Objetivo:
       - Minimizar Z = sum(costo_ij * x_ij)
       - 'costo_ij' es una función compleja: 
         (length_m * W1) + (costo_amenaza * W2)
    3. Restricciones:
       - R1 (Flujo): sum(x_si) = 1 (Sale 1 ruta del inicio 's')
       - R2 (Flujo): sum(x_it) = 1 (Llega 1 ruta al fin 't')
       - R3 (Flujo): sum(x_ik) - sum(x_kj) = 0 (Todo lo que entra a un nodo 'k', sale)
       - R4 (Usuario): x_ij = 0 para todas las calles 'ij' donde 
         (maxwidth_m < req.vehicle_width)
       - R5 (Riesgo): sum(prob_falla_ij * x_ij) <= RIESGO_MAXIMO (ej. 0.25)
         (Esta es la gran ventaja de CPLEX: puedes restringir el riesgo total)
         
    Esto es computacionalmente costoso. Se debe implementar usando
    librerías como 'docplex' (Python para CPLEX) o 'gurobipy'.
    """
    print("Calculando Ruta 5b: CPLEX (Stub - Implementación compleja pendiente)")
    # --- Aquí iría la lógica de Python para construir y resolver el modelo ---
    # 1. Consultar a la BD todas las 'rr.ways' (filtradas por ancho)
    # 2. Construir el modelo en docplex/gurobipy
    # 3. Resolver
    # 4. Devolver la ruta (GeoJSON) y costo
    
    # Retornamos un placeholder por ahora
    return (None, 0)

def calc_metaheuristica(conn, start_node, end_node, req: RouteRequest):
    """
    5d: (Stub) Metaheurística (Ej. Algoritmo Genético - GA).
    
    Detalle del Funcionamiento:
    1. Población: Se crea una población de 'individuos' (rutas aleatorias).
    2. Función Fitness: Cada ruta se evalúa. El 'fitness' es el inverso
       de su costo total (costo_combinado). Las rutas con menor costo
       tienen mejor fitness.
    3. Selección: Se seleccionan las mejores rutas (padres).
    4. Cruce (Crossover): Se combinan partes de dos rutas 'padre' para
       crear 'hijos' (nuevas rutas).
    5. Mutación: Se altera aleatoriamente una parte de una ruta (ej.
       cambiando un segmento) para explorar nuevas soluciones.
    6. Iteración: Se repite por N generaciones.
    7. Resultado: La mejor ruta encontrada en todas las generaciones.
    
    Es bueno para problemas muy grandes donde CPLEX no termina.
    """
    print("Calculando Ruta 5d: Metaheurística (Stub - Implementación compleja pendiente)")
    # --- Aquí iría la lógica de Python para el GA ---
    
    # Retornamos un placeholder por ahora
    return (None, 0)


# --- El Endpoint Principal de la API --------------------------------

@app.post("/api/v1/route")
async def get_routes_endpoint(req: RouteRequest):
    """
    Endpoint principal. Recibe el request, calcula las 4 rutas,
    mide sus tiempos y devuelve todo.
    """
    conn = get_db_conn()
    if not conn:
        raise fastapi.HTTPException(status_code=500, detail="Error de conexión a BD")

    try:
        # 1. Encontrar nodos de inicio y fin
        start_node = find_nearest_node(conn, req.start_lon, req.start_lat)
        end_node = find_nearest_node(conn, req.end_lon, req.end_lat)
        
        if not start_node or not end_node:
            raise fastapi.HTTPException(status_code=404, detail="No se encontraron nodos cercanos al inicio o fin")

        results = {}

        # 2. Calcular Ruta 5a (Dijkstra Distancia)
        t_start = time.perf_counter()
        geo_a, cost_a = calc_dijkstra_distancia(conn, start_node, end_node, req.vehicle_width)
        t_end = time.perf_counter()
        results['dijkstra_distancia'] = {
            "geojson": geo_a,
            "cost": cost_a,
            "time_ms": (t_end - t_start) * 1000
        }

        # 3. Calcular Ruta 5c (Dijkstra Ponderado)
        t_start = time.perf_counter()
        geo_c, cost_c = calc_dijkstra_ponderado(conn, start_node, end_node, req.vehicle_width)
        t_end = time.perf_counter()
        results['dijkstra_ponderada'] = {
            "geojson": geo_c,
            "cost": cost_c,
            "time_ms": (t_end - t_start) * 1000
        }

        # 4. Calcular Ruta 5b (CPLEX) - Stub
        t_start = time.perf_counter()
        geo_b, cost_b = calc_cplex_optimizado(conn, start_node, end_node, req)
        t_end = time.perf_counter()
        results['cplex_optimizado'] = {
            "geojson": geo_b,
            "cost": cost_b,
            "time_ms": (t_end - t_start) * 1000
        }
        
        # 5. Calcular Ruta 5d (Metaheurística) - Stub
        t_start = time.perf_counter()
        geo_d, cost_d = calc_metaheuristica(conn, start_node, end_node, req)
        t_end = time.perf_counter()
        results['metaheuristica'] = {
            "geojson": geo_d,
            "cost": cost_d,
            "time_ms": (t_end - t_start) * 1000
        }

    finally:
        conn.close()

    return {
        "request_params": req.dict(),
        "nodes": {"start_node_id": start_node, "end_node_id": end_node},
        "routes": results
    }

# --- Para ejecutar la API (localmente) -----------------------------
if __name__ == "__main__":
    import uvicorn
    # Ejecuta: uvicorn main:app --reload
    uvicorn.run(app, host="0.0.0.0", port=8000)