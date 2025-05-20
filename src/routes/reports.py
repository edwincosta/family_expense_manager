from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from src.models.user import db, Expense, Budget, Category, Family
from sqlalchemy import func, extract
import datetime

reports_bp = Blueprint("reports_bp", __name__)

@reports_bp.route("/reports/monthly_expenses", methods=["GET"])
@login_required
def get_monthly_expenses():
    family_id = request.args.get("family_id", type=int)
    year = request.args.get("year", type=int, default=datetime.date.today().year)
    month = request.args.get("month", type=int, default=datetime.date.today().month)

    if not family_id:
        return jsonify({"error": "family_id is required"}), 400

    family = Family.query.get(family_id)
    if not family or current_user not in family.members:
        return jsonify({"error": "User not authorized for this family or family not found"}), 403

    budget = Budget.query.filter_by(family_id=family_id, year=year, month=month).first()
    if not budget:
        return jsonify({"expenses": [], "total_spent": 0, "planned_budget": 0, "budget_id": None}), 200

    expenses = Expense.query.filter_by(budget_id=budget.id).order_by(Expense.expense_date.desc()).all()
    
    total_spent = db.session.query(func.sum(Expense.amount)).filter(Expense.budget_id == budget.id).scalar() or 0

    expenses_data = [
        {
            "id": exp.id,
            "description": exp.description,
            "amount": float(exp.amount),
            "expense_date": exp.expense_date.isoformat(),
            "category_id": exp.category_id,
            "category_name": exp.category.name if exp.category else None,
            "subcategory_id": exp.subcategory_id,
            "subcategory_name": exp.subcategory.name if exp.subcategory else None,
            "payment_type_id": exp.payment_type_id,
            "payment_type_name": exp.payment_type.name if exp.payment_type else None,
            "created_by": exp.created_by.username if exp.created_by else None,
            "updated_by": exp.updated_by.username if exp.updated_by else None,
            "created_at": exp.created_at.isoformat(),
            "updated_at": exp.updated_at.isoformat()
        } for exp in expenses
    ]
    return jsonify({
        "expenses": expenses_data, 
        "total_spent": float(total_spent),
        "planned_budget": float(budget.planned_amount),
        "budget_id": budget.id
    }), 200

@reports_bp.route("/reports/expenses_by_category", methods=["GET"])
@login_required
def get_expenses_by_category():
    family_id = request.args.get("family_id", type=int)
    year = request.args.get("year", type=int, default=datetime.date.today().year)
    month = request.args.get("month", type=int, default=datetime.date.today().month)
    category_id = request.args.get("category_id", type=int, default=None) # For subcategory drilldown

    if not family_id:
        return jsonify({"error": "family_id is required"}), 400

    family = Family.query.get(family_id)
    if not family or current_user not in family.members:
        return jsonify({"error": "User not authorized for this family or family not found"}), 403

    budget = Budget.query.filter_by(family_id=family_id, year=year, month=month).first()
    if not budget:
        return jsonify([]), 200

    query = db.session.query(
        Category.id,
        Category.name,
        func.sum(Expense.amount).label("total_amount")
    ).join(Expense, Expense.category_id == Category.id).filter(Expense.budget_id == budget.id)
    
    if category_id: # If a parent category is specified, get subcategories
        query = db.session.query(
            Category.id,
            Category.name,
            func.sum(Expense.amount).label("total_amount")
        ).join(Expense, Expense.subcategory_id == Category.id).filter(Expense.budget_id == budget.id, Category.parent_id == category_id)
    else: # Get top-level categories
        query = db.session.query(
            Category.id,
            Category.name,
            func.sum(Expense.amount).label("total_amount")
        ).join(Expense, Expense.category_id == Category.id).filter(Expense.budget_id == budget.id, Expense.subcategory_id == None) # Expenses directly under a category
        
        # Also include expenses that have subcategories, but sum them under their parent category for the main chart
        # This part might need refinement based on how exactly the user wants to see parent categories with subcategories summed up.
        # For simplicity now, the above query focuses on expenses directly linked to a category (no subcategory) or drills down.
        # A more complex query might be needed if the main category chart should sum up all its subcategories.
        # Let's refine the top-level category aggregation:
        query = (db.session.query(
            Category.id.label("category_id"),
            Category.name.label("category_name"),
            func.sum(Expense.amount).label("total_amount")
        ).select_from(Expense).join(Budget, Expense.budget_id == Budget.id)
        .join(Category, Expense.category_id == Category.id)
        .filter(Budget.family_id == family_id, Budget.year == year, Budget.month == month)
        .group_by(Category.id, Category.name))

    if category_id: # Drilldown for subcategories of the given category_id
        query = (db.session.query(
            Category.id.label("subcategory_id"),
            Category.name.label("subcategory_name"),
            func.sum(Expense.amount).label("total_amount")
        ).select_from(Expense).join(Budget, Expense.budget_id == Budget.id)
        .join(Category, Expense.subcategory_id == Category.id) # Join on subcategory_id
        .filter(Budget.family_id == family_id, Budget.year == year, Budget.month == month, Expense.category_id == category_id)
        .group_by(Category.id, Category.name))

    results = query.all()
    data_for_chart = [{"id": r[0], "name": r[1], "value": float(r[2])} for r in results]
    return jsonify(data_for_chart), 200

