from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from src.models.user import db, Expense, Credit, Budget, Category, PaymentType, Family
import datetime

expense_bp = Blueprint("expense_bp", __name__)

@expense_bp.route("/expense", methods=["POST"])
@login_required
def add_expense():
    data = request.get_json()
    try:
        # Validate required fields
        required_fields = ["family_id", "year", "month", "category_id", "payment_type_id", "description", "amount", "expense_date"]
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Missing required field: {field}"}), 400

        # Check if user is part of the family
        family = Family.query.get(data["family_id"])
        if not family or current_user not in family.members:
            return jsonify({"error": "User not authorized for this family or family not found"}), 403

        # Find or create budget for the month
        budget = Budget.query.filter_by(family_id=data["family_id"], year=data["year"], month=data["month"]).first()
        if not budget:
            budget = Budget(
                family_id=data["family_id"],
                year=data["year"],
                month=data["month"],
                planned_amount=0 # Default planned amount, can be set elsewhere
            )
            db.session.add(budget)
            # db.session.commit() # Commit later with expense

        # Validate category
        category = Category.query.filter_by(id=data["category_id"], family_id=data["family_id"]).first()
        if not category:
            return jsonify({"error": "Category not found or does not belong to this family"}), 400

        # Validate subcategory if provided
        subcategory_id = data.get("subcategory_id")
        if subcategory_id:
            subcategory = Category.query.filter_by(id=subcategory_id, family_id=data["family_id"], parent_id=data["category_id"]).first()
            if not subcategory:
                return jsonify({"error": "Subcategory not found, does not belong to this family, or is not a child of the selected category"}), 400
        
        # Validate payment type
        payment_type = PaymentType.query.filter_by(id=data["payment_type_id"], family_id=data["family_id"]).first()
        if not payment_type:
            return jsonify({"error": "Payment type not found or does not belong to this family"}), 400

        new_expense = Expense(
            budget_id=budget.id, # Will be set after budget is committed if new
            category_id=data["category_id"],
            subcategory_id=data.get("subcategory_id"),
            payment_type_id=data["payment_type_id"],
            description=data["description"],
            amount=data["amount"],
            expense_date=datetime.datetime.strptime(data["expense_date"], "%Y-%m-%d").date(),
            created_by_user_id=current_user.id,
            updated_by_user_id=current_user.id
        )
        db.session.add(new_expense)
        db.session.commit()
        return jsonify({"message": "Expense added successfully", "expense_id": new_expense.id}), 201

    except ValueError as ve:
        return jsonify({"error": f"Invalid data format: {str(ve)}"}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@expense_bp.route("/expense/<int:expense_id>", methods=["PUT"])
@login_required
def update_expense(expense_id):
    data = request.get_json()
    expense = Expense.query.get_or_404(expense_id)
    budget = Budget.query.get(expense.budget_id)
    family = Family.query.get(budget.family_id)

    if not family or current_user not in family.members:
        return jsonify({"error": "User not authorized to update this expense"}), 403

    try:
        if "category_id" in data:
            category = Category.query.filter_by(id=data["category_id"], family_id=family.id).first()
            if not category:
                return jsonify({"error": "Category not found or does not belong to this family"}), 400
            expense.category_id = data["category_id"]
        
        if "subcategory_id" in data:
            if data["subcategory_id"] is None:
                expense.subcategory_id = None
            else:
                subcategory = Category.query.filter_by(id=data["subcategory_id"], family_id=family.id, parent_id=expense.category_id).first()
                if not subcategory:
                    return jsonify({"error": "Subcategory not found, does not belong to this family, or is not a child of the selected category"}), 400
                expense.subcategory_id = data["subcategory_id"]
        elif "category_id" in data and expense.subcategory_id is not None: # if category changed, subcategory might be invalid
             # Check if current subcategory is still valid for the new category
            current_subcategory = Category.query.get(expense.subcategory_id)
            if current_subcategory and current_subcategory.parent_id != expense.category_id:
                expense.subcategory_id = None # or return error, or ask user to re-select

        if "payment_type_id" in data:
            payment_type = PaymentType.query.filter_by(id=data["payment_type_id"], family_id=family.id).first()
            if not payment_type:
                return jsonify({"error": "Payment type not found or does not belong to this family"}), 400
            expense.payment_type_id = data["payment_type_id"]

        if "description" in data:
            expense.description = data["description"]
        if "amount" in data:
            expense.amount = data["amount"]
        if "expense_date" in data:
            expense.expense_date = datetime.datetime.strptime(data["expense_date"], "%Y-%m-%d").date()
        
        expense.updated_at = datetime.datetime.utcnow()
        expense.updated_by_user_id = current_user.id
        
        db.session.commit()
        return jsonify({"message": "Expense updated successfully", "expense_id": expense.id}), 200

    except ValueError as ve:
        return jsonify({"error": f"Invalid data format: {str(ve)}"}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@expense_bp.route("/expense/<int:expense_id>", methods=["DELETE"])
@login_required
def delete_expense(expense_id):
    expense = Expense.query.get_or_404(expense_id)
    budget = Budget.query.get(expense.budget_id)
    family = Family.query.get(budget.family_id)

    if not family or current_user not in family.members:
         # More granular permission check might be needed here (e.g. only creator or family admin can delete)
        return jsonify({"error": "User not authorized to delete this expense"}), 403
    
    try:
        db.session.delete(expense)
        db.session.commit()
        return jsonify({"message": "Expense deleted successfully"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

credit_bp = Blueprint("credit_bp", __name__)

@credit_bp.route("/credit", methods=["POST"])
@login_required
def add_credit():
    data = request.get_json()
    try:
        required_fields = ["family_id", "year", "month", "description", "amount", "credit_date"]
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Missing required field: {field}"}), 400

        family = Family.query.get(data["family_id"])
        if not family or current_user not in family.members:
            return jsonify({"error": "User not authorized for this family or family not found"}), 403

        budget = Budget.query.filter_by(family_id=data["family_id"], year=data["year"], month=data["month"]).first()
        if not budget:
            budget = Budget(
                family_id=data["family_id"],
                year=data["year"],
                month=data["month"],
                planned_amount=0 
            )
            db.session.add(budget)

        new_credit = Credit(
            budget_id=budget.id,
            description=data["description"],
            amount=data["amount"],
            credit_date=datetime.datetime.strptime(data["credit_date"], "%Y-%m-%d").date(),
            created_by_user_id=current_user.id,
            updated_by_user_id=current_user.id
        )
        db.session.add(new_credit)
        db.session.commit()
        return jsonify({"message": "Credit added successfully", "credit_id": new_credit.id}), 201

    except ValueError as ve:
        return jsonify({"error": f"Invalid data format: {str(ve)}"}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@credit_bp.route("/credit/<int:credit_id>", methods=["PUT"])
@login_required
def update_credit(credit_id):
    data = request.get_json()
    credit = Credit.query.get_or_404(credit_id)
    budget = Budget.query.get(credit.budget_id)
    family = Family.query.get(budget.family_id)

    if not family or current_user not in family.members:
        return jsonify({"error": "User not authorized to update this credit"}), 403

    try:
        if "description" in data:
            credit.description = data["description"]
        if "amount" in data:
            credit.amount = data["amount"]
        if "credit_date" in data:
            credit.credit_date = datetime.datetime.strptime(data["credit_date"], "%Y-%m-%d").date()
        
        credit.updated_at = datetime.datetime.utcnow()
        credit.updated_by_user_id = current_user.id
        
        db.session.commit()
        return jsonify({"message": "Credit updated successfully", "credit_id": credit.id}), 200

    except ValueError as ve:
        return jsonify({"error": f"Invalid data format: {str(ve)}"}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@credit_bp.route("/credit/<int:credit_id>", methods=["DELETE"])
@login_required
def delete_credit(credit_id):
    credit = Credit.query.get_or_404(credit_id)
    budget = Budget.query.get(credit.budget_id)
    family = Family.query.get(budget.family_id)

    if not family or current_user not in family.members:
        return jsonify({"error": "User not authorized to delete this credit"}), 403
    
    try:
        db.session.delete(credit)
        db.session.commit()
        return jsonify({"message": "Credit deleted successfully"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

