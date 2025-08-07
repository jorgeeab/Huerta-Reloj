# Basic Gym Environment

This repository contains a custom Gym environment and several Flask servers used to control a plant irrigation simulator.  

## Installation

1. Install the Python dependencies:

```bash
pip install -r requirements.txt
```

OpenCV is included in the requirements file for the camera streaming features. If you need to install it manually, run:

```bash
pip install opencv-python
```

2. Install the package in editable mode if you plan to modify the environment:

```bash
pip install -e .
```

This will make the `basic_gym_env` package available in your Python environment.

## JSON data files

`BasicEnv` uses JSON files for all persistent data. The plants and regimens are
stored in a shared file while every robot keeps its own list of pending tasks.

```python
from basic_gym_env.basic_env import BasicEnv

env = BasicEnv(archivo_json='data/plants.json', archivo_tareas='data/tasks.json')
```

This setup lets multiple robots work in the same environment with the same
plant configuration while maintaining independent task queues.

## Execution Modes

`BasicEnv` can operate either with a physical robot connected over a serial port or with a virtual robot simulated in PyBullet. Select the mode when creating the environment:

```python
from basic_gym_env.basic_env import BasicEnv

# Physical robot on serial port COM6
real_env = BasicEnv(port='COM6', mode='serial')

# Virtual PyBullet robot
virtual_env = BasicEnv(mode='virtual')
```

Both modes share the same API so your control code works without changes.

## Web Interface

A Flask server provides a browser-based interface for manual control and
managing plants, regimens and tasks. Start the server with:

```bash
python servidor_plantas.py
```

The old Tkinter GUIs have been removed. All configuration is now stored in the
`data/` directory as JSON files and can be edited through the web panel.

## Assistant Instructions

The guidelines for interacting with the robot programmatically are now kept in `docs/assistant_instructions.txt`. This document explains the variables exposed by `BasicEnv` and demonstrates manual and automatic control flows. Consult it if you need to implement your own automation scripts.
