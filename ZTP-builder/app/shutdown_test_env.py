# -*- coding: utf-8 -*-

"""shutdown TNT enviroment"""
import smtplib
import time
from email.message import EmailMessage

import schedule
import urllib3

import app.ZTP as ZTP

urllib3.disable_warnings()

sender = "bmi-service stage <bmi-notify@example.com>"
receiver = "support@example.com"
server = smtplib.SMTP("smtp.example.com", 25)

msg = EmailMessage()
msg["Subject"] = "TnT testing servers shutdown notice"
msg["From"] = sender
msg["To"] = receiver


def TnT_server_shutdown_job():
    """Fn: TnT server shutdown job"""
    print("Fn: TnT_server_shutdown_job")
    servers = ["lab-dc1-r1-s14", "lab-dc1-r1-s15", "LAB-DC1-R1-S17"]
    for host in servers:
        print(f"--------------------- {host} -----------------------------")
        ztp_action = ZTP.Actions(host)
        ztp_action.ztp_power_off()
    with smtplib.SMTP("smtp.example.com", 25) as server:
        msg.set_content(
            f" Daily shutdown at 5PM Central, TnT environment has been shutdown!\nServers shutdown: {', '.join(servers)}"
        )
        server.send_message(msg)


def run_job():
    """Fn: run job to schedule the function execution"""
    schedule.every().day.at("17:00").do(TnT_server_shutdown_job)
    while True:
        schedule.run_pending()
        time.sleep(60)


### uncomment below lineand run python app/shutdown_test_env.py if you want to manually shutdown
# TnT_server_shutdown_job()
