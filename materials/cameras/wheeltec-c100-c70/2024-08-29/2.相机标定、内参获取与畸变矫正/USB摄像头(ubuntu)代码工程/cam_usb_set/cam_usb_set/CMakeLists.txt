cmake_minimum_required(VERSION 3.10)
project(set)

# 修改为C++17标准
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(OpenCV REQUIRED)

add_executable(${PROJECT_NAME} set.cpp)

include_directories(${OpenCV_INCLUDE_DIRS})

target_link_libraries(${PROJECT_NAME}
    ${OpenCV_LIBS}
    v4l2
)