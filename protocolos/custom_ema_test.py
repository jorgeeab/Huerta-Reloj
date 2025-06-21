def custom_action(obs):
    # Incremento de ángulo constante para observar movimiento del motor EMA
    increment_angle = 10  # Grados por paso
    acciones = []
    
    for i in range(10):  # Realiza 10 incrementos
        acciones.append({'slide': obs['inputX'], 'angle': obs['inputA'] + increment_angle, 'volume': obs['volumen']})
    
    return acciones