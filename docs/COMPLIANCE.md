# Hackathon requirement status

This checklist compares the supplied SafeSight project files with the official Embedded SF: CraftifAI Physical AI Hackathon brief. It describes the files in this package; it does not claim that hardware runs or external CraftifAI workflows have been completed.

## Track A — PipeGen (mandatory)

| Official requirement | Status in this package | What is still needed |
|---|---|---|
| Complete PipeGen Requirement → Pipeline IR → Model → Compiler → Run flow | Not complete. `pipegen/REQUIREMENT.md` is a draft to enter into PipeGen. No PipeGen export or completed pipeline is included. | Complete all five stages in PipeGen v0.5.1; commit the export. |
| At least one TensorRT engine and PipeGen speed report | Missing. The bundled YOLOX model is ONNX; the local prototype uses ONNX Runtime on CPU. | Compile and run the model with TensorRT through PipeGen on supported NVIDIA hardware; save the PipeGen report. |
| Live run on a supported NVIDIA GPU or Jetson | Missing/unverified. The included prototype analyzes uploaded video on CPU. | Demonstrate the PipeGen pipeline live on an NVIDIA GPU system or Jetson. |
| Actionable output | Partial prototype support: violation events can be written as JSON Lines and optionally published by MQTT. This is not output from a completed PipeGen live run. | Show the PipeGen pipeline producing an actionable JSON/MQTT/RTSP/alert output during the live run. |

## Track B — FirmGen (mandatory alternative)

| Official requirement | Status in this package | What is still needed |
|---|---|---|
| Reviewed and frozen PRD-driven build in FirmGen | A firmware PRD draft is included, but no FirmGen review/freeze evidence is included. | Complete the PRD-driven FirmGen workflow and freeze the requirements. |
| Firmware flashed to a physical ESP32 or STM32 | Missing. No firmware project or board run is included. | Build and flash the firmware to a physical supported board. |
| Acceptance evidence from the board | Missing. | Capture UART/Monitor output and demonstrate the physical behavior. |
| FirmGen traceability report | Missing. | Export the FirmGen report linking requirements, implementation, and tests. |

## Optional bonuses

The closed-loop bonus is not complete: no live PipeGen event is shown driving an actuator on a physical board. INT8/Jetson optimization and FirmGen Live Intelligence evidence are also not included.

## What is runnable here

The Ubuntu scripts start a local web dashboard and FastAPI backend. The app analyzes uploaded video with a CPU ONNX/OpenCV prototype and supports incident review and event export. This is useful for software development and demo preparation; it does not meet the mandatory hardware/tool workflow of Track A or Track B by itself.

For Track A evidence, use `pipegen/EVIDENCE_CHECKLIST.md`. Capture real screenshots, reports, and live-run evidence from the actual PipeGen/GPU or Jetson system; the checklist and draft requirement are preparation material only.