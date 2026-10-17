# PRD draft — SafeSight Zone Alarm (ESP32) — for FirmGen (NOT yet reviewed, frozen, built or flashed)

Purpose: physical alarm driven by the SafeSight vision pipeline (Closed-Loop bonus).
Review and freeze this in FirmGen yourself; the brief requires a *reviewed and frozen* requirement set.

| ID | Requirement | Acceptance (UART/Monitor + physical) |
|---|---|---|
| R1 | On boot, print `SAFESIGHT_ALARM v1 READY` on UART at 115200 baud. | Line visible in Monitor |
| R2 | Receive alert as `A\n` over UART (bridge) — optional Wi-Fi/MQTT subscribe to `safesight/zone-1/events`. | `RX alert` logged within 100 ms |
| R3 | On alert, turn the red LED (GPIO 2) on and pulse the buzzer (GPIO 4) 3× 200 ms. | LED lit, buzzer audible |
| R4 | LED stays on 5 s after the last alert, then turns off. | LED off after 5 s ± 0.5 s |
| R5 | Print `ALARM ON` / `ALARM OFF` on state changes. | Log lines match physical state |
| R6 | A heartbeat line `HB <uptime_s>` every 10 s. | Seen in Monitor |
