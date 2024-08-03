FROM --platform=linux/amd64 ubuntu:22.04
# FROM --platform=linux/arm64/v8 ubuntu:22.04

ARG UID
ARG GID
ARG USERNAME
ARG PASSWORD
ARG PROJECT_DIR="/opt/python/scraping_tp_ubuntu"

RUN groupadd -g $GID $USERNAME \
  && useradd -u $UID -g $GID -s /bin/bash -m $USERNAME \
  && usermod -a -G sudo $USERNAME \
  && echo $USERNAME:$PASSWORD | chpasswd
# RUN useradd --uid ${UID} --create-home --shell /bin/sh -G sudo,root ${USERNAME}
# RUN echo '%sudo ALL=(ALL) NOPASSWD:ALL' >> /etc/sudoers

RUN echo 'debconf debconf/frontend select Noninteractive' | debconf-set-selections

# RUN dpkg --add-architecture i386
RUN dpkg --add-architecture amd64
RUN apt-get update -y && \
    apt-get upgrade -y && \
    apt-get install -y --no-install-recommends \
    binutils:amd64 \
    sudo \
    dbus-user-session \
    git \
    language-pack-ja-base \
    language-pack-ja \
    ca-certificates \
    curl \
    vim \
    build-essential \
    xvfb

RUN locale-gen ja_JP.utf8

# RUN echo "deb [arch=amd64 signed-by=/usr/share/keyrings/googlechrom-keyring.gpg] http://dl.google.com/linux/chrome/deb/ stable main" | tee /etc/apt/sources.list.d/google-chrome.list
# RUN curl -fsSL https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /usr/share/keyrings/googlechrom-keyring.gpg
# RUN apt-get update -y &&  apt-get install -y google-chrome-stable

# RUN curl -fL -o /tmp/geckodriver.tar.gz \
#     https://github.com/mozilla/geckodriver/releases/download/v0.34.0/geckodriver-v0.34.0-linux-aarch64.tar.gz && \
#     tar -xzf /tmp/geckodriver.tar.gz -C /tmp/ && \
#     chmod +x /tmp/geckodriver && \
#     mv /tmp/geckodriver /usr/local/bin/

RUN mkdir -p $PROJECT_DIR
WORKDIR $PROJECT_DIR

ENV RYE_HOME="/opt/rye"
ENV PATH="$RYE_HOME/shims:$PATH"

SHELL [ "/bin/bash", "-o", "pipefail", "-c" ]
RUN curl -sSf https://rye.astral.sh/get | RYE_INSTALL_OPTION="--yes" bash && \
    rye config --set-bool behavior.global-python=true && \
    rye config --set-bool behavior.use-uv=true

RUN chown -R $USERNAME:$USERNAME $RYE_HOME
RUN chown -R $USERNAME:$USERNAME $PROJECT_DIR

USER $UID

RUN echo 'alias ll="ls -la"' >> ~/.bashrc
RUN echo "export LANG=ja_JP.UTF-8" >> ~/.bashrc
