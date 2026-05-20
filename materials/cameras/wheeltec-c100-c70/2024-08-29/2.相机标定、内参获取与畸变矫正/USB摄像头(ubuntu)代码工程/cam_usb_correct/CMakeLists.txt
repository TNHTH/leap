cmake_minimum_required(VERSION 3.10)
project(correct)

# 设置 C++ 标准
set(CMAKE_CXX_STANDARD 11)
set(CMAKE_CXX_STANDARD_REQUIRED True)

# 查找 OpenCV
find_package(OpenCV REQUIRED)

# 包含 OpenCV 的头文件
include_directories(${OpenCV_INCLUDE_DIRS})

# 添加可执行文件
add_executable(correct correct.cpp)

# 链接 OpenCV 库
target_link_libraries(correct ${OpenCV_LIBS})