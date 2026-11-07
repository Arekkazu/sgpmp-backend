#!/bin/sh
# Genera passwd del lab desde variables de entorno. No imprime las claves.
set -e
SECRETS=/mosquitto/secrets
mkdir -p "$SECRETS"
if [ -z "$MQTT_USERNAME" ] || [ -z "$MQTT_PASSWORD" ] || [ -z "$MQTT_DEVICE_USERNAME" ] || [ -z "$MQTT_DEVICE_PASSWORD" ]; then
  echo "ERROR: faltan MQTT_* en el entorno del laboratorio G43" >&2
  exit 1
fi
mosquitto_passwd -b -c "$SECRETS/passwd" "$MQTT_USERNAME" "$MQTT_PASSWORD"
mosquitto_passwd -b "$SECRETS/passwd" "$MQTT_DEVICE_USERNAME" "$MQTT_DEVICE_PASSWORD"
chown mosquitto:mosquitto "$SECRETS/passwd" 2>/dev/null || true
chmod 0600 "$SECRETS/passwd"
exec mosquitto -c /mosquitto/config/mosquitto.conf
