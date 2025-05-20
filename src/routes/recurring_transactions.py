from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from src.models.user import db, RecurringExpense, Expense, Budget, Category, PaymentType, Family
import datetime
from dateutil.relativedelta import relativedelta

recurring_expense_bp = Blueprint("recurring_expense_bp", __name__)

@recurring_expense_bp.route("/recurring_expense", methods=["POST"])
@login_required
def add_recurring_expense():
    data = request.get_json()
    try:
        required_fields = [
            "family_id", "category_id", "payment_type_id", "description", 
            "amount", "recurrence_type", "start_date"
        ]
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Missing required field: {field}"}), 400

        family = Family.query.get(data["family_id"])
        if not family or current_user not in family.members:
            return jsonify({"error": "User not authorized for this family or family not found"}), 403

        category = Category.query.filter_by(id=data["category_id"], family_id=data["family_id"]).first()
        if not category:
            return jsonify({"error": "Category not found or does not belong to this family"}), 400

        subcategory_id = data.get("subcategory_id")
        if subcategory_id:
            subcategory = Category.query.filter_by(id=subcategory_id, family_id=data["family_id"], parent_id=data["category_id"]).first()
            if not subcategory:
                return jsonify({"error": "Subcategory not found or invalid"}), 400
        
        payment_type = PaymentType.query.filter_by(id=data["payment_type_id"], family_id=data["family_id"]).first()
        if not payment_type:
            return jsonify({"error": "Payment type not found or does not belong to this family"}), 400

        start_date = datetime.datetime.strptime(data["start_date"], "%Y-%m-%d").date()
        end_date = datetime.datetime.strptime(data["end_date"], "%Y-%m-%d").date() if data.get("end_date") else None

        if data["recurrence_type"] not in ["weekly", "biweekly", "monthly"]:
            return jsonify({"error": "Invalid recurrence_type"}), 400
        
        day_of_week = data.get("day_of_week")
        day_of_month = data.get("day_of_month")

        if data["recurrence_type"] in ["weekly", "biweekly"] and day_of_week is None:
            return jsonify({"error": "day_of_week is required for weekly/biweekly recurrence"}), 400
        if data["recurrence_type"] == "monthly" and day_of_month is None:
            return jsonify({"error": "day_of_month is required for monthly recurrence"}), 400

        new_recurring_expense = RecurringExpense(
            family_id=data["family_id"],
            category_id=data["category_id"],
            subcategory_id=subcategory_id,
            payment_type_id=data["payment_type_id"],
            description=data["description"],
            amount=data["amount"],
            recurrence_type=data["recurrence_type"],
            start_date=start_date,
            end_date=end_date,
            day_of_week=day_of_week,
            day_of_month=day_of_month,
            created_by_user_id=current_user.id,
            updated_by_user_id=current_user.id
        )
        db.session.add(new_recurring_expense)
        db.session.commit()
        return jsonify({"message": "Recurring expense rule added successfully", "recurring_expense_id": new_recurring_expense.id}), 201

    except ValueError as ve:
        return jsonify({"error": f"Invalid data format: {str(ve)}"}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@recurring_expense_bp.route("/recurring_expense/<int:rule_id>", methods=["PUT"])
@login_required
def update_recurring_expense(rule_id):
    data = request.get_json()
    rule = RecurringExpense.query.get_or_404(rule_id)
    family = Family.query.get(rule.family_id)

    if not family or current_user not in family.members:
        return jsonify({"error": "User not authorized to update this rule"}), 403
    
    # Add logic to check if current_user has admin role for this family if needed

    try:
        if "category_id" in data:
            category = Category.query.filter_by(id=data["category_id"], family_id=family.id).first()
            if not category:
                return jsonify({"error": "Category not found or does not belong to this family"}), 400
            rule.category_id = data["category_id"]

        if "subcategory_id" in data:
            if data["subcategory_id"] is None:
                rule.subcategory_id = None
            else:
                subcategory = Category.query.filter_by(id=data["subcategory_id"], family_id=family.id, parent_id=rule.category_id).first()
                if not subcategory:
                    return jsonify({"error": "Subcategory not found or invalid"}), 400
                rule.subcategory_id = data["subcategory_id"]
        elif "category_id" in data and rule.subcategory_id is not None:
            current_subcategory = Category.query.get(rule.subcategory_id)
            if current_subcategory and current_subcategory.parent_id != rule.category_id:
                rule.subcategory_id = None

        if "payment_type_id" in data:
            payment_type = PaymentType.query.filter_by(id=data["payment_type_id"], family_id=family.id).first()
            if not payment_type:
                return jsonify({"error": "Payment type not found or does not belong to this family"}), 400
            rule.payment_type_id = data["payment_type_id"]

        for field in ["description", "amount", "recurrence_type", "day_of_week", "day_of_month"]:
            if field in data:
                setattr(rule, field, data[field])
        
        if "start_date" in data:
            rule.start_date = datetime.datetime.strptime(data["start_date"], "%Y-%m-%d").date()
        if "end_date" in data:
            rule.end_date = datetime.datetime.strptime(data["end_date"], "%Y-%m-%d").date() if data["end_date"] else None
        
        rule.updated_at = datetime.datetime.utcnow()
        rule.updated_by_user_id = current_user.id
        
        db.session.commit()
        return jsonify({"message": "Recurring expense rule updated successfully", "rule_id": rule.id}), 200

    except ValueError as ve:
        return jsonify({"error": f"Invalid data format: {str(ve)}"}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@recurring_expense_bp.route("/recurring_expense/<int:rule_id>", methods=["DELETE"])
@login_required
def delete_recurring_expense(rule_id):
    rule = RecurringExpense.query.get_or_404(rule_id)
    family = Family.query.get(rule.family_id)

    if not family or current_user not in family.members:
        return jsonify({"error": "User not authorized to delete this rule"}), 403
    
    # Add logic to check if current_user has admin role for this family if needed

    try:
        db.session.delete(rule)
        db.session.commit()
        return jsonify({"message": "Recurring expense rule deleted successfully"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@recurring_expense_bp.route("/recurring_expense/generate", methods=["POST"])
@login_required
def generate_recurring_expenses_for_month():
    data = request.get_json()
    try:
        required_fields = ["family_id", "year", "month"]
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Missing required field: {field}"}), 400

        family_id = data["family_id"]
        year = int(data["year"])
        month = int(data["month"])

        family = Family.query.get(family_id)
        if not family or current_user not in family.members:
            return jsonify({"error": "User not authorized for this family or family not found"}), 403
        
        # Add logic to check if current_user has admin role for this family if needed for generation

        budget = Budget.query.filter_by(family_id=family_id, year=year, month=month).first()
        if not budget:
            budget = Budget(family_id=family_id, year=year, month=month, planned_amount=0)
            db.session.add(budget)
            # db.session.commit() # Commit later with expenses

        rules = RecurringExpense.query.filter_by(family_id=family_id).all()
        generated_count = 0
        
        first_day_of_month = datetime.date(year, month, 1)
        if month == 12:
            last_day_of_month = datetime.date(year, month, 31)
        else:
            last_day_of_month = datetime.date(year, month + 1, 1) - datetime.timedelta(days=1)

        for rule in rules:
            if rule.start_date > last_day_of_month or (rule.end_date and rule.end_date < first_day_of_month):
                continue # Rule is not active in this month

            current_date = rule.start_date
            if rule.recurrence_type == "monthly":
                # Ensure day_of_month is valid for the target month
                actual_day_of_month = min(rule.day_of_month, (datetime.date(year, month + 1, 1) - datetime.timedelta(days=1)).day if month < 12 else 31)
                expense_date_for_month = datetime.date(year, month, actual_day_of_month)
                if (first_day_of_month <= expense_date_for_month <= last_day_of_month and
                   rule.start_date <= expense_date_for_month and
                   (not rule.end_date or expense_date_for_month <= rule.end_date)):
                    # Check if expense already exists for this rule and date
                    exists = Expense.query.filter_by(
                        budget_id=budget.id, 
                        description=f"Recurring: {rule.description}", 
                        amount=rule.amount, 
                        expense_date=expense_date_for_month,
                        # Could add a link to recurring_rule_id if model is extended
                    ).first()
                    if not exists:
                        new_expense = Expense(
                            budget_id=budget.id,
                            category_id=rule.category_id,
                            subcategory_id=rule.subcategory_id,
                            payment_type_id=rule.payment_type_id,
                            description=f"Recurring: {rule.description}",
                            amount=rule.amount,
                            expense_date=expense_date_for_month,
                            created_by_user_id=current_user.id,
                            updated_by_user_id=current_user.id
                        )
                        db.session.add(new_expense)
                        generated_count += 1
            
            elif rule.recurrence_type in ["weekly", "biweekly"]:
                interval = 1 if rule.recurrence_type == "weekly" else 2
                # Find the first occurrence in or after the rule's start_date
                temp_date = rule.start_date
                while temp_date.weekday() != rule.day_of_week:
                    temp_date += datetime.timedelta(days=1)
                
                # For biweekly, adjust if the first found date is in the wrong week of the 2-week cycle
                if rule.recurrence_type == "biweekly":
                    # This simple bi-weekly might need a more robust anchor date if strict bi-weekly periods are needed
                    # For now, it's every 2 weeks from the first valid day_of_week on or after start_date
                    pass # Assuming start_date itself or first valid day_of_week after it is the anchor

                current_occurrence_date = temp_date
                while current_occurrence_date <= last_day_of_month:
                    if (current_occurrence_date >= first_day_of_month and
                       (not rule.end_date or current_occurrence_date <= rule.end_date)):
                        exists = Expense.query.filter_by(
                            budget_id=budget.id, 
                            description=f"Recurring: {rule.description}", 
                            amount=rule.amount, 
                            expense_date=current_occurrence_date
                        ).first()
                        if not exists:
                            new_expense = Expense(
                                budget_id=budget.id,
                                category_id=rule.category_id,
                                subcategory_id=rule.subcategory_id,
                                payment_type_id=rule.payment_type_id,
                                description=f"Recurring: {rule.description}",
                                amount=rule.amount,
                                expense_date=current_occurrence_date,
                                created_by_user_id=current_user.id,
                                updated_by_user_id=current_user.id
                            )
                            db.session.add(new_expense)
                            generated_count += 1
                    current_occurrence_date += datetime.timedelta(weeks=interval)

        db.session.commit()
        return jsonify({"message": f"{generated_count} recurring expenses generated for {month}/{year}"}), 200

    except ValueError as ve:
        return jsonify({"error": f"Invalid data format: {str(ve)}"}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


