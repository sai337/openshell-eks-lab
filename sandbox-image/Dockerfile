# The agent workload image used by the security suite. Small on purpose:
# python3 and curl so the suite can act like a real (hostile) agent.
# Pin the base by digest in your registry before production use.
FROM python:3.13-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --gid 1500 agent \
    && useradd --uid 1500 --gid agent --create-home agent \
    && install -d -o agent -g agent /sandbox

WORKDIR /sandbox
USER agent
CMD ["sleep", "infinity"]
