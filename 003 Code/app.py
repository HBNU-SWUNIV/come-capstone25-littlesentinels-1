import sys
import json
from firebase_connection import FirebaseConnection

if __name__ == '__main__':
    fc = FirebaseConnection()
    print("데이터 수신 대기...")

    for line in sys.stdin:
        try:
            data = json.loads(line.strip())

            if data["Task"] == "init_data":
                fc.init_data(data["Total"], data["Mature"])

            elif data["Task"] == "init_log":
                fc.init_log(data["Total"], data["Mature"])

            elif data["Task"] == "count":
                fc.increment_harvest_count()

            elif data["Task"] == "clear":
                fc.clear_data()
                
            else:
                print(f"데이터 수신 오류: {data}")
                break

            print(f"수신됨 {data}")

        except EOFError:
            # 파이프가 닫히면 종료
            break