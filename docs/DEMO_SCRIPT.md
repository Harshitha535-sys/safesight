# One-minute demonstration script

Only say what is true on your machine. Before recording, perform the dry run in the second section and
keep your own recording/screenshot as evidence. Nothing here is pre-recorded for you.

## Script (~60 s)
| Time | Do | Say |
|---|---|---|
| 0–10 s | Show Overview with the header "Backend connected · Model: ready" | "SafeSight flags people entering a restricted zone in video, running on an ordinary laptop CPU." |
| 10–20 s | Settings: show zone, cooldown, fps | "Zone and alert cooldown are configurable; the zone is a fraction of the frame." |
| 20–40 s | Live Monitoring → choose your prepared clip → Start analysis → press Play when done | "Green boxes are detected people with track IDs and confidence. When a person's box enters the red zone it turns red and an alert fires." |
| 40–50 s | Active alerts panel → click a timestamp → open Snapshot | "Each violation has a timestamp and a snapshot; I can acknowledge it." |
| 50–60 s | Incidents page → Export CSV | "Incidents are exportable. This is a video-file prototype; it is not a PipeGen pipeline and has not been run on NVIDIA/TensorRT or a microcontroller yet." |

## Dry-run checklist
1. Backend + frontend running; header shows connected; model ready.
2. A 10–20 s clip: one person walking from outside the zone into it (default zone x 0.45–0.80, y 0.25–0.55).
3. Confirm boxes align (frame size known), at least one alert appears, snapshot opens.
4. Record your screen yourself.

## Demonstrating person detection and zone violations
1. **Detection:** play the processed video; each person gets a box labelled `#track  confidence%`.
   The Settings confidence slider only hides low-confidence boxes in the viewer; it does not change alerts.
2. **Violation:** a box inside the red `RESTRICTED ZONE` turns red (`in_zone`) and an alert appears in
   *Active safety alerts* at its video time. With cooldown 10 s, a person staying in the zone does not re-alert
   each frame; leaving and re-entering after the cooldown alerts again.
3. **Controls to show:** move the zone in Settings, re-run, observe different alerts. Set the zone so a stationary
   person is clearly outside → no alert (a useful negative test).
4. **Fallback with no usable video/model:** `curl -X POST http://localhost:8000/api/demo/events` loads 8 events
   marked `simulated`. These are **not detections** and the dashboard does not display them; show them via
   `/api/incidents?include=demo`, and say "simulated". Never present them as AI output.
