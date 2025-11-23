import sys, os, time, termios, tty, select

sys.path.append('/home/dfx')
from opencr.opencr_firmware.libraries.peripheral._opencr import OpenCRSerial


class MotorControl:
    def __init__(self):
        self.possible_device_ports = ['/dev/ttyACM0', '/dev/ttyACM1']
        self.connected_device_port = None
        self.baud_rate = 57600
        self.serial_timeout = 1.0
        self.device_address = 0xF0
        self.opencr_serial = None

        # 모터 ID 설정
        self.CENTER_MOTOR_ID = 16

        # 현재 모터 위치 (도 단위)
        self.center_position = 0

        # 연결 초기화
        self.connect()

        # 현재 모터 위치 읽어서 초기화
        self.initialize_current_position()

    def connect(self):
        """OpenCR 장치에 연결"""
        for device_port in self.possible_device_ports:
            try:
                self.opencr_serial = OpenCRSerial(device_port, self.baud_rate, self.serial_timeout, self.device_address)
                self.connected_device_port = device_port
                print(f"Connected to {device_port}")

                # 모터 초기화
                self.opencr_serial.dxl_init(self.CENTER_MOTOR_ID, 200, 0)

                # 토크 켜기
                self.opencr_serial.dxl_torqueOn(self.CENTER_MOTOR_ID)
                print("Center motor initialized and torque enabled")
                return True

            except Exception as connection_error:
                print(f"Failed to connect to {device_port}: {connection_error}")
                continue

        raise RuntimeError("No available /dev/ttyACM* device found.")

    def initialize_current_position(self):
        """현재 센터 모터 위치를 읽어서 초기화"""
        try:
            center_pos = self.opencr_serial.dxl_getPresentPositionData(self.CENTER_MOTOR_ID)
            self.center_position = center_pos * 200 / 1023
            print(f"Initialized center position: {self.center_position:.1f}°")

        except Exception as e:
            print(f"Warning: Could not read current motor position: {e}")
            print("Starting from 0 degrees")
            self.center_position = 0

    def start_center_motor_rotation(self, direction=1):
        """센터 모터 연속 회전 시작 (direction = 1: 정방향, -1: 역방향)"""
        try:
            dir_text = "정방향" if direction == 1 else "역방향"
            print(f"센터 모터 {dir_text} 연속 회전 시작")

            self.opencr_serial.dxl_torqueOff(self.CENTER_MOTOR_ID)
            self.opencr_serial.dxl_setOperatingMode(self.CENTER_MOTOR_ID, 1)
            self.opencr_serial.dxl_torqueOn(self.CENTER_MOTOR_ID)

            self.opencr_serial.dxl_goalVelocity(self.CENTER_MOTOR_ID, 100 * direction)

            print(f"  Motor ID: {self.CENTER_MOTOR_ID}")
            print(f"  Rotation speed: {100 * direction}")
            print(f"  Press 'c' to stop rotation")

        except Exception as e:
            print(f"  Error starting center motor rotation: {e}")

    def stop_center_motor_rotation(self):
        """센터 모터 연속 회전 정지"""
        try:
            print("Stopping center motor rotation...")

            self.opencr_serial.dxl_goalVelocity(self.CENTER_MOTOR_ID, 0)
            time.sleep(0.5)

            self.opencr_serial.dxl_torqueOff(self.CENTER_MOTOR_ID)
            self.opencr_serial.dxl_setOperatingMode(self.CENTER_MOTOR_ID, 3)
            self.opencr_serial.dxl_torqueOn(self.CENTER_MOTOR_ID)

            print(f"  Motor ID: {self.CENTER_MOTOR_ID}")
            print(f"  Rotation stopped")

        except Exception as e:
            print(f"  Error stopping center motor rotation: {e}")

    def reset_center_motor(self):
        """센터 모터를 중간 위치(100도)로 리셋"""
        try:
            target_angle = 100
            position_value = int(target_angle * 1023 / 200)

            print(f"Resetting center motor to {target_angle} degrees")
            print(f"  Motor ID: {self.CENTER_MOTOR_ID}")
            print(f"  Target position value: {position_value}")

            self.opencr_serial.dxl_goalPosition(self.CENTER_MOTOR_ID, position_value)
            print("  Reset command sent successfully")

            self.center_position = target_angle

        except Exception as e:
            print(f"  Error resetting center motor: {e}")

    def check_motor_status(self):
        """센터 모터 상태 확인"""
        print("\n=== Motor Status Check ===")
        try:
            center_pos = self.opencr_serial.dxl_getPresentPositionData(self.CENTER_MOTOR_ID)
            center_angle = center_pos * 200 / 1023
            print(f"Center Motor (ID {self.CENTER_MOTOR_ID}): Position={center_pos}, Angle={center_angle:.1f}°")
        except Exception as e:
            print(f"Error checking motor status: {e}")
        print("========================\n")

    def get_key(self):
        """키보드 입력을 논블로킹 방식으로 받기"""
        if select.select([sys.stdin], [], [], 0)[0]:
            return sys.stdin.read(1)
        return None

    def run(self):
        """메인 제어 루프"""
        old_settings = termios.tcgetattr(sys.stdin)
        try:
            tty.setcbreak(sys.stdin.fileno())

            print("\n=== Motor Control ===")
            print("Press 'a': Start center motor (정방향)")
            print("Press 'f': Start center motor (역방향)")
            print("Press 'c': Stop center motor rotation")
            print("Press 'r': Reset center motor to 100° position")
            print("Press 'q': Quit program")
            print("=====================\n")

            print(f"\nCurrent motor position: {self.center_position:.1f}°")
            self.check_motor_status()

            while True:
                key = self.get_key()

                if key == 'a':
                    self.start_center_motor_rotation(direction=1)
                elif key == 'f':
                    self.start_center_motor_rotation(direction=-1)
                elif key == 'c':
                    self.stop_center_motor_rotation()
                elif key == 'r':
                    self.reset_center_motor()
                elif key == 'q':
                    print("\nExiting...")
                    break

                time.sleep(0.01)

        finally:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
            if self.opencr_serial:
                self.opencr_serial.dxl_torqueOff(self.CENTER_MOTOR_ID)
                print("모터 사용 종료")


if __name__ == "__main__":
    try:
        motor_control = MotorControl()
        motor_control.run()
    except KeyboardInterrupt:
        print("\nProgram interrupted by user")
    except Exception as e:
        print(f"Error: {e}")
