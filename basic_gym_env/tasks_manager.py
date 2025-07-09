import json
from typing import List, Dict, Any

class RobotTasksManager:
    """Manage per-robot task lists stored in a JSON file."""

    def __init__(self, tasks_file: str = 'tareas_robot.json') -> None:
        self.tasks_file = tasks_file
        self.tareas: List[Dict[str, Any]] = []
        self._load()

    def _load(self) -> None:
        try:
            with open(self.tasks_file, 'r') as f:
                data = json.load(f)
                self.tareas = data.get('tareas', [])
        except FileNotFoundError:
            self.tareas = []

    def _save(self) -> None:
        with open(self.tasks_file, 'w') as f:
            json.dump({'tareas': self.tareas}, f, indent=4)

    def agregar_tarea(self, tarea: Dict[str, Any]) -> None:
        """Add a new task dictionary to the list."""
        self.tareas.append(tarea)
        self._save()

    def obtener_tareas(self) -> List[Dict[str, Any]]:
        return list(self.tareas)

    def eliminar_tarea(self, index: int) -> None:
        if 0 <= index < len(self.tareas):
            del self.tareas[index]
            self._save()
