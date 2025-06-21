def custom_action(env, params):
    """
    Protocolo para mover el robot a un punto específico.
    
    Parámetros:
        env: Entorno del robot.
        params: Diccionario con los parámetros:
            - target_angle (float): Ángulo objetivo.
            - target_x (float): Posición de corredera objetivo.
            - kpX, kiX, kdX (float): PIDs para la corredera.
            - kpA, kiA, kdA (float): PIDs para el ángulo.

    Retorna:
        Lista con la acción a ejecutar.
    """
    # Extraer parámetros
    target_angle = params.get("target_angle", 90.0)  # Cambiado a 90°
    target_x = params.get("target_x", 0.0)
    kpX, kiX, kdX = params.get("kpX", 1.0), params.get("kiX", 0.2), params.get("kdX", 0.1)
    kpA, kiA, kdA = params.get("kpA", 50.0), params.get("kiA", 5.0), params.get("kdA", 20.0)  # Parámetros mucho más altos

    # Obtener las observaciones actuales
    obs = env.get_observation()
    current_x = obs.get("InputX", 0.0)  # Input X actual
    current_a = obs.get("InputA", 0.0)  # Input A actual

    # Calcular si el robot está cerca del objetivo
    threshold_x = 1.0  # Tolerancia para X
    threshold_a = 1.0  # Tolerancia para el ángulo

    close_to_x = abs(current_x - target_x) <= threshold_x
    close_to_a = abs(current_a - target_angle) <= threshold_a

    if close_to_x and close_to_a:
        # Si está cerca del objetivo, detener todos los motores
        action = env.current_action.copy()
        action[1] = 0  # EMA
        action[2] = 0  # EMX
        action[3] = 0  # EMV
        print("Objetivo alcanzado. Deteniendo el robot.")
    else:
        # Configurar PIDs y modo automático antes de mover
        action = env.current_action.copy()
        action[0] = 0  # Modo automático
        action[4] = target_x  # X_Requerido
        action[5] = target_angle  # A_Requerido
        action[7], action[8], action[9] = kpX, kiX, kdX  # PIDs para corredera
        action[10], action[11], action[12] = kpA, kiA, kdA  # PIDs para ángulo
        print(f"Moviendo hacia X={target_x}, A={target_angle}")

    return action