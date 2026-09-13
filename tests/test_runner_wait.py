"""_wait_for_agent must tell a real timeout apart from a Docker/infra error."""

from __future__ import annotations

from docker.errors import APIError
from requests.exceptions import ReadTimeout

from faraday.orchestrator.runner import _wait_for_agent


class _FakeAgent:
    def __init__(self, wait_effect):
        self._wait_effect = wait_effect
        self.killed = False

    def wait(self, timeout):
        if isinstance(self._wait_effect, Exception):
            raise self._wait_effect
        return self._wait_effect

    def kill(self):
        self.killed = True


def test_normal_exit_reports_status_code() -> None:
    agent = _FakeAgent({"StatusCode": 0})
    timed_out, wait_error, rc = _wait_for_agent(agent, 30)
    assert (timed_out, wait_error, rc) == (False, None, 0)


def test_read_timeout_is_a_real_timeout_and_kills_the_container() -> None:
    agent = _FakeAgent(ReadTimeout("timed out"))
    timed_out, wait_error, rc = _wait_for_agent(agent, 30)
    assert timed_out is True
    assert wait_error is None
    assert agent.killed is True


def test_api_error_is_reported_as_an_error_not_a_timeout() -> None:
    agent = _FakeAgent(APIError("container removed"))
    timed_out, wait_error, rc = _wait_for_agent(agent, 30)
    assert timed_out is False
    assert wait_error is not None and "APIError" in wait_error
    assert agent.killed is False
