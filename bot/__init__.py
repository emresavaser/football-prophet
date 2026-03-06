__all__ = ["FootballProphet", "Runner"]


def __getattr__(name: str):
    if name == "FootballProphet":
        from .core import FootballProphet
        return FootballProphet
    if name == "Runner":
        from .runner import Runner
        return Runner
    raise AttributeError(name)
