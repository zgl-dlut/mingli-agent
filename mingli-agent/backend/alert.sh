#!/bin/bash

ALERT_THRESHOLD_CPU=80
ALERT_THRESHOLD_MEM=85
ALERT_THRESHOLD_DISK=90

echo "=== 系统告警检查 ==="
echo "时间: $(date)"

CPU_USAGE=$(top -bn1 | grep "Cpu(s)" | sed "s/.*, *\([0-9.]*\)%* id.*/\1/" | awk '{print 100 - $1}')
MEM_USAGE=$(free | grep Mem | awk '{print $3/$2 * 100.0}')
DISK_USAGE=$(df -h / | grep / | awk '{print $5}' | sed 's/%//g')

echo "CPU使用率: ${CPU_USAGE}%"
echo "内存使用率: ${MEM_USAGE}%"
echo "磁盘使用率: ${DISK_USAGE}%"

if (( $(echo "$CPU_USAGE > $ALERT_THRESHOLD_CPU" | bc -l) )); then
    echo "⚠️ 告警: CPU使用率超过${ALERT_THRESHOLD_CPU}%"
    echo "CPU告警: ${CPU_USAGE}% at $(date)" >> /var/log/mingli-alerts.log
fi

if (( $(echo "$MEM_USAGE > $ALERT_THRESHOLD_MEM" | bc -l) )); then
    echo "⚠️ 告警: 内存使用率超过${ALERT_THRESHOLD_MEM}%"
    echo "内存告警: ${MEM_USAGE}% at $(date)" >> /var/log/mingli-alerts.log
fi

if (( $(echo "$DISK_USAGE > $ALERT_THRESHOLD_DISK" | bc -l) )); then
    echo "⚠️ 告警: 磁盘使用率超过${ALERT_THRESHOLD_DISK}%"
    echo "磁盘告警: ${DISK_USAGE}% at $(date)" >> /var/log/mingli-alerts.log
fi

echo "=== 检查完成 ==="