class BenchError(Exception):
    pass


class SpecError(BenchError):
    pass


class RunnerError(BenchError):
    pass


class DockerUnavailable(RunnerError):
    pass
