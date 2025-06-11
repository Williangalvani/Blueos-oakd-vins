# BlueOS Oak D VINS

This project implements Visual-Inertial Navigation System (VINS) using the Luxonis OAK-D camera for ArduPilot-based vehicles. It provides position and velocity estimates that can be used as a substitute for GPS, enabling position control modes like Loiter, PosHold, RTL, and Auto to work in GPS-denied environments.
This extension is based on the guide at [Ardupilot](https://ardupilot.org/copter/docs//common-vio-oak-d.html)) and the work by [ChobitsFan](https://github.com/chobitsfan),
But replaces the mavlink proxy for mavlink2rest for integration into BlueOS

## Hardware Requirements

- Luxonis OAK-D or OAK-D Pro (OAK-D S2 should work but not tested yet)
- Raspberry Pi 4 or Raspberry Pi 5
- ArduPilot-compatible flight controller

## Hardware Setup

1. Connect the OAK-D to one of the RPI's blue USB3 ports


## ArduPilot Configuration

Configure your ArduPilot flight controller with these parameters:

- `SERIAL1_PROTOCOL = 2` (MAVLink2)
- `SERIAL1_BAUD = 1500` (1500000 baud)
- `VISO_TYPE = 1`
- `VISO_DELAY_MS = 50`
- `EK3_SRC1_POSXY = 6` (ExternalNav)
- `EK3_SRC1_VELXY = 6` (ExternalNav)
- `EK3_SRC1_POSZ = 1` (Baro which is safer)
- `EK3_SRC1_VELZ = 0` (can be set to 6 after successful flight test)
- `EK3_SRC1_YAW = 6` (ExternalNav)
- `COMPASS_USE = 0`, `COMPASS_USE2 = 0`, `COMPASS_USE3 = 0` (disable all compasses)

## Flight Testing

For your first flight:

1. Takeoff in Stabilize or Alt-Hold mode
2. Verify vehicle stability
3. Move the vehicle around and observe position tracking in Mission Planner
4. Switch to Loiter mode (be ready to switch back to Stabilize/Alt-Hold if needed)
5. Test position holding and movement at various speeds
6. If everything works as expected, future flights can be armed and taken off in Loiter mode

## Troubleshooting

- Ensure the OAK-D is properly connected to a USB3 port
- Verify MAVLink communication between RPI and flight controller
- Check Zenoh router connectivity
- Monitor system logs for any error messages

