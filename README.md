# ⚡ Smart Energy Management Gateway

**Môn học:** Lập trình và ảo hóa cho IoT — IT6130  
**Đề tài 5:** Virtual Smart Energy Management Gateway  
**Công cụ:** Docker, Docker Compose, Mosquitto MQTT, Python, InfluxDB, Grafana, FastAPI

---

## 📋 Mô tả hệ thống

Hệ thống giám sát và điều khiển điện năng thông minh ảo hóa hoàn toàn bằng phần mềm. Gồm:

- **3 Smart Meter** giả lập (HVAC, Lighting, Plug) — publish telemetry qua MQTT mỗi 5 giây
- **3 Load Actuator** giả lập — nhận lệnh on/off, publish status về
- **1 Solar Simulator** — mô phỏng đường cong công suất mặt trời theo chu kỳ ngày/đêm
- **Energy Gateway** — validate, normalize, chạy rule engine, ghi InfluxDB, publish summary
- **REST API** — truy vấn trạng thái, điều khiển thủ công
- **Grafana Dashboard** — hiển thị realtime power, events, load status

---

## 🏗️ Kiến trúc luồng dữ liệu

```
[meter-hvac]    ─┐
[meter-lighting] ├──► energy/{load}/meter/telemetry ──► [energy-gateway]
[meter-plug]    ─┘                                           │
[solar-sim]     ──► energy/solar/telemetry ─────────────────┤
                                                             │
                     ┌───────────────────────────────────────┤
                     │  Validate → Normalize → Rule Engine   │
                     │  → InfluxDB write                     │
                     └───────────────────────────────────────┤
                                                             │
          energy/{load}/load/command ◄───────────────────────┤
          energy/gateway/summary ◄───────────────────────────┤
          energy/gateway/event ◄─────────────────────────────┘
                     │
          [load-hvac / load-lighting / load-plug]
                     │
          energy/{load}/load/status ────────────────────────► [energy-gateway]
                                                                     │
                                                              [InfluxDB] ← [Grafana]
                                                                     │
                                                              [energy-api] ◄── REST clients
```

---

## 📦 Danh sách service

| Service | Image/Build | Port | Mô tả |
|---------|-------------|------|--------|
| `mosquitto` | eclipse-mosquitto:2.0 | 1883 | MQTT broker (có auth) |
| `influxdb` | influxdb:2.7 | 8086 | Time-series database |
| `grafana` | grafana/grafana:11.3.0 | 3000 | Dashboard monitoring |
| `energy-gateway` | build | — | Gateway xử lý dữ liệu |
| `energy-api` | build | 8000 | REST API |
| `meter-hvac` | build | — | Smart meter HVAC |
| `meter-lighting` | build | — | Smart meter Lighting |
| `meter-plug` | build | — | Smart meter Plug |
| `load-hvac` | build | — | Actuator HVAC |
| `load-lighting` | build | — | Actuator Lighting |
| `load-plug` | build | — | Actuator Plug |
| `solar-simulator` | build | — | Solar power simulator |

---

## 🚀 Cách chạy hệ thống

### 1. Clone và cấu hình

```bash
git clone <repo-url>
cd smart-energy-gateway
cp .env.example .env
# Chỉnh sửa .env nếu cần (mật khẩu, thresholds...)
```

### 2. Khởi động toàn bộ stack

```bash
docker compose up -d --build
```

### 3. Kiểm tra trạng thái container

```bash
docker compose ps
```

Tất cả container phải ở trạng thái `running` (trừ `mosquitto-init` là `exited 0`).

---

## 🔍 Kiểm tra log

```bash
# Gateway (rule engine, events)
docker compose logs -f energy-gateway

# REST API
docker compose logs -f energy-api

# Smart meter HVAC
docker compose logs -f meter-hvac

# Solar simulator
docker compose logs -f solar-simulator

# Load actuator
docker compose logs -f load-hvac

# Tất cả
docker compose logs -f
```

---

## 🌐 Truy cập các service

