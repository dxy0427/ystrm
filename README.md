Docker 部署
  docker run -d \
  --name ystrm \
  --restart unless-stopped \
  -v /mnt/media:/mnt/media:rslave \
  -v /mnt/strm:/mnt/strm:rslave \
  -v /home/docker/ystrm/config.yaml:/app/config.yaml \
  -v /home/docker/ystrm/logs:/app/logs \
  -e TZ=Asia/Shanghai \
  ghcr.io/dxy0427/ystrm:latest