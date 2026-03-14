from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from finance.models import Transaction, Goal, Budget
from django.core.exceptions import ValidationError
from decimal import Decimal
from datetime import date

class RegisterForm(UserCreationForm):
    email = forms.EmailField()
    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']

class TransactionForm(forms.ModelForm):
    class Meta:
        model = Transaction
        fields = ['title', 'amount', 'transaction_type', 'date', 'category']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
        }
    
    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount is None or amount <= 0:
            raise ValidationError('Amount must be greater than zero.')
        if amount > Decimal('9999999.99'):
            raise ValidationError('Amount cannot exceed Rs.9,999,999.99.')
        return amount
    
    def clean_title(self):
        title = self.cleaned_data.get('title')
        if title and len(title.strip()) < 2:
            raise ValidationError('Title must be at least 2 characters long.')
        return title.strip()
    
    def clean_category(self):
        category = self.cleaned_data.get('category')
        if category and category.lower() == 'goal':
            raise ValidationError('"Goal" is a reserved category. Please use a different category name.')
        return category

class BudgetForm(forms.ModelForm):
    class Meta:
        model = Budget
        fields = ['amount', 'period', 'month', 'year']
        widgets = {
            'month': forms.Select(choices=[
                (1, 'January'), (2, 'February'), (3, 'March'), (4, 'April'),
                (5, 'May'), (6, 'June'), (7, 'July'), (8, 'August'),
                (9, 'September'), (10, 'October'), (11, 'November'), (12, 'December')
            ]),
            'year': forms.NumberInput(attrs={'min': 2000, 'max': 2100}),
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        # Set default values to current month/year
        today = date.today()
        if not self.instance.pk:
            self.fields['month'].initial = today.month
            self.fields['year'].initial = today.year
    
    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount is None or amount <= 0:
            raise ValidationError('Budget amount must be greater than zero.')
        if amount > Decimal('9999999.99'):
            raise ValidationError('Budget amount cannot exceed $9,999,999.99.')
        return amount

    def clean(self):
        cleaned_data = super().clean()
        period = cleaned_data.get('period')
        month = cleaned_data.get('month')
        year = cleaned_data.get('year')
        
        if self.user and period and month and year:
            # Check for duplicate budget
            existing = Budget.objects.filter(
                user=self.user,
                period=period,
                month=month,
                year=year
            )
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                raise ValidationError(
                    f'A {period} budget for this period already exists. Please edit the existing budget.'
                )
        return cleaned_data

class GoalForm(forms.ModelForm):
    class Meta:
        model = Goal
        fields = ['name', 'target_amount', 'deadline']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500',
                'placeholder': 'e.g., New Car Fund, Emergency Savings'
            }),
            'target_amount': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500',
                'placeholder': '10000.00',
                'step': '0.01',
                'min': '0.01'
            }),
            'deadline': forms.DateInput(attrs={
                'type': 'date',
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
    
    def clean_name(self):
        name = self.cleaned_data.get('name')
        if name and len(name.strip()) < 2:
            raise ValidationError('Goal name must be at least 2 characters long.')
        if name and len(name) > 100:
            raise ValidationError('Goal name cannot exceed 100 characters.')
        
        # Check for duplicate goal names for the same user
        if self.user and name:
            existing = Goal.objects.filter(user=self.user, name__iexact=name.strip(), status='active')
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                raise ValidationError('You already have an active goal with this name.')
        return name.strip()
    
    def clean_target_amount(self):
        amount = self.cleaned_data.get('target_amount')
        if amount is None or amount <= 0:
            raise ValidationError('Target amount must be greater than zero.')
        if amount > Decimal('9999999.99'):
            raise ValidationError('Target amount cannot exceed Rs.9,999,999.99.')
        return amount
    
    def clean_deadline(self):
        deadline = self.cleaned_data.get('deadline')
        if deadline and deadline < date.today():
            raise ValidationError('Deadline cannot be in the past.')
        return deadline