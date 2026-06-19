FROM registry.access.redhat.com/ubi9/ubi-minimal:latest

RUN microdnf install -y dnf && \
    printf '[centos-baseos]\nname=CentOS Stream 9\nbaseurl=http://mirror.stream.centos.org/9-stream/BaseOS/$basearch/os/\ngpgcheck=0\nenabled=1\n' > /etc/yum.repos.d/centos.repo && \
    dnf install -y https://dl.fedoraproject.org/pub/epel/epel-release-latest-9.noarch.rpm && \
    dnf install -y \
    git openssh-server tar gzip shadow-utils findutils passwd \
    nodejs npm vim bash wget htop tree jq net-tools iputils \
    gcc make automake gcc-c++ libstdc++-devel \
    && rm /etc/yum.repos.d/centos.repo \
    && dnf clean all && microdnf clean all

RUN curl -fsSL https://pixi.sh/install.sh | bash && \
    mv /root/.pixi/bin/pixi /usr/local/bin/

RUN npm install -g opencode-ai@${OPENCODE_VERSION:-1.4.0}

RUN useradd -u ${APP_UID:-1000} -m -s /bin/bash ${APP_USER:-app-user} && \
    passwd -d ${APP_USER:-app-user}

RUN mkdir -p /var/run/sshd && \
    chmod 0755 /var/run/sshd && \
    ssh-keygen -A && \
    sed -i 's/#Port 22/Port 2222/' /etc/ssh/sshd_config && \
    chown -R ${APP_USER:-app-user}:0 /etc/ssh /var/run/sshd && \
    chmod 0600 /etc/ssh/ssh_host*key && \
    chmod 0644 /etc/ssh/ssh_host*key.pub

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

USER ${APP_UID:-1000}
WORKDIR /home/${APP_USER:-app-user}
EXPOSE 2222

ENTRYPOINT ["/bin/bash", "/entrypoint.sh"]
