from .basic_env import BasicEnv
from .plantas import PlantasManager
from .regimenes import RegimenesManager
from .ensayos import EnsayosEnv
from .interfaz import Interfaz
#from .utils import crear_archivos_plantas_y_regimenes

def register_env():
    from gym.envs.registration import register
    register(
        id='BasicEnv-v0',
        entry_point='basic_gym_env:BasicEnv',
    )

register_env()