@reports_bp.route("/reports/expenses_evolution", methods=["GET"])
@login_required
def get_expenses_evolution():
    family_id = request.args.get("family_id", type=int)
    # Default to last 6 months including current
    num_months = request.args.get("months", type=int, default=6)

    if not family_id:
        return jsonify({"error": "family_id is required"}), 400

    family = Family.query.get(family_id)
    if not family or current_user not in family.members:
        return jsonify({"error": "User not authorized for this family or family not found"}), 403

    today = datetime.date.today()
    evolution_data = []

    for i in range(num_months -1, -1, -1): # Iterate from num_months-1 down to 0 for chronological order
        target_date = today - datetime.timedelta(days=i * 30) # Approximate month stepping
        # A more precise way to step months:
        current_month_calc = today.month - i
        current_year_calc = today.year
        while current_month_calc <= 0:
            current_month_calc += 12
            current_year_calc -= 1
        
        year = current_year_calc
        month = current_month_calc

        budget = Budget.query.filter_by(family_id=family_id, year=year, month=month).first()
        total_spent = 0
        planned_budget = 0
        if budget:
            total_spent = db.session.query(func.sum(Expense.amount)).filter(Expense.budget_id == budget.id).scalar() or 0
            planned_budget = budget.planned_amount
        
        evolution_data.append({
            "month": month,
            "year": year,
            "label": f"{month:02d}/{year}",
            "total_spent": float(total_spent),
            "planned_budget": float(planned_budget)
        })
    
    return jsonify(sorted(evolution_data, key=lambda x: (x["year"], x["month"])) ), 200 # Ensure sorted by date

@reports_bp.route("/reports/budget_vs_actual", methods=["GET"])
@login_required
def get_budget_vs_actual():
    family_id = request.args.get("family_id", type=int)
    year = request.args.get("year", type=int, default=datetime.date.today().year)
    month = request.args.get("month", type=int, default=datetime.date.today().month)

    if not family_id:
        return jsonify({"error": "family_id is required"}), 400

    family = Family.query.get(family_id)
    if not family or current_user not in family.members:
        return jsonify({"error": "User not authorized for this family or family not found"}), 403

    budget = Budget.query.filter_by(family_id=family_id, year=year, month=month).first()
    if not budget:
        return jsonify({"planned_budget": 0, "total_spent": 0, "difference": 0}), 200

    total_spent = db.session.query(func.sum(Expense.amount)).filter(Expense.budget_id == budget.id).scalar() or 0
    planned_amount = budget.planned_amount
    difference = planned_amount - total_spent

    return jsonify({
        "planned_budget": float(planned_amount),
        "total_spent": float(total_spent),
        "difference": float(difference)
    }), 200

@reports_bp.route("/reports/historical_summary", methods=["GET"])
@login_required
def get_historical_summary():
    family_id = request.args.get("family_id", type=int)
    if not family_id:
        return jsonify({"error": "family_id is required"}), 400

    family = Family.query.get(family_id)
    if not family or current_user not in family.members:
        return jsonify({"error": "User not authorized for this family or family not found"}), 403

    # Query all budgets for the family, ordered by year and month
    budgets = Budget.query.filter_by(family_id=family_id).order_by(Budget.year.desc(), Budget.month.desc()).all()
    summary = []
    for b in budgets:
        total_spent = db.session.query(func.sum(Expense.amount)).filter(Expense.budget_id == b.id).scalar() or 0
        total_credits = db.session.query(func.sum(Credit.amount)).filter(Credit.budget_id == b.id).scalar() or 0 # Assuming Credit model exists
        summary.append({
            "budget_id": b.id,
            "year": b.year,
            "month": b.month,
            "planned_amount": float(b.planned_amount),
            "total_spent": float(total_spent),
            "total_credits": float(total_credits),
            "balance": float(b.planned_amount + total_credits - total_spent)
        })
    return jsonify(summary), 200

