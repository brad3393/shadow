"""
Shadow Logging System — structured, leveled logging to file + console.
"""
import sys
import importlib.util
from pathlib import Path

# Load stdlib logging safely even if package name is 'logging'
if 'logging' in sys.modules and not hasattr(sys.modules['logging'], 'Logger'):
    import linecache
    _stdlib_path = Path(linecache.__file__).parent / "logging" / "__init__.py"
    _spec = importlib.util.spec_from_file_location("_stdlib_logging", _stdlib_path)
    logging = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(logging)
else:
    import logging

from config.config import LOGS_DIR


class ShadowLogger:
    _instances: dict = {}

    @classmethod
    def get(cls, name: str = "shadow") -> logging.Logger:
        if name in cls._instances:
            return cls._instances[name]

        logger = logging.getLogger(name)
        logger.setLevel(logging.DEBUG)
        logger.handlers.clear()

        fmt = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        # File handler — always logs everything
        fh = logging.FileHandler(LOGS_DIR / "shadow.log", encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(fmt)
        logger.addHandler(fh)

        # Console handler — INFO and above
        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(logging.INFO)
        ch.setFormatter(fmt)
        logger.addHandler(ch)

        cls._instances[name] = logger
        return logger
