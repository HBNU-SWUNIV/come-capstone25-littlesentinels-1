from neuromeka import IndyDCP2
import time
import math

class indyCTL():
    def __init__(self, ip="192.168.0.6"):
        
        self.robot_ip = ip                          # 로봇 컨트롤 박스의 IP 주소
        self.robot_name = 'NRMK-Indy7'              # 로봇 이름
        self.indy = IndyDCP2(server_ip=self.robot_ip, robot_name=self.robot_name)


        self.indy.connect()                         # 연결
        self.indy.reset_robot()
        time.sleep(1)
        self.indy.set_joint_vel_level(1)            # 로봇 속도 조절, 기본 : 3
        self.indy.set_task_vel_level(1)             # [안전:1,2], [보통:3,4], [위험:5,6], [매우 위험:7,8,9]

       
        self.indy.go_home()
        self.indy.wait_for_move_finish()

        print(self.indy.get_task_vel_level())
        print(self.indy.get_task_vel_level())
        
        print("Ready")

    def set_point(self, cam_x, depth):

        # 첫번째 사진촬영 후
        robot_len       = 0.45  # 고정
        camera_distances = 0.04

        cam_x = -cam_x
        distance        = depth
        radian          = cam_x/(distance+robot_len+camera_distances)
        angle           = math.degrees(radian)

        self.indy.set_task_base(0)
        print(self.indy.get_control_torque()) 
        self.indy.joint_move_by([angle,0,0,0,0,0])
        self.indy.wait_for_move_finish()

        return "finish"

    def run(self, cam_x=0, cam_y=0, cam_z=0, angle=0):

        # 두번째 사진촬영 후
        camera_distance = 0.04
        end_tool=0.17
        x               = -cam_x
        y               = cam_y
        if cam_z > 0.32:
            z           = 0.3-end_tool
        else:
            z           = cam_z-camera_distance-end_tool
        tool_angle      = angle
        cam_offset      = 0.1

        self.indy.joint_move_by([0,0,0,0,0,20])
        self.indy.wait_for_move_finish()
        self.indy.set_task_base(1)
        self.indy.task_move_by([y-cam_offset,x,z,0,0,0]) # x(+ 아래, - 위), y(+ 왼쪽, - 오른쪽), z(+ 접근, - 후퇴) 마지막: yaw : 돌리는거
        self.indy.wait_for_move_finish()

        self.indy.set_task_base(0)
        self.indy.joint_move_by([0,0,0,0,0,-20])
        self.indy.wait_for_move_finish()

        self.indy.task_move_by([0,0,0,0,0,tool_angle]) # x(+ 아래, - 위), y(+ 왼쪽, - 오른쪽), z(+ 접근, - 후퇴) 마지막: yaw : 돌리는거
        self.indy.wait_for_move_finish()
        time.sleep(2)
        status = self.indy.get_robot_status()
        print(status)

        return


    def close(self):
        self.indy.go_home()
        self.indy.wait_for_move_finish()
        print("Task Pos: ", self.indy.get_task_pos())
        print("Angle Pos: ", self.indy.get_robot_status())
        time.sleep(0.5)
        self.indy.disconnect()                   # 연결 해제
        print("Close")


if __name__ == "__main__":
    indy = indyCTL()
    # indy.run()
    indy.close()



