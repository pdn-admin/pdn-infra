import yaml
from pathlib import Path


class Settings:
    def __init__(self):
        self.PROJECT_NAME: str = self._config['project']['name']
        self.VERSION: str = self._config['project']['version']

settings = Settings()
