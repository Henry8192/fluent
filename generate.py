import logging
import logging.handlers
import os
import pathlib
import subprocess
import time
import uuid
import datetime
import random
import tracemalloc

def generate_logs():
    num_logs_to_print = 1000000
    # num_logs_to_print = 100
    logger = logging.getLogger()
    current_date = datetime.datetime.now().strftime("%Y%m%d")
    for i in range(num_logs_to_print):
        logger.info(f"message_id<{i}> This is a log message with one spark unique app id per line: app-{current_date} {i % 1000}-{i % 20000} from spark-node-{i % 1000}")
    print(f"Printed {num_logs_to_print} logs")

if __name__ == '__main__':
    # tracemalloc.start()
    log_folder = "log"
    log_file_name = "input"
    os.makedirs(log_folder, exist_ok=True)
    # created a subfolder "log". maxBytes = 1MB and backup counts from log.1 to log.10
    logger_handler = logging.handlers.RotatingFileHandler(filename=f"{log_folder}/{log_file_name}.log", maxBytes=1048576, backupCount=10)
    logger_handler.setFormatter(fmt=logging.Formatter("%(asctime)s %(levelname)s %(name)s %(funcName)s: %(message)s"))
    rootLogger = logging.getLogger()
    rootLogger.setLevel(logging.INFO)
    rootLogger.addHandler(logger_handler)
    
    generate_logs()
