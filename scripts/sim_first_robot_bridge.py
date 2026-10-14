#!/usr/bin/env python3
"""Keep the single-player demo connected when a stationary second robot is added.

Only robot1 is bridged; robot2 receives no soccer commands.
"""
import rclpy
from rclpy.qos import qos_profile_sensor_data
from rosidl_runtime_py.utilities import get_message


def main():
    rclpy.init()
    node = rclpy.create_node('sim_first_robot_bridge')
    mappings = {
        '/LocoApiTopicReq': ('/LocoApiTopic/robot1Req', 'booster_msgs/msg/RpcReqMsg'),
        '/LocoApiTopic/robot1Resp': ('/LocoApiTopicResp', 'booster_msgs/msg/RpcRespMsg'),
        # Visual-kick targets: robot1's motion process reads rt/robot1/kick_ball.
        '/kick_ball': ('/robot1/kick_ball', 'brain/msg/Kick'),
        '/robot1/rgbd_camera/rgb/image_compressed': ('/rgbd_camera/rgb/image_compressed', 'sensor_msgs/msg/CompressedImage'),
        '/robot1/rgbd_camera/rgb/camera_info': ('/rgbd_camera/rgb/camera_info', 'sensor_msgs/msg/CameraInfo'),
        '/robot1/rgbd_camera/depth/image_raw': ('/rgbd_camera/depth/image_raw', 'sensor_msgs/msg/Image'),
        '/robot1/rgbd_camera/depth/camera_info': ('/rgbd_camera/depth/camera_info', 'sensor_msgs/msg/CameraInfo'),
        '/robot1/odometer_state': ('/odometer_state', 'booster_interface/msg/Odometer'),
        '/robot1/low_state': ('/low_state', 'booster_interface/msg/LowState'),
        '/robot1/head_pose': ('/head_pose', 'geometry_msgs/msg/Pose'),
        '/robot1/fall_down_recovery_state': ('/fall_down_recovery_state', 'booster_interface/msg/RawBytesMsg'),
        '/robot1/soccer/sim/localization/robot_pose': ('/soccer/sim/localization/robot_pose', 'geometry_msgs/msg/Pose2D'),
    }
    subscriptions = []
    for source, (target, typename) in mappings.items():
        cls = get_message(typename)
        publisher = node.create_publisher(cls, target, 10)
        subscriptions.append(node.create_subscription(cls, source, publisher.publish, qos_profile_sensor_data))
        node.get_logger().info(source + ' -> ' + target)
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
