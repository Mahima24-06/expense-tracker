from django.shortcuts import render, redirect, HttpResponse
from django.views import View
from finance.forms import RegisterForm, TransactionForm, GoalForm, BudgetForm
from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin
from .models import Transaction, Goal, Budget, GoalContribution
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Sum
from .admin import TransactionResource
from django.contrib import messages
from datetime import date, timedelta
from decimal import Decimal
from collections import defaultdict
import json

def get_budget_summary(user):
    """Helper function to get budget summary for a user."""
    today = date.today()
    
    # Get current month's budget
    current_budget = Budget.objects.filter(
        user=user,
        period='monthly',
        month=today.month,
        year=today.year
    ).first()
    
    # Calculate income and expenses for current month
    month_start = date(today.year, today.month, 1)
    
    monthly_income = Transaction.objects.filter(
        user=user,
        transaction_type='Income',
        date__gte=month_start,
        date__lte=today
    ).aggregate(Sum('amount'))['amount__sum'] or Decimal('0')
    
    monthly_expense = Transaction.objects.filter(
        user=user,
        transaction_type='Expense',
        date__gte=month_start,
        date__lte=today
    ).aggregate(Sum('amount'))['amount__sum'] or Decimal('0')
    
    # Calculate total goals amount
    total_goals_amount = Goal.objects.filter(user=user).aggregate(
        Sum('target_amount'))['target_amount__sum'] or Decimal('0')
    
    # Calculate overall totals
    total_income = Transaction.objects.filter(
        user=user, transaction_type='Income'
    ).aggregate(Sum('amount'))['amount__sum'] or Decimal('0')
    
    total_expense = Transaction.objects.filter(
        user=user, transaction_type='Expense'
    ).aggregate(Sum('amount'))['amount__sum'] or Decimal('0')
    
    net_savings = total_income - total_expense
    
    # Available for new goals (savings minus existing goals)
    available_for_goals = max(net_savings - total_goals_amount, Decimal('0'))
    
    budget_amount = current_budget.amount if current_budget else Decimal('0')
    budget_used = monthly_expense
    budget_remaining = budget_amount - budget_used if current_budget else Decimal('0')
    budget_used_percentage = (budget_used / budget_amount * 100) if budget_amount > 0 else 0
    
    return {
        'current_budget': current_budget,
        'budget_amount': budget_amount,
        'budget_used': budget_used,
        'budget_remaining': budget_remaining,
        'budget_used_percentage': min(budget_used_percentage, 100),
        'monthly_income': monthly_income,
        'monthly_expense': monthly_expense,
        'total_income': total_income,
        'total_expense': total_expense,
        'net_savings': net_savings,
        'total_goals_amount': total_goals_amount,
        'available_for_goals': available_for_goals,
    }

class RegisterView(View):
    def get(self, request, *args, **kwargs):
        form = RegisterForm()
        return render(request, 'finance/register.html', {'form': form})
    
    def post(self, request, *args, **kwargs):
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Account created successfully!')
            return redirect('dashboard')
        return render(request, 'finance/register.html', {'form': form})

