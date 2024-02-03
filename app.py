from flask import Flask
import redis
import time
import random
import string
import logging
import json
import os
from threading import Thread
import requests
from waitress import serve

# Logging Config
logging.basicConfig(level=logging.INFO, format='%(created)d - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# IF A needs to send a message to B it queues it on queue:B
app = Flask(__name__)

@app.route('/info', methods=['GET'])
def info():
    return json.loads({'ID': ID})

@app.route('/<config>', methods=['GET'])
def route_config(config):
    global NODEPOOL
    full = config
    ttl = len(full)-1
    trace = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(10))
    if config[0] == ID:
        message=json.dumps({"FULL":full,"TTL":ttl,"TRACE":trace,"CONFIG":config[1:]})
        if len(config) == 1:
            logger.info(f"{trace} - {ttl} - {full} - DONE")
            return f"Traversal Complete {full}"
        else:
            logger.info(f"{trace} - {ttl} - {full} - PROCESSING")
            
            if config[1] in NODEPOOL:
                redis_client.lpush(f"queue:{config[1]}",message)
            else:
                # REFRESH NODEPOOL
                NODEPOOL = redis_client.get("nodepool").split("|")
                if config[1] in NODEPOOL:
                    redis_client.lpush(f"queue:{config[1]}",message)
                else:
                    logger.info(f"could not find {config[1]}")
                    return f"traversal incomplete {full}"
            return f"traversal began for {full}"
    else:
        logger.info(f"this message is not for me {ID} got {config}")
        return f"traversal incomplete {full}"

def message_processor():
    redis_worker = redis.StrictRedis(host=redis_host, port=redis_port, charset="utf-8", decode_responses=True)
    logging.basicConfig(level=logging.INFO, format='%(created)d - %(levelname)s - %(message)s')
    logger = logging.getLogger("Thread-1")
    logger.info(f"{ID} established redis processor connection")
    NODEPOOL = redis_worker.get("nodepool").split("|")
 
    while True:
        queue, message = redis_worker.brpop(f"queue:{ID}")
        if message:
            message = json.loads(message)
            full = message["FULL"]
            ttl = message["TTL"] - 1
            trace = message["TRACE"]
            config = message["CONFIG"]
            logger.info(f"{trace} - {ttl} - {full} - PROCESSING")
            if len(config) == 1:
                logger.info(f"{trace} - {ttl} - {full} - DONE")
            else:
                if config[0] == ID:
                    message["TTL"] = ttl
                    message["CONFIG"] = config[1:]
                    message = json.dumps(message)
                    if config[1] in NODEPOOL:
                        redis_worker.lpush(f"queue:{config[1]}",message)
                    else:
                        # REFRESH NODEPOOL
                        NODEPOOL = redis_worker.get("nodepool").split("|")
                        if config[1] in NODEPOOL:
                            redis_worker.lpush(f"queue:{config[1]}",message)
                        else:
                            logger.info(f"could not find {config[1]}")
                else:
                    logger.info(f"this message is not for me {ID} got {config} {trace}")

def heartBeat():
    logging.basicConfig(level=logging.INFO, format='%(created)d - %(levelname)s - %(message)s')
    logger = logging.getLogger("heartbeat")
    while True:
        requests.get(f"http://{MASTER_HOST}:{MASTER_PORT}/heart",params={"ID":ID})
        logger.info(f"{ID} sent heartbeat to master")
        time.sleep(20)

def acquire_lock(redis_client, lock_key, expiration_time=30):
    lock_acquired = redis_client.set(lock_key, "locked", nx=True, ex=expiration_time)
    return lock_acquired

def release_lock(redis_client, lock_key):
    redis_client.delete(lock_key)

if __name__ == "__main__":
    # Get Environment Vars
    ID = os.getenv("BID")
    PORT=os.getenv("PORT")
    MASTER_HOST=os.getenv("MASTER_HOST")
    MASTER_PORT=os.getenv("MASTER_PORT")
    redis_host = os.getenv("REDIS_HOST")
    redis_port = os.getenv("REDIS_PORT")
    
    if any(value is None for value in [ID,PORT,MASTER_HOST,MASTER_PORT,redis_host,redis_port]):
        logger.error("please set the following environment variables BID,PORT,MASTER_HOST,MASTER_PORT,REDIS_HOST,REDIS_PORT")
        exit()

    # This thread sends heartbeat to the ringleader
    heartbeat_thread = Thread(target=heartBeat)
    heartbeat_thread.start()

    # Get the Redis Configuration
    redis_client = redis.StrictRedis(host=redis_host, port=redis_port, charset="utf-8", decode_responses=True)
    logger.info(f"{ID} established redis sender connection")

    # Register on Redis (acquire lock on nodepool key to avoid race condition)
    ok = False
    while not ok:
        if acquire_lock(redis_client,lock_key="nodepool_lock"):
            try:
                global NODEPOOL
                NODEPOOL = redis_client.get("nodepool")
                if NODEPOOL is None:
                    NODEPOOL = []
                else:
                    NODEPOOL = NODEPOOL.split("|")
                if ID not in NODEPOOL:
                    NODEPOOL.append(ID)
                    nodepoolval = "|".join(NODEPOOL)
                    redis_client.set("nodepool",nodepoolval)
                    ok = True
                    logger.info(f"registered new node {ID}")
            finally:
                release_lock(redis_client,lock_key="nodepool_lock")
        else:
            logger.info("Failed to acquire the lock. Another process is already using the key. Retrying...")

    # Start the message processing thread
    message_thread = Thread(target=message_processor)
    message_thread.start()

    logger.info(f"STARTING NODE {ID}")
    serve(app,port=PORT)
