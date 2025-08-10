# file: config.py
"""Configuration management for persistent user settings."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict

from report import OutputFormat

@dataclass
class AppConfig:
    """Application configuration settings"""
    # Last used paths
    last_source_folder: Optional[str] = None
    last_save_folder: Optional[str] = None
    last_save_file: Optional[str] = None  # NEW: last selected output file
    
    # Export options
    output_format: str = OutputFormat.MARKDOWN.value
    include_contents: bool = True
    
    # Window settings
    window_width: int = 720
    window_height: int = 500
    window_x: Optional[int] = None
    window_y: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AppConfig":
        """Create config from dictionary"""
        # Filter out any unknown keys to handle version changes
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered_data = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered_data)

class ConfigManager:
    """Manages loading and saving application configuration"""
    
    def __init__(self, config_name: str = "project_export_helper.json"):
        self.config_path = self._get_config_dir() / config_name
        self._config: Optional[AppConfig] = None
    
    def _get_config_dir(self) -> Path:
        """Get the appropriate config directory for the platform"""
        import os
        import sys
        
        if sys.platform == "win32":
            # Windows: %APPDATA%
            config_dir = Path(os.environ.get("APPDATA", "~")).expanduser()
        elif sys.platform == "darwin":
            # macOS: ~/Library/Application Support
            config_dir = Path("~/Library/Application Support").expanduser()
        else:
            # Linux/Unix: ~/.config
            config_dir = Path("~/.config").expanduser()
        
        app_config_dir = config_dir / "ProjectExportHelper"
        app_config_dir.mkdir(parents=True, exist_ok=True)
        return app_config_dir
    
    def load_config(self) -> AppConfig:
        """Load configuration from disk, or create default if not found"""
        if self._config is not None:
            return self._config
        
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self._config = AppConfig.from_dict(data)
            else:
                self._config = AppConfig()
        except (json.JSONDecodeError, KeyError, TypeError, OSError):
            # If config is corrupted or unreadable, use defaults
            self._config = AppConfig()
        
        return self._config
    
    def save_config(self, config: AppConfig) -> None:
        """Save configuration to disk"""
        self._config = config
        try:
            # Ensure directory exists
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config.to_dict(), f, indent=2, ensure_ascii=False)
        except OSError:
            # Silently fail if we can't save - don't crash the app
            pass
    
    def update_source_folder(self, path: str) -> None:
        """Update the last used source folder"""
        config = self.load_config()
        config.last_source_folder = path
        self.save_config(config)
    
    def update_save_folder(self, path: str) -> None:
        """Update the last used save folder and file"""
        config = self.load_config()
        config.last_save_folder = str(Path(path).parent)
        config.last_save_file = str(path)
        self.save_config(config)
    
    def update_export_options(self, format_value: str, include_contents: bool) -> None:
        """Update export format and content inclusion setting"""
        config = self.load_config()
        config.output_format = format_value
        config.include_contents = include_contents
        self.save_config(config)
    
    def update_window_geometry(self, width: int, height: int, x: int, y: int) -> None:
        """Update window size and position"""
        config = self.load_config()
        config.window_width = width
        config.window_height = height
        config.window_x = x
        config.window_y = y
        self.save_config(config)

# Global config manager instance
_config_manager: Optional[ConfigManager] = None

def get_config_manager() -> ConfigManager:
    """Get the global config manager instance"""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager
