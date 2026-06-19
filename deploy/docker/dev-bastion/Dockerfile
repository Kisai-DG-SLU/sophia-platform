FROM alpine:latest
RUN apk add --no-cache openssh bash && \
    adduser -D -s /bin/bash ${APP_USER:-app-user} && \
    passwd -d ${APP_USER:-app-user} && \
    ssh-keygen -A && \
    mkdir -p /var/run/sshd

RUN echo "Port 2222" > /etc/ssh/sshd_config && \
    echo "PasswordAuthentication no" >> /etc/ssh/sshd_config && \
    echo "AllowTcpForwarding yes" >> /etc/ssh/sshd_config && \
    echo "GatewayPorts yes" >> /etc/ssh/sshd_config && \
    echo "PidFile /tmp/sshd.pid" >> /etc/ssh/sshd_config

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
EXPOSE 2222
CMD ["/entrypoint.sh"]
