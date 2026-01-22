# Web Log Analysis & Monitoring (Kafka + Elasticsearch + Docker)

A real-time web-server log streaming, indexing, visualization, and monitoring pipeline built with **Apache Kafka**, **Elasticsearch**, **Kibana**, **Prometheus**, and **Grafana**, orchestrated via **Docker Compose**. The system is designed to be modular, scalable, and fault-tolerant for large-scale log processing. 

---

## What this project does

1. **Preprocess raw web logs** (`access.log`) into structured **JSON lines**. 
2. **Stream JSON logs in real-time** to a Kafka topic using a **producer**.   
3. **Consume messages** from Kafka and **index** them into Elasticsearch in real time. 
4. **Visualize** indexed logs using Kibana dashboards. :contentReference[oaicite:4]{index=4}  
5. **Monitor** producers/consumers and pipeline health with Prometheus + Grafana (latency, throughput, etc.). 

---

## Dataset (not included in this repo)

This repository does **not** include the log dataset. Download it from Kaggle:

- Kaggle: https://www.kaggle.com/datasets/eliasdabbas/web-server-access-logs

Place the raw log file as:

The project is intended for large-scale web log analysis (the report references processing ~3.3GB logs and common fields like timestamps, methods, IPs, status, URLs, user agents). 

---

## Architecture (Dockerized services)

This project runs everything in containers to keep setup consistent and portable. 

### Services
- **Zookeeper** (Kafka coordination)
- **Kafka brokers (3)** for scalability + fault tolerance
- **Elasticsearch** for indexing + search
- **Kibana** for log visualization
- **Prometheus** for metrics scraping
- **Grafana** for monitoring dashboards
- **script-runner** container to run Python producer/consumer/index scripts

Fault tolerance is improved using a 3-broker Kafka cluster and replication requirements (e.g., minimum in-sync replicas).

---

## Repository layout (expected)

.
├── docker-compose.yml
├── Dockerfile
├── preprocess_logs.py
├── kafka_producer.py
├── kafka_consumer.py
├── create_index.py
├── prometheus.yml
└── data/
└── access.log # (downloaded from Kaggle; not tracked)


---

## Prerequisites
- Docker + Docker Compose (Docker Desktop on Windows/macOS is fine)

---

## Quickstart

### 1) Start the stack
From the repo root:
```bash
docker compose up -d

```

###  2) Open UIs
Kibana: http://localhost:5601
Grafana: http://localhost:3000
 (default: admin / admin)

Prometheus: http://localhost:9090
Elasticsearch: http://localhost:9201

Note: In docker-compose.yml, Elasticsearch is mapped to host port 9201 (container port 9200).

Running the pipeline

All scripts are run inside the script-runner container (it mounts your repo at /app).

###  1) Enter the script-runner container

```bash
docker exec -it script-runner bash
cd /app

```

###  2) Create the Elasticsearch index (one-time)

```bash
python create_index.py

```
This creates an index (default: web_logs) with mappings (IP, timestamp, method, url, status, bytes, referrer, user_agent) and sets shards/replicas.

###  3) Preprocess raw logs into JSONL

```bash
python preprocess_logs.py

```
Input:
/app/data/access.log
Output:
/app/data/processed_logs.json

This step converts raw unstructured logs into structured JSON lines for ingestion.

###  4) Start the Kafka producer (streams JSON logs)
   
```bash
python kafka_producer.py producer_1 8000

```
Exposes Prometheus metrics on: http://<container>:8000/metrics
Sends messages to Kafka topic: web_topic

###  5) Start Kafka consumers (index into Elasticsearch)

```bash
Run these in separate terminals (or separate docker exec sessions):
docker exec -it script-runner bash -lc "cd /app && python kafka_consumer.py consumer_1 8001"
docker exec -it script-runner bash -lc "cd /app && python kafka_consumer.py consumer_2 8002"
docker exec -it script-runner bash -lc "cd /app && python kafka_consumer.py consumer_3 8003"

```
Each consumer:
Pulls from web_topic
Computes processing latency (based on producer timestamp)
Indexes to Elasticsearch via index_log(...)
Exposes Prometheus metrics at /metrics on its port
Running multiple consumers helps observe scalability and consumer latency behavior.


Monitoring (Prometheus + Grafana)
Metrics exposed
Producer: produced_messages{instance="..."}
Consumer: consumed_messages{instance="..."}
Consumer latency gauge: log_processing_latency{instance="..."}
The report notes consumer latency generally stays low (with occasional spikes under load), showing why continuous monitoring matters. 
Example prometheus.yml
If you don’t already have one, here is a minimal config you can use:

```bash
global:
  scrape_interval: 5s

scrape_configs:
  - job_name: "kafka-producers"
    static_configs:
      - targets: ["script-runner:8000"]

  - job_name: "kafka-consumers"
    static_configs:
      - targets: ["script-runner:8001", "script-runner:8002", "script-runner:8003"]

```
Prometheus can scrape script-runner:<port> over the Docker Compose network even if you don’t publish those ports to the host.

Troubleshooting
Kafka topic not found / no messages
Ensure producer is running and sending to web_topic.
Ensure consumers use the same topic name (web_topic) and brokers.
Elasticsearch not receiving data
Confirm index exists:

```bash
curl http://localhost:9201/_cat/indices?v

```

Confirm consumer logs show “Successfully indexed”.

Kibana shows nothing

Ensure Elasticsearch index has documents.
In Kibana, create a Data View for web_logs* and use timestamp as the time field.
