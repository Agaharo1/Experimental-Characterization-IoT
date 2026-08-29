import time
import json
import paho.mqtt.client as mqtt
from pubsub import pub
import meshtastic.serial_interface

DESTINATION_NODE = "!02ed8570" 
PAYLOAD_SIZE = 200 

EXPERIMENTOS = {
    "1_KB": 5,      
    "10_KB": 50,    
    "100_KB": 500   
}

MQTT_BROKER = "192.168.1.36" 
MQTT_PORT = 1883
MQTT_TOPIC_BASE = f"iot/mesh/node/{DESTINATION_NODE.strip('!')}/metrics/experimentos"

# Variables globales
waiting_for_ack = False
ack_received = False
last_snr = 0.0

mqtt_client = mqtt.Client()

def on_receive(packet, interface):
    global waiting_for_ack, ack_received, last_snr
    
    if waiting_for_ack and packet.get('decoded', {}).get('portnum') == 'ROUTING_APP':
        ack_received = True
        waiting_for_ack = False
        last_snr = packet.get('rxSnr', 0.0)

def ejecutar_experimento(interface, nombre, num_paquetes):
    global waiting_for_ack, ack_received, last_snr
    
    print(f"\n{'='*60}")
    print(f"🚀 INICIANDO EXPERIMENTO: {nombre} ({num_paquetes} paquetes)")
    print(f"{'='*60}")
    
    payload_data = "X" * PAYLOAD_SIZE
    paquetes_exitosos = 0
    lista_snr = []
    
    # Inicia el cronómetro maestro del experimento
    tiempo_inicio_total = time.time()
    
    for i in range(num_paquetes):
        ack_received = False
        waiting_for_ack = True
        last_snr = 0.0
        paquete_actual = i + 1
        
        print(f"📦 Enviando paquete {paquete_actual}/{num_paquetes}...")
        tiempo_envio_paquete = time.time()
        
        interface.sendData(payload_data.encode('utf-8'), 
                           destinationId=DESTINATION_NODE, 
                           portNum=256,
                           wantAck=True)
        
        # Espera hasta 15 segundos por el ACK
        while waiting_for_ack and (time.time() - tiempo_envio_paquete) < 15:
            time.sleep(0.1)
            
        if ack_received:
            tiempo_llegada_ack = time.time()
            latencia = (tiempo_llegada_ack - tiempo_envio_paquete) / 2
            throughput_paquete = PAYLOAD_SIZE / latencia if latencia > 0 else 0
            
            print(f"  ✅ ACK: Latencia {latencia:.2f}s | Throughput {throughput_paquete:.2f} B/s | SNR: {last_snr} dB")
            
            paquetes_exitosos += 1
            lista_snr.append(last_snr)
        else:
            print("  ❌ Timeout: Paquete perdido.")
            waiting_for_ack = False
            

        tiempo_transcurrido = time.time() - tiempo_inicio_total
        bytes_entregados_acumulados = paquetes_exitosos * PAYLOAD_SIZE
        
        throughput_acumulado = bytes_entregados_acumulados / tiempo_transcurrido if tiempo_transcurrido > 0 else 0
        snr_promedio_acumulado = sum(lista_snr) / len(lista_snr) if len(lista_snr) > 0 else 0.0
        
        mqtt_payload = {
            "mac": DESTINATION_NODE,
            "experimento": nombre,
            "paquetes_intentados": paquete_actual,
            "paquetes_entregados": paquetes_exitosos,
            "tiempo_total_segundos": round(tiempo_transcurrido, 2),
            "throughput_bps": round(throughput_acumulado, 2),
            "snr_promedio_db": round(snr_promedio_acumulado, 2)
        }
        
        topic = f"{MQTT_TOPIC_BASE}/{nombre.lower()}"
        mqtt_client.publish(topic, json.dumps(mqtt_payload))
        # Quitado el print() de MQTT en cada ciclo para no saturarte la pantalla de texto,
        # pero los datos sí se están enviando al servidor.
        
        # Pausa obligatoria por Duty Cycle antes de lanzar el siguiente
        time.sleep(1) 
        
    print(f"\n🏁 FIN DEL EXPERIMENTO {nombre}")
    print(f"   Entregados: {paquetes_exitosos}/{num_paquetes}")
    print(f"   Tiempo: {tiempo_transcurrido:.2f}s | Throughput: {throughput_acumulado:.2f} B/s | SNR: {snr_promedio_acumulado:.2f} dB")


def main():
    print("Conectando al broker MQTT...")
    try:
        mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
        mqtt_client.loop_start()
    except Exception as e:
        print(f"❌ Error MQTT: {e}")
        return

    print("Conectando al Nodo Base por USB...")
    interface = meshtastic.serial_interface.SerialInterface()
    pub.subscribe(on_receive, "meshtastic.receive")
    
    try:
        for nombre, num_paquetes in EXPERIMENTOS.items():
            ejecutar_experimento(interface, nombre, num_paquetes)
            
            if nombre != "100_KB":
                print("⏳ Esperando 15 segundos para que la radio descanse...")
                time.sleep(15)

    except KeyboardInterrupt:
        print("\nInterrumpido por el usuario.")
    
    print("\n🏁 TODOS LOS EXPERIMENTOS COMPLETADOS.")
    interface.close()
    mqtt_client.loop_stop()
    mqtt_client.disconnect()


if __name__ == "__main__":
    main()