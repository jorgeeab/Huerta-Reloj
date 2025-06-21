import gym
import csv
from basic_gym_env.basic_env import BasicEnv
import numpy as np
import matplotlib.pyplot as plt

def main():
    env = BasicEnv(port='COM12', baudrate=115200)

    simulation_duration = 10  # Duración de la simulación en segundos

    start_time = env.simulation_time

    # Enviar comando de prueba para establecer modo manual y energías de motor
    env.set_manual_mode(True)#cuando se establece modo manual se pueden establecer la energía de los motores
    env.set_motor_energy('angulo', 100)#mover el angulo hacia adelante
    env.set_motor_energy('corredera', -100)# mover la corredera hacia adelante
    env.set_motor_energy('valvula', -100)

    # Ejecutar la simulación durante el tiempo especificado
    while env.simulation_time - start_time < simulation_duration:
        obs, reward, _, _ = env.step(env.current_action)
        print(f"Obs: {obs}, Reward: {reward}")

    # Enviar comando de prueba para establecer modo manual y energías de motor
    env.set_manual_mode(False)#cuando se establece modo manual se pueden establecer la energía de los motores



    # Ejecutar la simulación durante el tiempo especificado
    start_time = env.simulation_time
    while env.simulation_time - start_time < simulation_duration:
        obs, reward, _, _ = env.step(env.current_action)
        print(f"Obs: {obs}, Reward: {reward}")

    # Detener la recepción de datos antes de generar el plot
    env.close()

    # Obtener todos los pasos guardados
    all_steps = env.get_last_steps(500)

    with open('robot_steps_all.csv', 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(all_steps)

    data = np.loadtxt('robot_steps_all.csv', delimiter=',', skiprows=1)
    time_steps = data[:, 0]
    angle = data[:, 2]
    motor_energy = data[:, 18]

    plt.figure(figsize=(10, 5))
    plt.subplot(2, 1, 1)
    plt.plot(time_steps, angle, label='Angle')
    plt.xlabel('Time (s)')
    plt.ylabel('Angle (deg)')
    plt.legend()

    plt.subplot(2, 1, 2)
    plt.plot(time_steps, motor_energy, label='Motor Energy')
    plt.xlabel('Time (s)')
    plt.ylabel('Motor Energy')
    plt.legend()

    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    main()

