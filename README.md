# SnAC: Sense and Act (React is Dead) ⚡️

Passive analytical pipelines are a liability. This repository contains the code for the **SnAC Architecture**, demonstrating how to inject a serverless reasoning engine directly into an Apache Kafka stream. 

By combining Kafka, Google's Gemini 1.5 Flash, chDB (for localized memory), and ClickHouse, this pipeline doesn't just move data—it *reasons* about unstructured payloads and *acts* on threats in real-time before they ever hit the disk.

[Image of The SnAC Architecture showing Kafka streaming to Google Cloud Run with Gemini and chDB, persisting to ClickHouse]

---

## ⏱ Quickstart: Run this in under 2 minutes

### Prerequisites
* Docker & Docker Compose
* Python 3.10+
* A Google Cloud Project with the Vertex AI API enabled

### Step 1: Clone and Setup Infrastructure
Clone the repository and spin up the local Kafka broker and ClickHouse database.

```bash
git clone [https://github.com/yourusername/snac-kafka-demo.git](https://github.com/yourusername/snac-kafka-demo.git)
cd snac-kafka-demo

# Spin up local Kafka and ClickHouse
docker-compose up -d
```
### Step 2: Install Dependencies
Create a clean Python environment and install the required libraries.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Step 3: Authenticate with Google Cloud
The SnAC agent uses Vertex AI to access Gemini 1.5 Flash. Ensure your local environment is authenticated:

```bash
gcloud auth application-default login
export GCP_PROJECT_ID="your-actual-gcp-project-id"
```

## 🚀 Running the Demo
You will need two separate terminal windows to see the architecture in action.

### Terminal 1: Start the Agent
Boot up the reasoning engine. It will initialize its local chDB cache, create the necessary tables in ClickHouse, and start listening to the Kafka stream.

```bash
source .venv/bin/activate
python agent.py
```
### Terminal 2: Unleash the Firehose
In a new terminal window, start the producer. This will pump simulated, unstructured firewall logs into the Kafka topic.

```bash
source .venv/bin/activate
python producer.py
```

## 👀 What to Watch For
Keep your eyes on Terminal 1 (the Agent). You are looking for the millisecond reflex in action.

#### The First Attack: When a malicious IP (e.g., 10.0.0.5) hits the stream, watch Gemini reason about the payload, assign a high risk score, and execute the ban_ip action.

##### The Localized Reflex: Watch what happens when that same IP attacks again. The agent will drop it at the edge using its chDB cache. You will see:

WARNING:snac_agent:BLOCKED IP REJECTED AT EDGE: 10.0.0.5. Skipping LLM.

### Verification
Open a third terminal to query ClickHouse and see the perfectly structured, AI-enriched intelligence that was persisted after the agent took action:

```bash
docker exec -it <clickhouse_container_id> clickhouse-client --query="SELECT triage_time, ip_address, event_type, risk_score, recommended_action FROM triage_intelligence"
```

## 🧹 Teardown
To clean up your environment, stop the Python scripts (Ctrl+C) and tear down the Docker containers:

```bash
docker-compose down
```
