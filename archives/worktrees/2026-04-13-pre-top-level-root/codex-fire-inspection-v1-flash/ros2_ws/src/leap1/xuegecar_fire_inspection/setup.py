from setuptools import find_packages, setup


package_name = 'xuegecar_fire_inspection'


setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch', ['launch/xuegecar_fire_inspection.launch.py']),
        ('share/' + package_name + '/config', ['config/fire_inspection.yaml']),
        ('share/' + package_name, ['README.md']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='xuegeros',
    maintainer_email='xuegeros@todo.todo',
    description='Fire inspection stack for Leap1.',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'camera_node = xuegecar_fire_inspection.camera_node:main',
            'fire_detector_node = xuegecar_fire_inspection.fire_detector_node:main',
            'mission_manager_node = xuegecar_fire_inspection.mission_manager_node:main',
            'pump_guard_node = xuegecar_fire_inspection.pump_guard_node:main',
        ],
    },
)
