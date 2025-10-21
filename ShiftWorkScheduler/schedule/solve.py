
from ortools.sat.python import cp_model

class Duty:
    def __init__(self, name, code, time, color):
        self.name = name
        self.code = code
        self.time = time
        self.color = color

ALL_DUTIES = [
    Duty("OFF", 0, 0, "#FF7B7B"),
    Duty("DAY", 1, 10, "#38AFFF"),
    Duty("NIGHT", 2, 14, "#FFF064"),
    Duty("VACATION", 3, 0, "#B9B9B9")
]
NUM_SHIFT = len(ALL_DUTIES)
DUTIES_CODE = {duty.name: duty.code for duty in ALL_DUTIES}
ALL_DUTIES_DICT = {duty.code: duty for duty in ALL_DUTIES}

def solve_schedule(num_workers, num_days, fixed_assignments=None, weekends=[], holidays=[], max_monthly_hours=200):
    """OR-Tools를 사용하여 스케줄을 계산하고 결과를 반환하는 함수"""
    OFF = DUTIES_CODE["OFF"]
    DAY = DUTIES_CODE["DAY"]
    NIGHT = DUTIES_CODE["NIGHT"]
    VACATION = DUTIES_CODE["VACATION"]

    model = cp_model.CpModel()
    all_workers = range(num_workers)
    all_shifts = range(NUM_SHIFT)
    all_days = range(num_days)
    
    # 표현 : n에게 d일에 s근무 배정 여부
    shifts = {}
    for n in all_workers:
        for d in all_days:
            for s in all_shifts:
                shifts[(n, d, s)] = model.NewBoolVar(f'shift_n{n}_d{d}_s{s}')

    # 제약조건 1: 각 근무자는 하루에 한 가지 근무만 들어감
    for n in all_workers:
        for d in all_days:
            model.AddExactlyOne(shifts[(n, d, s)] for s in all_shifts)
    
    # 제약조건 2: 매일 주간근무와 야간근무 보장. 만일, 남은 사람이 2명이면 야간/비번 반복 가능
    for d in all_days:
        available_workers = num_workers - sum(shifts[(n, d, VACATION)] for n in all_workers)
        
        has_at_least_3_workers = model.NewBoolVar(f'has_at_least_3_workers_d{d}')
        model.Add(available_workers >= 3).OnlyEnforceIf(has_at_least_3_workers)
        model.Add(available_workers < 3).OnlyEnforceIf(has_at_least_3_workers.Not())
        
        # 스위치가 켜져 있을 때만(3명 이상일 때만) 주간 근무 규칙을 적용
        model.Add(sum(shifts[(n, d, DAY)] for n in all_workers) >= 1).OnlyEnforceIf(has_at_least_3_workers)

        model.Add(sum(shifts[(n, d, NIGHT)] for n in all_workers) == 1)

    # 제약조건 3: 야간근무 다음날은 무조건 비번
    for d in range(num_days - 1):
        available_workers_next_day = num_workers - sum(shifts[(n, d + 1, VACATION)] for n in all_workers)
        
        has_at_least_2_workers_next_day = model.NewBoolVar(f'has_at_least_2_workers_d{d+1}')
        model.Add(available_workers_next_day >= 2).OnlyEnforceIf(has_at_least_2_workers_next_day)
        model.Add(available_workers_next_day < 2).OnlyEnforceIf(has_at_least_2_workers_next_day.Not())

        for n in all_workers:
            model.AddImplication(shifts[(n, d, NIGHT)], shifts[(n, d + 1, OFF)]).OnlyEnforceIf(has_at_least_2_workers_next_day)
    
    # 제약조건 5: 고정 근무 배정
    if fixed_assignments:
        for (n, d), s in fixed_assignments.items():
            model.add(shifts[(n, d, s)] == 1)
    
    # 제약조건 6: 휴가는 고정 근무가 아니라면 배정하지 말 것
    for n in all_workers:
        for d in all_days:
            if not fixed_assignments or (n, d) not in fixed_assignments:
                model.add(shifts[(n, d, VACATION)] == 0)
    
    # 제약조건 7: 연속 OFF 금지
    for n in all_workers:
        for d in range(num_days - 1):
            model.add(shifts[(n, d, OFF)] + shifts[(n, d + 1, OFF)] <= 1)
    
    # 제약조건 8: 한 달 근무시간 160시간 초과, 최소 한 번 야간 근무, 근무일 15일 이상
    for n in all_workers:
        total_work_hours = cp_model.LinearExpr.Sum([
            shifts[(n, d, s)] * ALL_DUTIES_DICT[s].time
            for d in all_days for s in [DAY, NIGHT]
        ])
        total_work_days = cp_model.LinearExpr.Sum([
            shifts[(n, d, s)]
            for d in all_days for s in [DAY, NIGHT]
        ])
        model.Add(total_work_days >= 15)
        model.Add(total_work_hours >= 160)
        model.Add(total_work_hours <= max_monthly_hours)
        
        model.Add(cp_model.LinearExpr.Sum([shifts[(n, d, NIGHT)] for d in all_days]) >= 1)

    worker_total_hours = []
    worker_weekday_day_shifts = []
    worker_holiday_day_shifts = []
    all_holidays = set(weekends) | set(holidays)

    for n in all_workers:
        total_hours = cp_model.LinearExpr.Sum([
            shifts[(n, d, s)] * ALL_DUTIES_DICT[s].time for d in all_days for s in [DAY, NIGHT]
        ])
        worker_total_hours.append(total_hours)
        weekday_days = cp_model.LinearExpr.Sum([
            shifts[(n, d, DAY)] for d in all_days if d not in all_holidays
        ])
        worker_weekday_day_shifts.append(weekday_days)
        holiday_days = cp_model.LinearExpr.Sum([
            shifts[(n, d, DAY)] for d in all_days if d in all_holidays
        ])
        worker_holiday_day_shifts.append(holiday_days)

    max_h = model.NewIntVar(0, max_monthly_hours, 'max_hours')
    min_h = model.NewIntVar(0, max_monthly_hours, 'min_hours')
    model.AddMaxEquality(max_h, worker_total_hours)
    model.AddMinEquality(min_h, worker_total_hours)
    hours_diff = max_h - min_h

    max_wd = model.NewIntVar(0, num_days, 'max_weekday_days')
    min_wd = model.NewIntVar(0, num_days, 'min_weekday_days')
    model.AddMaxEquality(max_wd, worker_weekday_day_shifts)
    model.AddMinEquality(min_wd, worker_weekday_day_shifts)
    weekday_diff = max_wd - min_wd

    max_hd = model.NewIntVar(0, num_days, 'max_holiday_days')
    min_hd = model.NewIntVar(0, num_days, 'min_holiday_days')
    model.AddMaxEquality(max_hd, worker_holiday_day_shifts)
    model.AddMinEquality(min_hd, worker_holiday_day_shifts)
    holiday_diff = max_hd - min_hd
    
    # [수정된 목표] 전체 근무 시간의 총합도 최소화하도록 약한 페널티 추가
    total_hours_penalty = cp_model.LinearExpr.Sum(worker_total_hours)
    
    model.Minimize(hours_diff * 1 + weekday_diff * 8 + holiday_diff * 3 + total_hours_penalty)


    # --- 4. 솔버 실행 ---
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 30.0 # 계산 시간 연장
    status = solver.Solve(model)

    # --- 5. 결과 처리 ---
    schedule_data = None
    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        print("\n최적의 스케줄을 찾았습니다!")
        schedule_data = {}
        for n in all_workers:
            schedule_data[n] = []
            for d in all_days:
                for s in all_shifts:
                    if solver.Value(shifts[(n, d, s)]):
                        schedule_data[n].append(s)
                        break
    else:
        print("해결 가능한 스케줄을 찾을 수 없습니다.")

    # Statistics.
    print("\nStatistics")
    print(f"  - Status           : {solver.StatusName(status)}")
    print(f"  - Objective value  : {solver.ObjectiveValue()}")
    print(f"  - conflicts        : {solver.NumConflicts()}")
    print(f"  - branches         : {solver.NumBranches()}")
    print(f"  - wall time        : {solver.WallTime()} s")
    
    return schedule_data

