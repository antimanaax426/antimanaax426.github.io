# Raspberry Pi Wi-Fi 省电导致局域网 / SSH 突然失联

> 故障现象、排查过程、根因确认与永久修复记录。  
> 本版本已隐藏具体 IP、BSSID、MAC 等网络标识，适合对外分享。

## 结论

**Raspberry Pi 的 `wlan0` 开启 Wi-Fi power save 后，局域网内 ARP / ICMP / SSH 通信出现异常；临时关闭 power save 后立即恢复。最终通过 NetworkManager 配置将 Wi-Fi 省电永久关闭。**

---

## 1. 环境与故障现象

场景：Windows 开发机与 Raspberry Pi 连接到同一 Wi-Fi 网络，并通过 VS Code Remote-SSH / SSH 管理 Raspberry Pi。

| 设备 | 网络信息 | 状态 |
|---|---|---|
| Windows PC | `PC_IP/24` | 本机路由存在，网卡正常 |
| Raspberry Pi `wlan0` | `PI_IP/24` | `UP`；与 Windows 连接到同一 AP |
| Raspberry Pi `eth0` | 另有有线网段地址 | 与本故障无直接关系 |

故障表现：

- 数分钟前连接仍正常，随后突然无法通过 VS Code / SSH 连接 Raspberry Pi。
- Windows → Pi：`ping` 返回 **Destination Host Unreachable**。
- Pi → Windows：同样返回 **Destination Host Unreachable**。
- 重启 Raspberry Pi、重启路由器、断开并重连 Wi-Fi 后仍未恢复。

---

## 2. 排查过程

### 2.1 先排除 Python / VS Code 层问题

由于双方连 `ping` 都失败，问题发生在 SSH 和 VS Code Remote-SSH 之前，因此不应继续优先检查 Python 环境、SSH key 或 VS Code 配置。

### 2.2 验证 Windows 路由

执行：

```powershell
route print -4
```

确认 Windows 已存在目标 WLAN 网段的 on-link 路由，说明基本 IPv4 路由配置正确。

### 2.3 验证 Raspberry Pi 接口、地址与回程路由

执行：

```bash
ip -br link
ip -br addr
ip route get PC_IP
ping -c 4 PC_IP
```

结果确认：

- `PI_IP` 位于 `wlan0`。
- `wlan0` 状态为 `UP`。
- Pi 到 Windows 的回程路由明确使用 `wlan0`。
- 但 Pi 仍无法 `ping` Windows。

因此问题仍位于 Wi-Fi / 二层通信附近。

### 2.4 排除“连接到了不同 AP”

分别检查 Windows 和 Raspberry Pi 当前连接的 BSSID，确认两台设备实际连接到同一个 AP。

因此可以排除“设备漫游到了不同 AP，导致客户端之间无法直接通信”这一类问题。

### 2.5 ARP 与抓包出现关键线索

Windows 侧查看 ARP：

```powershell
arp -a
```

Raspberry Pi 侧抓取 ARP / ICMP：

```bash
sudo tcpdump -ni wlan0 arp or icmp
```

后续 Windows 能够学习到 Pi 的 `wlan0` MAC 地址。

更关键的是：

> **在 Raspberry Pi 上运行 `tcpdump` 时，Windows 的 `ping` 又能恢复。**

这说明网络并非永久被 AP 隔离，更像是 Pi WLAN 接口的节能 / 接收状态异常。

---

## 3. 根因确认：Wi-Fi Power Save

检查当前状态：

```bash
iw dev wlan0 get power_save
```

临时关闭：

```bash
sudo iw dev wlan0 set power_save off
```

再次确认：

```bash
iw dev wlan0 get power_save
```

A/B 验证结果：

- Power save 开启时：局域网通信异常。
- Power save 关闭后：即使不运行 `tcpdump`，Windows ↔ Pi 的 `ping` 和 SSH 均恢复。

因此本次故障可确认与 Raspberry Pi 的 Wi-Fi 省电模式有关。

> **注意**  
> 本案例确认的是：在该 Raspberry Pi / 驱动 / WLAN 环境中，`power save` 与通信异常具有直接因果关系。  
> 不应仅凭一次 `ping` 失败就普遍断言所有 Raspberry Pi 的 Wi-Fi 省电都会导致相同故障。

---

## 4. 修复方法

### 4.1 临时关闭省电

用于快速验证：

```bash
sudo iw dev wlan0 set power_save off
```

该设置通常不会跨重启长期保持，因此适合故障确认，不适合作为最终配置。

### 4.2 通过 NetworkManager 永久关闭

创建配置文件：

```bash
sudo nano /etc/NetworkManager/conf.d/wifi-powersave-off.conf
```

写入：

```ini
[connection]
wifi.powersave = 2
```

随后重启 NetworkManager：

```bash
sudo systemctl restart NetworkManager
```

或者直接重启 Raspberry Pi：

```bash
sudo reboot
```

### 4.3 重启后的确认

执行：

```bash
iw dev wlan0 get power_save
```

预期输出：

```text
Power save: off
```

---

## 5. 修复验证

### Windows 连续 ping

```powershell
ping PI_IP -t
```

确认不再出现周期性的 `Destination Host Unreachable`。

### SSH

```powershell
ssh <user>@PI_IP
```

确认可以正常建立连接。

### VS Code Remote-SSH

重新使用 VS Code Remote-SSH，确认：

- 可以正常连接。
- 长时间空闲后仍可连接。
- Raspberry Pi 重启后仍然正常。

最后再次执行：

```bash
iw dev wlan0 get power_save
```

确认仍为：

```text
Power save: off
```

---

## 6. 可复用的诊断顺序

| 顺序 | 检查项 | 目的 |
|---|---|---|
| ① | IP / Interface | 确认双方 IP、掩码、接口 `UP / LOWER_UP` |
| ② | Route | 确认访问目标时实际走预期网卡 |
| ③ | Bidirectional ping | 双方互 ping，区分单向 / 双向问题 |
| ④ | ARP / Neighbor | 看能否解析对方 MAC；ARP 失败通常说明问题早于 SSH |
| ⑤ | AP / BSSID | 确认是否同 AP、是否存在 client isolation / roaming |
| ⑥ | `tcpdump` | 观察 ARP / ICMP 是否真正抵达接口 |
| ⑦ | Power save | 如果抓包时通信恢复，重点验证 WLAN 省电与驱动状态 |
| ⑧ | SSH / VS Code | 只有网络层恢复后才继续排查 22 端口和 Remote-SSH |

---

## 7. 经验总结

- “几分钟前还能用”并不意味着 SSH 或 VS Code 本身发生了变化；网络节能策略也可能在运行一段时间后才暴露。
- 双方同网段、同 BSSID 仍不代表终端通信一定正常，必须结合 ARP、抓包和双向测试判断。
- `tcpdump` 开启后通信恢复是很强的诊断信号，但 `tcpdump` 本身不是修复方案。
- 对于需要长期在线、远程维护或现场监控的 Raspberry Pi，建议显式关闭 Wi-Fi power save，并在重启后验证。
- 生产 / PoC 网络应尽量使用稳定的有线链路或受控 WLAN，不应把关键服务可靠性建立在默认省电策略上。

---

**记录日期：2026-10-05**
