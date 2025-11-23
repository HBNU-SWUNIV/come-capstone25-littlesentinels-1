# tof_sensor.py  (Py3.6/3.7/3.8 호환)
import sys
import os
import time
from statistics import median
from typing import Optional

sys.path.append('/home/dfx')
from opencr.opencr_firmware.libraries.peripheral._opencr import OpenCRSerial


class ToF_Sensor:
    def __init__(self,
                 port: Optional[str] = None,
                 baudrate: int = 115200,
                 timeout: float = 1.0,
                 devaddr: int = 0xF0,
                 shared_opencr: Optional[OpenCRSerial] = None,
                 warmup_samples: int = 3):
        self._owns_opencr = False
        self.opencr = None  

        if shared_opencr is not None:
            self.opencr = shared_opencr
            self._owns_opencr = False
            print("[ToF] Using shared OpenCRSerial instance")
        else:
            if port is not None:
                try:
                    # (port, baudrate, timeout, devaddr) 포지셔널 사용
                    self.opencr = OpenCRSerial(port, baudrate, timeout, devaddr)
                    self._owns_opencr = True
                    print("[ToF] Connected to {}".format(port))
                except Exception as e:
                    raise RuntimeError("[ToF] Failed to open {}: {}".format(port, e))
            else:
                for p in ['/dev/ttyACM0', '/dev/ttyACM1']:
                    try:
                        self.opencr = OpenCRSerial(p, baudrate, timeout, devaddr)
                        self._owns_opencr = True
                        print("[ToF] Connected to {}".format(p))
                        break
                    except Exception:
                        continue
                if self.opencr is None:
                    raise RuntimeError("[ToF] 보드 연결 실패 (no /dev/ttyACM*)")

        for _ in range(max(0, warmup_samples)):
            try:
                _ = self.read_distance()
            except Exception:
                pass
            time.sleep(0.02)

    def read_distance(self) -> Optional[int]:
        if not self.opencr:
            return None
        try:
            d = self.opencr.get_tof_distance()
            if d is None:
                return None
            return int(d)
        except Exception:
            return None

    def read_avg_mm(self, samples: int = 5, timeout_s: float = 2.0) -> Optional[int]:
        vals = []
        t0 = time.time()
        while len(vals) < max(1, samples) and (time.time() - t0) < max(0.1, timeout_s):
            d = self.read_distance()
            if d is not None and d > 0:
                vals.append(d)
            else:
                time.sleep(0.03)
        if not vals:
            return None
        return int(sum(vals) / len(vals))

    def read_med_mm(self, samples: int = 5, timeout_s: float = 2.0) -> Optional[int]:
        """여러 번 읽어 중값(mm). 실패 시 None."""
        vals = []
        t0 = time.time()
        while len(vals) < max(1, samples) and (time.time() - t0) < max(0.1, timeout_s):
            d = self.read_distance()
            if d is not None and d > 0:
                vals.append(d)
            else:
                time.sleep(0.03)
        if not vals:
            return None
        return int(median(vals))

    def close(self):
        if self.opencr and self._owns_opencr:
            try:
                if hasattr(self.opencr, "close"):
                    self.opencr.close()
                print("[ToF] Closed")
            except Exception:
                pass
            finally:
                self.opencr = None

    def test_connection(self, n: int = 20, sleep_s: float = 0.2):
        print("\n[ToF] Testing ToF sensor ...")
        for i in range(n):
            d = self.read_distance()
            if d is not None:
                print("#{:<02d}: {} mm".format(i+1, d))
            else:
                print("#{:<02d}: No data".format(i+1))
            time.sleep(max(0.02, sleep_s))

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass


if __name__ == "__main__":
    tof = ToF_Sensor()
    tof.test_connection()
    tof.close()
