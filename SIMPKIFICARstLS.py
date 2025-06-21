import os
import trimesh

def simplify_mesh(input_stl, output_stl, reduction_ratio=0.5):
    mesh = trimesh.load(input_stl)
    simplified_mesh = mesh.simplify_quadratic_decimation(int(mesh.faces.shape[0] * reduction_ratio))
    simplified_mesh.export(output_stl)
    print(f"Mesh simplified and saved to {output_stl}")

def simplify_all_stl_files(input_dir, output_dir, reduction_ratio=0.5):
    for filename in os.listdir(input_dir):
        if filename.endswith('.stl'):
            input_stl = os.path.join(input_dir, filename)
            output_stl = os.path.join(output_dir, filename)
            simplify_mesh(input_stl, output_stl, reduction_ratio)

# Directorio de los archivos STL originales y de salida
input_dir = 'basic_gym_env/Reloj_1_description/meshes/not_simplified'
output_dir = 'basic_gym_env/Reloj_1_description/meshes'

# Simplificar los archivos STL y guardarlos en la carpeta de salida
simplify_all_stl_files(input_dir, output_dir, reduction_ratio=0.1)
