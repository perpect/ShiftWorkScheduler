from django import forms
import json, ast

class ScheduleSettingsForm(forms.Form):
    num_workers = forms.IntegerField(
        min_value=1, 
        max_value=15, 
        label="근무자 수"
    )
    num_days = forms.IntegerField(
        min_value=28, 
        max_value=31, 
        label="월의 일수"
    )
    start_day_of_week = forms.IntegerField(
        min_value=0, 
        max_value=6, 
        label="시작 요일 (월=0, 일=6)"
    )
    max_monthly_hours = forms.IntegerField(
        min_value=100, 
        max_value=300, 
        initial=200, 
        label="최대 근무 시간"
    )
    
    # JSON 문자열로 받아서 유효성 검사
    holidays = forms.CharField(
        required=False, 
        label="공휴일 (e.g., [15, 25])"
    )
    fixed_assignments = forms.CharField(
        required=False, 
        label="고정 근무 (e.g., [{\"worker\": 1, \"day\": 11, \"shift\": 3}])", 
        empty_value="[]"
    )

    def clean_holidays(self):
        """
        CharField로 받은 문자열(data)을 json.loads()로 파싱합니다.
        - 입력 (문자열): "[24]"
        - 출력 (리스트): [24]
        """
        data = self.cleaned_data['holidays']
        if not data:
            return []
            
        try:
            parsed_data = json.loads(data)
            if not isinstance(parsed_data, list):
                raise forms.ValidationError("공휴일은 리스트(배열) 형태여야 합니다.")
            
            # 추가 검증: 리스트의 모든 항목이 숫자인지
            if not all(isinstance(item, int) for item in parsed_data):
                raise forms.ValidationError("공휴일 리스트는 숫자만 포함해야 합니다.")
            
            return parsed_data
            
        except json.JSONDecodeError:
            raise forms.ValidationError("잘못된 JSON 형식의 공휴일 데이터입니다.")
        except TypeError:
            raise forms.ValidationError("공휴일 데이터 파싱 중 타입 오류가 발생했습니다.")

    def clean_fixed_assignments(self):
        data = self.cleaned_data['fixed_assignments']
        if not data:
            return {} # solver는 빈 딕셔너리를 기대
            
        parsed_data = None
        try:
            # 1. 표준 JSON (쌍따옴표) 파싱 시도
            parsed_data = json.loads(data)
        except json.JSONDecodeError:
            # 2. JSON 파싱 실패 시, Python 리터럴(홑따옴표 등) 파싱 시도
            try:
                parsed_data = ast.literal_eval(data)
            except (ValueError, SyntaxError):
                # 1, 2 모두 실패 시 에러 발생
                raise forms.ValidationError("잘못된 JSON 형식의 고정 근무 데이터입니다. (쌍따옴표와 홑따옴표 모두 파싱 실패)")

        if not isinstance(parsed_data, list):
            raise forms.ValidationError("고정 근무는 딕셔너리(객체)의 리스트(배열) 형태여야 합니다.")

        final_fixed_assignments = {}
        try:
            for item in parsed_data:
                if not isinstance(item, dict):
                    raise ValueError("고정 근무 항목이 딕셔너리(객체)가 아닙니다.")

                # get()을 사용해 안전하게 키에 접근
                n = item.get('worker')
                d = item.get('day')
                s = item.get('shift')
                
                # 키 존재 및 타입 검증
                if n is None or d is None or s is None:
                    raise ValueError(f"항목에 'worker', 'day', 'shift' 키가 모두 필요합니다: {item}")
                
                if not all(isinstance(val, int) for val in [n, d, s]):
                        raise ValueError(f"worker, day, shift 값은 모두 숫자여야 합니다: {item}")

                # solve.py가 요구하는 튜플 key로 변환
                final_fixed_assignments[(n, d)] = s

            return final_fixed_assignments
            
        except (ValueError, TypeError, SyntaxError) as e:
            # key 파싱 로직이 단순해졌으므로 에러 메시지도 단순화
            raise forms.ValidationError(f"고정 근무 데이터 처리 중 오류: {e}")