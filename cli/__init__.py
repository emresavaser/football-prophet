__all__ = ["CLICommands", "CLIFormatter"]


def __getattr__(name: str):
    if name == "CLICommands":
        from .commands import CLICommands
        return CLICommands
    if name == "CLIFormatter":
        from .formatter import CLIFormatter
        return CLIFormatter
    raise AttributeError(name)
