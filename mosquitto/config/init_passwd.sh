#!/bin/sh
# Generate Mosquitto password file
# Run: docker run --rm -v $(pwd)/mosquitto/config:/mosquitto/config eclipse-mosquitto mosquitto_passwd -b /mosquitto/config/passwd energy_user energy_pass123
# Or use init container in docker-compose

# Pre-hashed password for energy_user:energy_pass123
# Generated with: mosquitto_passwd -b passwd energy_user energy_pass123
cat > /mosquitto/config/passwd << 'EOF'
energy_user:$7$101$your-hash-here$replace-with-real-hash==
EOF

# This script is used by the init container
mosquitto_passwd -b /mosquitto/config/passwd energy_user "${MQTT_PASSWORD:-energy_pass123}"
echo "Password file generated for user: energy_user"
