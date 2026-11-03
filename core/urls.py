from django.urls import path
from . import views, user_management
app_name='core'
urlpatterns=[path('users/',user_management.users,name='users'),path('users/new/',user_management.user_edit,name='user_create'),path('users/<int:pk>/edit/',user_management.user_edit,name='user_edit'),path('travels/<int:pk>/edit/',views.travel_edit,name='travel_edit'),path('attachments/<int:pk>/download/',views.attachment_download,name='attachment_download'),path('travels/<int:pk>/costs/',views.travel_costs,name='travel_costs'),path('',views.home,name='home'),path('travels/new/',views.travel_create,name='travel_create'),path('travels/<int:pk>/',views.travel_detail,name='travel_detail')]
