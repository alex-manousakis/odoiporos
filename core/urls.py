from django.urls import path
from . import views
app_name='core'
urlpatterns=[path('travels/<int:pk>/costs/',views.travel_costs,name='travel_costs'),path('',views.home,name='home'),path('travels/new/',views.travel_create,name='travel_create'),path('travels/<int:pk>/',views.travel_detail,name='travel_detail')]
