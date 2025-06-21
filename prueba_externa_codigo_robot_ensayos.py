import gym
from basic_gym_env.basic_env import BasicEnv
from basic_gym_env.interfaz import Interfaz  # Asegúrate de que Interfaz esté correctamente importado
import threading


def run_simulation(env, number_of_executions, simulation_duration):
    env.reset()

    for execution_number in range(1, number_of_executions + 1):
        env.set_pid_angulo(2, 1, 0)
        env.set_pid_corredera(0.5, 0.5, 0.5)
        env.set_pid_valvula(0.7, 0.7, 0.7)
        env.set_manual_mode(False)  # Modo automático

        start_time = env.simulation_time

        while env.simulation_time - start_time < simulation_duration:
            env.set_angulo(10)  # Establecer el ángulo en 40 grados

            obs, reward, _, _ = env.step(env.current_action)
            print(f"Execution {execution_number} - Obs: {obs}, Reward: {reward}")

        execution_name = f"execution_{execution_number}"
        env.save_execution(execution_name)
        env.reset()


def run_interface(env):
    # Inicializa la interfaz gráfica con la instancia de BasicEnv
    app = Interfaz('archivo_plantas.xlsx', 'archivo_regimenes.xlsx', 'archivo_ensayos.xlsx', env=env)

    # Ejecuta la interfaz gráfica
    app.mainloop()


def main():
    env = BasicEnv(port='COM13', baudrate=115200)

    try:
        number_of_executions = 1  # Número de ejecuciones que quieres realizar
        simulation_duration = 10  # Duración de cada simulación en segundos
        # Ejecuta la simulación primero
        run_simulation(env, number_of_executions, simulation_duration)
        # Luego ejecuta la interfaz gráfica
        run_interface(env)

    except Exception as e:
        print(f"Unexpected error: {e}")

    finally:
        env.close()


if __name__ == "__main__":
    main()
