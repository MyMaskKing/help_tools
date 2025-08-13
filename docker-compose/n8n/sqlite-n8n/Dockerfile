FROM n8nio/n8n:1.106.3

ARG N8N_VERSION=1.106.3
ENV N8N_VERSION=${N8N_VERSION}
ENV N8N_DEFAULT_LOCALE=zh-CN

USER root

RUN npm install -g pnpm --unsafe-perm=true

WORKDIR /tmp

# 下载汉化包，直接覆盖到 n8n-editor-ui/dist
RUN git clone --depth 1 https://gitee.com/MyMaskKing/n8n-i18n-chinese.git n8n-zh && \
    cd n8n-zh && \
    git fetch --tags && \
    git checkout tags/n8n@${N8N_VERSION} && \
    cp -a editor-ui-dist/* /usr/local/lib/node_modules/n8n/node_modules/n8n-editor-ui/dist/ && \
    cd /tmp && rm -rf n8n-zh && npm cache clean --force

USER node
WORKDIR /home/node