class DashboardView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        transactions = Transaction.objects.filter(user=request.user).order_by('-date')
        goals = Goal.objects.filter(user=request.user, status='active')[:5]  # Show only active goals, limit to 5
        
        # Get budget summary
        budget_summary = get_budget_summary(request.user)
        
        net_savings = budget_summary['net_savings']
        
        # Use the new goal model's built-in progress tracking
        goal_progress = [{'goal': goal} for goal in goals]
        
        # ===== CHART DATA =====
        # Bar Chart: Transactions by date (last 30 days)
        today = date.today()
        thirty_days_ago = today - timedelta(days=30)
        
        # Get transactions for last 30 days
        recent_transactions = Transaction.objects.filter(
            user=request.user,
            date__gte=thirty_days_ago,
            date__lte=today
        ).order_by('date')
        
        # Aggregate by date
        daily_income = defaultdict(lambda: Decimal('0'))
        daily_expense = defaultdict(lambda: Decimal('0'))
        
        for txn in recent_transactions:
            date_str = txn.date.strftime('%Y-%m-%d')
            if txn.transaction_type == 'Income':
                daily_income[date_str] += txn.amount
            else:
                daily_expense[date_str] += txn.amount
        
        # Create sorted date labels for the last 30 days
        date_labels = []
        income_data = []
        expense_data = []
        
        for i in range(30, -1, -1):
            d = today - timedelta(days=i)
            date_str = d.strftime('%Y-%m-%d')
            display_date = d.strftime('%d %b')
            date_labels.append(display_date)
            income_data.append(float(daily_income.get(date_str, 0)))
            expense_data.append(float(daily_expense.get(date_str, 0)))
        
        # Pie Chart: Category-wise expenses
        category_expenses = Transaction.objects.filter(
            user=request.user,
            transaction_type='Expense'
        ).values('category').annotate(
            total=Sum('amount')
        ).order_by('-total')
        
        category_labels = [item['category'] for item in category_expenses]
        category_data = [float(item['total']) for item in category_expenses]
        
        # Recent transactions for the list (limit to 5)
        recent_txn_list = transactions[:5]
        
        context = {
            'transactions': transactions,
            'recent_transactions': recent_txn_list,
            'total_income': budget_summary['total_income'],
            'total_expense': budget_summary['total_expense'],
            'net_savings': net_savings,
            'goal_progress': goal_progress,
            # Budget tracking data
            'current_budget': budget_summary['current_budget'],
            'budget_amount': budget_summary['budget_amount'],
            'budget_used': budget_summary['budget_used'],
            'budget_remaining': budget_summary['budget_remaining'],
            'budget_used_percentage': budget_summary['budget_used_percentage'],
            'monthly_income': budget_summary['monthly_income'],
            'monthly_expense': budget_summary['monthly_expense'],
            # Chart data (as JSON)
            'date_labels': json.dumps(date_labels),
            'income_data': json.dumps(income_data),
            'expense_data': json.dumps(expense_data),
            'category_labels': json.dumps(category_labels),
            'category_data': json.dumps(category_data),
            # Stats
            'transaction_count': transactions.count(),
            'goal_count': goals.count(),
        }
        return render(request, 'finance/dashboard.html', context)

class TransactionCreateView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        form = TransactionForm()
        return render(request, 'finance/transaction_form.html', {'form': form})
    
    def post(self, request, *args, **kwargs):
        form = TransactionForm(request.POST)
        if form.is_valid():
            transaction = form.save(commit=False)
            transaction.user = request.user
            transaction.save()
            messages.success(request, 'Transaction added successfully!')
            return redirect('dashboard')
        return render(request, 'finance/transaction_form.html', {'form': form})

class TransactionListView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        transactions = Transaction.objects.filter(user=request.user)
        return render(request, 'finance/transaction_list.html', {'transactions': transactions})

class BudgetCreateView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        form = BudgetForm(user=request.user)
        budget_summary = get_budget_summary(request.user)
        context = {
            'form': form,
            **budget_summary,
        }
        return render(request, 'finance/budget_form.html', context)
    
    def post(self, request, *args, **kwargs):
        form = BudgetForm(request.POST, user=request.user)
        if form.is_valid():
            budget = form.save(commit=False)
            budget.user = request.user
            budget.save()
            messages.success(request, 'Budget set successfully!')
            return redirect('dashboard')
        budget_summary = get_budget_summary(request.user)
        context = {
            'form': form,
            **budget_summary,
        }
        return render(request, 'finance/budget_form.html', context)

