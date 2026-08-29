import os
import matplotlib.pyplot as plt
from influxdb import InfluxDBClient, DataFrameClient


INFLUX_HOST = '192.168.1.36' 
INFLUX_PORT = 8086
DB_NAME = 'sensores'
MEASUREMENT = 'mqtt_consumer'
MQTT_TOPIC = 'iot/power/gateway'

GROUP_BY_INTERVAL = '15s'
OUTPUT_DIR = 'resultados_consumo_power'


campos_consumo = {
    'volts_avg': ('Voltaje Medio (V)', '#1E90FF'),
    'amps_avg': ('Corriente Media (A)', '#FF8C00'),
    'watts_avg': ('Potencia Media (W)', '#32CD32'),
    'watts_max': ('Potencia Máxima (W)', '#DC143C'), # Añadido por si quieres ver los picos
    'watt_hour': ('Energía Consumida (Wh)', '#8A2BE2')
}

print(f"Conectando a InfluxDB en {INFLUX_HOST}...")
df_client = DataFrameClient(host=INFLUX_HOST, port=INFLUX_PORT, database=DB_NAME)

def generar_grafica(query, nombre_metrica, unidad, color_linea, carpeta_destino):
    try:
        # Ejecutar la consulta en InfluxDB
        resultados = df_client.query(query)

        if MEASUREMENT not in resultados:
            print(f"    [AVISO] Sin datos para {nombre_metrica}.")
            return

        df = resultados[MEASUREMENT]

        if df.empty or df[nombre_metrica].isna().all():
            print(f"    [AVISO] Datos vacíos para {nombre_metrica}.")
            return

      
        minutos_transcurridos = (df.index - df.index[0]).total_seconds() / 60.0

        # Crear figura
        plt.figure(figsize=(10, 5))
        
        plt.plot(minutos_transcurridos, df[nombre_metrica], color=color_linea, linewidth=2.0, marker='o', markersize=4)

        # Configurar títulos y etiquetas
        titulo = f'Evolución de {nombre_metrica.upper()}\n(SmartPower2 Gateway)'
        plt.title(titulo.replace('\n', ' '), fontsize=14, fontweight='bold')
        plt.xlabel('Tiempo de medición (minutos)', fontsize=11, fontweight='bold')
        plt.ylabel(f'{nombre_metrica}\n({unidad})', fontsize=11, fontweight='bold')

        # Estilos de la gráfica
        plt.grid(True, linestyle='--', alpha=0.6)
        plt.xlim(left=0)
        
        
        if nombre_metrica != 'volts_avg':
            plt.ylim(bottom=0) 
        
        plt.tight_layout()

        # Guardar archivo
        nombre_archivo = f"grafica_{nombre_metrica}.png"
        ruta_archivo = os.path.join(carpeta_destino, nombre_archivo)

        plt.savefig(ruta_archivo, dpi=300)
        plt.close()
        print(f"    [OK] Guardada: {nombre_archivo}")

    except Exception as e:
        print(f"    [ERROR] Fallo al procesar {nombre_metrica}: {e}")

if __name__ == '__main__':

    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    print("\n--- GENERANDO GRÁFICAS DE CONSUMO ELÉCTRICO ---")
    print(f"Topic objetivo: {MQTT_TOPIC}")
    print(f"Destino: ./{OUTPUT_DIR}/")
    print("-" * 50)
    
    for metrica, (unidad, color) in campos_consumo.items():
        print(f" -> Consultando métrica: {metrica}")
        
    
        funcion_agregacion = 'last' if metrica == 'watt_hour' or metrica == 'watts_max' else 'mean'
        
        query = (
            f'SELECT {funcion_agregacion}("{metrica}") AS "{metrica}" '
            f'FROM "{MEASUREMENT}" '
            f'WHERE ("topic" = \'{MQTT_TOPIC}\') '
            f'GROUP BY time({GROUP_BY_INTERVAL}) fill(linear)'
        )
        
        generar_grafica(
            query=query, 
            nombre_metrica=metrica, 
            unidad=unidad, 
            color_linea=color, 
            carpeta_destino=OUTPUT_DIR
        )

    print("\n[INFO] Proceso finalizado. Revisa la carpeta de resultados.")