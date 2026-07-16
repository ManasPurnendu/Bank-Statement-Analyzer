from services.analytics import calculate_analytics
import pandas as pd

def generate_insights(analytics_data=None):
    """
    Evaluates rule-based logic on analytics data and generates text insights.
    """
    if analytics_data is None:
        analytics_data = calculate_analytics()
        
    kpis = analytics_data["kpis"]
    cat_spending = analytics_data["category_spending"]
    monthly_trends = analytics_data["monthly_trends"]
    subscriptions = analytics_data["subscriptions"]
    weekly_heatmap = analytics_data["weekly_heatmap"]
    
    insights = []
    
    # 1. Total Savings Insight
    if kpis["savings"] > 0:
        savings_val = f"\u20b9 {kpis['savings']:,.2f}"
        insights.append({
            "text": f"You saved {savings_val} this period. Great job!",
            "type": "savings",
            "status": "success",
            "icon": "bi-piggy-bank"
        })
    elif kpis["savings"] < 0:
        overspend_val = f"\u20b9 {abs(kpis['savings']):,.2f}"
        insights.append({
            "text": f"You spent {overspend_val} more than you earned this period. Consider establishing a budget.",
            "type": "savings",
            "status": "danger",
            "icon": "bi-exclamation-triangle"
        })
        
    # 2. Savings Rate check
    if kpis["savings_rate"] > 30:
        insights.append({
            "text": "Excellent savings performance this period (Savings rate is above 30%).",
            "type": "savings",
            "status": "success",
            "icon": "bi-graph-up-arrow"
        })
    elif 0 < kpis["savings_rate"] < 10:
        insights.append({
            "text": "Your savings rate is below the recommended 10% level. Consider reducing non-essential spending.",
            "type": "savings",
            "status": "warning",
            "icon": "bi-exclamation-circle"
        })

    # 3. Highest Spending Category
    highest_cat = None
    highest_pct = 0.0
    for cat in cat_spending:
        if cat["category_name"] != "Uncategorized" and cat["percentage"] > highest_pct:
            highest_pct = cat["percentage"]
            highest_cat = cat["category_name"]
            
    if highest_cat:
        insights.append({
            "text": f"{highest_cat} is your highest spending category ({highest_pct:.1f}% of total spending).",
            "type": "category",
            "status": "info",
            "icon": "bi-tag"
        })
        
        # Category warnings
        if highest_cat == "Food & Dining" and highest_pct > 30:
            insights.append({
                "text": "Food & Dining represents a large portion of your expenses. Consider reviewing dining habits.",
                "type": "category",
                "status": "warning",
                "icon": "bi-egg-fried"
            })
        elif highest_cat == "Shopping" and highest_pct > 25:
            insights.append({
                "text": "Shopping expenses are unusually high. Review discretionary purchases.",
                "type": "category",
                "status": "warning",
                "icon": "bi-cart"
            })

    # 4. Weekend vs Weekday spending
    weekend_days = ["Saturday", "Sunday"]
    weekday_days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    
    weekend_sum = sum(weekly_heatmap.get(day, 0.0) for day in weekend_days)
    weekday_sum = sum(weekly_heatmap.get(day, 0.0) for day in weekday_days)
    
    # Average per day
    avg_weekend = weekend_sum / 2
    avg_weekday = weekday_sum / 5
    
    if avg_weekend > avg_weekday * 1.5:
        # Find busiest day
        busiest_day = kpis["busiest_day"]
        insights.append({
            "text": f"You spent the most on {busiest_day}s. Weekend average spend exceeds weekdays significantly.",
            "type": "behavior",
            "status": "info",
            "icon": "bi-calendar-week"
        })

    # 5. Subscriptions detected
    if subscriptions:
        total_sub_cost = sum(sub["amount"] for sub in subscriptions)
        sub_cost_str = f"\u20b9 {total_sub_cost:,.2f}"
        insights.append({
            "text": f"You have {len(subscriptions)} active subscriptions costing {sub_cost_str} per month.",
            "type": "subscription",
            "status": "warning" if len(subscriptions) > 4 else "info",
            "icon": "bi-arrow-repeat"
        })
        if len(subscriptions) > 5:
            insights.append({
                "text": "Multiple recurring subscriptions detected. Consider reviewing and cancelling unused services.",
                "type": "subscription",
                "status": "warning",
                "icon": "bi-shield-exclamation"
            })

    # 6. Month-on-Month Trends
    if len(monthly_trends) >= 2:
        prev_month = monthly_trends[-2]
        curr_month = monthly_trends[-1]
        
        # Expenses comparison
        if prev_month.get("expense") and prev_month["expense"] > 0 and curr_month.get("expense") is not None:
            exp_change = (curr_month["expense"] - prev_month["expense"]) / prev_month["expense"] * 100
            if exp_change > 10:
                insights.append({
                    "text": f"Your spending increased by {exp_change:.1f}% in {curr_month['month']} compared to the previous month.",
                    "type": "spending",
                    "status": "warning",
                    "icon": "bi-graph-up"
                })
            elif exp_change < -10:
                insights.append({
                    "text": f"Great! Your spending decreased by {abs(exp_change):.1f}% in {curr_month['month']} compared to the previous month.",
                    "type": "spending",
                    "status": "success",
                    "icon": "bi-graph-down"
                })
                
        # Income comparison
        if prev_month.get("income") and prev_month["income"] > 0 and curr_month.get("income") is not None:
            inc_change = (curr_month["income"] - prev_month["income"]) / prev_month["income"] * 100
            if inc_change > 5:
                insights.append({
                    "text": f"Your income has improved by {inc_change:.1f}% relative to the previous period.",
                    "type": "spending",
                    "status": "success",
                    "icon": "bi-cash-coin"
                })
    else:
        # Fallback if less than 2 months
        pass

    # Ensure we return at least a few default insights if the dataset is small
    if not insights:
        insights.append({
            "text": "Keep tracking your statements monthly to build a comprehensive financial profile.",
            "type": "behavior",
            "status": "info",
            "icon": "bi-info-circle"
        })
        
    return insights
