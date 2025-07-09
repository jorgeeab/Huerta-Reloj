# Basic Gym Environment

This repository contains a custom Gym environment and several Flask servers used to control a plant irrigation simulator.  

## Installation

1. Install the Python dependencies:

```bash
pip install -r requirements.txt
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

env = BasicEnv(archivo_json='plantas.json', archivo_tareas='tareas_robot.json')
```

This setup lets multiple robots work in the same environment with the same
plant configuration while maintaining independent task queues.
