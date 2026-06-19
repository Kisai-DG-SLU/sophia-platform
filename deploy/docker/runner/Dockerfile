FROM ${BASE_IMAGE:-registry.access.redhat.com/ubi9/ubi-minimal:latest}

USER root

RUN curl -L ${ACT_RUNNER_URL:-https://gitea.com/gitea/act_runner/releases/download/v0.2.10/act_runner-0.2.10-linux-amd64} -o /usr/local/bin/act_runner && \
    chmod +x /usr/local/bin/act_runner

RUN mkdir -p /data-runner && chown -R ${APP_UID:-1000}:0 /data-runner && chmod -R g+rwX /data-runner

WORKDIR /data-runner
ENTRYPOINT ["/usr/local/bin/act_runner", "daemon"]
