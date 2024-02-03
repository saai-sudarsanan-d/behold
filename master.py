from flask import Flask, request
import logging
from waitress import serve
import time
from threading import Thread
import os
import requests

app = Flask(__name__)

logging.basicConfig(level=logging.DEBUG, format='%(created)d - %(levelname)s - %(message)s')
logger = logging.getLogger("flask_api")

clientMon = {}

def updateMon():
    while True:
        for k,lastheartbeat in clientMon.items():
            if time.time() - lastheartbeat > 60:
                logger.critical(f"ID {k} has been down for more than 60 seconds")
        time.sleep(20)

@app.route('/heart', methods=['GET'])
def receive_heartbeat():
    try:
        bid = request.args.get('ID')
        if bid not in clientMon.keys():
            logger.info(f"new client joined {bid}")
        clientMon[bid] = time.time()
        logger.info(f"Heartbeat received from client ID: {bid}")
        return "Heartbeat received successfully"
    except Exception as e:
        logger.error(f"Error processing heartbeat: {str(e)}")
        return "Internal Server Error"
    
@app.route('/<config>', methods=['GET'])
def receive_config(config):
    if len(config) > 0:
        try:
            bid = config[0]
            requests.get(f"http://hyena{bid}:5000/{config}")
            return "Sent Config Successfully"
        except Exception as e:
            logger.error(f"Error processing config: {str(e)}")
            return "Internal Server Error"
    else:
        return "Invalid Config"

if __name__ == '__main__':
    # Use Waitress to serve the application
    updater = Thread(target=updateMon)
    updater.start()

    serve(app,port=os.getenv("PORT"))