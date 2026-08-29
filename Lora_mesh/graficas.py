import os
import matplotlib.pyplot as plt
from influxdb import InfluxDBClient, DataFrameClient


INFLUX_HOST = '192.168.1.36' 
INFLUX_PORT = 8086
DB_NAME = 'sensores'

GROUP_BY_INTERVAL = '15s'
OUTPUT_DIR = 'resultados_tfg_lora'

EXPERIMENTOS = ['1_KB', '10_KB', '100_KB']

campos_rendimiento = {
    'throughput_bps': ('Bytes por segundo (B/s)', '#1E90FF'),
    'snr_promedio_db': ('Relación Señal/Ruido (dB)', '#FF8C00'),
    'paquetes_entregados': ('Cantidad de paquetes', '#32CD32'),
    'tiempo_total_segundos': ('Segundos (s)', '#8A2BE2')
}

print(f"Conectando a InfluxDB en {INFLUX_HOST}...")
meta_client = InfluxDBClient(host=INFLUX_HOST, port=INFLUX_PORT, database=DB_NAME)
df_client = DataFrameClient(host=INFLUX_HOST, port=INFLUX_PORT, database=DB_NAME)

def obtener_nodos_lora():
    resultado = meta_client.query('SHOW TAG VALUES FROM "mqtt_consumer" WITH KEY = "mac"')
    puntos = list(resultado.get_points())
    nodos = sorted(set(p['value'] for p in puntos))
    return nodos

def generar_grafica(query, nombre_metrica, unidad, color_linea, carpeta_destino, titulo_extra="", sufijo_archivo=""):
    try:
        resultados = df_client.query(query)

        if 'mqtt_consumer' not in resultados:
            print(f"    [AVISO] Sin datos para {nombre_metrica}{sufijo_archivo}.")
            return

        df = resultados['mqtt_consumer']

        if df.empty or df[nombre_metrica].isna().all():
            print(f"    [AVISO] Datos vacíos para {nombre_metrica}{sufijo_archivo}.")
            return

        minutos_transcurridos = (df.index - df.index[0]).total_seconds() / 60.0

        plt.figure(figsize=(10, 5))
        
        plt.plot(minutos_transcurridos, df[nombre_metrica], color=color_linea, linewidth=2.0, marker='o', markersize=4)

        titulo = f'Evolución de {nombre_metrica.upper()}'
        if titulo_extra:
            titulo += f'\n({titulo_extra})'

        plt.title(titulo.replace('\n', ' '), fontsize=14, fontweight='bold')
        plt.xlabel('Tiempo del experimento (minutos)', fontsize=11, fontweight='bold')
        plt.ylabel(f'{nombre_metrica}\n({unidad})', fontsize=11, fontweight='bold')

        plt.grid(True, linestyle='--', alpha=0.6)
        plt.xlim(left=0)
        
        if nombre_metrica != 'snr_promedio_db':
            plt.ylim(bottom=0) 
        
        plt.tight_layout()

        nombre_archivo = f"{nombre_metrica}{sufijo_archivo}"
        ruta_archivo = f'{carpeta_destino}/{nombre_archivo}.png'

        plt.savefig(ruta_archivo, dpi=300)
        plt.close()
        print(f"    [OK] Guardada: {nombre_archivo}.png")

    except Exception as e:
        print(f"    [ERROR] Fallo al procesar {nombre_metrica}{sufijo_archivo}: {e}")


if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

nodos = obtener_nodos_lora()

if nodos:
    print(f"\nNodos LoRa detectados: {nodos}")
    
    for nodo in nodos:
        nodo_limpio = nodo.replace('!', '')
        carpeta_nodo = f'{OUTPUT_DIR}/nodo_{nodo_limpio}'
        if not os.path.exists(carpeta_nodo):
            os.makedirs(carpeta_nodo)

    print("\n--- GENERANDO GRÁFICAS DE RENDIMIENTO ---")
    for nodo in nodos:
        nodo_limpio = nodo.replace('!', '')
        carpeta_destino = f'{OUTPUT_DIR}/nodo_{nodo_limpio}'
        print(f"\nProcesando Nodo {nodo}:")
        
        for exp in EXPERIMENTOS:
            print(f"  -> Extrayendo datos del experimento: {exp}")
            topic_suffix = exp.lower() 
            
            for metrica, (unidad, color) in campos_rendimiento.items():
                
                query = (
                    f'SELECT mean("{metrica}") AS "{metrica}" FROM "mqtt_consumer" '
                    f'WHERE ("mac"::tag = \'{nodo}\') AND ("topic" =~ /{topic_suffix}$/) '
                    f'GROUP BY time({GROUP_BY_INTERVAL}) fill(linear)'
                )
                
                generar_grafica(
                    query=query, 
                    nombre_metrica=metrica, 
                    unidad=unidad, 
                    color_linea=color, 
                    carpeta_destino=carpeta_destino, 
                    titulo_extra=f"LoRa Mesh -- Nodo {nodo} -- Exp: {exp}",
                    sufijo_archivo=f"_{topic_suffix}"
                )

else:
    print("\n[AVISO] No se encontraron datos de nodos LoRa ('mac') en InfluxDB.")

print("\n Listo. Todas las gráficas se han generado y separado correctamente.")