from abc import ABC, abstractmethod



class BaseAgent(ABC):
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self

    @abstractmethod
    def run(self, input: str) -> str:
        pass
