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

OFF = DUTIES_CODE["OFF"]
DAY = DUTIES_CODE["DAY"]
NIGHT = DUTIES_CODE["NIGHT"]
VACATION = DUTIES_CODE["VACATION"]

# 제약조건 1: 하루에 한 가지 근무만 배정
def addExactlyOne(self):
    for n in self.all_workers:
        for d in self.all_days:
            self.model.AddExactlyOne(self.shifts[(n, d, s)] for s in self.all_shifts)

# 제약조건 2: 일일 근무 요구사항
def addDailyShiftRequirements(self):
    for d in self.all_days:
        available_workers = self.num_workers - sum(self.shifts[(n, d, VACATION)] for n in self.all_workers)
        has_at_least_3_workers = self.model.NewBoolVar(f'has_at_least_3_workers_d{d}')
        self.model.Add(available_workers >= 3).OnlyEnforceIf(has_at_least_3_workers)
        self.model.Add(available_workers < 3).OnlyEnforceIf(has_at_least_3_workers.Not())
        self.model.Add(sum(self.shifts[(n, d, DAY)] for n in self.all_workers) >= 1).OnlyEnforceIf(has_at_least_3_workers)
        self.model.Add(sum(self.shifts[(n, d, NIGHT)] for n in self.all_workers) == 1)

# 제약조건 3: 야간 근무 후 휴식 요구사항
def addNightShiftRestRequirement(self):
    for d in range(self.num_days - 1):
        available_workers_next_day = self.num_workers - sum(self.shifts[(n, d + 1, VACATION)] for n in self.all_workers)
        has_at_least_2_workers_next_day = self.model.NewBoolVar(f'has_at_least_2_workers_d{d+1}')
        self.model.Add(available_workers_next_day >= 2).OnlyEnforceIf(has_at_least_2_workers_next_day)
        self.model.Add(available_workers_next_day < 2).OnlyEnforceIf(has_at_least_2_workers_next_day.Not())
        for n in self.all_workers:
            self.model.AddImplication(self.shifts[(n, d, NIGHT)], self.shifts[(n, d + 1, OFF)]).OnlyEnforceIf(has_at_least_2_workers_next_day)


# 제약조건 4: 고정 근무 배정
def addFixedAssignments(self):
    if self.fixed_assignments:
        for (n, d), s in self.fixed_assignments.items():
            self.model.Add(self.shifts[(n, d, s)] == 1)

# 제약조건 5: 휴가는 고정 근무가 아니라면 배정하지 말 것
def addVacationRestrictions(self):
    for n in self.all_workers:
        for d in self.all_days:
            if not self.fixed_assignments or (n, d) not in self.fixed_assignments:
                self.model.Add(self.shifts[(n, d, VACATION)] == 0)

# 제약조건 6: 연속 OFF 금지
def addNoConsecutiveOffDays(self):
    for n in self.all_workers:
        for d in range(self.num_days - 1):
            self.model.Add(self.shifts[(n, d, OFF)] + self.shifts[(n, d + 1, OFF)] <= 1)

# 제약조건 7: 한 달 근무시간 160시간 초과, 최소 한 번 야간 근무, 근무일 15일 이상
def addMonthlyWorkConstraints(self):
    for n in self.all_workers:
        total_work_hours = cp_model.LinearExpr.Sum([
            self.shifts[(n, d, s)] * ALL_DUTIES_DICT[s].time
            for d in self.all_days for s in [DAY, NIGHT]
        ])
        total_work_days = cp_model.LinearExpr.Sum([
            self.shifts[(n, d, s)]
            for d in self.all_days for s in [DAY, NIGHT]
        ])
        self.model.Add(total_work_days >= 15)
        self.model.Add(total_work_hours >= 160)
        self.model.Add(total_work_hours <= self.max_monthly_hours)
        self.model.Add(cp_model.LinearExpr.Sum([self.shifts[(n, d, NIGHT)] for d in self.all_days]) >= 1)

# 목적함수
def setObjective(self):
    worker_total_hours = []
    worker_weekday_day_shifts = []
    worker_holiday_day_shifts = []
    all_holidays = set(self.weekends) | set(self.holidays)
    for n in self.all_workers:
        total_hours = cp_model.LinearExpr.Sum([
            self.shifts[(n, d, s)] * ALL_DUTIES_DICT[s].time for d in self.all_days for s in [DAY, NIGHT]
        ])
        worker_total_hours.append(total_hours)
        weekday_days = cp_model.LinearExpr.Sum([
            self.shifts[(n, d, DAY)] for d in self.all_days if d not in all_holidays
        ])
        worker_weekday_day_shifts.append(weekday_days)
        holiday_days = cp_model.LinearExpr.Sum([
            self.shifts[(n, d, DAY)] for d in self.all_days if d in all_holidays
        ])
        worker_holiday_day_shifts.append(holiday_days)
        
    max_h = self.model.NewIntVar(0, self.max_monthly_hours, 'max_hours')
    min_h = self.model.NewIntVar(0, self.max_monthly_hours, 'min_hours')
    self.model.AddMaxEquality(max_h, worker_total_hours)
    self.model.AddMinEquality(min_h, worker_total_hours)

    hours_diff = max_h - min_h
    max_wd = self.model.NewIntVar(0, self.num_days, 'max_weekday_days')
    min_wd = self.model.NewIntVar(0, self.num_days, 'min_weekday_days')
    self.model.AddMaxEquality(max_wd, worker_weekday_day_shifts)
    self.model.AddMinEquality(min_wd, worker_weekday_day_shifts)

    weekday_diff = max_wd - min_wd
    max_hd = self.model.NewIntVar(0, self.num_days, 'max_holiday_days')
    min_hd = self.model.NewIntVar(0, self.num_days, 'min_holiday_days')
    self.model.AddMaxEquality(max_hd, worker_holiday_day_shifts)
    self.model.AddMinEquality(min_hd, worker_holiday_day_shifts)

    holiday_diff = max_hd - min_hd
    total_hours_penalty = cp_model.LinearExpr.Sum(worker_total_hours)
    self.model.Minimize(hours_diff * 1 + weekday_diff * 8 + holiday_diff * 3 + total_hours_penalty)