#!/usr/bin/env python3
"""
Configuration loader for HoneyGrid.
Supports YAML configuration files with environment variable overrides.
"""

import yaml
import os
from pathlib import Path
from typing import Dict, Any, Optional
import logging


logger = logging.getLogger(__name__)


def load_config(config_path: str, defaults: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Load configuration from YAML file.
    
    Args:
        config_path: Path to YAML configuration file
        defaults: Default configuration dictionary
    
    Returns:
        Configuration dictionary
    """
    config_file = Path(config_path)
    
    if not config_file.exists():
        logger.warning(f"Configuration file not found: {config_path}")
        if defaults:
            logger.info("Using default configuration")
            return defaults
        return {}
    
    try:
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f) or {}
        
        logger.info(f"Loaded configuration from: {config_path}")
        
        # Merge with defaults if provided
        if defaults:
            config = merge_configs(defaults, config)
        
        # Apply environment variable overrides
        config = apply_env_overrides(config)
        
        return config
    
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        if defaults:
            logger.info("Using default configuration")
            return defaults
        return {}


def merge_configs(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deep merge two configuration dictionaries.
    
    Args:
        base: Base configuration
        override: Override configuration
    
    Returns:
        Merged configuration
    """
    result = base.copy()
    
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_configs(result[key], value)
        else:
            result[key] = value
    
    return result


def apply_env_overrides(config: Dict[str, Any], prefix: str = "HONEYGRID") -> Dict[str, Any]:
    """
    Apply environment variable overrides to configuration.
    
    Environment variables should be in format: PREFIX_SECTION_KEY
    Example: HONEYGRID_SERVER_HOST=192.168.1.1
    
    Args:
        config: Configuration dictionary
        prefix: Environment variable prefix
    
    Returns:
        Configuration with environment overrides applied
    """
    for env_key, env_value in os.environ.items():
        if not env_key.startswith(f"{prefix}_"):
            continue
        
        # Parse environment variable key
        parts = env_key[len(prefix) + 1:].lower().split('_')
        
        # Navigate config structure
        current = config
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]
        
        # Set value
        key = parts[-1]
        
        # Try to parse as appropriate type
        try:
            # Try boolean
            if env_value.lower() in ('true', 'false'):
                current[key] = env_value.lower() == 'true'
            # Try integer
            elif env_value.isdigit():
                current[key] = int(env_value)
            # Try float
            elif '.' in env_value and all(p.isdigit() for p in env_value.split('.', 1)):
                current[key] = float(env_value)
            # String
            else:
                current[key] = env_value
            
            logger.debug(f"Applied environment override: {env_key} = {env_value}")
        
        except Exception as e:
            logger.warning(f"Failed to apply environment override {env_key}: {e}")
    
    return config


def get_nested_value(config: Dict[str, Any], path: str, default: Any = None) -> Any:
    """
    Get nested configuration value using dot notation.
    
    Args:
        config: Configuration dictionary
        path: Dot-separated path (e.g., "server.database.path")
        default: Default value if path not found
    
    Returns:
        Configuration value or default
    """
    parts = path.split('.')
    current = config
    
    for part in parts:
        if not isinstance(current, dict) or part not in current:
            return default
        current = current[part]
    
    return current


def set_nested_value(config: Dict[str, Any], path: str, value: Any) -> None:
    """
    Set nested configuration value using dot notation.
    
    Args:
        config: Configuration dictionary
        path: Dot-separated path (e.g., "server.database.path")
        value: Value to set
    """
    parts = path.split('.')
    current = config
    
    for part in parts[:-1]:
        if part not in current:
            current[part] = {}
        current = current[part]
    
    current[parts[-1]] = value


# Default server configuration
DEFAULT_SERVER_CONFIG = {
    "server": {
        "host": "0.0.0.0",
        "port": 9000,
        "ca_cert": "certs/ca.crt",
        "server_cert": "certs/server.crt",
        "server_key": "certs/server.key",
        "database": {
            "path": "data/honeygrid.db",
            "password": "change_this_password"
        },
        "security": {
            "max_nonce_cache": 1000,
            "timestamp_tolerance": 60,
            "rate_limit_per_agent": 100
        }
    },
    "notifications": {
        "enabled": False,
        "rate_limit_seconds": 60,
        "batch_mode": False,
        "batch_interval_seconds": 3600,
        "min_severity": "low",
        "email": {
            "enabled": False,
            "smtp_host": "smtp.gmail.com",
            "smtp_port": 587,
            "smtp_username": "",
            "smtp_password": "",
            "from_address": "honeygrid@example.com",
            "to_addresses": [],
            "use_tls": True,
            "logo_url": ""
        },
        "discord": {
            "enabled": False,
            "webhook_url": "",
            "username": "HoneyGrid Bot",
            "avatar_url": None
        }
    },
    "logging": {
        "level": "INFO"
    }
}

# Default agent configuration
DEFAULT_AGENT_CONFIG = {
    "agent": {
        "agent_id": "agent-001",
        "server": {
            "host": "localhost",
            "port": 9000
        },
        "certificates": {
            "ca_cert": "certs/ca.crt",
            "client_cert": "certs/client_agent-001.crt",
            "client_key": "certs/client_agent-001.key"
        },
        "monitoring": {
            "watch_paths": [],
            "rate_limit": {
                "max_events_per_second": 10,
                "burst_size": 20
            }
        },
        "heartbeat": {
            "interval_seconds": 30,
            "timeout_seconds": 10
        }
    },
    "logging": {
        "level": "INFO"
    }
}


if __name__ == "__main__":
    # Test configuration loading
    print("Configuration Loader Test")
    print("=" * 60)
    
    # Test server config
    print("\n1. Loading server config...")
    server_config = load_config("server/config.example.yaml", DEFAULT_SERVER_CONFIG)
    print(f"   Server host: {get_nested_value(server_config, 'server.host')}")
    print(f"   Server port: {get_nested_value(server_config, 'server.port')}")
    print(f"   Notifications enabled: {get_nested_value(server_config, 'notifications.enabled')}")
    
    # Test agent config
    print("\n2. Loading agent config...")
    agent_config = load_config("agent/config.example.yaml", DEFAULT_AGENT_CONFIG)
    print(f"   Agent ID: {get_nested_value(agent_config, 'agent.agent_id')}")
    print(f"   Server: {get_nested_value(agent_config, 'agent.server.host')}:{get_nested_value(agent_config, 'agent.server.port')}")
    
    # Test environment override
    print("\n3. Testing environment override...")
    os.environ["HONEYGRID_SERVER_PORT"] = "9001"
    config = apply_env_overrides({"server": {"port": 9000}})
    print(f"   Port after override: {config['server']['port']}")
    
    print("\n" + "=" * 60)
    print("✓ Configuration loader tests completed")
