# Evidence you must produce yourself at the venue (nothing here is pre-filled or faked)

Track A (PipeGen) — submit form: https://forms.gle/eJyeCKCG2UH757QZ8
- [ ] `pipegen --version` prints `0.5.1`
- [ ] All five stages completed in PipeGen: Requirement → Pipeline IR → Model → Compiler → Run
- [ ] Screenshot of the Pipeline IR node graph
- [ ] ≥1 model compiled to a TensorRT engine; screenshot/export of PipeGen's speed report
- [ ] Live run recorded (video file, USB cam, CSI or RTSP) on an NVIDIA GPU or Jetson (JetPack 6)
- [ ] Actionable output shown: MQTT/JSON feed (`python pipegen/mqtt_listener.py`) or RTSP/alerts
- [ ] PipeGen export folder committed to the repository
- [ ] Bonus (optional): INT8 engine + speed/power/accuracy trade-off from PipeGen reports
- [ ] Bonus (optional): Closed loop — firmware/PRD_SAFESIGHT_ALARM.md built in FirmGen, flashed to ESP32

Deadline 4:00 pm; labs 10am–12pm. Keep videos under `/home`.
Deep-integration warning from the brief: the SafeSight CPU code is **not** PipeGen. Judges score PipeGen as load-bearing,
so the PipeGen pipeline must be the thing that runs live; the FastAPI dashboard/incident DB is the consumer of its output.
