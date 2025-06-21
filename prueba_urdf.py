import pybullet as p
import pybullet_data
import time
import math

# Conectar a PyBullet
p.connect(p.GUI)

# Establecer la ruta de datos de PyBullet
p.setAdditionalSearchPath(pybullet_data.getDataPath())

# Configuración del entorno
p.setGravity(0, 0, -9.81)
p.loadURDF("plane.urdf")

# Cargar tu robot URDF
robot_id = p.loadURDF("Reloj_1_description/urdf/Reloj_1.xacro", useFixedBase=True)

# Establecer la simulación en tiempo real
p.setRealTimeSimulation(1)

# Crear sliders para controlar los joints
slider_revolucion = p.addUserDebugParameter("Revolución", 0, 360, 0)
slider_corredera = p.addUserDebugParameter("Corredera", 0, 1000, 0)

# Índices de los joints
revolucion_joint_index = 0
corredera_joint_indices = [1, 2, 4, 5]

def move_joints(robot_id, joint_indices, target_positions, max_force=10.0):
    """ Mover múltiples joints a posiciones objetivo simultáneamente """
    for joint_index, target_position in zip(joint_indices, target_positions):
        p.setJointMotorControl2(
            bodyIndex=robot_id,
            jointIndex=joint_index,
            controlMode=p.POSITION_CONTROL,
            targetPosition=target_position,
            force=max_force
        )

while True:
    # Leer la posición objetivo del slider de revolución y convertir a radianes
    target_position_revolucion = math.radians(p.readUserDebugParameter(slider_revolucion))
    # Leer la posición objetivo del slider de corredera y escalar al rango [-0.2, 0]
    slider_value = p.readUserDebugParameter(slider_corredera)
    target_position_corredera = - (slider_value / 1000.0) * 0.2  # Corredera desde 0 (completamente estirada) a -0.2 (completamente contraída)
    # Mover el joint de revolución
    move_joints(robot_id, [revolucion_joint_index], [target_position_revolucion])
    # Mover los joints de corredera
    move_joints(robot_id, corredera_joint_indices, [target_position_corredera] * len(corredera_joint_indices))
    # Avanzar en la simulación
    p.stepSimulation()

    # Añadir un pequeño delay para no saturar la CPU
    time.sleep(1. / 240.)

# Desconectar de PyBullet
p.disconnect()
