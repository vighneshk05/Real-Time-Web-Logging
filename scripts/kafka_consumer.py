
import json
import time
import logging
import threading
import sys
from kafka import KafkaConsumer
from kafka.admin import KafkaAdminClient
from kafka.errors import KafkaError, NoBrokersAvailable
from prometheus_client import start_http_server, Gauge, Counter
from create_index import index_log


KAFKA_BROKERS = ['kafka-broker-1:9092', 'kafka-broker-2:9093', 'kafka-broker-3:9094']
KAFKA_TOPIC = 'web_topic'
GROUP_ID = 'log_consumers'


logging.basicConfig(level=logging.DEBUG)


LATENCY = Gauge('log_processing_latency', 'Processing latency in seconds', ['instance'])
CONSUMED_MESSAGES = Counter('consumed_messages', 'Number of messages consumed', ['instance'])

def create_consumer():

    for attempt in range(5):
        try:
            return KafkaConsumer(
                KAFKA_TOPIC,
                bootstrap_servers=KAFKA_BROKERS,
                group_id=GROUP_ID,
                auto_offset_reset='earliest',
                value_deserializer=lambda v: json.loads(v.decode('utf-8')),
                metadata_max_age_ms=10000,
                reconnect_backoff_max_ms=5000
            )
        except NoBrokersAvailable as e:
            logging.warning(f"[Attempt {attempt + 1}] No brokers available. Retrying in 5 seconds...")
            time.sleep(5)
    raise Exception("Failed to connect to any Kafka brokers after multiple attempts.")

def get_consumer_lag():

    while True:
        try:
            admin_client = KafkaAdminClient(bootstrap_servers=KAFKA_BROKERS)
            group_info = admin_client.describe_consumer_groups([GROUP_ID])
            for group in group_info:
                logging.info(f"Group ID: {group['groupId']}, State: {group['state']}")
                if group.get('members'):
                    logging.info(f"Members: {len(group['members'])}")
                else:
                    logging.warning("No members in group.")
        except Exception as e:
            logging.error(f"Error fetching consumer lag: {e}")


        time.sleep(10)

def consume_messages(instance_name, port):


    start_http_server(port)
    logging.info(f"Prometheus metrics available at http://localhost:{port}/metrics")


    consumer = create_consumer()
    logging.info(f"Consumer started. Listening on topic: {KAFKA_TOPIC}")

    while True:
        try:
            for message in consumer:
                try:
                    log_entry = message.value
                    if not log_entry:
                        logging.info("Skipping empty message.")
                        continue

                    logging.info(f"Received log entry: {log_entry}")


                    CONSUMED_MESSAGES.labels(instance=instance_name).inc()


                    timestamp_produced = log_entry.get('timestamp_produced', None)
                    if timestamp_produced:
                        latency = time.time() - timestamp_produced
                        LATENCY.labels(instance=instance_name).set(latency)


                    index_log(log_entry)
                except json.JSONDecodeError as e:
                    logging.error(f"Invalid JSON message: {message.value} Error: {e}")
                except Exception as e:
                    logging.error(f"Error processing message: {e}")

        except KafkaError as e:
            logging.error(f"Kafka error encountered: {e}. Restarting consumer...")
            consumer.close()
            time.sleep(5)
            consumer = create_consumer()

if __name__ == "__main__":

    instance_name = sys.argv[1] if len(sys.argv) > 1 else 'default_consumer'
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8001


    lag_monitor_thread = threading.Thread(target=get_consumer_lag, daemon=True)
    lag_monitor_thread.start()


    consume_messages(instance_name, port)