| Service | URL | Thông tin đăng nhập |
|---------|-----|---------------------|
| **Grafana** | http://localhost:3000 | admin / grafana_pass_2026 |
| **InfluxDB** | http://localhost:8086 | admin / admin_pass_2026 |
| **REST API** | http://localhost:8000 | — |
| **API Docs** | http://localhost:8000/docs | Swagger UI |

---

## 📡 MQTT Topics

| Topic | Hướng | Mô tả |
|-------|-------|--------|
| `energy/{load}/meter/telemetry` | Meter → Gateway | Dữ liệu đo lường |
| `energy/solar/telemetry` | Solar → Gateway | Công suất solar |
| `energy/{load}/load/command` | Gateway → Actuator | Lệnh bật/tắt |
| `energy/{load}/load/status` | Actuator → Gateway | Trạng thái sau lệnh |
| `energy/gateway/summary` | Gateway → All | Tổng quan điện năng |
| `energy/gateway/event` | Gateway → All | Event bất thường |
| `energy/gateway/config` | API → Gateway | Cập nhật threshold |

---

## 🔌 REST API

### Kiểm tra sức khỏe
```bash
curl http://localhost:8000/health
```

### Danh sách tải điện
```bash
curl http://localhost:8000/loads
```

### Trạng thái tải cụ thể
```bash
curl http://localhost:8000/loads/hvac/state
curl http://localhost:8000/loads/lighting/state
curl http://localhost:8000/loads/plug/state
```

### Tổng quan điện năng
```bash
curl http://localhost:8000/energy/summary
```

### Xem tất cả events
```bash
curl http://localhost:8000/events
```

### Gửi lệnh điều khiển thủ công
```bash
# Tắt HVAC
curl -X POST http://localhost:8000/loads/hvac/command \
  -H "Content-Type: application/json" \
  -d '{"action": "off", "reason": "manual_control"}'

# Bật lại Plug
curl -X POST http://localhost:8000/loads/plug/command \
  -H "Content-Type: application/json" \
  -d '{"action": "on", "reason": "manual_control"}'
```

### Cập nhật ngưỡng overload (bonus)
```bash
curl -X PUT http://localhost:8000/config/threshold \
  -H "Content-Type: application/json" \
  -d '{"threshold_watt": 4000}'
```

---

## 🧪 Chạy unit test

```bash
pip install -r tests/requirements-test.txt
python -m pytest tests/ -v --tb=short
```

Với coverage:
```bash
python -m pytest tests/ -v --cov=energy_gateway --cov-report=term-missing
```

---

## 💉 Inject dữ liệu bất thường (kiểm thử)

```bash
# Từ máy host (cần paho-mqtt)
pip install paho-mqtt
python tests/inject_anomaly.py --scenario overload

# Hoặc tất cả scenarios
python tests/inject_anomaly.py --scenario all

# Từ trong container gateway
docker compose exec energy-gateway python /dev/stdin < tests/inject_anomaly.py
```

---

## 📊 InfluxDB — Kiểm tra dữ liệu

Truy cập http://localhost:8086, đăng nhập `admin / admin_pass_2026`.

**Measurements:**
- `meter_telemetry` — power, current, voltage theo load_id
- `solar_telemetry` — công suất solar + irradiance
- `energy_summary` — total/solar/grid power, overload flag
- `gateway_events` — events với severity, event_type
- `load_status` — trạng thái switch từng tải

**Flux query ví dụ (Data Explorer):**
```flux
from(bucket: "energy_data")
  |> range(start: -30m)
  |> filter(fn: (r) => r._measurement == "energy_summary")
  |> filter(fn: (r) => r._field == "total_power_watt")
```

---

## 🔧 Rule Engine — Luật xử lý

| # | Điều kiện | Hành động |
|---|-----------|-----------|
| 1 | `total_power > 3500W` | Sinh event `overload_detected` |
| 2 | Overload detected | Tắt tải priority thấp trước (plug, hvac trước lighting) |
| 3 | `solar_power > 500W` & có tải bị tắt do overload | Khôi phục tải (restore) |
| 4 | `solar_power > 500W` & projected < 85% threshold | Bật lại tải đã shed |
| 5 | Meter không gửi data `> 30s` | Sinh event `meter_offline` |

