from __future__ import annotations

from dataclasses import dataclass
from inspect import Signature, signature
from typing import Callable


@dataclass(frozen=True)
class ToolSpec:
    name: str
    func: Callable
    signature: Signature
    description: str

    @property
    def prompt_description(self) -> str:
        return f"{self.name}{self.signature}: {self.description}"


class ToolBox:
    def __init__(self):
        self.tools_dict: dict[str, ToolSpec] = {}

    def store(self, functions_list: dict[str, Callable]) -> dict[str, ToolSpec]:
        """
        Store tool metadata for each supported callable.

        Parameters:
        functions_list (dict): Mapping of tool names to callable objects.

        Returns:
        dict: Dictionary with function names as keys and tool specs as values.
        """
        for name, func in functions_list.items():
            description = (func.__doc__ or "").strip().replace("\n", " ")
            self.tools_dict[name] = ToolSpec(
                name=name,
                func=func,
                signature=signature(func),
                description=description,
            )
        return self.tools_dict

    def tools(self) -> str:
        """
        Return stored tool descriptions formatted for prompts.
        """
        return "\n".join(spec.prompt_description for spec in self.tools_dict.values()).strip()

    def get(self, function_name: str) -> ToolSpec | None:
        return self.tools_dict.get(function_name)
