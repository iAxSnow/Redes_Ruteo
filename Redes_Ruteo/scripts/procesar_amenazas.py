import psycopg2
import sys

# --- Configuración de la Base de Datos ---
DB_CONFIG = {
    "host": "localhost", # O el nombre de tu servicio de Docker
    "dbname": "tu_base_de_datos",
    "user": "tu_usuario",
    "password": "tu_contraseña",
    "port": "5432"
}

# --- Parámetros del Modelo de Costo (AJUSTA ESTOS VALORES) ---

# Pesos para calcular la penalización de costo:
# ¿Cuánto importa la severidad vs. el impacto crítico?
W_SEVERIDAD = 0.5  
W_IMPACTO = 1.5   # Damos más peso al impacto en la misión

# Distancias de búfer para las amenazas (en metros)
# ST_DWithin usará estas distancias. Requiere que las geometrías estén en un SRID en metros.
# ¡TU SRID ES 4326 (grados)! Necesitamos transformar o castear a geography.
# Usaremos 'geography' para cálculos en metros con SRID 4326.
DIST_CALMING = 15     # Afecta a calles a 15m del lomo de toro
DIST_WAZE = 15        # Afecta a calles a 15m del incidente Waze
DIST_WEATHER = 500    # Afecta a calles a 500m del punto de clima

# Pesos para el costo combinado final (Req #5c)
W_DISTANCIA = 1.0  # Peso para la longitud (length_m)
W_RIESGO = 3.0     # Peso para la penalización (costo_amenaza)


def conectar_db():
    """Establece conexión con la base de datos PostGIS."""
    try:
        conn_str = " ".join([f"{k}='{v}'" for k, v in DB_CONFIG.items()])
        conn = psycopg2.connect(conn_str)
        return conn
    except Exception as e:
        print(f"Error al conectar a la BD: {e}")
        sys.exit(1)

def resetear_costos(conn):
    """Resetea los costos en rr.ways antes de recalcular."""
    print("Reseteando costos en rr.ways...")
    with conn.cursor() as cur:
        cur.execute("""
            UPDATE rr.ways
            SET prob_falla = 0.0,
                costo_amenaza = 0.0,
                costo_combinado = NULL;
        """)
    conn.commit()

def procesar_amenazas(conn):
    """Procesa todas las tablas de amenazas y actualiza rr.ways."""
    print("Procesando amenazas...")
    
    # Lista de amenazas: (tabla, radio_en_metros)
    amenazas_config = [
        ("rr.amenazas_calming", DIST_CALMING),
        ("rr.amenazas_waze", DIST_WAZE),
        ("rr.amenazas_weather", DIST_WEATHER)
    ]
    
    with conn.cursor() as cur:
        for tabla, distancia in amenazas_config:
            print(f"  Procesando tabla: {tabla} con radio {distancia}m...")
            
            # NOTA: Usamos 'geom::geography' para que ST_DWithin funcione en metros
            # con SRID 4326 (grados).
            sql_update = f"""
            WITH amenazas AS (
                SELECT 
                    geom::geography AS geog,
                    -- Cálculo de penalización y probabilidad
                    (severidad * %s) + (impacto_critico * %s) AS penalizacion,
                    -- Normaliza la probabilidad (asumiendo max 10 en sev/imp)
                    (severidad + impacto_critico) / 20.0 AS prob
                FROM {tabla}
            )
            UPDATE rr.ways w
            SET 
                -- Acumula el costo de amenaza (una calle puede tener varias)
                costo_amenaza = w.costo_amenaza + a.penalizacion,
                -- La probabilidad de falla es la MÁXIMA que encuentre
                prob_falla = GREATEST(w.prob_falla, a.prob)
            FROM amenazas a
            WHERE 
                -- Comprueba si la calle está dentro del radio de la amenaza
                ST_DWithin(w.geom::geography, a.geog, %s);
            """
            
            try:
                cur.execute(sql_update, (W_SEVERIDAD, W_IMPACTO, distancia))
                print(f"    - {cur.rowcount} filas de 'ways' actualizadas por {tabla}.")
            except Exception as e:
                print(f"ERROR al procesar {tabla}: {e}")
                conn.rollback()
                return

    conn.commit()

def calcular_costo_combinado(conn):
    """Calcula el costo combinado final para Dijkstra ponderado."""
    print("Calculando costo combinado final...")
    with conn.cursor() as cur:
        # Asegura que length_m no sea nulo
        cur.execute("UPDATE rr.ways SET length_m = 0 WHERE length_m IS NULL;")
        
        cur.execute("""
            UPDATE rr.ways
            SET costo_combinado = (length_m * %s) + (costo_amenaza * %s);
        """, (W_DISTANCIA, W_RIESGO))
        
        # Caso especial: calles intransitables (prob_falla = 1.0)
        # Asigna un costo "infinito" (o muy alto)
        cur.execute("""
            UPDATE rr.ways
            SET costo_combinado = 9999999.0
            WHERE prob_falla >= 1.0;
        """)
        
    conn.commit()
    print("Cálculo de costo combinado finalizado.")

# --- Ejecución Principal ---
if __name__ == "__main__":
    conn = conectar_db()
    if conn:
        resetear_costos(conn)
        procesar_amenazas(conn)
        calcular_costo_combinado(conn)
        conn.close()
        print("\n¡Proceso de actualización de amenazas completado!")