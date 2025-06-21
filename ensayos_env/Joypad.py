import pygame

# Inicializamos Pygame y los joysticks
pygame.init()
pygame.joystick.init()

# Detecta si hay algún joystick conectado
joystick_count = pygame.joystick.get_count()

if joystick_count == 0:
    print("No hay joystick conectado.")
else:
    # Inicializa el primer joystick encontrado
    joystick = pygame.joystick.Joystick(0)
    joystick.init()

    print(f"Joystick detectado: {joystick.get_name()}")
    print(f"Ejes: {joystick.get_numaxes()}")
    print(f"Botones: {joystick.get_numbuttons()}")
    print(f"Hats (crucetas): {joystick.get_numhats()}")

    # Bucle principal para leer las entradas del joystick
    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            # Leer el movimiento de los ejes del joystick
            if event.type == pygame.JOYAXISMOTION:
                axis = event.axis
                value = joystick.get_axis(axis)
                print(f"Eje {axis} movido a {value}")

            # Leer los botones presionados
            if event.type == pygame.JOYBUTTONDOWN:
                button = event.button
                # Aquí puedes asignar nombres personalizados en español a cada botón
                if button == 0:
                    print("Botón A presionado")
                elif button == 1:
                    print("Botón B presionado")
                elif button == 2:
                    print("Botón X presionado")
                elif button == 3:
                    print("Botón Y presionado")
                elif button == 4:
                    print("Botón L1 presionado")
                elif button == 5:
                    print("Botón R1 presionado")
                elif button == 6:
                    print("Botón Select presionado")
                elif button == 7:
                    print("Botón Start presionado")
                elif button == 8:
                    print("Botón Joystick Izquierdo presionado")
                elif button == 9:
                    print("Botón Joystick Derecho presionado")
                else:
                    print(f"Botón {button} presionado")

            # Leer el hat (cruceta)
            if event.type == pygame.JOYHATMOTION:
                hat = joystick.get_hat(0)
                print(f"Cruceta movida a {hat}")

# Cerrar Pygame
pygame.quit()
