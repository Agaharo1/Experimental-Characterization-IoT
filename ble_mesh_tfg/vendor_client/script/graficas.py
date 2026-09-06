import os
import warnings
import pandas as pd
import matplotlib.pyplot as plt
from influxdb import InfluxDBClient, DataFrameClient

# Ocultar la advertencia roja de Pandas en la consola
warnings.filterwarnings("ignore", category=UserWarning)

# --- CONFIGURACIÓN ---
INFLUX_HOST = '192.168.1.36' 
INFLUX_PORT = 8086
DB_NAME = 'sensores'

OUTPUT_DIR = 'resultados_tfg_ble_individuales'

EXPERIMENTOS_TRANSFER = {
    '1_kb':   'transfer_1024b$',
    '10_kb':  'transfer_10240b$',
    '100_kb': 'transfer_102400b$'
}

CAMPOS_TRANSFER = {
    'received_chunks':     ('paquetes_entregados', 'Cantidad de paquetes', '#32CD32'), 
    'throughput_bps':      ('throughput_bps', 'Bytes por segundo (B/s)', '#1E90FF'),   
    'snr_estimate_avg_db': ('snr_promedio_db', 'Relación Señal/Ruido (dB)', '#FF8C00'),
    'tiempo_total':        ('tiempo_total_segundos', 'Segundos (s)', '#8A2BE2')     
}

CAMPOS_PING = {
    'latencia_avg':        ('latencia_promedio_ms', 'Milisegundos (ms)', '#8A2BE2'),  
    'pdr':                 ('tasa_entrega_pdr', 'Porcentaje (%)', '#32CD32'),         
    'snr_estimate_avg_db': ('snr_promedio_db', 'Relación Señal/Ruido (dB)', '#FF8C00') 
}

print(f"Conectando a InfluxDB en {INFLUX_HOST}...")
meta_client = InfluxDBClient(host=INFLUX_HOST, port=INFLUX_PORT, database=DB_NAME)
df_client = DataFrameClient(host=INFLUX_HOST, port=INFLUX_PORT, database=DB_NAME)

def obtener_nodos_ble():
    resultado = meta_client.query('SHOW TAG VALUES FROM "mqtt_consumer" WITH KEY = "node_addr"')
    puntos = list(resultado.get_points())
    return sorted(set(p['value'] for p in puntos))

def aislar_ultimo_experimento(df):
    """
    Busca si hay datos de pruebas antiguas en la base de datos y los recorta,
    quedándose ÚNICAMENTE con los datos de la última prueba ininterrumpida.
    """
    df = df.sort_index()
    diferencias = df.index.to_series().diff()
    # Si hay un parón de más de 30 segundos, consideramos que es una prueba nueva
    saltos = diferencias[diferencias > pd.Timedelta(seconds=30)]
    if not saltos.empty:
        ultimo_salto = saltos.index[-1]
        df = df.loc[ultimo_salto:]
    return df

def generar_grafica(df, columna_datos, nombre_archivo_base, unidad, color_linea, carpeta_destino, titulo_extra, sufijo_archivo):
    if columna_datos not in df.columns:
        return

    # Quitamos huecos vacíos
    df_limpio = df[[columna_datos]].dropna()
    if df_limpio.empty:
        return

    # Calculamos los minutos transcurridos SÓLO desde que empezó esta prueba
    minutos_transcurridos = (df_limpio.index - df_limpio.index[0]).total_seconds() / 60.0

    plt.figure(figsize=(10, 5))
    
    # Si solo hay 1 punto (ej. prueba super corta), dibujamos solo el punto
    if len(df_limpio) == 1:
        plt.plot(minutos_transcurridos, df_limpio[columna_datos], color=color_linea, marker='o', markersize=6)
    else:
        plt.plot(minutos_transcurridos, df_limpio[columna_datos], color=color_linea, linewidth=2.0, marker='o', markersize=4)

    titulo = f'Evolución de {nombre_archivo_base.upper()}'
    if titulo_extra:
        titulo += f'\n({titulo_extra})'

    plt.title(titulo.replace('\n', ' '), fontsize=14, fontweight='bold')
    plt.xlabel('Tiempo de transmisión activa (minutos)', fontsize=11, fontweight='bold')
    plt.ylabel(f'{nombre_archivo_base}\n({unidad})', fontsize=11, fontweight='bold')

    plt.grid(True, linestyle='--', alpha=0.6)
    
    # Esto fuerza a que la gráfica acabe EXACTAMENTE en el último dato
    limite_derecho = minutos_transcurridos[-1] if len(minutos_transcurridos) > 1 else 0.05
    plt.xlim(left=0, right=limite_derecho)
    
    if nombre_archivo_base != 'snr_promedio_db':
        plt.ylim(bottom=0) 
    
    plt.tight_layout()

    nombre_archivo = f"{nombre_archivo_base}_{sufijo_archivo}.png"
    ruta_archivo = f'{carpeta_destino}/{nombre_archivo}'

    plt.savefig(ruta_archivo, dpi=300)
    plt.close()
    print(f"    [OK] Guardada: {nombre_archivo}")

