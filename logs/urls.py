from django.urls import path
from logs.views import export, logs

urlpatterns = [
  path('insulin/', logs.log_insulin, name='log-insulin'),
  path('insulin/add', logs.add_insulin, name='add-insulin'),
  path('insulin/<int:pk>/edit/', logs.add_insulin, name='edit-insulin'),
  path('insulin/<int:pk>/delete/', logs.delete_insulin_record, name='delete-insulin'),
  path('glucose/', logs.log_glucose, name='log-glucose'),
  path('glucose/add', logs.add_glucose, name='add-glucose'),
  path('glucose/<int:pk>/edit/', logs.add_glucose, name='edit-glucose'),
  path('glucose/<int:pk>/delete/', logs.delete_glucose_reading, name='delete-glucose'),
  path('meal/', logs.log_meal, name='log-meal'),
  path('meal/add', logs.add_meal, name='add-meal'),
  path('meal/<int:pk>/edit/', logs.add_meal, name='edit-meal'),
  path('meal/<int:pk>/delete/', logs.delete_meal_log, name='delete-meal'),
  path('export/', export.export_csv, name='export-csv'),
  
]