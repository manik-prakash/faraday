class FaradayError(Exception):
    pass


class SpecError(FaradayError):
    pass


class RunnerError(FaradayError):
    pass


class DockerUnavailable(RunnerError):
    pass
