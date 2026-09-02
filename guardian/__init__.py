"""
Shadow Guardian Security Layer.
Provides execution permissions, sandbox boundaries, dangerous operation detection,
file access restrictions, user approval handling, checkpoints, rollback, and audit logging.
"""
from guardian.guardian import Guardian

__all__ = ["Guardian"]
