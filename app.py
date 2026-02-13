
import streamlit as st
import gspread
import pandas as pd
import plotly.express as px
from datetime import datetime
from google.oauth2.service_account import Credentials
import json

# ====================== CONFIG ======================
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

MASTER_SHEET_URL = "https://docs.google.com/spreadsheets/d/YOUR_MASTER_SHEET_ID/edit"  # ← CHANGE THIS

# Load service account
creds = Credentials.from_service_account_file("service_account.json", scopes=SCOPES)
gc = gspread.authorize(creds)

# Load master users
master_sheet = gc.open_by_url(MASTER_SHEET_URL)
users_df = master_sheet.worksheet("Sheet1").get_all_records()
users_df = pd.DataFrame(users_df)

# ====================== AUTH ======================
if "user" not in st.session_state:
    st.session_state.user = None

if st.session_state.user is None:
    st.title("🔐 Family Finance Tracker - Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    
    if st.button("Login"):
        match = users_df[(users_df["username"] == username) & (users_df["password"] == password)]
        if not match.empty:
            st.session_state.user = match.iloc[0]
            st.success(f"Welcome {username}!")
            st.rerun()
        else:
            st.error("Wrong username or password")
    st.stop()

# ====================== USER'S SHEET ======================
user = st.session_state.user
user_sheet = gc.open_by_url(user["sheet_url"])
st.title(f"🧾 {user['username'].title()}'s Finance Tracker")

# Create worksheets if not exist
try:
    expenses_ws = user_sheet.worksheet("Expenses")
except:
    expenses_ws = user_sheet.add_worksheet("Expenses", 1000, 10)
    expenses_ws.append_row(["Date", "Amount", "Category", "Description", "Type"])

try:
    budgets_ws = user_sheet.worksheet("Budgets")
except:
    budgets_ws = user_sheet.add_worksheet("Budgets", 50, 2)
    budgets_ws.append_row(["Category", "Budget"])

# Load data
expenses = pd.DataFrame(expenses_ws.get_all_records())
budgets = pd.DataFrame(budgets_ws.get_all_records())

# ====================== SIDEBAR ======================
with st.sidebar:
    st.header("Add Entry")
    entry_type = st.radio("Type", ["Expense", "Income"])
    date = st.date_input("Date", datetime.now())
    amount = st.number_input("Amount (₹)", min_value=0.0, step=10.0)
    
    if entry_type == "Expense":
        cat = st.selectbox("Category", [
            "impulse", "take-out", "groceries", "home needs", "Son needs",
            "son impulse", "charity", "loan emi", "LIC", "investment",
            "foolish commitments", "transport"
        ])
    else:
        cat = st.selectbox("Income Source", ["Salary Income", "Other Income"])
    
    desc = st.text_input("Description")
    
    if st.button("➕ Add"):
        expenses_ws.append_row([str(date), amount, cat, desc, entry_type])
        st.success("Added!")
        st.rerun()

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
