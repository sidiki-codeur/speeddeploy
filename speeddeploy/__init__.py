"""SpeedDeploy package."""

from .config import ConfigError, ConfigTemplate, DeploymentTarget, ProjectConfig, load_config, render_config_template
from .deployer import build_deployment_plan, clone_or_update, full_deploy, init_project, update_project
from .runner import CommandError, is_dry_run, run, set_dry_run
from .system import RuntimeInfo, detect_runtime

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "build_deployment_plan",
    "clone_or_update",
    "CommandError",
    "ConfigError",
    "ConfigTemplate",
    "DeploymentTarget",
    "full_deploy",
    "init_project",
    "is_dry_run",
    "load_config",
    "ProjectConfig",
    "render_config_template",
    "run",
    "RuntimeInfo",
    "detect_runtime",
    "set_dry_run",
    "update_project",
]
