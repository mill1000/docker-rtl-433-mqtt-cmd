#! /usr/bin/env python3

import os
import argparse
import logging
import json
import paho.mqtt.client as mqtt
import subprocess
import string

# rtl-433-mqtt-cmd  -d -H 10.100.1.6 --user cli --password habitual-letdown-clubhouse

def mqtt_connect(client, userdata, flags, rc):
    """Callback for MQTT connects."""

    topic = userdata
    logging.info("MQTT connected: " + mqtt.connack_string(rc))
    if rc != 0:
        logging.error("Could not connect. Error: " + str(rc))
    else:
        logging.info("Subscribing to: " + topic)
        client.subscribe(topic)


def mqtt_disconnect(client, userdata, rc):
    """Callback for MQTT disconnects."""
    logging.info("MQTT disconnected: " + mqtt.connack_string(rc))


def mqtt_message(client, userdata, msg):
    """Callback for MQTT message PUBLISH."""
    logging.debug("MQTT message: " + json.dumps(msg.payload.decode()))

    try:
        # Decode JSON payload
        data = json.loads(msg.payload.decode())

    except json.decoder.JSONDecodeError:
        logging.error("JSON decode error: " + msg.payload.decode())
        return

    process_json_message(data)


def process_json_message(data):
    # Drop anything after a semicolon to prevent trailing commands
    cmd = data["cmd"].split(";")[0]

    # Remove rtl_433 from command if present
    cmd = cmd.strip().removeprefix("rtl_433").strip()

    if not cmd:
        logging.error("Empty command after sanitizing. ")
        return

    # Re-add rtl_433
    cmd = " ".join(["rtl_433", cmd])

    # Split command into array
    cmd = cmd.split(" ")

    # Fetch timeout if present
    timeout = data.get("timeout", None)

    logging.debug("Executing command '%s' with timeout %s", cmd, timeout or "N/A")
    try:
        subprocess.run(cmd, timeout=timeout)
    except Exception as e:
        logging.error("Command failed. " + str(e))


if __name__ == "__main__":
    logging.getLogger().setLevel(logging.INFO)

    parser = argparse.ArgumentParser(description="Subscribe to an MQTT topic and execute received commands in rtl_433.")

    parser.add_argument("-d", "--debug", action="store_true")
    parser.add_argument("-u", "--user", type=str, help="MQTT username")
    parser.add_argument("-P", "--password", type=str, help="MQTT password")
    parser.add_argument("-H", "--host", type=str, default="127.0.0.1",
                        help="MQTT hostname to connect to (default: %(default)s)")
    parser.add_argument("-p", "--port", type=int, default=1883,
                        help="MQTT port (default: %(default)s)")
    parser.add_argument("-c", "--ca_cert", type=str, help="MQTT TLS CA certificate path")
    parser.add_argument("-t", "--topic", type=str,
                        default="rtl-433-cmd/",
                        dest="topic",
                        help="MQTT event topic to subscribe to (default: %(default)s)")
    
    
    args = parser.parse_args()

    if args.debug:
        logging.info("Enabling debug logging")
        logging.getLogger().setLevel(logging.DEBUG)

    # allow setting MQTT username and password via environment variables
    if not args.user and 'MQTT_USERNAME' in os.environ:
        args.user = os.environ['MQTT_USERNAME']

    if not args.password and 'MQTT_PASSWORD' in os.environ:
        args.password = os.environ['MQTT_PASSWORD']

    if not args.user or not args.password:
        logging.warning("User or password is not set. Check credentials if subscriptions do not return messages.")

    client = mqtt.Client(userdata=args.topic)

    if args.debug:
        client.enable_logger()

    if args.user is not None:
        client.username_pw_set(args.user, args.password)

    if args.ca_cert is not None:
        client.tls_set(ca_certs=args.ca_cert)

    client.on_connect = mqtt_connect
    client.on_disconnect = mqtt_disconnect
    client.on_message = mqtt_message

    logging.debug("MQTT Client: Connecting.")
    client.connect_async(args.host, args.port, 60)

    logging.debug("MQTT Client: Starting Loop")
    try:
        client.loop_forever()
    except KeyboardInterrupt:
        pass
