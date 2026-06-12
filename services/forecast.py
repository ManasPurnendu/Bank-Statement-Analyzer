from services.analytics import calculate_analytics
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

def generate_forecast(reduction_category=None, reduction_pct=0.0, horizon=3, start_date=None, end_date=None):
    """
    Generates 1, 3, 6, and 9-month projections using moving-average and trend analysis.
    Supports What-If scenario modifications and dynamic horizons.
    """
    analytics = calculate_analytics(start_date, end_date)
    monthly_trends = analytics["monthly_trends"]
    kpis = analytics["kpis"]
    category_spending = analytics["category_spending"]
    subscriptions = analytics["subscriptions"]
    
    # 1. Check if sufficient data exists
    if len(monthly_trends) < 2:
        return {
            "success": False,
            "message": "Forecast unavailable. At least 2 months of statement data are required."
        }
        
    # Build historical data frames
    m_df = pd.DataFrame(monthly_trends)
    
    # Store clean historical status (actual vs interpolated)
    historical_status = []
    for m in monthly_trends:
        if m["income"] is None:
            historical_status.append("interpolated")
        else:
            historical_status.append("actual")
            
    # Calculate historical averages on actual months only
    avg_income = m_df["income"].mean()
    avg_expense = m_df["expense"].mean()
    if pd.isna(avg_income):
        avg_income = 0.0
    if pd.isna(avg_expense):
        avg_expense = 0.0
        
    # Interpolate missing values in-place for forecast modeling and plotting
    m_df["income"] = m_df["income"].astype(float).interpolate(method="linear").ffill().bfill()
    m_df["expense"] = m_df["expense"].astype(float).interpolate(method="linear").ffill().bfill()
    m_df["savings"] = m_df["income"] - m_df["expense"]
    
    # Apply category reduction for What-If simulator
    # If reduction_category is set, we adjust historical average expense
    what_if_adjusted_saving = 0.0
    what_if_message = ""
    reduction_amount = 0.0
    
    if reduction_category and reduction_pct > 0:
        # Find category current spend
        target_cat = next((cat for cat in category_spending if cat["category_name"] == reduction_category), None)
        if target_cat:
            # Monthly category spend
            cat_monthly = target_cat["amount"] / len(monthly_trends)
            reduction_amount = cat_monthly * (reduction_pct / 100)
            avg_expense = avg_expense - reduction_amount
            what_if_adjusted_saving = reduction_amount
            what_if_message = f"Reducing {reduction_category} spend by {reduction_pct}% saves \u20b9 {reduction_amount:,.2f} per month!"

    # Trend calculation (Income & Expense growth rate)
    income_growth = 0.0
    expense_growth = 0.0
    
    if len(m_df) >= 3:
        # Calculate month-over-month growth rates and average them
        inc_growths = m_df["income"].pct_change().dropna()
        exp_growths = m_df["expense"].pct_change().dropna()
        # Cap growth rates to prevent unrealistic compounding (+/- 10% max)
        income_growth = np.clip(inc_growths.mean(), -0.1, 0.1)
        expense_growth = np.clip(exp_growths.mean(), -0.1, 0.1)

    # 2. Project future periods (up to 12 months to support 9 months horizon)
    last_month_str = m_df.iloc[-1]["month"]
    last_month_dt = datetime.strptime(last_month_str + "-01", "%Y-%m-%d")
    
    future_months = []
    # Baseline prioritizes the latest month's actual value to prevent step-change shocks
    latest_inc = m_df.iloc[-1]["income"]
    latest_exp = m_df.iloc[-1]["expense"]
    current_inc = (0.7 * latest_inc) + (0.3 * avg_income)
    current_exp = (0.7 * latest_exp) + (0.3 * (avg_expense + reduction_amount)) - reduction_amount
    current_bal = kpis["balance"]
    
    forecast_details = []
    for i in range(1, 13):
        proj_dt = last_month_dt + timedelta(days=i*31)
        # Avoid day calculation shifting (force 1st day of month)
        proj_dt = proj_dt.replace(day=1)
        month_label = proj_dt.strftime("%Y-%m")
        
        # Apply damped trend growth to prevent exponential growth/decay spikes over long horizons
        damping_factor = 0.8
        current_growth_inc = income_growth * (damping_factor ** (i - 1))
        current_growth_exp = expense_growth * (damping_factor ** (i - 1))
        current_inc = current_inc * (1 + current_growth_inc)
        current_exp = current_exp * (1 + current_growth_exp)
        
        # Forecast aggregates
        proj_income = float(current_inc)
        proj_expense = float(current_exp)
        proj_savings = proj_income - proj_expense
        proj_savings_rate = (proj_savings / proj_income * 100) if proj_income > 0 else 0.0
        current_bal += proj_savings
        
        forecast_details.append({
            "month": month_label,
            "projected_income": proj_income,
            "projected_expense": proj_expense,
            "projected_savings": proj_savings,
            "savings_rate": proj_savings_rate,
            "projected_balance": current_bal
        })
        
    # Calculate Summary KPIs for dynamic horizon
    proj_horizon_income = sum(f["projected_income"] for f in forecast_details[:horizon])
    proj_horizon_expense = sum(f["projected_expense"] for f in forecast_details[:horizon])
    proj_horizon_savings = proj_horizon_income - proj_horizon_expense
    proj_horizon_avg_saving_rate = (proj_horizon_savings / proj_horizon_income * 100) if proj_horizon_income > 0 else 0.0
    
    # Growth comparisons
    inc_horizon_change = (proj_horizon_income / horizon - avg_income) / avg_income * 100 if avg_income > 0 else 0.0
    exp_horizon_change = (proj_horizon_expense / horizon - avg_expense) / avg_expense * 100 if avg_expense > 0 else 0.0
    
    # 3. Upcoming Large Expenses
    # Large expenses: subscriptions, bills, or insurance that occur in specific months.
    upcoming_expenses = []
    # Identify active subscriptions next payment
    for sub in subscriptions:
        if sub["status"] == "Active":
            billing_dt = datetime.strptime(sub["next_billing"], "%Y-%m-%d")
            upcoming_expenses.append({
                "description": f"{sub['merchant_name']} ({sub['frequency']})",
                "expected_month": billing_dt.strftime("%b %Y"),
                "raw_date": billing_dt,
                "amount": sub["amount"]
            })
            

        
    upcoming_expenses.sort(key=lambda x: x["raw_date"])
    
    # Format and filter based on horizon months
    formatted_upcoming = []
    total_upcoming_amount = 0.0
    for item in upcoming_expenses:
        month_diff = (item["raw_date"].year - last_month_dt.year) * 12 + (item["raw_date"].month - last_month_dt.month)
        if 0 < month_diff <= horizon:
            total_upcoming_amount += item["amount"]
            formatted_upcoming.append({
                "description": item["description"],
                "expected_month": item["expected_month"],
                "amount": item["amount"]
            })
            if len(formatted_upcoming) >= 4:  # Cap at 4 items
                break
        
    # 4. Top Category Forecast (Next H Months)
    # Renders estimated spend by category in next H months based on historical percentages
    category_forecasts = []
    for cat in category_spending:
        proj_cat_spend = proj_horizon_expense * (cat["percentage"] / 100)
        hist_horizon_spend = (cat["amount"] / len(monthly_trends)) * horizon
        cat_change = (proj_cat_spend - hist_horizon_spend) / hist_horizon_spend * 100 if hist_horizon_spend > 0 else 0.0
        
        category_forecasts.append({
            "category_name": cat["category_name"],
            "projected_spend": float(proj_cat_spend),
            "percentage": cat["percentage"],
            "change": float(cat_change)
        })
    category_forecasts.sort(key=lambda x: x["projected_spend"], reverse=True)

    # 5. Recommendations
    recommendations = []
    if exp_horizon_change > 5:
        recommendations.append({
            "text": f"Your expenses are likely to increase by {exp_horizon_change:.1f}% in the next {horizon} months. Plan your budget accordingly.",
            "type": "warning",
            "icon": "bi-graph-up-arrow"
        })
    else:
        recommendations.append({
            "text": f"Your expenses are projected to remain stable over the next {horizon} months.",
            "type": "success",
            "icon": "bi-graph-down"
        })
        
    if reduction_category and reduction_pct > 0:
        recommendations.append({
            "text": f"What-If Success: Reducing {reduction_category} by {reduction_pct}% will increase savings by \u20b9 {reduction_amount:,.0f}/month.",
            "type": "success",
            "icon": "bi-calculator"
        })
    else:
        # Generic shopping recommendation
        shop_cat = next((c for c in category_spending if c["category_name"] == "Shopping"), None)
        if shop_cat and shop_cat["percentage"] > 20:
            recommendations.append({
                "text": f"Shopping expenses are projected to increase. Try setting a monthly limit of \u20b9 {(shop_cat['amount']/len(monthly_trends)*0.85):,.0f} (15% reduction).",
                "type": "shopping",
                "icon": "bi-cart"
            })
            
    # Savings Rate recommendation
    if proj_horizon_avg_saving_rate > 30:
        recommendations.append({
            "text": "Your savings rate is improving! Great job. Keep maintaining and try to invest your surplus.",
            "type": "savings",
            "icon": "bi-piggy-bank"
        })
    else:
        recommendations.append({
            "text": f"Try to maintain expenses below a strict threshold to reach a target 35% savings rate.",
            "type": "savings",
            "icon": "bi-bullseye"
        })
        
    if total_upcoming_amount > 20000:
        recommendations.append({
            "text": f"You have large upcoming expenses totaling \u20b9 {total_upcoming_amount:,.0f} soon. Ensure you have adequate liquidity.",
            "type": "bill",
            "icon": "bi-calendar-event"
        })

    # Prepare data for charts
    historical_months = m_df["month"].tolist()
    historical_incomes = m_df["income"].tolist()
    historical_expenses = m_df["expense"].tolist()
    historical_balances = []
    
    # Back-calculate historical balances for plotting if needed
    running_bal = kpis["balance"]
    for i in range(len(m_df)-1, -1, -1):
        historical_balances.insert(0, running_bal)
        running_bal -= (historical_incomes[i] - historical_expenses[i])
        
    # Chart dataset: merge historical + forecast_details matching the selected horizon
    active_forecast = forecast_details[:horizon]
    chart_months = historical_months + [f["month"] for f in active_forecast]
    chart_incomes = historical_incomes + [f["projected_income"] for f in active_forecast]
    chart_expenses = historical_expenses + [f["projected_expense"] for f in active_forecast]
    chart_savings = [historical_incomes[i] - historical_expenses[i] for i in range(len(m_df))] + [f["projected_savings"] for f in active_forecast]
    chart_balances = historical_balances + [f["projected_balance"] for f in active_forecast]
    chart_status = historical_status + ["projected"] * len(active_forecast)

    return {
        "success": True,
        "kpis": {
            "projected_income": float(proj_horizon_income),
            "projected_expense": float(proj_horizon_expense),
            "projected_savings": float(proj_horizon_savings),
            "savings_rate": float(proj_horizon_avg_saving_rate),
            "avg_monthly_income": float(proj_horizon_income / horizon),
            "avg_monthly_expense": float(proj_horizon_expense / horizon),
            "avg_monthly_savings": float(proj_horizon_savings / horizon),
            "income_change_pct": float(inc_horizon_change),
            "expense_change_pct": float(exp_horizon_change)
        },
        "forecast_details": active_forecast,
        "all_forecast": active_forecast,
        "category_forecasts": category_forecasts,
        "upcoming_expenses": formatted_upcoming,
        "total_upcoming_expenses": float(total_upcoming_amount),
        "recommendations": recommendations[:5],
        "what_if": {
            "adjusted_saving": float(what_if_adjusted_saving),
            "message": what_if_message
        },
        "chart_data": {
            "months": chart_months,
            "incomes": chart_incomes,
            "expenses": chart_expenses,
            "savings": chart_savings,
            "balances": chart_balances,
            "status": chart_status,
            "historical_count": len(historical_months)
        }
    }
