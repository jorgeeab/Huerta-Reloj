from .basic_env import BasicEnv
from nuevo_plantas import PlantasManager
from .tasks_manager import RobotTasksManager


def register_env():
    from gym.envs.registration import register
    register(
        id='BasicEnv-v0',
        entry_point='basic_gym_env:BasicEnv',
    )
register_env()