---

## ❗ Lỗi thường gặp

| Lỗi | Nguyên nhân | Giải pháp |
|-----|-------------|-----------|
| Container `mosquitto` ở trạng thái `restarting` | `mosquitto-init` chưa chạy xong | Chờ 30s hoặc `docker compose restart mosquitto` |
| `energy-gateway` không connect MQTT | MQTT chưa sẵn sàng | Gateway có retry tự động, chờ thêm 30s |
| InfluxDB không có data | Token sai | Kiểm tra `.env` — `INFLUXDB_TOKEN` phải khớp `INFLUXDB_ADMIN_TOKEN` |
| Grafana dashboard trắng | InfluxDB chưa có data | Chờ 1-2 phút sau khi stack khởi động |
| API trả về `503 MQTT unreachable` | MQTT broker down | `docker compose restart mosquitto` |

---

## 🛑 Dừng hệ thống

```bash
# Dừng nhưng giữ data volumes
docker compose down

# Dừng và xóa toàn bộ data
docker compose down -v
```

---

## 📁 Cấu trúc thư mục

```
smart-energy-gateway/
├── docker-compose.yml
├── .env                        ← cấu hình (copy từ .env.example)
├── .env.example
├── README.md
├── mosquitto/
│   └── config/
│       └── mosquitto.conf      ← MQTT auth config
├── smart_meter/
│   ├── meter.py                ← smart meter simulator
│   ├── requirements.txt
│   └── Dockerfile
├── load_actuator/
│   ├── actuator.py             ← load actuator simulator
│   ├── requirements.txt
│   └── Dockerfile
├── solar_simulator/
│   ├── solar.py                ← solar PV simulator
│   ├── requirements.txt
│   └── Dockerfile
├── energy_gateway/
│   ├── gateway.py              ← main gateway logic
│   ├── rule_engine.py          ← rule engine (5+ rules)
│   ├── state_store.py          ← thread-safe state + persistence
│   ├── requirements.txt
│   └── Dockerfile
├── energy_api/
│   ├── api.py                  ← FastAPI REST API
│   ├── requirements.txt
│   └── Dockerfile
├── grafana/
│   └── provisioning/
│       ├── datasources/influxdb.yml
│       └── dashboards/
│           ├── dashboard.yml
│           └── energy_dashboard.json
└── tests/
    ├── test_rule_engine.py     ← unit tests rule engine
    ├── test_state_store.py     ← unit tests state store
    ├── inject_anomaly.py       ← script inject dữ liệu bất thường
    └── requirements-test.txt
```

---

## 👥 Phân công công việc

| Thành viên | Nhiệm vụ |
|------------|----------|
| Thành viên 1 | Smart meter simulator, Load actuator, Solar simulator, thiết kế MQTT topics & message format |
| Thành viên 2 | Energy Gateway, Rule Engine, InfluxDB integration, State Store |
| Thành viên 3 | REST API (FastAPI), Docker Compose, Grafana dashboard, README, unit tests, tích hợp toàn bộ |

---

## ✅ Checklist trước khi nộp

- [ ] `docker compose up -d --build` không báo lỗi
- [ ] `docker compose ps` — tất cả container `running`
- [ ] `docker compose logs -f energy-gateway` — thấy rule evaluation mỗi 5s
- [ ] Grafana http://localhost:3000 — dashboard hiển thị data
- [ ] InfluxDB http://localhost:8086 — có data trong `energy_data` bucket
- [ ] `curl http://localhost:8000/loads` — trả về 3 loads
- [ ] `curl -X POST http://localhost:8000/loads/plug/command -H "Content-Type: application/json" -d '{"action":"off","reason":"test"}'` — thành công
- [ ] `python tests/inject_anomaly.py --scenario overload` — trigger overload events
- [ ] `python -m pytest tests/ -v` — tất cả test pass
# smart-energy-gateway
