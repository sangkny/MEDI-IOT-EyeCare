#!/usr/bin/env python3
"""
파일명: iot_simulator.py
목적: iot_simulator.py 실행 스크립트
히스토리:
  2026-06-11 - 현재 상태 문서화 + 히스토리 추가

IoT 측정 시뮬레이터 (D R4-IoT W1) — REST API 로 전송.
"""
from __future__ import annotations

import argparse
import random
import sys
import time

try:
    import httpx
except ImportError:
    print("pip install httpx", file=sys.stderr)
    sys.exit(2)


def main() -> int:
    p = argparse.ArgumentParser(description="Simulate IoT measurements")
    p.add_argument("--base", default="http://localhost:8001")
    p.add_argument("--patient-id", default="P-IOT-SIM")
    p.add_argument("--interval", type=float, default=2.0)
    p.add_argument("--count", type=int, default=5)
    args = p.parse_args()

    base = args.base.rstrip("/")
    with httpx.Client(timeout=30.0) as client:
        r = client.post(
            f"{base}/api/v1/iot/devices/register",
            json={
                "patient_id": args.patient_id,
                "device_type": "tonometer",
                "label": "sim-tonometer",
            },
        )
        r.raise_for_status()
        device_id = r.json()["device_id"]
        print(f"registered device {device_id}")

        for i in range(args.count):
            iop = round(random.uniform(14.0, 26.0), 1)
            payload = {"iop_mmhg": iop}
            if iop > 21:
                payload["high_iop_alert"] = True
            m = client.post(
                f"{base}/api/v1/iot/measurements",
                json={
                    "patient_id": args.patient_id,
                    "device_id": device_id,
                    "device_type": "tonometer",
                    "payload": payload,
                },
            )
            m.raise_for_status()
            body = m.json()
            print(
                f"[{i+1}] iop={iop} alerts={body.get('alerts')} "
                f"ontology={body.get('ontology_passed')}"
            )
            time.sleep(args.interval)
    return 0


if __name__ == "__main__":
    sys.exit(main())
