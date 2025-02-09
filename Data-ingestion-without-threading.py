# -*- coding: utf-8 -*-
import valve.source.master_server
import valve.source.a2s
import time
import os
import csv
import logging
from datetime import datetime
from valve.source.messages import BufferExhaustedError  # Correct Import!

# Constants
DATA_PATH = "Data-25"
PERIOD = 900
MASTER_TIMEOUT = 60
SERVER_TIMEOUT = 5  # Reduce timeout
VALVE_REGIONS = ['na-west', 'na-east', 'sa', 'eu', 'as', 'oc', 'af', 'rest']
REGION = 3  # Europe
RETRY_ATTEMPTS = 3  # Retry for unstable servers

# Configure Logging
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')


def fetch_server_data(address, csvfile):
    """Query a server and write data to CSV with retries."""
    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            with valve.source.a2s.ServerQuerier(address, timeout=SERVER_TIMEOUT) as server:
                info = server.info()
                ping = server.ping()
                physical_players = info["player_count"] - info["bot_count"]

                if physical_players > 0:
                    csvfile.write(f"{address[0]};{address[1]};{ping};{info['player_count']};{info['max_players']};{info['bot_count']}\n")
                return  # Successfully processed

        except BufferExhaustedError:  # Correct Error Handling
            logging.error(f"Incomplete message from server {address}. Attempt {attempt}/{RETRY_ATTEMPTS}.")
        except valve.source.a2s.NoResponseError:
            logging.warning(f"Server {address} did not respond. Attempt {attempt}/{RETRY_ATTEMPTS}.")
        except Exception as e:
            logging.error(f"Unexpected error fetching server {address}: {e}")

    # If all retries fail, log the failed server
    with open(os.path.join(DATA_PATH, "failed_servers.csv"), 'a', encoding="utf-8") as fail_log:
        fail_log.write(f"{address[0]};{address[1]}\n")


def getServers():
    """Fetch CSGO server list and store data in CSV (No Threading, With Retries)."""
    logging.info(f"Fetching servers at {time.ctime()}")

    req = valve.source.master_server.MasterServerQuerier(timeout=MASTER_TIMEOUT)
    
    try:
        servers = req.find(
            region=VALVE_REGIONS[REGION],
            duplicates="skip",
            gamedir="csgo",
            empty="not"
        )

        server_list = list(servers)
        logging.info(f"Number of servers found: {len(server_list)}")

        if not server_list:
            logging.warning("No servers found. Skipping this cycle.")
            return

        # Prepare directories
        now = datetime.now().strftime('%Y-%m-%d-%H-%M-%S')
        path_dir = os.path.join(DATA_PATH, now)
        os.makedirs(path_dir, exist_ok=True)

        filename = os.path.join(path_dir, f"{VALVE_REGIONS[REGION]}.csv")
        filename_all = os.path.join(path_dir, f"{VALVE_REGIONS[REGION]}_all.csv")

        logging.info(f"Saving to: {filename}")

        # Save all server addresses
        with open(filename_all, 'w', newline='', encoding="utf-8") as csv_all:
            for address in server_list:
                csv_all.write(f"{address[0]};{address[1]}\n")

        # Sequentially fetch server data (NO THREADS, WITH RETRIES)
        with open(filename, 'w', newline='', encoding="utf-8") as csvfile:
            for address in server_list:
                fetch_server_data(address, csvfile)

    except Exception as e:  # Replace NoResponseError with a General Catch
        logging.error(f"Master server query failed: {e}")
        error_log = os.path.join(DATA_PATH, "no_response_servers.csv")
        with open(error_log, 'a', encoding="utf-8") as masterfile:
            masterfile.write(f"{datetime.now()}, Region {VALVE_REGIONS[REGION]}\n")

    finally:
        req.close()

    # Schedule next run
    time.sleep(PERIOD)
    getServers()


# Start Fetching
getServers()
