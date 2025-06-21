import pybullet as p
import pybullet_data
import numpy as np
import time

# Conectar a PyBullet
p.connect(p.GUI)
p.setAdditionalSearchPath(pybullet_data.getDataPath())
p.setGravity(0, 0, -9.8)

# Cargar el plano y el modelo URDF del robot con yaw inicial de 30 grados
planeId = p.loadURDF("plane.urdf")
robot_orientation = p.getQuaternionFromEuler([0, 0, np.pi / 6])
robotId = p.loadURDF("Reloj_1_description/urdf/Reloj_1.xacro", [0, 0, 0.01], robot_orientation, useFixedBase=True)

# Crear slider para controlar la tasa de generación de esferas
slider_rate = p.addUserDebugParameter("Tasa de generación (esferas/segundo)", 1.0, 10.0, 1.0)

# Definir el límite de esferas
MAX_SPHERES = 100


# Función para generar esferas en una posición específica
def generate_spheres():
    sphere_radius = 0.001  # Esferas más pequeñas
    sphere_mass = 0.001  # Reducir la masa de las esferas
    sphere_collision = p.createCollisionShape(p.GEOM_SPHERE, radius=sphere_radius)
    sphere_visual = p.createVisualShape(p.GEOM_SPHERE, radius=sphere_radius, rgbaColor=[0, 0, 1, 1])

    generated_spheres = []

    last_sphere_time = time.time()

    while True:
        # Obtener la tasa de generación desde el slider
        rate = p.readUserDebugParameter(slider_rate)

        # Calcular el intervalo de tiempo entre generación de esferas en segundos
        interval = 1.0 / rate

        # Verificar si ha pasado suficiente tiempo para generar una nueva esfera
        current_time = time.time()
        if current_time - last_sphere_time >= interval:
            last_sphere_time = current_time

            # Obtener la posición y orientación del joint específico (joint de la corredera)
            joint_index = 5  # Índice del joint de la corredera
            joint_state = p.getLinkState(robotId, joint_index, computeForwardKinematics=True)

            pos = joint_state[0]
            ori = joint_state[1]

            # Convertir orientación a matriz de rotación
            rot_matrix = p.getMatrixFromQuaternion(ori)
            rot_matrix = np.array(rot_matrix).reshape(3, 3)

            # Agregar la rotación adicional de 30 grados (yaw) en sentido correcto
            yaw_matrix = np.array([
                [np.cos(np.pi / 6), -np.sin(np.pi / 6), 0],
                [np.sin(np.pi / 6), np.cos(np.pi / 6), 0],
                [0, 0, 1]
            ])
            combined_rot_matrix = np.dot(rot_matrix, yaw_matrix)

            # Posición relativa de generación de esferas en el sistema de coordenadas del joint
            distance_from_center = -0.2  # Distancia radial desde el centro del joint
            relative_pos = np.array([0.0, distance_from_center, -0.03])  # Ajustar según sea necesario

            # Calcular la posición global de generación de esferas
            global_pos = np.dot(combined_rot_matrix, relative_pos) + np.array(pos)

            if len(generated_spheres) < MAX_SPHERES:
                # Generar una nueva esfera si no se ha alcanzado el límite
                sphere_id = p.createMultiBody(baseMass=sphere_mass, baseCollisionShapeIndex=sphere_collision,
                                              baseVisualShapeIndex=sphere_visual, basePosition=global_pos)
                generated_spheres.append(sphere_id)
            else:
                # Reciclar una esfera existente
                sphere_id = generated_spheres.pop(0)
                p.resetBasePositionAndOrientation(sphere_id, global_pos, [0, 0, 0, 1])
                generated_spheres.append(sphere_id)



        p.stepSimulation()
        time.sleep(1. / 240.)  # Asegura la simulación en tiempo real


# Ejecutar la función para generar esferas
generate_spheres()