class BudgetEditView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        today = date.today()
        budget = Budget.objects.filter(
            user=request.user,
            period='monthly',
            month=today.month,
            year=today.year
        ).first()
        
        if not budget:
            messages.info(request, 'No budget found for current month. Create one first.')
            return redirect('budget_add')
        
        form = BudgetForm(instance=budget, user=request.user)
        budget_summary = get_budget_summary(request.user)
        context = {
            'form': form,
            'editing': True,
            **budget_summary,
        }
        return render(request, 'finance/budget_form.html', context)
    
    def post(self, request, *args, **kwargs):
        today = date.today()
        budget = Budget.objects.filter(
            user=request.user,
            period='monthly',
            month=today.month,
            year=today.year
        ).first()
        
        if not budget:
            return redirect('budget_add')
        
        form = BudgetForm(request.POST, instance=budget, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Budget updated successfully!')
            return redirect('dashboard')
        budget_summary = get_budget_summary(request.user)
        context = {
            'form': form,
            'editing': True,
            **budget_summary,
        }
        return render(request, 'finance/budget_form.html', context)

class GoalListView(LoginRequiredMixin, View):
    """List all goals with their progress"""
    def get(self, request, *args, **kwargs):
        goals = Goal.objects.filter(user=request.user)
        active_goals = goals.filter(status='active')
        completed_goals = goals.filter(status='completed')
        
        # Calculate totals
        total_target = sum(g.target_amount for g in active_goals)
        total_saved = sum(g.current_amount for g in active_goals)
        
        context = {
            'active_goals': active_goals,
            'completed_goals': completed_goals,
            'total_target': total_target,
            'total_saved': total_saved,
            'goals_count': active_goals.count(),
        }
        return render(request, 'finance/goal_list.html', context)


class GoalCreateView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        form = GoalForm(user=request.user)
        return render(request, 'finance/goal_form.html', {'form': form})
    
    def post(self, request, *args, **kwargs):
        form = GoalForm(request.POST, user=request.user)
        if form.is_valid():
            goal = form.save(commit=False)
            goal.user = request.user
            goal.save()
            messages.success(request, 'Goal created successfully!')
            return redirect('goal_list')
        return render(request, 'finance/goal_form.html', {'form': form})


def get_available_savings(user):
    """Calculate available savings (total income - total expenses)"""
    total_income = Transaction.objects.filter(
        user=user, transaction_type='Income'
    ).aggregate(Sum('amount'))['amount__sum'] or Decimal('0')
    
    total_expense = Transaction.objects.filter(
        user=user, transaction_type='Expense'
    ).aggregate(Sum('amount'))['amount__sum'] or Decimal('0')
    
    return max(total_income - total_expense, Decimal('0'))


class GoalDetailView(LoginRequiredMixin, View):
    """View goal details and add contributions"""
    def get(self, request, pk, *args, **kwargs):
        goal = get_object_or_404(Goal, pk=pk, user=request.user)
        contributions = goal.contributions.all()[:10]
        available_savings = get_available_savings(request.user)
        
        context = {
            'goal': goal,
            'contributions': contributions,
            'available_savings': available_savings,
        }
        return render(request, 'finance/goal_detail.html', context)


class GoalContributeView(LoginRequiredMixin, View):
    """Add contribution to a goal - creates an expense transaction"""
    def post(self, request, pk, *args, **kwargs):
        goal = get_object_or_404(Goal, pk=pk, user=request.user)
        
        if goal.status != 'active':
            messages.error(request, 'Cannot contribute to a completed or cancelled goal.')
            return redirect('goal_detail', pk=pk)
        
        try:
            amount = Decimal(request.POST.get('amount', '0'))
            note = request.POST.get('note', '')
            
            if amount <= 0:
                messages.error(request, 'Please enter a valid amount.')
                return redirect('goal_detail', pk=pk)
            
            # Check available savings
            available_savings = get_available_savings(request.user)
            if amount > available_savings:
                messages.error(request, f'Insufficient savings. You have Rs.{available_savings:.2f} available.')
                return redirect('goal_detail', pk=pk)
            
            # Create an expense transaction for the goal contribution
            Transaction.objects.create(
                user=request.user,
                title=f'Goal: {goal.name}' + (f' - {note}' if note else ''),
                amount=amount,
                transaction_type='Expense',
                date=date.today(),
                category='Goal'
            )
            
            # Create contribution record
            GoalContribution.objects.create(
                goal=goal,
                amount=amount,
                note=note
            )
            
            # Update goal's current amount
            goal.current_amount += amount
            
            # Auto-complete if target reached
            if goal.current_amount >= goal.target_amount:
                goal.status = 'completed'
                goal.completed_at = timezone.now()
                messages.success(request, f'Congratulations! You have completed your goal "{goal.name}"!')
            else:
                messages.success(request, f'Rs.{amount} added to "{goal.name}"!')
            
            goal.save()
            
        except (ValueError, TypeError):
            messages.error(request, 'Invalid amount.')
        
        return redirect('goal_detail', pk=pk)


class GoalCompleteView(LoginRequiredMixin, View):
    """Mark a goal as completed"""
    def post(self, request, pk, *args, **kwargs):
        goal = get_object_or_404(Goal, pk=pk, user=request.user)
        
        if goal.status == 'active':
            goal.status = 'completed'
            goal.completed_at = timezone.now()
            goal.save()
            messages.success(request, f'Goal "{goal.name}" marked as completed!')
        
        return redirect('goal_list')


class GoalDeleteView(LoginRequiredMixin, View):
    """Delete a goal"""
    def post(self, request, pk, *args, **kwargs):
        goal = get_object_or_404(Goal, pk=pk, user=request.user)
        goal_name = goal.name
        goal.delete()
        messages.success(request, f'Goal "{goal_name}" has been deleted.')
        return redirect('goal_list')

def export_transactions(request):
    user_transactions = Transaction.objects.filter(user=request.user)
    
    transactions_resource = TransactionResource()
    dataset = transactions_resource.export(queryset=user_transactions)
    
    excel_data = dataset.export('xlsx')
    
    # Create an HttpResponse with the correct MIME type for an Excel file
    response = HttpResponse(excel_data, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    
    # Set the header for downloading the file
    response['Content-Disposition'] = 'attachment; filename=transactions_report.xlsx'
    return response

