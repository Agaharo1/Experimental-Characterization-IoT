import json
import socket
import time
from datetime import datetime, timezone

import paho.mqtt.client as mqtt


SMARTPOWER_IP = "192.168.4.1"   
SMARTPOWER_PORT = 23              

MQTT_IP = "192.168.1.35"        
MQTT_PORT = 1883
MQTT_TOPIC = "iot/power/gateway"  


SAMPLES_MIN = 10
RECONNECT_TEMP = 3


def parse(line: str):

    parts = line.strip().split(",")
    if len(parts) != 4:
        return None
    try:
        return {
            "volts":     float(parts[0]),
            "amps":      float(parts[1]),
            "watts":     float(parts[2]),
            "watt_hour": float(parts[3]),
        }
    except ValueError:
        return None


def estadist(muest: list) -> dict:
  
    num = len(muest)
    return {
        "volts_avg":     sum(s["volts"]     for s in muest) / num,
        "amps_avg":      sum(s["amps"]      for s in muest) / num,
        "watts_avg":     sum(s["watts"]     for s in muest) / num,
        "watts_min":     min(s["watts"]     for s in muest),
        "watts_max":     max(s["watts"]     for s in muest),
        "watt_hour":     muest[-1]["watt_hour"],
    }


def main():
    print(f"Conectando a MQTT {MQTT_IP}:{MQTT_PORT}...")
    mqtt_client = mqtt.Client()
    mqtt_client.connect(MQTT_IP, MQTT_PORT, keepalive=30)
    mqtt_client.loop_start()

    while True:
        try:
            print(f"Conectando a SmartPower2 telnet {SMARTPOWER_IP}:{SMARTPOWER_PORT}...")
            with socket.create_connection((SMARTPOWER_IP, SMARTPOWER_PORT), timeout=5) as sock:
    
                buffer = ""
                pending = []

                print(f"Leyendo muestras (publica cada {SAMPLES_MIN} muestras en '{MQTT_TOPIC}')...")
                while True:

                    datos_brutos = sock.recv(4096) #esto sirve pa
                    if not datos_brutos:
                        raise ConnectionError("Telnet cerrado por el otro extremo")

                    buffer += datos_brutos.decode("ascii", errors="ignore")
                    while "\n" in buffer: #Mientras haya datos en el buffer ...
                        line, buffer = buffer.split("\n", 1)
                        sample = parse(line)
                        if sample is None:
                            continue
                        pending.append(sample)

                        if len(pending) >= SAMPLES_MIN:
                            payload = estadist(pending)
                            mqtt_client.publish(MQTT_TOPIC, json.dumps(payload), qos=0)
                            print(f"  publicado: watts_avg={payload['watts_avg']:.3f} "f"volts_avg={payload['volts_avg']:.3f} "f"amps_avg={payload['amps_avg']:.3f}")
                            pending.clear()

        except (socket.timeout, ConnectionError, OSError) as e:
            print(f"[WARN] Conexion perdida ({e}). Reintentando en {RECONNECT_TEMP}s...")
            time.sleep(RECONNECT_TEMP)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrumpido ")
