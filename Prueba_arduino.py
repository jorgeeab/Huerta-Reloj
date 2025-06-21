import time
from basic_gym_env.basic_env import BasicEnv  # Asegúrate de que BasicEnv esté correctamente importado


def main():
    # Inicializar el entorno con el puerto serial y baudrate adecuados
    env = BasicEnv(port='COM8', baudrate=115200)

    try:
        # Restablecer el entorno para obtener la observación inicial
        observation = env.reset()
        print('Observación Inicial:')
        # Crear un diccionario de variable:valor
        obs_dict = dict(zip(env.variable_names, observation))
        for name, value in obs_dict.items():
            print(f"{name}: {value}")

        # Definir el número de pasos a ejecutar en cada escenario
        steps_per_scenario = 10  # Puedes ajustar este número según sea necesario

        # Escenario 1: Modo Automático con setpoints y parámetros PID específicos
        print("\nEscenario 1: Modo Automático")
        env.set_manual_mode(0)  # Asegurarnos de que estamos en modo automático

        env.set_corredera(200)  # Establecer setpoint para el motor lineal (X_Requerido)
        env.set_angulo(90)  # Establecer setpoint para el motor angular (A_Requerido)
        env.set_volumen_requerido(500)  # Establecer volumen requerido (Vol_requerido)
        env.set_pid_corredera(1.0, 0.1, 0.05)  # Parámetros PID para el motor lineal
        env.set_pid_angulo(1.0, 0.1, 0.05)  # Parámetros PID para el motor angular

        for step in range(steps_per_scenario):
            # Realizar un paso en el entorno
            observation, reward, done, info = env.step()
            # Crear un diccionario de variable:valor
            obs_dict = dict(zip(env.variable_names, observation))
            print(f"\nPaso {step + 1} - Observación:")
            for name, value in obs_dict.items():
                print(f"{name}: {value}")
            # Esperar un poco antes del siguiente paso

        # Esperar antes de pasar al siguiente escenario
        time.sleep(2)
        env.set_manual_mode(1)  # Cambiar a modo manual para el siguiente escenario

        # Escenario 2: Modo Manual con energías específicas para los motores
        print("\nEscenario 2: Modo Manual")
        env.set_energy_corredera(100)
        env.set_energy_angulo(200)
        env.set_energy_valvula(200)  # Controlar la bomba manualmente

        for step in range(steps_per_scenario):
            observation, reward, done, info = env.step()
            obs_dict = dict(zip(env.variable_names, observation))
            print(f"\nPaso {step + 1} - Observación:")
            for name, value in obs_dict.items():
                print(f"{name}: {value}")


        time.sleep(3)

        # Escenario 3: Modo Manual con energías negativas para invertir dirección
        print("\nEscenario 3: Modo Manual con Energías Negativas")
        env.set_manual_mode(1)  # Asegurarnos de que estamos en modo manual
        env.set_energy_corredera(-100)
        env.set_energy_angulo(-250)
        env.set_energy_valvula(0)

        for step in range(steps_per_scenario):
            observation, reward, done, info = env.step()
            obs_dict = dict(zip(env.variable_names, observation))
            print(f"\nPaso {step + 1} - Observación:")
            for name, value in obs_dict.items():
                print(f"{name}: {value}")


        # Detener los motores
        env.set_energy_corredera(0)
        env.set_energy_angulo(0)
        env.set_energy_valvula(0)
        # Escenario 4: Calibración


    finally:
        # Cerrar el entorno
        env.close()


if __name__ == '__main__':
    main()
