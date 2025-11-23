import firebase_admin
from firebase_admin import firestore
from firebase_admin import credentials
import datetime
from datetime import datetime as dt

class FirebaseConnection:
    def __init__(self):
        file_path = '' # Firebase - 앱 간 연결용 json 파일 경로
        cred = credentials.Certificate(file_path)
        firebase_admin.initialize_app(cred)

        self.db = firestore.client()
        self.doc_data = self.db.collection('Harvest_Data').document('Data')
        self.doc_log = self.db.collection('Growth_Log')
        self.last_log = self.get_last_log()
        self.count = 0
        self.cumul_count = self.last_log.get('n_cumul_harvest') if self.last_log is not None else 0

        # 실시간 현황 화면 초기화
    def init_data(self, n_total, n_mature):
        self.doc_data.update({'n_total': n_total,
                            'n_mature': n_mature,
                            'n_immature': n_total - n_mature,
                            'n_harvest': 0})
        
        # 새로운 로그 초기화
    def init_log(self, n_total, n_mature):
        if self.last_log is not None:
            prev_cumul_total = self.last_log.get('n_cumul_total')
            prev_cumul_mature = self.last_log.get('n_cumul_mature')

            prev_current_total = self.last_log.get('n_current_total')
            prev_current_mature = self.last_log.get('n_current_mature')
            prev_current_harvest = self.last_log.get('n_current_harvest')

        else:
            prev_cumul_total = 0
            prev_cumul_mature = 0

            prev_current_total = 0
            prev_current_mature = 0
            prev_current_harvest = 0

        n_cumul_total = prev_cumul_total + max(0, n_total - (prev_current_total - prev_current_harvest))
        n_cumul_mature = prev_cumul_mature + max(0, n_mature - (prev_current_mature - prev_current_harvest))
        
        self.doc_log.add({'datetime': dt.now(tz = datetime.timezone.utc),
                          'n_cumul_total': n_cumul_total,
                          'n_current_total': n_total,
                          'n_cumul_mature': n_cumul_mature,
                          'n_current_mature': n_mature,
                          'n_cumul_harvest': self.cumul_count,
                          'n_current_harvest': 0})
        
        # 최신 로그 상태 업데이트
        self.last_log = self.get_last_log()

    # 수확량 증가
    def increment_harvest_count(self):
        self.count += 1
        self.cumul_count += 1
        
        self.doc_data.update({'n_harvest': self.count})
        self.last_log.reference.update({'n_cumul_harvest': self.cumul_count,
                                        'n_current_harvest': self.count})

    def update_log(self, n_total, n_mature):
        self.last_log.reference.update({'n_cumul_total': self.last_log.get('n_cumul_total') + n_total,
                                        'n_current_total': self.last_log.get('n_current_total') + n_total,
                                        'n_cumul_mature': self.last_log.get('n_cumul_mature') + n_mature,
                                        'n_current_mature': self.last_log.get('n_current_mature') + n_mature})
   
        # 실시간 현황 0으로 초기화
    def clear_data(self):
        self.doc_data.update({'n_total': 0,
                            'n_mature': 0,
                            'n_immature': 0,
                            'n_harvest': 0})

    def get_last_log(self):
        query = self.doc_log.order_by('datetime', direction=firestore.Query.DESCENDING).limit(1)
        docs = query.stream()
        
        try:
            return next(docs)
        except StopIteration:
            return None