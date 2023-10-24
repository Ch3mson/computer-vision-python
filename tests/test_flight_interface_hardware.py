"""
Simple hardware test, requires drone connection.
"""

from modules.flight_interface import flight_interface


MAVLINK_CONNECTION_ADDRESS = "tcp:localhost:14550"
FLIGHT_INTERFACE_TIMEOUT = 10.0  # seconds


if __name__ == "__main__":
    # Setup
    result, interface = flight_interface.FlightInterface.create(
        MAVLINK_CONNECTION_ADDRESS,
        FLIGHT_INTERFACE_TIMEOUT,
    )
    assert result
    assert interface is not None

    # Run
    result, odometry_time = interface.run()

    # Test
    assert result
    assert odometry_time is not None

    print("Done!")
