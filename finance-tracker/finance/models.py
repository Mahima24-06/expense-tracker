from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from decimal import Decimal
from datetime import date

class Transaction(models.Model):
  TRANSACTION_TYPES = [
    ('Income', 'Income'),
    ('Expense', 'Expense')
  ]
  user = models.ForeignKey(User, on_delete=models.CASCADE)
  title = models.CharField(max_length=255)
  amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
  transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPES)
  date = models.DateField()
  category = models.CharField(max_length=255)

  def __str__(self):
    return self.title

class Budget(models.Model):
    PERIOD_CHOICES = [
        ('monthly', 'Monthly'),
        ('yearly', 'Yearly'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    period = models.CharField(max_length=10, choices=PERIOD_CHOICES, default='monthly')
    month = models.PositiveIntegerField(default=1)  # 1-12 for monthly budgets
    year = models.PositiveIntegerField(default=2024)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['user', 'period', 'month', 'year']
        ordering = ['-year', '-month']

    def __str__(self):
        if self.period == 'monthly':
            return f"{self.user.username}'s Budget - {self.get_month_name()} {self.year}"
        return f"{self.user.username}'s Budget - {self.year}"
    
    def get_month_name(self):
        months = ['', 'January', 'February', 'March', 'April', 'May', 'June',
                  'July', 'August', 'September', 'October', 'November', 'December']
        return months[self.month]

    def clean(self):
        if self.month < 1 or self.month > 12:
            raise ValidationError({'month': 'Month must be between 1 and 12.'})
        if self.year < 2000 or self.year > 2100:
            raise ValidationError({'year': 'Year must be between 2000 and 2100.'})

class Goal(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    target_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    current_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00')
    )
    deadline = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['deadline']

    def __str__(self):
        return self.name

    @property
    def progress_percentage(self):
        if self.target_amount > 0:
            return min((self.current_amount / self.target_amount) * 100, 100)
        return 0
    
    @property
    def remaining_amount(self):
        return max(self.target_amount - self.current_amount, Decimal('0.00'))
    
    @property
    def is_completed(self):
        return self.status == 'completed'
    
    @property
    def days_remaining(self):
        if self.deadline:
            delta = self.deadline - date.today()
            return max(delta.days, 0)
        return 0

    def clean(self):
        if self.deadline and self.deadline < date.today() and not self.pk:
            raise ValidationError({'deadline': 'Deadline cannot be in the past.'})


class GoalContribution(models.Model):
    """Track individual contributions to goals"""
    goal = models.ForeignKey(Goal, on_delete=models.CASCADE, related_name='contributions')
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Rs.{self.amount} to {self.goal.name}"