import socket
from threading import Thread

import app.message_consumer as message_consumer
from app.shutdown_test_env import run_job

if __name__ == "__main__":
    ### below is temp solution to shutdown TnT testing environment everyday
    hostname = socket.gethostname()
    if hostname == "lab-bmi-stage-01":  # if this is stage environment run scheduler
        print(f"{hostname} starting thread TnT shutdown job")
        thrd = Thread(target=run_job)
        thrd.start()

    message_consumer.start_consumer()
