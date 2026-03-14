from django.urls import path
from finance.views import (
    RegisterView, DashboardView, TransactionCreateView, TransactionListView, 
    GoalListView, GoalCreateView, GoalDetailView, GoalContributeView,
    GoalCompleteView, GoalDeleteView,
    BudgetCreateView, BudgetEditView, export_transactions
)

urlpatterns = [
    path('register/', RegisterView.as_view(), name="register"),    
    path('', DashboardView.as_view(), name="dashboard"),
    path('transaction/add/', TransactionCreateView.as_view(), name='transaction_add'),
    path('transactions/', TransactionListView.as_view(), name='transaction_list'), 
    # Goal URLs
    path('goals/', GoalListView.as_view(), name='goal_list'),
    path('goals/add/', GoalCreateView.as_view(), name='goal_add'),
    path('goals/<int:pk>/', GoalDetailView.as_view(), name='goal_detail'),
    path('goals/<int:pk>/contribute/', GoalContributeView.as_view(), name='goal_contribute'),
    path('goals/<int:pk>/complete/', GoalCompleteView.as_view(), name='goal_complete'),
    path('goals/<int:pk>/delete/', GoalDeleteView.as_view(), name='goal_delete'),
    # Budget URLs
    path('budget/add/', BudgetCreateView.as_view(), name='budget_add'),
    path('budget/edit/', BudgetEditView.as_view(), name='budget_edit'),
    path('generate-report/', export_transactions, name='export_transactions'),
]
