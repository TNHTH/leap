add_library(gridfastslam
        gfsreader.cpp
        gridslamprocessor.cpp
        gridslamprocessor_tree.cpp
        motionmodel.cpp
        )
target_include_directories(gridfastslam PUBLIC
  ${CMAKE_SOURCE_DIR}/include
  ${CMAKE_CURRENT_SOURCE_DIR}
)
target_link_libraries(gridfastslam scanmatcher sensor_range)

install(TARGETS gridfastslam DESTINATION lib)

#ament_export_libraries(gridfastslam)
