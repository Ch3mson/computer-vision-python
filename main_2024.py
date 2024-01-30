"""
For 2023-2024 UAS competition.
"""
import argparse
import multiprocessing as mp
import pathlib
import queue

import cv2
import yaml

from modules import odometry_and_time
from modules.detect_target import detect_target_worker
from modules.flight_interface import flight_interface_worker
from modules.video_input import video_input_worker
from utilities.workers import queue_proxy_wrapper
from utilities.workers import worker_controller
from utilities.workers import worker_manager



CONFIG_FILE_PATH = pathlib.Path("config.yaml")


def main() -> int:
    """
    Main function for airside code.
    """
    # Open config file
    try:
        with CONFIG_FILE_PATH.open("r", encoding="utf8") as file:
            try:
                config = yaml.safe_load(file)
            except yaml.YAMLError as exc:
                print(f"Error parsing YAML file: {exc}")
                return -1
    except FileNotFoundError:
        print(f"File not found: {CONFIG_FILE_PATH}")
        return -1
    except IOError as exc:
        print(f"Error when opening file: {exc}")
        return -1

    # Parse whether or not to force cpu from command line
    parser = argparse.ArgumentParser()
    parser.add_argument("--cpu", action="store_true", help="option to force cpu")
    parser.add_argument("--full", action="store_true", help="option to force full precision")
    args = parser.parse_args()

    # Set constants
    try:
        QUEUE_MAX_SIZE = config["queue_max_size"]

        LOG_DIRECTORY_PATH = config["log_directory_path"]

        VIDEO_INPUT_CAMERA_NAME = config["video_input"]["camera_name"]
        VIDEO_INPUT_WORKER_PERIOD = config["video_input"]["worker_period"]
        VIDEO_INPUT_SAVE_NAME_PREFIX = config["video_input"]["save_prefix"]
        VIDEO_INPUT_SAVE_PREFIX = f"{LOG_DIRECTORY_PATH}/{VIDEO_INPUT_SAVE_NAME_PREFIX}"

        DETECT_TARGET_WORKER_COUNT = config["detect_target"]["worker_count"]
        DETECT_TARGET_DEVICE =  "cpu" if args.cpu else config["detect_target"]["device"]
        DETECT_TARGET_MODEL_PATH = config["detect_target"]["model_path"]
        DETECT_TARGET_OVERRIDE_FULL_PRECISION = args.full
        DETECT_TARGET_SAVE_NAME_PREFIX = config["detect_target"]["save_prefix"]
        DETECT_TARGET_SAVE_PREFIX = f"{LOG_DIRECTORY_PATH}/{DETECT_TARGET_SAVE_NAME_PREFIX}"

        FLIGHT_INTERFACE_ADDRESS = config["flight_interface"]["address"]
        FLIGHT_INTERFACE_TIMEOUT = config["flight_interface"]["timeout"]
        FLIGHT_INTERFACE_WORKER_PERIOD = config["flight_interface"]["worker_period"]
    except KeyError:
        print("Config key(s) not found")
        return -1

    pathlib.Path(LOG_DIRECTORY_PATH).mkdir(exist_ok=True)

    # Setup
    controller = worker_controller.WorkerController()

    mp_manager = mp.Manager()
    video_input_to_detect_target_queue = queue_proxy_wrapper.QueueProxyWrapper(
        mp_manager,
        QUEUE_MAX_SIZE,
    )
    detect_target_to_main_queue = queue_proxy_wrapper.QueueProxyWrapper(
        mp_manager,
        QUEUE_MAX_SIZE,
    )
    flight_interface_to_main_queue = queue_proxy_wrapper.QueueProxyWrapper(
        mp_manager,
        QUEUE_MAX_SIZE
    )

    video_input_manager = worker_manager.WorkerManager()
    video_input_manager.create_workers(
        1,
        video_input_worker.video_input_worker,
        (
            VIDEO_INPUT_CAMERA_NAME,
            VIDEO_INPUT_WORKER_PERIOD,
            VIDEO_INPUT_SAVE_PREFIX,
            video_input_to_detect_target_queue,
            controller,
        ),
    )

    detect_target_manager = worker_manager.WorkerManager()
    detect_target_manager.create_workers(
        DETECT_TARGET_WORKER_COUNT,
        detect_target_worker.detect_target_worker,
        (
            DETECT_TARGET_DEVICE,
            DETECT_TARGET_MODEL_PATH,
            DETECT_TARGET_OVERRIDE_FULL_PRECISION,
            DETECT_TARGET_SAVE_PREFIX,
            video_input_to_detect_target_queue,
            detect_target_to_main_queue,
            controller,
        ),
    )

    flight_interface_manager = worker_manager.WorkerManager()
    flight_interface_manager.create_workers(
        1,
        flight_interface_worker.flight_interface_worker,
        (
            FLIGHT_INTERFACE_ADDRESS,
            FLIGHT_INTERFACE_TIMEOUT,
            FLIGHT_INTERFACE_WORKER_PERIOD,
            flight_interface_to_main_queue,
            controller,
        ),
    )

    # Run
    video_input_manager.start_workers()
    detect_target_manager.start_workers()
    flight_interface_manager.start_workers()

    while True:
        try:
            image = detect_target_to_main_queue.queue.get_nowait()
        except queue.Empty:
            image = None

        odometry_and_time_info: "odometry_and_time.OdometryAndTime | None" = \
            flight_interface_to_main_queue.queue.get()

        if odometry_and_time_info is not None:
            timestamp = odometry_and_time_info.timestamp
            position = odometry_and_time_info.odometry_data.position
            orientation = odometry_and_time_info.odometry_data.orientation.orientation

            print("timestamp: " + str(timestamp))
            print("north: " + str(position.north))
            print("east: " + str(position.east))
            print("down: " + str(position.down))
            print("yaw: " + str(orientation.yaw))
            print("roll: " + str(orientation.roll))
            print("pitch: " + str(orientation.pitch))
            print("")

        if image is None:
            continue

        cv2.imshow("Landing Pad Detector", image)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    # Teardown
    controller.request_exit()

    video_input_to_detect_target_queue.fill_and_drain_queue()
    detect_target_to_main_queue.fill_and_drain_queue()
    flight_interface_to_main_queue.fill_and_drain_queue()

    video_input_manager.join_workers()
    detect_target_manager.join_workers()
    flight_interface_manager.join_workers()

    return 0


if __name__ == "__main__":
    result_run = main()
    if result_run < 0:
        print(f"ERROR: Status code: {result_run}")

    print("Done!")
