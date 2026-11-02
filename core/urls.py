from django.urls import path
from . import views
app_name='core'
urlpatterns=[path('',views.home,name='home'),path('travels/new/',views.travel_create,name='travel_create'),path('travels/<int:pk>/',views.travel_detail,name='travel_detail')]
