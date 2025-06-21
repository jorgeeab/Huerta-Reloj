import pybullet as p
import pybullet_data
import time

# Conectar a PyBullet
p.connect(p.GUI)
p.setAdditionalSearchPath(pybullet_data.getDataPath())
p.setGravity(0, 0, -9.8)

# Configurar una luz direccional
p.configureDebugVisualizer(p.COV_ENABLE_SHADOWS, 1)
p.configureDebugVisualizer(p.COV_ENABLE_GUI, 0)
p.configureDebugVisualizer(p.COV_ENABLE_RENDERING, 1)
p.resetDebugVisualizerCamera(cameraDistance=2.5, cameraYaw=90, cameraPitch=-30, cameraTargetPosition=[0, 0, 0])

# Cargar el plano y el modelo URDF del robot
planeId = p.loadURDF("plane.urdf")
robotId = p.loadURDF("Reloj_1_description/urdf/Reloj_1.xacro", [0, 0, 0.01], useFixedBase=True)

# Función para imprimir los nombres y los índices de las partes del robot
def print_robot_parts(robot_id):
    num_joints = p.getNumJoints(robot_id)
    print(f"Número de articulaciones: {num_joints}")
    for i in range(num_joints):
        joint_info = p.getJointInfo(robot_id, i)
        joint_name = joint_info[1].decode('utf-8', errors='ignore')
        link_name = joint_info[12].decode('utf-8', errors='ignore')
        print(f"Índice: {i}, Nombre de la articulación: {joint_name}, Nombre del enlace: {link_name}")

# Imprimir los nombres y los índices de las partes del robot
print_robot_parts(robotId)

# Colores en formato RGBA
silver_color = [192/255, 192/255, 192/255, 1]
light_beige_color = [245/255, 245/255, 220/255, 1]  # Beige claro
dark_gray_color = [50/255, 50/255, 50/255, 1]  # Gris oscuro

# Índices de las partes del robot
arm_indices = [0, 1, 2, 3, 4, 5]  # Índices de los brazos
motor_box_index = 6  # Índice de la caja del motor
base_index = 0  # Asumiendo que la base está en el índice 0 (Revolución 8)

# Función para cambiar el color de las partes del robot
def change_joint_color(robot_id, joint_indices, color):
    for joint_index in joint_indices:
        p.changeVisualShape(robot_id, joint_index, rgbaColor=color)

# Cambiar el color de los brazos a plateado
change_joint_color(robotId, arm_indices, silver_color)

# Cambiar el color de la caja del motor a beige claro
change_joint_color(robotId, [motor_box_index], light_beige_color)

# Cambiar el color de la base a gris oscuro
p.changeVisualShape(robotId, -1, rgbaColor=dark_gray_color)  # Usamos -1 para cambiar el color del cuerpo base

# Ejecutar la simulación
for i in range(10000):
    p.stepSimulation()
    time.sleep(1./240.)

# Desconectar de PyBullet
p.disconnect()

