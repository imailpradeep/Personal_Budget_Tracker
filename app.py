
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import os
import io
from dateutil.relativedelta import relativedelta

# LOCAL FILES (saved in the same folder where you run the app)
CSV_FILE = "family_expenses.csv"
BUDGET_FILE = "monthly_budgets.csv"
SCHEDULED_FILE = "scheduled_expenses.csv"

PASSWORD = "family2026"   # ← CHANGE THIS TO YOUR PASSWORD

EXPENSE_CATEGORIES = [
    "impulse", "take-out", "groceries", "home needs", "Son needs",
    "son impulse", "charity", "loan emi", "LIC", "investment",
    "foolish commitments", "transport"
]
INCOME_CATEGORIES = ["Salary Income", "Other Income"]

# Robust load
def load_data(file, columns):
    if os.path.exists(file):
        df = pd.read_csv(file)
        if "Date" in df.columns and not df.empty:
            df["Date"] = pd.to_datetime(df["Date"], errors="coerce", format='mixed')
            df = df.dropna(subset=["Date"])
        return df.sort_values("Date", ascending=False).reset_index(drop=True) if not df.empty else pd.DataFrame(columns=columns)
    else:
        df = pd.DataFrame(columns=columns)
        df.to_csv(file, index=False)
        return df

def load_budgets():
    if os.path.exists(BUDGET_FILE):
        return pd.read_csv(BUDGET_FILE).set_index("Category")["Budget"].to_dict()
    else:
        df = pd.DataFrame({"Category": EXPENSE_CATEGORIES, "Budget": 0.0})
        df.to_csv(BUDGET_FILE, index=False)
        return {cat: 0.0 for cat in EXPENSE_CATEGORIES}

# Load data
expenses = load_data(CSV_FILE, ["Date", "Amount", "Category", "Description", "Type"])
budgets = load_budgets()
scheduled = load_data(SCHEDULED_FILE, ["Date", "Amount", "Category", "Description", "Recurring", "Frequency"])

# Authentication
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("🔒 Family Finance Tracker")
    pwd = st.text_input("Enter Password", type="password")
    if st.button("Login"):
        if pwd == PASSWORD:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Incorrect password")
    st.stop()

# App
st.set_page_config(page_title="Family Finance Tracker", layout="wide")
st.title("🧾 Family Finance Tracker")

current_month_str = datetime.now().strftime("%Y-%m")

# Safe filtering
if not expenses.empty and "Date" in expenses.columns and pd.api.types.is_datetime64_any_dtype(expenses["Date"]):
    current_month_df = expenses[expenses["Date"].dt.strftime("%Y-%m") == current_month_str]
else:
    current_month_df = expenses.copy()

this_month_exp = current_month_df[current_month_df.get("Type") == "Expense"] if not current_month_df.empty else pd.DataFrame()
this_month_inc = current_month_df[current_month_df.get("Type") == "Income"] if not current_month_df.empty else pd.DataFrame()

# Sidebar
with st.sidebar:
    st.header("Add New Entry")
    entry_type = st.radio("Type", ["Expense", "Income"], horizontal=True)
    date = st.date_input("Date", value=datetime.now())
    amount = st.number_input("Amount (₹)", min_value=0.0, step=10.0, format="%.0f")
    if entry_type == "Expense":
        category = st.selectbox("Category", EXPENSE_CATEGORIES)
    else:
        category = st.selectbox("Income Source", INCOME_CATEGORIES)
    description = st.text_input("Description / Notes (optional)")
    if st.button("➕ Add", type="primary") and amount > 0:
        new_row = pd.DataFrame([{
            "Date": pd.Timestamp(date), "Amount": amount, "Category": category,
            "Description": description.strip(), "Type": entry_type
        }])
        expenses = pd.concat([expenses, new_row], ignore_index=True)
        expenses.to_csv(CSV_FILE, index=False)
        st.success(f"Added ₹{amount:,.0f} → {category}")
        st.rerun()

    st.markdown("---")
    st.header("Monthly Budgets")
    for cat in EXPENSE_CATEGORIES:
        current = budgets.get(cat, 0.0)
        new_b = st.number_input(f"{cat}", value=float(current), step=500.0, key=f"b_{cat}")
        if new_b != current:
            budgets[cat] = new_b
            pd.DataFrame({"Category": list(budgets.keys()), "Budget": list(budgets.values())}).to_csv(BUDGET_FILE, index=False)

