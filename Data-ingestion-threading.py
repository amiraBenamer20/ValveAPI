# -*- coding: utf-8 -*-
import threading
import logging
import os
import valve.source.a2s
import valve.source.master_server
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from valve.source.messages import BufferExhaustedError  # Correct exception

# Constants
PERIOD = 900  # Relaunch every 15 minutes (900 seconds)
SERVER_TIMEOUT = 5  # Avoid long hangs
MASTER_TIMEOUT = 60
DATA_PATH = "Data-25"
VALVE_REGIONS = ['na-west', 'na-east', 'sa', 'eu', 'as', 'oc', 'af', 'rest']
REGION = 5  # Set desired region
MAX_WORKERS = 50  # Controls active threads

# Configure Logging
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')


def query_server(address, now, path_dir):
    """Queries a game server and writes its data to CSV files."""
    try:
        with valve.source.a2s.ServerQuerier(address, timeout=SERVER_TIMEOUT) as server:
            info = server.info()
            ping = server.ping()
            player_count = info["player_count"] - info["bot_count"]

            filename = os.path.join(path_dir, f"{VALVE_REGIONS[REGION]}.csv")
            if player_count > 0:
                with open(filename, 'a', newline='', encoding="utf-8") as csvfile:
                    csvfile.write(f"{address[0]};{address[1]};{ping};{info['player_count']};{info['max_players']};{info['bot_count']}\n")
            else:
                empty_file = os.path.join(path_dir, f"Empty-{VALVE_REGIONS[REGION]}.csv")
                with open(empty_file, 'a') as videfile:
                    videfile.write(f"{address[0]};{address[1]};{ping}\n")

    except BufferExhaustedError:
        logging.error(f"Incomplete message from server {address}")
    except Exception as e:
        logging.error(f"Error querying server {address}: {e}")
        timeout_file = os.path.join(path_dir, f"TimedOut-{VALVE_REGIONS[REGION]}.csv")
        with open(timeout_file, 'a') as outfile:
            outfile.write(f"{address[0]};{address[1]}\n")


def getServers():
    """Fetch CSGO servers and store data using threads."""
    logging.info(f"Fetching servers at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

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

        # Create directory for data storage
        now = datetime.now().strftime('%Y-%m-%d-%H-%M-%S')
        path_dir = os.path.join(DATA_PATH, now)
        os.makedirs(path_dir, exist_ok=True)

        filename_all = os.path.join(path_dir, f"{VALVE_REGIONS[REGION]}_all.csv")

        # Save all server addresses
        with open(filename_all, 'w', newline='', encoding="utf-8") as csv_all:
            for address in server_list:
                csv_all.write(f"{address[0]};{address[1]}\n")

        if server_list:
            # Use ThreadPoolExecutor for concurrent server queries
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                executor.map(lambda addr: query_server(addr, now, path_dir), server_list)
        else:
            logging.warning("No servers found in this cycle.")

    except Exception as e:
        logging.error(f"Master server query failed: {e}")
        error_log = os.path.join(DATA_PATH, "no_response_servers.csv")
        with open(error_log, 'a', encoding="utf-8") as masterfile:
            masterfile.write(f"{datetime.now()}, Region {VALVE_REGIONS[REGION]}\n")

    finally:
        req.close()

    # Relaunch after 15 minutes (Always, even if no servers found)
    logging.info("Waiting 15 minutes before next cycle...")
    threading.Timer(PERIOD, getServers).start()


# Start Fetching
getServers()
