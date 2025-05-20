FROM maven:3.9.6-eclipse-temurin-17 AS build
WORKDIR /app

# 添加阿里云Maven镜像配置
RUN mkdir -p /root/.m2 && \
    echo '<settings>\n  <mirrors>\n    <mirror>\n      <id>aliyunmaven</id>\n      <mirrorOf>*</mirrorOf>\n      <name>阿里云公共仓库</name>\n      <url>https://maven.aliyun.com/repository/public</url>\n    </mirror>\n  </mirrors>\n</settings>' > /root/.m2/settings.xml

# 克隆代码（使用 gitee 镜像）
RUN git clone --depth=1 --single-branch -b master https://gitee.com/ityxx/campus-imaotai.git .

# 在源码根目录一次性构建所有模块，确保依赖 install
RUN mvn clean install -DskipTests

WORKDIR /app/campus-modular
RUN mvn package -DskipTests

# 确保输出目录存在，并添加调试信息
RUN mkdir -p /output && \
    echo "=== Listing target directory ===" && \
    ls -l target/ && \
    echo "=== Copying jar files ===" && \
    cp target/campus-modular*.jar /output/ && \
    echo "=== Listing output directory ===" && \
    ls -l /output/ 