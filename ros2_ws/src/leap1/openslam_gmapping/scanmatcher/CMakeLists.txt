add_library(scanmatcher STATIC eig3.cpp scanmatcher.cpp scanmatcherprocessor.cpp smmap.cpp)
target_include_directories(scanmatcher PUBLIC
  ${CMAKE_SOURCE_DIR}/include
  ${CMAKE_CURRENT_SOURCE_DIR}
)
target_link_libraries(scanmatcher sensor_range utils)

install(TARGETS scanmatcher DESTINATION lib)
