#!/bin/bash

# Define variables
EC2_USER="ubuntu"
EC2_IP="ec2-3-22-220-27.us-east-2.compute.amazonaws.com"
PEM_FILE="/Users/mandyhong/Downloads/aws_personalmac.pem"
REMOTE_PATH="/home/ubuntu/myspotipal-dev/app_logs.db"  # Path to the SQLite file on EC2
LOCAL_PATH="./ec2_app_logs.db"                    # Path to save the file locally (current directory)

# Print information
echo "Downloading SQLite database file from EC2 instance..."
echo "EC2 Address: ${EC2_USER}@${EC2_IP}"
echo "Remote File: ${REMOTE_PATH}"
echo "Saving to: ${LOCAL_PATH}"

# Run the SCP command
scp -i "${PEM_FILE}" "${EC2_USER}@${EC2_IP}:${REMOTE_PATH}" "${LOCAL_PATH}"

# Check if the SCP command succeeded
if [ $? -eq 0 ]; then
    echo "Download successful! File saved to ${LOCAL_PATH}"
else
    echo "Download failed. Please check your settings and try again."
fi