# Tabs
tab_overview, tab_transactions, tab_visuals, tab_transport, tab_salary, tab_other_income, tab_balance, tab_scheduled, tab_yearly, tab_export = st.tabs([
    "📊 Overview", "📋 Transactions", "📈 Visuals", "🚗 Transport",
    "💰 Salary Income", "🎁 Other Income", "💸 Monthly Balance",
    "🗓️ Scheduled Expenses", "📅 Yearly Summary", "📤 Export"
])

def color_impulse(val):
    return 'background-color: orange' if val in ["impulse", "son impulse", "foolish commitments"] else ''

# Overview
with tab_overview:
    st.subheader(f"This Month ({current_month_str})")
    inc = this_month_inc["Amount"].sum() if not this_month_inc.empty else 0
    exp = this_month_exp["Amount"].sum() if not this_month_exp.empty else 0
    net = inc - exp
    col1, col2, col3 = st.columns(3)
    col1.metric("Income", f"₹{inc:,.0f}")
    col2.metric("Expenses", f"₹{exp:,.0f}")
    col3.metric("Net Savings", f"₹{net:,.0f}", delta_color="normal" if net >= 0 else "inverse")

# Monthly Balance (with scheduled deductions)
with tab_balance:
    st.subheader("Monthly Balance")
    inc = this_month_inc["Amount"].sum() if not this_month_inc.empty else 0
    exp = this_month_exp["Amount"].sum() if not this_month_exp.empty else 0
    balance = inc - exp
    col1, col2, col3 = st.columns(3)
    col1.metric("Income", f"₹{inc:,.0f}")
    col2.metric("Expenses", f"₹{exp:,.0f}")
    col3.metric("Current Balance", f"₹{balance:,.0f}", delta_color="normal" if balance >= 0 else "inverse")

    upcoming = scheduled[scheduled["Date"].dt.strftime("%Y-%m") == current_month_str] if not scheduled.empty else pd.DataFrame()
    potential = upcoming["Amount"].sum() if not upcoming.empty else 0
    projected = balance - potential
    st.metric("Projected Balance (after scheduled)", f"₹{projected:,.0f}")

# Scheduled (enhanced)
with tab_scheduled:
    st.subheader("Scheduled Expenses")
    with st.expander("➕ Add New Scheduled Expense"):
        d = st.date_input("Date", value=datetime.now())
        amt = st.number_input("Amount (₹)", min_value=0.0)
        cat = st.selectbox("Category", EXPENSE_CATEGORIES)
        desc = st.text_input("Description")
        rec = st.checkbox("Recurring?")
        freq = st.selectbox("Frequency", ["Monthly", "Quarterly", "Yearly"], disabled=not rec)
        if st.button("Schedule") and amt > 0:
            new = pd.DataFrame([{"Date": pd.Timestamp(d), "Amount": amt, "Category": cat, "Description": desc,
                                 "Recurring": "Yes" if rec else "No", "Frequency": freq if rec else "One-time"}])
            scheduled = pd.concat([scheduled, new], ignore_index=True)
            scheduled.to_csv(SCHEDULED_FILE, index=False)
            st.rerun()

    if not scheduled.empty:
        edited = st.data_editor(scheduled, num_rows="dynamic", use_container_width=True)
        if st.button("Save Changes"):
            scheduled = edited
            scheduled.to_csv(SCHEDULED_FILE, index=False)
            st.success("Saved!")

# Export
with tab_export:
    st.subheader("Export Report")
    if not expenses.empty:
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
            expenses.to_excel(writer, sheet_name="All Transactions", index=False)
        buffer.seek(0)
        st.download_button("Download Excel", buffer, "family_finance.xlsx")

st.caption("✅ Local version • Data saved in current folder")
