#!/bin/bash
# Work around the virtual image's mismatched BT library export without changing ROS.
set -euo pipefail
cd "$(dirname "$0")/.."
prefix="$PWD/.cache/bt-overlay"
ros_prefix="/opt/ros/humble"
test -f "$ros_prefix/lib/x86_64-linux-gnu/libbehaviortree_cpp.so"
mkdir -p "$prefix/share" "$prefix/lib"
cp -r "$ros_prefix/share/behaviortree_cpp" "$prefix/share/"
ln -sfn "$ros_prefix/include" "$prefix/include"
ln -sfn "$ros_prefix/lib/x86_64-linux-gnu" "$prefix/lib/x86_64-linux-gnu"
ln -sfn "$ros_prefix/lib/x86_64-linux-gnu/libbehaviortree_cpp.so" "$prefix/lib/libbehaviortree_cpp.so"
echo "Use: ./scripts/build_no_cuda.sh -Dbehaviortree_cpp_DIR=$prefix/share/behaviortree_cpp/cmake"
