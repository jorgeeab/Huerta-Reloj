import pybullet as p
import pybullet_data
import time
import numpy as np

# Conectar a PyBullet
p.connect(p.GUI)
p.setAdditionalSearchPath(pybullet_data.getDataPath())
p.setGravity(0, 0, -9.8)

# Cargar el plano y el modelo URDF del robot
planeId = p.loadURDF("plane.urdf")
robotId = p.loadURDF("Reloj_1_description/urdf/Reloj_1.xacro", [0, 0, 0.01], useFixedBase=True)

# Establecer el índice del joint que vamos a limitar
joint_index = 0  # Cambia este índice según tu modelo URDF

# Establecer límites en el joint (en grados)
lower_limit_deg = 0  # Límite inferior en grados
upper_limit_deg = 300  # Límite superior en grados

# Convertir límites a radianes para PyBullet
lower_limit = np.deg2rad(lower_limit_deg)
upper_limit = np.deg2rad(upper_limit_deg)

# Función para mover el joint a una posición específica dentro de los límites
def move_joint_to_position(robot_id, joint_idx, position_deg, max_force=10):
    # Convertir posición de grados a radianes
    position = np.deg2rad(np.clip(position_deg, lower_limit_deg, upper_limit_deg))
    p.setJointMotorControl2(robot_id, joint_idx, p.POSITION_CONTROL, targetPosition=position, force=max_force)

# Probar moviendo el joint a varias posiciones (en grados)
positions_to_test_deg = [0, 90, 180, 300,0, 90, 180, 300]

for pos_deg in positions_to_test_deg:
    move_joint_to_position(robotId, joint_index, pos_deg)
    for _ in range(240):
        p.stepSimulation()
        time.sleep(1./240.)

# Desconectar de PyBullet
p.disconnect()
