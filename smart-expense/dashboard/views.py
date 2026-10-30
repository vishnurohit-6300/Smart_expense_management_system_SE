
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render

from .services import get_dashboard_data


def health(request):
    return JsonResponse({"status": "ok"})


@login_required
def home(request):
    """
    Display the financial dashboard for the authenticated user.
    """

    context = get_dashboard_data(request.user)

    return render(
        request,
        "dashboard/home.html",
        context,
    )
