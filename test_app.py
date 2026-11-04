import copy
from http.client import HTTPConnection
import json
from pathlib import Path
import threading
import unittest

from app import make_server
from engine import RESEARCH, calculate


def fixture(index=3):
    case=json.loads((RESEARCH/'cases.json').read_text())[index]
    return {'horizon':case['horizon'],'inspection':case['turnaround'],
            'lateness':0,'requests':case['requests']}


class ReviewEngineTests(unittest.TestCase):
    def test_all_cases_match_research_baseline(self):
        baseline=json.loads((RESEARCH/'results__v001.json').read_text())['results']
        for index,previous in enumerate(baseline):
            report=calculate(fixture(index))
            for strategy in ('strict','gap','deadline'):
                self.assertEqual(report['strategies'][strategy]['bookings'],previous['strategies'][strategy]['bookings'])
                self.assertEqual(report['strategies'][strategy]['served'],previous['strategies'][strategy]['served'])

    def test_refusal_explained_at_decision_time(self):
        report=calculate(fixture())
        reason=report['strategies']['gap']['reasons'][0]
        self.assertEqual(reason['id'],'C')
        self.assertEqual(reason['code'],'BUFFER_CONFLICT')
        self.assertEqual(reason['blocking_requests'],['B'])
        # D is accepted AFTER C is rejected; it must not be blamed for C's refusal.
        self.assertNotIn('D',reason['blocking_requests'])

    def test_alternative_respects_final_bookings_and_buffer(self):
        payload = {"horizon": 8, "inspection": 1, "lateness": 0, "requests": [
            {"id": "A", "release": 0, "deadline": 3, "duration": 3},
            {"id": "B", "release": 0, "deadline": 4, "duration": 2},
            {"id": "C", "release": 4, "deadline": 5, "duration": 1},
        ]}
        gap = calculate(payload)["strategies"]["gap"]
        self.assertEqual(gap["bookings"], [
            {"id": "A", "start": 0, "end": 3}, {"id": "C", "start": 4, "end": 5},
        ])
        self.assertEqual(gap["reasons"][0]["alternative"],
                         {"start": 6, "end": 8, "deadline_extension": 4})
        payload["horizon"] = 7
        self.assertIsNone(calculate(payload)["strategies"]["gap"]["reasons"][0]["alternative"])

    def test_lateness_adds_to_inspection_and_changes_feasibility(self):
        payload=fixture();payload['lateness']=1
        report=calculate(payload)
        self.assertEqual(report['effective_buffer'],2)
        self.assertEqual(report['strategies']['gap']['served'],2)
        self.assertIn('여유',report['strategies']['gap']['reasons'][0]['message'])

    def test_invalid_schema_bounds_and_ids(self):
        bad=[]
        x=fixture();x['horizon']=False;bad.append(x)
        x=fixture();x['requests'][1]['id']='A';bad.append(x)
        x=fixture();x['requests'][0]['id']='<script>';bad.append(x)
        x=fixture();x['horizon']=49;bad.append(x)
        x=fixture();x['requests']=[];bad.append(x)
        x=fixture();x['extra']='unexpected';bad.append(x)
        for payload in bad:
            with self.assertRaises(ValueError): calculate(payload)


class LocalHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=make_server()
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join()

    def call(self,method,path,body=None,headers=None):
        connection=HTTPConnection('127.0.0.1',self.server.server_port,timeout=2)
        connection.request(method,path,body=body,headers=headers or {})
        response=connection.getresponse(); data=response.read(); status=response.status
        connection.close();return status,data

    def test_http_calculation_and_static_route(self):
        status,page=self.call('GET','/')
        self.assertEqual(status,200);self.assertIn('대여 배정 검토',page.decode())
        status,data=self.call('POST','/calculate',json.dumps(fixture()),{'Content-Type':'application/json'})
        self.assertEqual(status,200)
        self.assertEqual(json.loads(data)['strategies']['gap']['served'],3)

    def test_http_refuses_cross_origin_and_arbitrary_files(self):
        status,_=self.call('POST','/calculate',json.dumps(fixture()),{'Content-Type':'application/json','Origin':'https://example.invalid'})
        self.assertEqual(status,403)
        self.assertEqual(self.call('GET','/../engine.py')[0],404)
        self.assertEqual(self.call('GET','/engine.py')[0],404)

    def test_http_invalid_json_and_oversized_body(self):
        self.assertEqual(self.call('POST','/calculate','{',{'Content-Type':'application/json'})[0],400)
        self.assertEqual(self.call('POST','/calculate','x'*24001,{'Content-Type':'application/json'})[0],413)


if __name__=='__main__':unittest.main()
