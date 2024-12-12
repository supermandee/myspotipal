#!/bin/bash

# Define variables
EC2_USER="ubuntu"
EC2_IP="ec2-3-22-220-27.us-east-2.compute.amazonaws.com"
PEM_FILE="/Users/mandyhong/Downloads/aws_personalmac.pem"

# Define remote file paths
REMOTE_PATH_1="/home/ubuntu/myspotipal-dev/app_logs.db"  # Path to the first SQLite file on EC2
REMOTE_PATH_2="/home/ubuntu/myspotipal/app_logs.db"     # Path to the second SQLite file on EC2

# Define local file paths
LOCAL_PATH_1="./ec2_app_logs_dev.db"  # Local path for the first file
LOCAL_PATH_2="./ec2_app_logs.db"      # Local path for the second file

# Print information
echo "Downloading SQLite database files from EC2 instance..."
echo "EC2 Address: ${EC2_USER}@${EC2_IP}"

# Download the first file
echo "Downloading: ${REMOTE_PATH_1}"
scp -i "${PEM_FILE}" "${EC2_USER}@${EC2_IP}:${REMOTE_PATH_1}" "${LOCAL_PATH_1}"

# Check if the first SCP command succeeded
if [ $? -eq 0 ]; then
    echo "Download of ${REMOTE_PATH_1} successful! File saved to ${LOCAL_PATH_1}"
else
    echo "Download of ${REMOTE_PATH_1} failed. Please check your settings and try again."
fi

# Download the second file
echo "Downloading: ${REMOTE_PATH_2}"
scp -i "${PEM_FILE}" "${EC2_USER}@${EC2_IP}:${REMOTE_PATH_2}" "${LOCAL_PATH_2}"

# Check if the second SCP command succeeded
if [ $? -eq 0 ]; then
    echo "Download of ${REMOTE_PATH_2} successful! File saved to ${LOCAL_PATH_2}"
else
    echo "Download of ${REMOTE_PATH_2} failed. Please check your settings and try again."
fi