if __name__ == "__main__":
    num_workers = 3
    num_days = 30
    start_day_of_week = 5
    weekends = [d for d in range(num_days) if (d + start_day_of_week) % 7 == 5 or (d + start_day_of_week) % 7 == 6]
    holidays = []
    max_monthly_hours = 250
    fixed = {(1, 10): 3, (1, 11): 3, (1, 12): 3, (1, 13): 3, (1, 14): 3, (1, 15): 3, (1, 0): 0}
    rst = solve_schedule(num_workers, num_days, fixed_assignments=fixed, weekends=weekends, holidays=holidays, max_monthly_hours=max_monthly_hours)
    if rst:
        print("\n--- 최종 근무표 ---")
        print("\t ", end="")
        for d in range(1, num_days + 1):
            day_index = d - 1
            if day_index in weekends:
                print(f"\033[94m{d:2}\033[0m ", end="") # 주말은 파란색
            elif day_index in holidays:
                print(f"\033[91m{d:2}\033[0m ", end="") # 공휴일은 빨간색
            else:
                print(f"{d:2} ", end="")
        print()
        
        for worker in rst:
            print(f"Worker {worker}: ", end="")
            for day_code in rst[worker]: 
                duty = ALL_DUTIES_DICT[day_code]
                print(f"{duty.name[0]} ", end=" ")
            print()

        print("\n--- 근무 요약 ---")
        for worker_idx, schedule in rst.items():
            total_hours = 0
            duty_counts = {duty.code: 0 for duty in ALL_DUTIES}
            
            for duty_code in schedule:
                duty = ALL_DUTIES_DICT[duty_code]
                total_hours += duty.time
                duty_counts[duty_code] += 1
            
            summary_str = f"Worker {worker_idx}: 총 근무시간 = {total_hours:3}시간 | "
            
            count_parts = []
            # ALL_DUTIES 순서대로 출력
            for duty in ALL_DUTIES:
                if duty == ALL_DUTIES[DUTIES_CODE["DAY"]]:
                    # 주간근무는 휴일 주간 파악
                    weekday_count = 0
                    holiday_count = 0
                    for d in range(num_days):
                        if schedule[d] == DUTIES_CODE["DAY"]:
                            if d in weekends or d in holidays:
                                holiday_count += 1
                            else:
                                weekday_count += 1
                    if weekday_count > 0:
                        count_parts.append(f"주간(평일): {weekday_count}회")
                    if holiday_count > 0:
                        count_parts.append(f"주간(휴일): {holiday_count}회")
                    continue
                count = duty_counts[duty.code]
                if count > 0:
                    count_parts.append(f"{duty.name}: {count}회")
            
            summary_str += ", ".join(count_parts)
            print(summary_str)