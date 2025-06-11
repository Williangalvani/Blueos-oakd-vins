#!/usr/bin/env python3

import socket
import select
import time
import struct
import signal
import sys
import os
import requests
from typing import Dict, Any
import logging
import zenoh
import json

# Configuration
MY_COMP_ID = 191
TARGET_SYSTEM_ID = 1  # Default target system ID
SERVER_PATH = "/tmp/chobits_server"
MAVLINK2REST_URL = "http://host.docker.internal:6040/mavlink"  # Default mavlink2rest endpoint

# Global variables
running = True

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class MavlinkRestClient:
    """Client for sending MAVLink messages via mavlink2rest HTTP API"""
    
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.session.timeout = 1.0
        
    def send_message(self, message_type: str, message_data: Dict[str, Any], target_system: int = TARGET_SYSTEM_ID) -> bool:
        """Send a MAVLink message via REST API"""
        try:
            url = self.base_url  # Remove the duplicate /mavlink since it's already in base_url
            payload = {
                "header": {
                    "system_id": target_system,
                    "component_id": MY_COMP_ID,
                    "sequence": 0
                },
                "message": {
                    "type": message_type,
                    **message_data
                }
            }
            
            response = self.session.post(url, json=payload)
            if response.status_code == 200:
                return True
            else:
                logger.warning(f"Failed to send {message_type}: {response.status_code}")
                return False
                
        except requests.RequestException as e:
            logger.error(f"Error sending {message_type}: {e}")
            return False


def signal_handler(signum, frame):
    """Handle interrupt signals"""
    global running
    logger.info("Received interrupt signal, shutting down...")
    running = False


def setup_unix_sockets():
    """Setup Unix domain sockets for IPC"""
    # Socket 1 - for pose data
    sock1 = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    try:
        os.unlink(SERVER_PATH)
    except OSError:
        pass
    sock1.bind(SERVER_PATH)
    
    # Set non-blocking
    sock1.setblocking(False)
    
    return sock1


def send_att_pos_mocap(mavlink_client: MavlinkRestClient, pose):
    """Send attitude position mocap message"""
    current_time_us = int(time.time() * 1000000)
    
    # Updated coordinate transformations - new format: [qw, qx, qy, qz, px, py, pz, vx, vy, vz]
    # Quaternion components are at indices 0-3, positions at 4-6
    qw, qx, qy, qz = pose[0], pose[1], pose[2], pose[3]
    x, y, z = pose[4], pose[5], -pose[6]  # Apply coordinate transformation for z
    
    message_data = {
        "time_usec": current_time_us,
        "q": [qw, qx, -qy, -qz],  # Apply coordinate transformations for quaternion
        "x": x,
        "y": y, 
        "z": z,
        "covariance": [0.0] * 21
    }
    
    return mavlink_client.send_message("ATT_POS_MOCAP", message_data)


def send_vision_speed_estimate(mavlink_client: MavlinkRestClient, pose):
    """Send vision speed estimate message"""
    current_time_us = int(time.time() * 1000000)
    
    # Updated coordinate transformations for velocities - new format: [qw, qx, qy, qz, px, py, pz, vx, vy, vz]
    # Velocities are at indices 7, 8, 9
    vx, vy, vz = pose[7], -pose[8], -pose[9]  # Apply coordinate transformations for velocities
    
    message_data = {
        "usec": current_time_us,
        "x": vx,
        "y": vy,
        "z": vz,
        "covariance": [0.0] * 9,
        "reset_counter": 0
    }
    
    return mavlink_client.send_message("VISION_SPEED_ESTIMATE", message_data)


def publish_zenoh_data(zenoh_session, pose):
    """Publish pose data to Zenoh using Foxglove Pose schema"""
    # Updated coordinate transformations - new format: [qw, qx, qy, qz, px, py, pz, vx, vy, vz]
    # Quaternion components are at indices 0-3, positions at 4-6
    qw, qx, qy, qz = pose[0], pose[1], pose[2], pose[3]
    x, y, z = pose[4], pose[5], pose[6]
    
    # Create foxglove.Pose message format
    # Reference: https://raw.githubusercontent.com/foxglove/foxglove-sdk/refs/heads/main/schemas/jsonschema/Pose.json
    pose_data = {
        "position": {
            "x": x,
            "y": y,
            "z": z
        },
        "orientation": {
            "x": qx,
            "y": qy,
            "z": qz,
            "w": qw
        }
    }
    
    # Use put() with the Foxglove schema data
    zenoh_session.put(json.dumps(pose_data))


def handle_pose_data(mavlink_client: MavlinkRestClient, sock1, zenoh_session):
    """Handle pose data from Unix socket"""
    try:
        # Receive pose data: [qw, qx, qy, qz, px, py, pz, vx, vy, vz]
        data = sock1.recv(40)  # 10 floats * 4 bytes each
        print("received data")
        if len(data) == 40:
            pose = struct.unpack('10f', data)
            
            # Send both attitude/position and velocity data
            send_att_pos_mocap(mavlink_client, pose)
            send_vision_speed_estimate(mavlink_client, pose)
            publish_zenoh_data(zenoh_session, pose)
                
    except socket.error:
        pass  # No data available


def main():
    """Main function"""
    global running
    
    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    logger.info("Starting MAVLink REST proxy...")
    
    # Initialize mavlink2rest client
    mavlink_client = MavlinkRestClient(MAVLINK2REST_URL)
    
    router_host = sys.argv[1] if len(sys.argv) > 1 else "host.docker.internal"
    router_port = sys.argv[2] if len(sys.argv) > 2 else "7447"
    
    print(f"Connecting to Zenoh router at {router_host}:{router_port}")
    
    # Configure Zenoh to connect to host
    config = zenoh.Config()
    config.insert_json5("connect/endpoints", json.dumps([f"tcp/{router_host}:{router_port}"]))
    config.insert_json5("mode", '"client"')
    
    # Add some timeout and retry settings for Docker networking
    config.insert_json5("transport/unicast/lowlatency", "false")

    try:
        session = zenoh.open(config)
        print("✅ Connected to Zenoh router successfully!")
    except Exception as e:
        print(f"❌ Failed to connect to router: {e}")
        print(f"💡 Troubleshooting tips:")
        print(f"   • Make sure Zenoh router is running on host at {router_host}:{router_port}")
        print(f"   • Check Docker networking configuration")
        print(f"   • Try running with: docker run --network=host ...")
        print(f"   • Or use port mapping: docker run -p 7447:7447 ...")
        return
    
    # Define the key/topic to publish to
    pose_key = "robot/pose"
    
    print(f"Declaring publisher on '{pose_key}'...")
    pose_publisher = session.declare_publisher(pose_key)
    
    # Setup Unix domain sockets
    try:
        sock1 = setup_unix_sockets()
        logger.info("Unix domain socket created")
    except Exception as e:
        logger.error(f"Failed to setup socket: {e}")
        return 1
    
    # Main event loop
    logger.info("Entering main loop...")
    
    try:
        while running:
            # Use select to monitor socket
            ready_sockets, _, _ = select.select([sock1], [], [], 0.1)
            
            for sock in ready_sockets:
                if sock == sock1:
                    handle_pose_data(mavlink_client, sock1, pose_publisher)
            
            time.sleep(0.01)  # Small delay to prevent busy waiting
            
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"Error in main loop: {e}")
    finally:
        # Cleanup
        running = False
        sock1.close()
        
        try:
            os.unlink(SERVER_PATH)
        except OSError:
            pass
        
        logger.info("Cleanup completed. Goodbye!")
    
    return 0


if __name__ == "__main__":
    sys.exit(main()) 