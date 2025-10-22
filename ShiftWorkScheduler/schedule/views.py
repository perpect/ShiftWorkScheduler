from django.shortcuts import render
from .solve import *
import json
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.http import require_POST
from .forms import ScheduleSettingsForm
from django.views.decorators.csrf import ensure_csrf_cookie

@ensure_csrf_cookie
def index(request):
    return render(request, "index.html")

@require_POST
def solve_schedule(request):
    try:
        request_data = json.loads(request.body)
    except json.JSONDecodeError:
        return HttpResponseBadRequest("잘못된 JSON 요청입니다.")

    form = ScheduleSettingsForm(request_data)

    if not form.is_valid():
        return JsonResponse({'status': 'error', 'errors': form.errors}, status=400)
    try:
        data = form.cleaned_data
        
        # 1. 주말 계산
        weekends = [
            d for d in range(data['num_days']) 
            if (d + data['start_day_of_week']) % 7 == 5 or 
               (d + data['start_day_of_week']) % 7 == 6
        ]

        # 2. 제약조건 리스트
        constraints = [
            addExactlyOne,
            addDailyShiftRequirements,
            addNightShiftRestRequirement,
            addFixedAssignments,
            addVacationRestrictions,
            addNoConsecutiveOffDays,
            addMonthlyWorkConstraints,
        ]
        
        solver = ScheduleSolver(
            num_workers=data['num_workers'],
            num_days=data['num_days'],
            fixed_assignments=data['fixed_assignments'],
            weekends=weekends,
            holidays=data['holidays'],
            max_monthly_hours=data['max_monthly_hours'],
            constraints=constraints,
            objectiveFunc=setObjective
        )
        
        schedule_result = solver.solve()

        if not schedule_result:
            return JsonResponse({'status': 'error', 'message': '해결 가능한 스케줄을 찾지 못했습니다.'}, status=422)

        final_schedule = {}
        for worker, codes in schedule_result.items():
            final_schedule[f"worker_{worker}"] = [code for code in codes]

        return JsonResponse({'status': 'success', 'schedule': final_schedule})

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': f'서버 오류: {str(e)}'}, status=500)