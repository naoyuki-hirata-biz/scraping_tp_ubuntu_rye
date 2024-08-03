FROM --platform=linux/amd64 ubuntu:22.04

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

RUN dpkg --add-architecture i386
RUN apt-get update -y && \
    apt-get upgrade -y && \
    apt-get install -y --no-install-recommends \
    sudo \
    git \
    language-pack-ja-base \
    language-pack-ja \
    ca-certificates \
    curl \
    vim \
    build-essential \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libglib2.0-0 \
    libnss3 \
    libxcb1 \
    libxcomposite-dev \
    libxdamage1 \
    libxrandr2 \
    libgbm-dev \
    libxkbcommon-x11-0 \
    libpangocairo-1.0-0 \
    libgtk-3-0 \
    libasound2 \
    dbus-x11 \
    xvfb
    # chromium-browser \
    # firefox \


RUN update-locale LANG=ja_JP.UTF-8 LANGUAGE=ja=JP.UTF-8

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
