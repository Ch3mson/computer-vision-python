"""
Test worker process.
"""
import multiprocessing as mp
import time

import numpy as np

from modules import detections_and_time
from modules import merged_odometry_detections
from modules.common.mavlink.modules import drone_odometry
from modules.geolocation import camera_properties
from modules.geolocation import geolocation_worker
from utilities.workers import queue_proxy_wrapper
from utilities.workers import worker_controller


STARTUP_TIMEOUT = 10.0  # seconds
WORK_COUNT = 3


def simulate_previous_worker(in_queue: queue_proxy_wrapper.QueueProxyWrapper):
    """
    Place the image into the queue.
    """
    result_simulate, drone_position = \
        drone_odometry.DronePosition.create(
            43.472978,
            -80.540103,
            336.0 + 100.0,  # 100m above ground
        )
    assert result_simulate
    assert drone_position is not None

    result_simulate, drone_orientation = \
        drone_odometry.DroneOrientation.create(
            0.0,
            -np.pi / 2,
            0.0,
        )
    assert result_simulate
    assert drone_orientation is not None

    result_simulate, detection = detections_and_time.Detection.create(
        np.array([0.0, 0.0, 2000.0, 2000.0], dtype=np.float32),
        1,
        1.0 / 1,
    )
    assert result_simulate
    assert detection is not None

    value = merged_odometry_detections.MergedOdometryDetections(
        drone_position,
        drone_orientation,
        [detection],
    )

    in_queue.queue.put(value)


if __name__ == "__main__":
    # Setup
    result, camera_intrinsics = camera_properties.CameraIntrinsics.create(
        2000,
        2000,
        np.pi / 2,
        np.pi / 2,
    )
    assert result
    assert camera_intrinsics is not None

    result, camera_extrinsics = camera_properties.CameraDroneExtrinsics.create(
        (0.0, 0.0, 0.0),
        (0.0, 0.0, 0.0),
    )
    assert result
    assert camera_extrinsics is not None

    result, home_location = drone_odometry.DronePosition.create(43.472978, -80.540103, 336.0)
    assert result
    assert home_location is not None

    controller = worker_controller.WorkerController()

    mp_manager = mp.Manager()

    home_location_queue = queue_proxy_wrapper.QueueProxyWrapper(mp_manager)
    detection_in_queue = queue_proxy_wrapper.QueueProxyWrapper(mp_manager)
    detection_out_queue = queue_proxy_wrapper.QueueProxyWrapper(mp_manager)

    worker = mp.Process(
        target=geolocation_worker.geolocation_worker,
        args=(
            camera_intrinsics,
            camera_extrinsics,
            home_location_queue,
            STARTUP_TIMEOUT,
            detection_in_queue,
            detection_out_queue,
            controller,
        ),
    )

    # Run
    worker.start()

    home_location_queue.queue.put(home_location)

    for _ in range(0, WORK_COUNT):
        simulate_previous_worker(detection_in_queue)

    time.sleep(1)

    for _ in range(0, WORK_COUNT):
        simulate_previous_worker(detection_in_queue)

    controller.request_exit()

    # Test
    for _ in range(0, WORK_COUNT * 2):
        input_data: list = detection_out_queue.queue.get_nowait()
        assert input_data[0] is not None

    assert detection_out_queue.queue.empty()

    # Teardown
    detection_in_queue.fill_and_drain_queue()
    worker.join()

    print("Done!")
