import json
from typing import Any, Dict, List, Union


class Memory:

    def __init__(self, is_structured: bool = True, has_history: str = None):
        self.is_structured = is_structured
        self.memory = [] if is_structured else []

        if has_history is not None:
            try:
                data = self.read_history(has_history)
                if (self.is_structured and all(isinstance(item, dict) for item in data)) or not self.is_structured:
                    self.memory = data
                else:
                    print('Loaded data does not match the expected memory structure.')
            except FileNotFoundError:
                self.memory = []
            except (json.JSONDecodeError, ValueError) as e:
                print(f'Error reading history: {e}')


    def read_history(self, has_history: str) -> Union[Dict[Any, Any], List[Any]]:
        if has_history.endswith('.json'):
            with open(has_history, 'r', encoding='utf-8') as file:
                data = json.load(file)
            return data
        elif has_history.endswith('.txt'):
            with open(has_history, 'r', encoding='utf-8') as file:
                data = file.read().splitlines()
            return data
        else:
            raise ValueError("Unsupported file type")
        

    def extend_memory(self, new_memory: Union[Dict[Any, Any], Any]) -> None:
        if self.is_structured:
            if not isinstance(new_memory, dict):
                raise ValueError("New memory must be a dictionary in structured mode.")
            self.memory.append(new_memory)
        else:
            if isinstance(new_memory, list):
                self.memory.extend(new_memory)
            else:
                self.memory.append(new_memory)
        

    def _format_entry(self, item: Any) -> str:
        if self.is_structured and isinstance(item, dict):
            return json.dumps(item, ensure_ascii=False, default=str)
        return str(item)

    def recall_raw(self, steps: int | None = None) -> list[Any]:
        if steps is None:
            return list(self.memory)
        return list(self.memory[-steps:])

    def save_history(self, file_path: str) -> None:
        """Save the current memory to a specified location in either JSON or TXT format."""
        try:
            if file_path.endswith('.json'):
                with open(file_path, 'w', encoding='utf-8') as file:
                    json.dump(self.memory, file, indent=4, ensure_ascii=False)

            elif file_path.endswith('.txt'):
                with open(file_path, 'w', encoding='utf-8') as file:
                    file.write('\n'.join(self._format_entry(item) for item in self.memory) + '\n')
            else:
                raise ValueError("Unsupported file type. Please use .json or .txt")

        except Exception as e:
            print(f"Error saving history: {e}")
