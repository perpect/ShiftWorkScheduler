from .rules import *

class ScheduleSolver:
    def __init__(self, num_workers, num_days, fixed_assignments=None, weekends=[], holidays=[], max_monthly_hours=200, constraints=[], objectiveFunc=None):
        self.num_workers = num_workers
        self.num_days = num_days
        self.all_workers = range(num_workers)
        self.all_days = range(num_days)
        self.all_shifts = range(NUM_SHIFT)
        self.fixed_assignments = dict(map(lambda x: ((x[0][0], x[0][1] - 1), x[1]), fixed_assignments.items())) if fixed_assignments else {}
        self.weekends = weekends
        self.holidays = list(map(lambda x: x - 1, holidays))
        self.max_monthly_hours = max_monthly_hours
        self.constraints = constraints
        self.model = cp_model.CpModel()
        self.shifts = {}
        self.objectiveFunc = objectiveFunc

        # 표현 : 근무자 n이 날 d에 근무 s를 하는가?
        for n in self.all_workers:
            for d in self.all_days:
                for s in self.all_shifts:
                    self.shifts[(n, d, s)] = self.model.NewBoolVar(f'shift_n{n}_d{d}_s{s}')

    def solve(self):
        """OR-Tools를 사용하여 스케줄을 계산하고 결과를 반환하는 함수"""
        # 제약조건 반영
        for constraint in self.constraints:
            constraint(self)

        # 목적함수 설정
        if self.objectiveFunc:
            self.objectiveFunc(self)

        # 해결
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 10.0
        status = solver.Solve(self.model)

        # 결과
        schedule_data = None
        if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
            print("\n최적의 스케줄을 찾았습니다!")
            schedule_data = {}
            for n in self.all_workers:
                schedule_data[n] = []
                for d in self.all_days:
                    for s in self.all_shifts:
                        if solver.Value(self.shifts[(n, d, s)]):
                            schedule_data[n].append(s)
                            break
        else:
            print("해결 가능한 스케줄을 찾을 수 없습니다.")

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
    holidays = [24]
    max_monthly_hours = 250
    fixed = {(1, 11): 3, (1, 12): 3, (1, 13): 3, (1, 14): 3, (1, 15): 3, (1, 16): 3, (1, 1): 0}
    constraints = [
        addExactlyOne,
        addDailyShiftRequirements,
        addNightShiftRestRequirement,
        addFixedAssignments,
        addVacationRestrictions,
        addNoConsecutiveOffDays,
        addMonthlyWorkConstraints,
    ]
    schedule = ScheduleSolver(num_workers, num_days, fixed_assignments=fixed, weekends=weekends, holidays=holidays, max_monthly_hours=max_monthly_hours, constraints=constraints, objectiveFunc=setObjective)
    rst = schedule.solve()
    if rst:
        print("\n--- 최종 근무표 ---")
        print("\t ", end="")
        for d in range(1, num_days + 1):
            day_index = d - 1
            if day_index in weekends:
                print(f"\033[94m{d:2}\033[0m ", end="") # 주말은 파란색
            elif d in holidays:
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