from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from . import auth_views, views

urlpatterns = [
    path("recommend/", views.recommend, name="recommend"),
    path("departments/", views.department_list, name="department-list"),
    path("hospitals/", views.hospital_list, name="hospital-list"),
    path("hospitals/<int:pk>/", views.hospital_detail, name="hospital-detail"),
    path("hospitals/<int:pk>/reviews/", views.hospital_reviews, name="hospital-reviews"),
    path("reviews/<int:pk>/", views.delete_review, name="delete-review"),
    path("emergency-centers/", views.emergency_center_list, name="emergency-center-list"),
    path("directions/", views.directions, name="directions"),
    # 인증 (F01·F09 — 게스트 흐름과 독립)
    path("auth/signup/", auth_views.signup, name="signup"),
    path("auth/login/", auth_views.login, name="login"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("auth/me/", auth_views.me, name="me"),
    path("auth/logs/<int:pk>/", auth_views.delete_log, name="delete-log"),
    path("auth/logs/<int:pk>/feedback/", auth_views.log_feedback, name="log-feedback"),
]
