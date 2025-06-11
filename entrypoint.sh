#!/bin/bash

# Function to handle shutdown
cleanup() {
    echo "Shutting down services..."
    pkill nginx
    pkill ttyd
    tmux kill-server
    exit 0
}

# Set up signal handlers
trap cleanup SIGTERM SIGINT

# start a ttyd server, showing a tmux session split into 3 panes

# Create a new tmux session named "main" in detached mode
tmux new-session -d -s main

# Split the window horizontally (top and bottom)
tmux split-window -h -t main

# Split the bottom pane vertically (left and right in bottom half)
tmux split-window -v -t main:0.1

# Optional: Set up different commands in each pane
tmux send-keys -t main:0.0 'cd oak_d_vins_cpp && ./feature_tracker' C-m
sleep 10
tmux send-keys -t main:0.1 'cd VINS-Fusion/vins_estimator && ./vins_fusion oak_d.yaml' C-m  
sleep 10
tmux send-keys -t main:0.2 'python3 mavlink2restForwarder.py' C-m

# Start nginx in the background
nginx -c /etc/nginx/nginx.conf &
nginx_pid=$!

# Start ttyd server on port 7681 (nginx will proxy from 8000 to 7681)
ttyd -p 7681 tmux attach-session -t main &
ttyd_pid=$!

# Wait for both processes
wait $nginx_pid $ttyd_pid

