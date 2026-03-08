import json
import time
import random
from confluent_kafka import Producer

KAFKA_BROKER = '127.0.0.1:9092'
TOPIC = 'raw_security_logs'

producer = Producer({'bootstrap.servers': KAFKA_BROKER})

def delivery_report(err, msg):
    if err is not None:
        print(f"Message delivery failed: {err}")
    else:
        print(f"Produced event to topic {msg.topic()}")

# Mock unstructured logs
sample_logs = [
    {"timestamp": time.time(), "src_ip": "192.168.1.50", "msg": "User login successful via SSH."},
    {"timestamp": time.time(), "src_ip": "10.0.0.5", "action": "DROP", "reason": "Malformed packet detected on port 80."},
    {"timestamp": time.time(), "src_ip": "45.33.22.11", "payload": "GET /etc/passwd HTTP/1.1", "status": "403 Forbidden"},
    {"timestamp": time.time(), "src_ip": "10.0.0.5", "alert": "Repeated failed login attempts (15) in 2 seconds."}
]

print("Starting to produce messy logs to Kafka...")
try:
    while True:
        log_event = random.choice(sample_logs)
        producer.produce(TOPIC, json.dumps(log_event).encode('utf-8'), callback=delivery_report)
        producer.poll(0)
        time.sleep(2) # Send a log every 2 seconds
except KeyboardInterrupt:
    print("Stopping producer.")
finally:
    producer.flush()
