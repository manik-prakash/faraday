FROM python:3.12-slim
WORKDIR /agent
COPY solve.py .
# The platform runs your agent as a non-root user with a read-only root
# filesystem. Write only under /task (and /tmp). Keep your deps light.
ENTRYPOINT ["python", "/agent/solve.py"]
