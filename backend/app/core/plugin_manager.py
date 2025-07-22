"""Gerenciador de plugins extensível.

Implementa sistema para descoberta, carregamento e gerenciamento de plugins.
"""

import importlib
import os
from typing import Dict, List, Type, TypeVar
from app.core.container import container

T = TypeVar('T')

class PluginManager:
    """Gerenciador central de plugins."""
    
    def __init__(self, plugin_dir: str = 'app/plugins'):
        self.plugin_dir = plugin_dir
        self.plugins: Dict[str, object] = {}
        self._load_plugins()
    
    def _load_plugins(self):
        """Carrega plugins dinamicamente do diretório."""
        for filename in os.listdir(self.plugin_dir):
            if filename.endswith('.py') and not filename.startswith('__'):
                module_name = filename[:-3]
                try:
                    module = importlib.import_module(f'app.plugins.{module_name}')
                    if hasattr(module, 'register'):
                        plugin = module.register()
                        self.plugins[module_name] = plugin
                        container.register(type(plugin), implementation=type(plugin), lifetime='singleton')
                except Exception as e:
                    print(f'Erro ao carregar plugin {module_name}: {e}')
    
    def get_plugin(self, name: str) -> object:
        """Obtém um plugin carregado."""
        return self.plugins.get(name)
    
    def list_plugins(self) -> List[str]:
        """Lista plugins disponíveis."""
        return list(self.plugins.keys())

# Instância global
plugin_manager = PluginManager()