#!/bin/bash

# Define paths to your Python files
START_SCRIPT="start.py"
TERMINATE_SCRIPT="terminate.py"
BENCHMARK_SCRIPT="benchmarkscript.py"

# Log file to capture the output
LOG_FILE="cloud_automation.log"

# Function to check for errors and exit if a command fails
check_error() {
    if [ $? -ne 0 ]; then
        echo "Error encountered during $1. Check the log file for details."
        exit 1
    fi
}

echo "Starting cloud infrastructure with $START_SCRIPT..." | tee -a $LOG_FILE
# Run the start.py script to set up infrastructure
python3 -u $START_SCRIPT | tee -a $LOG_FILE &
check_error "starting cloud infrastructure"

sleep 60
# Sleep to allow instances to start (adjust sleep time based on instance setup time)
echo "Waiting for instances to fully start..." | tee -a $LOG_FILE
sleep 240  

echo "Running benchmarks with $BENCHMARK_SCRIPT..." | tee -a $LOG_FILE
# Run the benchmark script
python3 -u $BENCHMARK_SCRIPT | tee -a $LOG_FILE
check_error "running benchmark"

# Terminate question
echo "Do you want to terminate the infrastructure? (yes/no)"
read TERMINATE_CONFIRM

if [ "$TERMINATE_CONFIRM" == "yes" ]; then
    echo "Terminating cloud infrastructure with $TERMINATE_SCRIPT..." | tee -a $LOG_FILE
    # Run the terminate.py script to tear down infrastructure
    python3 -u $TERMINATE_SCRIPT | tee -a $LOG_FILE
    check_error "terminating cloud infrastructure"
    echo "Cloud infrastructure terminated." | tee -a $LOG_FILE
else
    echo "Skipping termination. You can run $TERMINATE_SCRIPT manually later."
fi

echo "All tasks completed successfully!" | tee -a $LOG_FILE
killall python3
