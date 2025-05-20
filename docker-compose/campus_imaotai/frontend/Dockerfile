FROM node:18 AS build
WORKDIR /app

# 设置 NODE_OPTIONS 环境变量以解决 OpenSSL 问题
ENV NODE_OPTIONS=--openssl-legacy-provider

# 创建 .npmrc 文件配置镜像源
RUN echo "registry=https://registry.npmmirror.com" > ~/.npmrc

# 克隆代码（使用 gitee 镜像）
RUN git clone --depth=1 --single-branch -b master https://gitee.com/ityxx/campus-imaotai.git .

# 进入前端目录并安装依赖
WORKDIR /app/vue_campus_admin

# 只安装生产环境依赖并构建
RUN npm install --production=false && \
    npm run build:prod && \
    npm cache clean --force

# 确保输出目录存在并复制构建产物
RUN mkdir -p /output && \
    cp -r dist/* /output/ 