#!/usr/bin/env bash
# Build TensorRT engines from the project's ONNX model with trtexec (ships with TensorRT / JetPack).
# This is a fallback / cross-check. The graded artefact is the engine + speed report that PipeGen itself produces.
# Usage: ./build_trt_engine.sh [model.onnx] [calibration_cache]   (run on the NVIDIA GPU / Jetson)
set -euo pipefail
ONNX="${1:-../backend/models/yolox_nano.onnx}"
CALIB="${2:-}"
OUT="engines"; mkdir -p "$OUT"
command -v trtexec >/dev/null || { echo "trtexec not found - install TensorRT/JetPack (not available on CPU-only machines)"; exit 2; }
echo "== FP16 =="; trtexec --onnx="$ONNX" --fp16 --saveEngine="$OUT/yolox_nano_fp16.engine" --warmUp=500 --iterations=200 2>&1 | tee "$OUT/fp16_report.txt" | grep -E "mean|GPU Compute|Throughput|qps" || true
if [ -n "$CALIB" ]; then
  echo "== INT8 (calib: $CALIB) =="; trtexec --onnx="$ONNX" --int8 --calib="$CALIB" --fp16 --saveEngine="$OUT/yolox_nano_int8.engine" --warmUp=500 --iterations=200 2>&1 | tee "$OUT/int8_report.txt" | grep -E "mean|GPU Compute|Throughput|qps" || true
else
  echo "INT8 skipped: pass a calibration cache (PipeGen can generate one)."
fi
echo "Reports in $OUT/. Compare accuracy yourself - trtexec measures speed only."