# --- EJECUCIÓN PRINCIPAL ---
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

nodos = obtener_nodos_ble()

if nodos:
    print(f"\nNodos BLE detectados: {nodos}")
    
    for nodo in nodos:
        nodo_limpio = nodo.replace('0x', '')
        carpeta_destino = f'{OUTPUT_DIR}/nodo_{nodo_limpio}'
        if not os.path.exists(carpeta_destino):
            os.makedirs(carpeta_destino)

        print(f"\n--- Procesando Nodo {nodo} ---")

        for exp_nombre, exp_regex in EXPERIMENTOS_TRANSFER.items():
            print(f"  -> Extrayendo datos de Transferencia: {exp_nombre}")
            
            # ATENCIÓN: Ya no usamos GROUP BY. Pedimos los datos puros.
            query = (
                f'SELECT "received_chunks", "throughput_bps", "snr_estimate_avg_db", "total_bytes_observed" '
                f'FROM "mqtt_consumer" '
                f'WHERE ("node_addr"::tag = \'{nodo}\') AND ("topic" =~ /{exp_regex}/)'
            )
            
            try:
                resultados = df_client.query(query)
                if 'mqtt_consumer' in resultados:
                    df = resultados['mqtt_consumer']
                    
                    # Cortamos los datos antiguos
                    df = aislar_ultimo_experimento(df)
                    
                    if 'total_bytes_observed' in df.columns and 'throughput_bps' in df.columns:
                        # Prevenimos divisiones por 0 de manera segura
                        throughput_valido = df['throughput_bps'].replace(0, pd.NA)
                        df['tiempo_total'] = (df['total_bytes_observed'] * 8) / throughput_valido

                    for campo_influx, (nombre_archivo, unidad, color) in CAMPOS_TRANSFER.items():
                        generar_grafica(
                            df=df,
                            columna_datos=campo_influx,
                            nombre_archivo_base=nombre_archivo,
                            unidad=unidad,
                            color_linea=color,
                            carpeta_destino=carpeta_destino,
                            titulo_extra=f"BLE Mesh -- Nodo {nodo_limpio} -- Exp: {exp_nombre.upper()}",
                            sufijo_archivo=exp_nombre
                        )
            except Exception as e:
                print(f"    [ERROR] Fallo en {exp_nombre}: {e}")

        print(f"  -> Extrayendo datos de Ping")
        query_ping = (
            f'SELECT "latencia_avg", "pdr", "snr_estimate_avg_db" '
            f'FROM "mqtt_consumer" '
            f'WHERE ("node_addr"::tag = \'{nodo}\') AND ("topic" =~ /ping$/)'
        )
        
        try:
            res_ping = df_client.query(query_ping)
            if 'mqtt_consumer' in res_ping:
                df_ping = res_ping['mqtt_consumer']
                
                # Cortamos los datos antiguos
                df_ping = aislar_ultimo_experimento(df_ping)

                for campo_influx, (nombre_archivo, unidad, color) in CAMPOS_PING.items():
                    generar_grafica(
                        df=df_ping,
                        columna_datos=campo_influx,
                        nombre_archivo_base=nombre_archivo,
                        unidad=unidad,
                        color_linea=color,
                        carpeta_destino=carpeta_destino,
                        titulo_extra=f"BLE Mesh -- Nodo {nodo_limpio} -- Exp: PING",
                        sufijo_archivo="ping"
                    )
        except Exception as e:
            print(f"    [ERROR] Fallo en Ping: {e}")

else:
    print("\n[AVISO] No se encontraron datos de nodos BLE Mesh en InfluxDB.")

print("\nListo. Gráficas ajustadas exactamente al tiempo de transmisión activa.")