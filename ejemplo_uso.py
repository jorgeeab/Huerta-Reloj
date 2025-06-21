from Protocolo_Reloj.robot_control import RobotControl, RobotEnv
from Protocolo_Reloj.controlador import Controlador
import time

def main():

    virtual_env = RobotEnv(port='COM12', baudrate=115200)
    real_env = RobotEnv(port='COM4', baudrate=115200)
    controlador = Controlador(port='COM14', baudrate=115200)



    robot_control = RobotControl(virtual_env, real_env, controlador)


    virtual_env.disconnect_serial()
    if not virtual_env.connect_serial():
        print("Error al conectar al entorno virtual en el puerto COM12")
    else:
        print("Conectado al entorno virtual en el puerto COM12")

    if not real_env.connect_serial():
        print("Error al conectar al entorno real en el puerto COM4")
    else:
        print("Conectado al entorno real en el puerto COM4")

    # Lista de ángulos y posiciones de corredera para el robot
    angles_and_positions = [
        {'angle_horizontal': 45, 'angle_vertical': 30, 'angle_valve': 15, 'corredera_position': 100},
        {'angle_horizontal': 90, 'angle_vertical': 60, 'angle_valve': 30, 'corredera_position': 200},
        {'angle_horizontal': 135, 'angle_vertical': 90, 'angle_valve': 45, 'corredera_position': 300},
        {'angle_horizontal': 180, 'angle_vertical': 120, 'angle_valve': 60, 'corredera_position': 400},
    ]

    # Iterar sobre la lista de ángulos y posiciones de corredera
    for config in angles_and_positions:
        print(f"Estableciendo ángulos y posición de corredera: {config}")
        robot_control.set_servos(
            angle_horizontal=config['angle_horizontal'],
            angle_vertical=config['angle_vertical'],
            angle_valve=config['angle_valve']
        )
        robot_control.set_flow_setpoint(config['corredera_position'])
        time.sleep(5)

    # Obtener los últimos 5 pasos guardados
    print("Obteniendo los últimos 5 pasos guardados...")
    last_steps = robot_control.get_last_steps(5)
    for step in last_steps:
        elapsed_time, obs, action, reward, done = step
        print(f"Tiempo: {elapsed_time}, Observación: {obs}, Acción: {action}, Recompensa: {reward}, Terminado: {done}")

if __name__ == "__main__":
    main()
