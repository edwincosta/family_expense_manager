from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import datetime

db = SQLAlchemy()

# Association table for User and Family (many-to-many)
family_members = db.Table('family_members',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('family_id', db.Integer, db.ForeignKey('family.id'), primary_key=True),
    db.Column('role', db.String(50), nullable=False, default='member') # e.g., 'admin', 'member'
)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    # Relationship to families they are part of
    families = db.relationship('Family', secondary=family_members,
                               lazy='subquery', backref=db.backref('members', lazy=True))

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username}>'

class Family(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True) # Name of the family or budget group
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    # Relationships
    budgets = db.relationship('Budget', backref='family', lazy=True, cascade="all, delete-orphan")
    categories = db.relationship('Category', backref='family', lazy=True, cascade="all, delete-orphan")
    payment_types = db.relationship('PaymentType', backref='family', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f'<Family {self.name}>'

class Budget(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    family_id = db.Column(db.Integer, db.ForeignKey('family.id'), nullable=False)
    month = db.Column(db.Integer, nullable=False) # 1-12
    year = db.Column(db.Integer, nullable=False)
    planned_amount = db.Column(db.Numeric(10, 2), nullable=False, default=0.00)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    # Relationships
    expenses = db.relationship('Expense', backref='budget', lazy=True)
    credits = db.relationship('Credit', backref='budget', lazy=True)

    __table_args__ = (db.UniqueConstraint('family_id', 'month', 'year', name='uq_family_month_year'),)

    def __repr__(self):
        return f'<Budget {self.family_id} - {self.month}/{self.year}>'

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    family_id = db.Column(db.Integer, db.ForeignKey('family.id'), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=True) # For subcategories
    subcategories = db.relationship('Category', backref=db.backref('parent', remote_side=[id]), lazy='dynamic')
    expenses = db.relationship('Expense', backref='category', lazy=True)

    __table_args__ = (db.UniqueConstraint('family_id', 'name', 'parent_id', name='uq_family_category_name'),)

    def __repr__(self):
        return f'<Category {self.name}>'

class PaymentType(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    family_id = db.Column(db.Integer, db.ForeignKey('family.id'), nullable=False)
    expenses = db.relationship('Expense', backref='payment_type', lazy=True)

    __table_args__ = (db.UniqueConstraint('family_id', 'name', name='uq_family_payment_type_name'),)

    def __repr__(self):
        return f'<PaymentType {self.name}>'

class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    budget_id = db.Column(db.Integer, db.ForeignKey('budget.id'), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)
    subcategory_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=True)
    payment_type_id = db.Column(db.Integer, db.ForeignKey('payment_type.id'), nullable=False)
    description = db.Column(db.String(255), nullable=True)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    expense_date = db.Column(db.Date, nullable=False, default=datetime.date.today)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    updated_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    created_by = db.relationship('User', foreign_keys=[created_by_user_id])
    updated_by = db.relationship('User', foreign_keys=[updated_by_user_id])

    def __repr__(self):
        return f'<Expense {self.description} - {self.amount}>'

class Credit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    budget_id = db.Column(db.Integer, db.ForeignKey('budget.id'), nullable=False)
    description = db.Column(db.String(255), nullable=True)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    credit_date = db.Column(db.Date, nullable=False, default=datetime.date.today)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    updated_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    created_by = db.relationship('User', foreign_keys=[created_by_user_id])
    updated_by = db.relationship('User', foreign_keys=[updated_by_user_id])

    def __repr__(self):
        return f'<Credit {self.description} - {self.amount}>'

class RecurringExpense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    family_id = db.Column(db.Integer, db.ForeignKey('family.id'), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)
    subcategory_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=True)
    payment_type_id = db.Column(db.Integer, db.ForeignKey('payment_type.id'), nullable=False)
    description = db.Column(db.String(255), nullable=True)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    recurrence_type = db.Column(db.String(20), nullable=False)  # 'weekly', 'biweekly', 'monthly'
    start_date = db.Column(db.Date, nullable=False, default=datetime.date.today)
    end_date = db.Column(db.Date, nullable=True) # Optional end date
    day_of_week = db.Column(db.Integer, nullable=True) # For weekly/biweekly (0=Monday, 6=Sunday)
    day_of_month = db.Column(db.Integer, nullable=True) # For monthly (1-31)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    updated_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    family = db.relationship('Family', backref='recurring_expenses')
    category_rel = db.relationship('Category', foreign_keys=[category_id])
    subcategory_rel = db.relationship('Category', foreign_keys=[subcategory_id])
    payment_type_rel = db.relationship('PaymentType', foreign_keys=[payment_type_id])
    created_by = db.relationship('User', foreign_keys=[created_by_user_id])
    updated_by = db.relationship('User', foreign_keys=[updated_by_user_id])

    def __repr__(self):
        return f'<RecurringExpense {self.description} - {self.amount}>'

