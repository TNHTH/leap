include_directories(./)
add_library(utils movement.cpp stat.cpp)
target_include_directories(utils PUBLIC
  ${CMAKE_SOURCE_DIR}/include
  ${CMAKE_CURRENT_SOURCE_DIR}
)
install(TARGETS utils DESTINATION lib)

ament_export_libraries(utils)
