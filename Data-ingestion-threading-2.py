import threading
import logging
import os
import valve.source.a2s
import valve.source.master_server
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from valve.source.messages import BufferExhaustedError  # Correct exception

# Constants
SERVER_TIMEOUT = 5  # Reduced to avoid long hangs
DATA_PATH = "Data-25"
VALVE_REGIONS = ['na-west', 'na-east', 'sa', 'eu', 'as', 'oc', 'af', 'rest']
REGION = 5  # Australia
MAX_WORKERS = 50  # Limit active threads to avoid overload

# Configure Logging
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')


def query_server(address, now, csvfile, path):
    """Queries a game server and writes its data to a CSV file."""
    try:
        with valve.source.a2s.ServerQuerier(address, timeout=SERVER_TIMEOUT) as server:
            info = server.info()
            ping = server.ping()
            player_count = info["player_count"] - info["bot_count"]

            if player_count > 0:
                try:
                    csvfile.write(
                        f"{address[0]};{address[1]};{ping};{info['player_count']};{info['max_players']};{info['bot_count']}\n"
                    )
                except UnicodeEncodeError:
                    logging.warning(f"Unicode error in server name: {info['server_name']}")

            else:
                empty_file = os.path.join(path, f"Empty-{VALVE_REGIONS[REGION]}.csv")
                with open(empty_file, 'a') as videfile:
                    videfile.write(f"{address[0]};{address[1]};{ping}\n")

    except BufferExhaustedError:
        logging.error(f"Incomplete message from server {address}")
    except Exception as e:
        logging.error(f"Error querying server {address}: {e}")
        timeout_file = os.path.join(path, f"TimedOut-{VALVE_REGIONS[REGION]}.csv")
        with open(timeout_file, 'a') as outfile:
            outfile.write(f"{address[0]};{address[1]}\n")


def getServers():
    """Fetch CSGO servers and store data (Threaded version)."""
    logging.info(f"Fetching servers at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    req = valve.source.master_server.MasterServerQuerier(timeout=60)

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

        # Use ThreadPoolExecutor instead of manual threading
        with open(filename, 'w', newline='', encoding="utf-8") as csvfile, \
             ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = [executor.submit(query_server, address, now, csvfile, path_dir) for address in server_list]

            # Wait for all threads to complete
            for future in futures:
                future.result()

    except Exception as e:
        logging.error(f"Master server query failed: {e}")
        error_log = os.path.join(DATA_PATH, "no_response_servers.csv")
        with open(error_log, 'a', encoding="utf-8") as masterfile:
            masterfile.write(f"{datetime.now()}, Region {VALVE_REGIONS[REGION]}\n")

    finally:
        req.close()

    # Relaunch after 15 minutes
    threading.Timer(900, getServers).start()


# Start Fetching
getServers()
