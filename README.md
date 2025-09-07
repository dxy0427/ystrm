# ystrm

docker run -d \
  --name ystrm \
  --restart unless-stopped \
  -v /mnt/strm:/mnt/strm:rslave \
  -v /mnt/media:/mnt/media:rslave \
  -v /home/ystrm/config.yaml:/app/config.yaml \
  -v /home/ystrm/logs:/app/logs \
  -e TZ=Asia/Shanghai \
  ghcr.io/dxy0427/ystrm:latest