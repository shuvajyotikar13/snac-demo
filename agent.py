import json
import logging
import os
import pandas as pd
from datetime import datetime
from chdb import session

import chdb
from confluent_kafka import Consumer, KafkaException
from google.cloud import aiplatform
from vertexai.generative_models import GenerativeModel
import clickhouse_driver

# ==========================================
# CONFIGURATION
# ==========================================
# Ensure you have authenticated via `gcloud auth application-default login`
# or set your GOOGLE_APPLICATION_CREDENTIALS environment variable.
GCP_PROJECT = os.environ.get("GCP_PROJECT_ID", "your-gcp-project-id")
GCP_REGION = "us-central1"

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("snac_agent")

# ==========================================
# INITIALIZATION: Gemini & ClickHouse
# ==========================================
aiplatform.init(project=GCP_PROJECT, location=GCP_REGION)
gemini_model = GenerativeModel("gemini-2.5-flash")

ch_client = clickhouse_driver.Client(
    host='localhost', 
    user='default', 
    password='snacdemo', 
    port=19000
)
ch_client.execute('''
    CREATE TABLE IF NOT EXISTS triage_intelligence (
        triage_time DateTime,
        ip_address String,
        event_type String,
        risk_score UInt8,
        recommended_action String,
        raw_log String
    ) ENGINE = MergeTree() ORDER BY triage_time;
''')

# ==========================================
# LOCALIZED STATE: chDB
# ==========================================
logger.info("Initializing chDB localized cache...")

# 1. Instantiate a stateful session for the agent's memory
local_reflex = session.Session()

# 2. Execute queries against THIS session so state is retained
local_reflex.query("CREATE DATABASE IF NOT EXISTS localized_cache;")
local_reflex.query("CREATE TABLE IF NOT EXISTS localized_cache.malicious_ips (ip String, last_seen DateTime) ENGINE = MergeTree() ORDER BY ip;")
def is_ip_blocked(ip):
    result = local_reflex.query(f"SELECT count() FROM localized_cache.malicious_ips WHERE ip = '{ip}'", "DataFrame")
    return int(result.iloc[0, 0]) > 0

def block_ip_locally(ip):
    local_reflex.query(f"INSERT INTO localized_cache.malicious_ips VALUES ('{ip}', now())")

# ==========================================
# CONSUMER LOOP
# ==========================================
SYSTEM_PROMPT = """
You are a Real-time Security Triage Agent analyzing raw logs.
Output ONLY valid JSON with this schema:
{"event_type": "string", "risk_score": "int (1-10)", "recommended_action": "string (ban_ip, alert, ignore)"}
"""

consumer = Consumer({
    'bootstrap.servers': '127.0.0.1:9092',
    'group.id': "snac_triage_group",
    'auto.offset.reset': 'earliest'
})
consumer.subscribe(['raw_security_logs'])

logger.info("Listening to Kafka stream. Press Ctrl+C to stop...")

try:
    while True:
        msg = consumer.poll(timeout=1.0)
        if msg is None: continue
        if msg.error(): continue

        raw_log = msg.value().decode('utf-8')
        log_data = json.loads(raw_log)
        ip_address = log_data.get("src_ip", "0.0.0.0")

        # 1. SENSE (Check Local Memory First)
        if is_ip_blocked(ip_address):
            logger.warning(f"BLOCKED IP REJECTED AT EDGE: {ip_address}. Skipping LLM.")
            continue

        # 2. REASON (Gemini API)
        prompt = f"{SYSTEM_PROMPT}\n\nLog to triage:\n{raw_log}"
        response = gemini_model.generate_content(prompt)
        triage_results = json.loads(response.text.strip("`json\n ").strip(" \n`"))

        logger.info(f"Analyzed {ip_address} -> Risk: {triage_results['risk_score']}, Action: {triage_results['recommended_action']}")

        # 3. ACT (Update State & Persist)
        if triage_results['risk_score'] >= 8:
            logger.error(f"ACTION TAKEN: Banning IP {ip_address} in chDB local cache.")
            block_ip_locally(ip_address)

        enriched_event = {
            "triage_time": datetime.utcnow(),
            "ip_address": ip_address,
            "event_type": triage_results["event_type"],
            "risk_score": triage_results["risk_score"],
            "recommended_action": triage_results["recommended_action"],
            "raw_log": raw_log
        }
        
        ch_client.execute('INSERT INTO triage_intelligence VALUES', [enriched_event])

except KeyboardInterrupt:
    logger.info("Shutting down agent.")
finally:
    consumer.close()
    ch_client.disconnect()
