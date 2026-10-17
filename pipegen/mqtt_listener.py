"""Subscribe to SafeSight alerts and act on them (Closed-Loop bridge).

    pip install paho-mqtt pyserial
    python pipegen/mqtt_listener.py --host localhost                 # print alerts
    python pipegen/mqtt_listener.py --host localhost --serial COM5   # also send 'A\n' to an ESP32 over USB serial

The ESP32 firmware (see firmware/PRD_SAFESIGHT_ALARM.md) should light an LED / sound a buzzer when it receives
'A\n' (or, in the Wi-Fi variant, when it receives the MQTT message itself). Serial is the simplest bridge.
"""
import argparse, json

import paho.mqtt.client as mqtt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="localhost"); ap.add_argument("--port", type=int, default=1883)
    ap.add_argument("--topic", default="safesight/+/events"); ap.add_argument("--serial")
    ap.add_argument("--baud", type=int, default=115200)
    a = ap.parse_args()
    ser = None
    if a.serial:
        import serial
        ser = serial.Serial(a.serial, a.baud, timeout=1)

    def on_message(_c, _u, msg):
        try:
            m = json.loads(msg.payload)
        except ValueError:
            return print("bad payload", msg.payload[:80])
        print(f"ALERT {m.get('type')} zone={m.get('zone_id')} track={m.get('track_id')} t={m.get('video_time_s')} at {m.get('occurred_at')}")
        if ser and m.get("type") == "violation":
            ser.write(b"A\n")

    try:
        c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    except AttributeError:
        c = mqtt.Client()
    c.on_message = on_message
    c.connect(a.host, a.port)
    c.subscribe(a.topic, qos=1)
    print(f"listening on {a.topic} @ {a.host}:{a.port}")
    c.loop_forever()


if __name__ == "__main__":
    main()
