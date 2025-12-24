import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import base64
import io
import os
from pathlib import Path

# Page Configuration
st.set_page_config(
    page_title="نظام إدارة المزرعة | Farm Management System",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for RTL support and professional styling
st.markdown("""
<style>
    .rtl-text {
        direction: rtl;
        text-align: right;
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 20px;
        border-radius: 10px;
        color: white;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .stMetric {
        background-color: #f0f2f6;
        padding: 15px;
        border-radius: 8px;
        border-left: 4px solid #667eea;
    }
    .success-box {
        padding: 10px;
        background-color: #d4edda;
        border-left: 4px solid #28a745;
        border-radius: 4px;
        margin: 10px 0;
    }
</style>
""", unsafe_allow_html=True)

# Database Setup
DB_PATH = "farm_management.db"
UPLOADS_DIR = Path("uploads")
UPLOADS_DIR.mkdir(exist_ok=True)

def init_database():
    """Initialize SQLite database with all required tables"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Cost Centers Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cost_centers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            name_ar TEXT,
            category TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Expenses Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date DATE NOT NULL,
            item_name TEXT NOT NULL,
            category TEXT NOT NULL,
            subcategory TEXT,
            cost_center_id INTEGER,
            amount REAL NOT NULL,
            quantity REAL,
            unit TEXT,
            notes TEXT,
            receipt_image TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (cost_center_id) REFERENCES cost_centers(id)
        )
    """)
    
    # Inventory Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_name TEXT NOT NULL,
            category TEXT NOT NULL,
            subcategory TEXT,
            quantity REAL NOT NULL,
            unit TEXT,
            unit_price REAL,
            total_value REAL,
            linked_season TEXT,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Assets Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS assets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_name TEXT NOT NULL,
            asset_type TEXT NOT NULL,
            purchase_date DATE NOT NULL,
            purchase_price REAL NOT NULL,
            useful_life_years INTEGER NOT NULL,
            depreciation_method TEXT DEFAULT 'straight_line',
            current_value REAL,
            status TEXT DEFAULT 'active',
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Indirect Costs Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS indirect_costs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date DATE NOT NULL,
            cost_type TEXT NOT NULL,
            description TEXT,
            amount REAL NOT NULL,
            allocation_method TEXT DEFAULT 'equal',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Cost Allocation Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cost_allocations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            indirect_cost_id INTEGER,
            cost_center_id INTEGER,
            allocated_amount REAL NOT NULL,
            allocation_percentage REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (indirect_cost_id) REFERENCES indirect_costs(id),
            FOREIGN KEY (cost_center_id) REFERENCES cost_centers(id)
        )
    """)
    
    # Revenue Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS revenue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date DATE NOT NULL,
            cost_center_id INTEGER,
            product_name TEXT NOT NULL,
            quantity REAL NOT NULL,
            unit TEXT,
            unit_price REAL NOT NULL,
            total_amount REAL NOT NULL,
            season TEXT,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (cost_center_id) REFERENCES cost_centers(id)
        )
    """)
    
    # Insert default cost centers
    default_centers = [
        ('Mango Production', 'إنتاج المانجو', 'Crops'),
        ('Orange Production', 'إنتاج البرتقال', 'Crops'),
        ('Plum Production', 'إنتاج البرقوق', 'Crops'),
        ('Short-Cycle Crops', 'المحاصيل القصيرة', 'Crops'),
        ('Poultry', 'الدواجن', 'Livestock'),
        ('Livestock', 'الماشية', 'Livestock'),
        ('General Administration', 'الإدارة العامة', 'Admin')
    ]
    
    for name, name_ar, category in default_centers:
        cursor.execute("""
            INSERT OR IGNORE INTO cost_centers (name, name_ar, category)
            VALUES (?, ?, ?)
        """, (name, name_ar, category))
    
    conn.commit()
    conn.close()

def get_connection():
    """Get database connection"""
    return sqlite3.connect(DB_PATH)

def calculate_depreciation(purchase_price, useful_life_years, purchase_date, method='straight_line'):
    """Calculate asset depreciation"""
    years_elapsed = (datetime.now() - datetime.strptime(purchase_date, '%Y-%m-%d')).days / 365.25
    
    if method == 'straight_line':
        annual_depreciation = purchase_price / useful_life_years
        total_depreciation = min(annual_depreciation * years_elapsed, purchase_price)
        current_value = purchase_price - total_depreciation
    else:
        current_value = purchase_price
    
    return round(current_value, 2)

def encode_image(image_file):
    """Encode image to base64"""
    if image_file is not None:
        bytes_data = image_file.getvalue()
        return base64.b64encode(bytes_data).decode()
    return None

def decode_image(base64_string):
    """Decode base64 to image"""
    if base64_string:
        return base64.b64decode(base64_string)
    return None

# Initialize database
init_database()

# Sidebar Navigation
st.sidebar.title("🌾 Farm Management")
st.sidebar.markdown("---")

menu_options = {
    "Dashboard": "📊",
    "Expense Entry": "💰",
    "Indirect Costs": "🏢",
    "Revenue Entry": "💵",
    "Inventory Management": "📦",
    "Asset Management": "🏗️",
    "Analytics & Reports": "📈",
    "Search & Filter": "🔍",
    "Settings": "⚙️"
}

selected_menu = st.sidebar.radio(
    "Navigation",
    list(menu_options.keys()),
    format_func=lambda x: f"{menu_options[x]} {x}"
)

st.sidebar.markdown("---")
st.sidebar.info("Farm Management System v1.0\nDesigned for Multi-Enterprise Farms")

# Main Content Area
if selected_menu == "Dashboard":
    st.title("📊 Farm Management Dashboard")
    st.markdown("### Overview of Farm Operations")
    
    conn = get_connection()
    
    # Key Metrics
    col1, col2, col3, col4 = st.columns(4)
    
    # Total Expenses
    total_expenses = pd.read_sql_query(
        "SELECT SUM(amount) as total FROM expenses",
        conn
    )['total'][0] or 0
    
    # Total Revenue
    total_revenue = pd.read_sql_query(
        "SELECT SUM(total_amount) as total FROM revenue",
        conn
    )['total'][0] or 0
    
    # Total Assets Value
    assets_df = pd.read_sql_query(
        "SELECT * FROM assets WHERE status='active'",
        conn
    )
    if not assets_df.empty:
        assets_df['current_value'] = assets_df.apply(
            lambda row: calculate_depreciation(
                row['purchase_price'],
                row['useful_life_years'],
                row['purchase_date']
            ), axis=1
        )
        total_assets = assets_df['current_value'].sum()
    else:
        total_assets = 0
    
    # Inventory Value
    total_inventory = pd.read_sql_query(
        "SELECT SUM(total_value) as total FROM inventory",
        conn
    )['total'][0] or 0
    
    with col1:
        st.metric("Total Expenses", f"${total_expenses:,.2f}", delta=None)
    
    with col2:
        st.metric("Total Revenue", f"${total_revenue:,.2f}", delta=None)
    
    with col3:
        profit = total_revenue - total_expenses
        st.metric("Net Profit/Loss", f"${profit:,.2f}", 
                 delta=f"{(profit/total_expenses*100) if total_expenses > 0 else 0:.1f}%")
    
    with col4:
        st.metric("Total Assets", f"${total_assets:,.2f}", delta=None)
    
    st.markdown("---")
    
    # Charts
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Expenses by Cost Center")
        expenses_by_center = pd.read_sql_query("""
            SELECT cc.name, SUM(e.amount) as total
            FROM expenses e
            JOIN cost_centers cc ON e.cost_center_id = cc.id
            GROUP BY cc.name
        """, conn)
        
        if not expenses_by_center.empty:
            fig = px.pie(expenses_by_center, values='total', names='name',
                        title='Distribution of Expenses')
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No expense data available yet.")
    
    with col2:
        st.subheader("Monthly Expenses Trend")
        monthly_expenses = pd.read_sql_query("""
            SELECT strftime('%Y-%m', date) as month, SUM(amount) as total
            FROM expenses
            GROUP BY month
            ORDER BY month DESC
            LIMIT 12
        """, conn)
        
        if not monthly_expenses.empty:
            fig = px.line(monthly_expenses, x='month', y='total',
                         title='Last 12 Months Expenses',
                         markers=True)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No expense trend data available yet.")
    
    # Recent Activities
    st.markdown("---")
    st.subheader("Recent Transactions")
    
    recent_expenses = pd.read_sql_query("""
        SELECT e.date, e.item_name, cc.name as cost_center, e.amount
        FROM expenses e
        JOIN cost_centers cc ON e.cost_center_id = cc.id
        ORDER BY e.date DESC
        LIMIT 10
    """, conn)
    
    if not recent_expenses.empty:
        st.dataframe(recent_expenses, use_container_width=True)
    else:
        st.info("No recent transactions.")
    
    conn.close()

elif selected_menu == "Expense Entry":
    st.title("💰 Expense Entry")
    st.markdown("### Record Farm Expenses")
    
    conn = get_connection()
    cost_centers = pd.read_sql_query("SELECT id, name FROM cost_centers", conn)
    
    with st.form("expense_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            expense_date = st.date_input("Date", value=datetime.now())
            item_name = st.text_input("Item Name *")
            
            category = st.selectbox("Category *", [
                "Inputs (Consumables)",
                "Operating Expenses",
                "Assets (Capital)",
                "Labor",
                "Transportation",
                "Other"
            ])
            
            subcategory = st.text_input("Sub-category")
            
        with col2:
            cost_center = st.selectbox(
                "Cost Center *",
                cost_centers['id'].tolist(),
                format_func=lambda x: cost_centers[cost_centers['id']==x]['name'].values[0]
            )
            
            amount = st.number_input("Amount ($) *", min_value=0.0, step=0.01)
            quantity = st.number_input("Quantity", min_value=0.0, step=0.1)
            unit = st.text_input("Unit (kg, liters, pieces, etc.)")
        
        notes = st.text_area("Notes")
        receipt_image = st.file_uploader("Upload Receipt/Invoice (Optional)", 
                                        type=['png', 'jpg', 'jpeg', 'pdf'])
        
        submitted = st.form_submit_button("💾 Save Expense")
        
        if submitted:
            if item_name and amount > 0:
                image_data = encode_image(receipt_image) if receipt_image else None
                
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO expenses (date, item_name, category, subcategory, 
                                        cost_center_id, amount, quantity, unit, notes, receipt_image)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (expense_date, item_name, category, subcategory, cost_center,
                     amount, quantity, unit, notes, image_data))
                
                # Update inventory if applicable
                if category in ["Inputs (Consumables)", "Operating Expenses"]:
                    cursor.execute("""
                        INSERT OR REPLACE INTO inventory 
                        (item_name, category, subcategory, quantity, unit, unit_price, total_value)
                        VALUES (?, ?, ?, 
                               COALESCE((SELECT quantity FROM inventory WHERE item_name=?), 0) + ?,
                               ?, ?, ?)
                    """, (item_name, category, subcategory, item_name, quantity or 0,
                         unit, amount/(quantity if quantity > 0 else 1), amount))
                
                conn.commit()
                st.success("✅ Expense recorded successfully!")
                st.balloons()
            else:
                st.error("Please fill in all required fields marked with *")
    
    conn.close()

elif selected_menu == "Indirect Costs":
    st.title("🏢 Indirect Costs & Governance")
    st.markdown("### Manage Overhead and Administrative Costs")
    
    conn = get_connection()
    cost_centers = pd.read_sql_query("SELECT id, name FROM cost_centers", conn)
    
    tab1, tab2 = st.tabs(["Add Indirect Cost", "View & Allocate"])
    
    with tab1:
        with st.form("indirect_cost_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                cost_date = st.date_input("Date", value=datetime.now())
                cost_type = st.selectbox("Cost Type", [
                    "Electricity",
                    "Water",
                    "Consultation Fees",
                    "Taxes",
                    "Maintenance",
                    "Insurance",
                    "Administrative Salaries",
                    "Other"
                ])
                
            with col2:
                description = st.text_input("Description")
                amount = st.number_input("Amount ($)", min_value=0.0, step=0.01)
            
            allocation_method = st.radio("Allocation Method", [
                "Equal Distribution",
                "Manual Allocation",
                "Based on Direct Costs"
            ])
            
            submitted = st.form_submit_button("💾 Save Indirect Cost")
            
            if submitted and amount > 0:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO indirect_costs (date, cost_type, description, amount, allocation_method)
                    VALUES (?, ?, ?, ?, ?)
                """, (cost_date, cost_type, description, amount, allocation_method))
                
                indirect_cost_id = cursor.lastrowid
                
                # Automatic allocation
                if allocation_method == "Equal Distribution":
                    num_centers = len(cost_centers)
                    allocation_per_center = amount / num_centers
                    
                    for _, center in cost_centers.iterrows():
                        cursor.execute("""
                            INSERT INTO cost_allocations 
                            (indirect_cost_id, cost_center_id, allocated_amount, allocation_percentage)
                            VALUES (?, ?, ?, ?)
                        """, (indirect_cost_id, center['id'], allocation_per_center, 
                             100.0/num_centers))
                
                conn.commit()
                st.success("✅ Indirect cost recorded and allocated!")
    
    with tab2:
        st.subheader("Indirect Costs Summary")
        
        indirect_costs = pd.read_sql_query("""
            SELECT ic.*, 
                   COUNT(ca.id) as allocations,
                   SUM(ca.allocated_amount) as total_allocated
            FROM indirect_costs ic
            LEFT JOIN cost_allocations ca ON ic.id = ca.indirect_cost_id
            GROUP BY ic.id
            ORDER BY ic.date DESC
        """, conn)
        
        if not indirect_costs.empty:
            st.dataframe(indirect_costs, use_container_width=True)
            
            # Visualization
            fig = px.bar(indirect_costs, x='cost_type', y='amount',
                        title='Indirect Costs by Type',
                        color='cost_type')
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No indirect costs recorded yet.")
    
    conn.close()

elif selected_menu == "Revenue Entry":
    st.title("💵 Revenue Entry")
    st.markdown("### Record Farm Income")
    
    conn = get_connection()
    cost_centers = pd.read_sql_query("SELECT id, name FROM cost_centers", conn)
    
    with st.form("revenue_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            revenue_date = st.date_input("Date", value=datetime.now())
            product_name = st.text_input("Product Name *")
            cost_center = st.selectbox(
                "Cost Center *",
                cost_centers['id'].tolist(),
                format_func=lambda x: cost_centers[cost_centers['id']==x]['name'].values[0]
            )
            quantity = st.number_input("Quantity *", min_value=0.0, step=0.1)
            
        with col2:
            unit = st.text_input("Unit (kg, liters, pieces, etc.) *")
            unit_price = st.number_input("Unit Price ($) *", min_value=0.0, step=0.01)
            season = st.text_input("Season/Batch")
            total_amount = quantity * unit_price
            st.metric("Total Amount", f"${total_amount:,.2f}")
        
        notes = st.text_area("Notes")
        
        submitted = st.form_submit_button("💾 Save Revenue")
        
        if submitted:
            if product_name and quantity > 0 and unit_price > 0:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO revenue (date, cost_center_id, product_name, quantity, 
                                       unit, unit_price, total_amount, season, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (revenue_date, cost_center, product_name, quantity, unit,
                     unit_price, total_amount, season, notes))
                
                conn.commit()
                st.success("✅ Revenue recorded successfully!")
                st.balloons()
            else:
                st.error("Please fill in all required fields marked with *")
    
    conn.close()

elif selected_menu == "Inventory Management":
    st.title("📦 Inventory Management")
    st.markdown("### Warehouse & Stock Control")
    
    conn = get_connection()
    
    tab1, tab2, tab3 = st.tabs([
        "Inputs (Consumables)",
        "Operating Expenses",
        "Current Stock Overview"
    ])
    
    with tab1:
        st.subheader("Inputs Inventory")
        inputs = pd.read_sql_query("""
            SELECT * FROM inventory 
            WHERE category = 'Inputs (Consumables)'
            ORDER BY last_updated DESC
        """, conn)
        
        if not inputs.empty:
            st.dataframe(inputs, use_container_width=True)
            
            # Low stock alert
            low_stock = inputs[inputs['quantity'] < 10]
            if not low_stock.empty:
                st.warning(f"⚠️ {len(low_stock)} items are running low on stock!")
        else:
            st.info("No inputs in inventory yet.")
    
    with tab2:
        st.subheader("Operating Expenses Inventory")
        operating = pd.read_sql_query("""
            SELECT * FROM inventory 
            WHERE category = 'Operating Expenses'
            ORDER BY last_updated DESC
        """, conn)
        
        if not operating.empty:
            st.dataframe(operating, use_container_width=True)
        else:
            st.info("No operating expenses items in inventory yet.")
    
    with tab3:
        st.subheader("Stock Overview")
        
        # Summary metrics
        col1, col2, col3 = st.columns(3)
        
        total_inventory_value = pd.read_sql_query(
            "SELECT SUM(total_value) as total FROM inventory", conn
        )['total'][0] or 0
        
        total_items = pd.read_sql_query(
            "SELECT COUNT(*) as count FROM inventory", conn
        )['count'][0] or 0
        
        low_stock_count = pd.read_sql_query(
            "SELECT COUNT(*) as count FROM inventory WHERE quantity < 10", conn
        )['count'][0] or 0
        
        with col1:
            st.metric("Total Inventory Value", f"${total_inventory_value:,.2f}")
        
        with col2:
            st.metric("Total Items", total_items)
        
        with col3:
            st.metric("Low Stock Items", low_stock_count, delta="Alert" if low_stock_count > 0 else None)
        
        # Category breakdown
        category_breakdown = pd.read_sql_query("""
            SELECT category, COUNT(*) as items, SUM(total_value) as value
            FROM inventory
            GROUP BY category
        """, conn)
        
        if not category_breakdown.empty:
            fig = px.bar(category_breakdown, x='category', y='value',
                        title='Inventory Value by Category',
                        text='items')
            st.plotly_chart(fig, use_container_width=True)
    
    conn.close()

elif selected_menu == "Asset Management":
    st.title("🏗️ Asset Management")
    st.markdown("### Capital Assets & Depreciation Tracking")
    
    conn = get_connection()
    
    tab1, tab2, tab3 = st.tabs(["Add Asset", "View Assets", "Depreciation Report"])
    
    with tab1:
        with st.form("asset_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                asset_name = st.text_input("Asset Name *")
                asset_type = st.selectbox("Asset Type", [
                    "Machinery",
                    "Buildings",
                    "Barns",
                    "Equipment",
                    "Vehicles",
                    "Irrigation Systems",
                    "Other"
                ])
                purchase_date = st.date_input("Purchase Date")
                
            with col2:
                purchase_price = st.number_input("Purchase Price ($) *", min_value=0.0, step=0.01)
                useful_life = st.number_input("Useful Life (Years) *", min_value=1, max_value=50, value=10)
                depreciation_method = st.selectbox("Depreciation Method", ["straight_line"])
            
            notes = st.text_area("Notes (Specifications, Location, etc.)")
            
            submitted = st.form_submit_button("💾 Add Asset")
            
            if submitted and asset_name and purchase_price > 0:
                current_value = calculate_depreciation(
                    purchase_price, useful_life, 
                    purchase_date.strftime('%Y-%m-%d')
                )
                
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO assets (asset_name, asset_type, purchase_date, 
                                      purchase_price, useful_life_years, 
                                      depreciation_method, current_value, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (asset_name, asset_type, purchase_date, purchase_price,
                     useful_life, depreciation_method, current_value, notes))
                
                conn.commit()
                st.success("✅ Asset added successfully!")
    
    with tab2:
        st.subheader("Assets Registry")
        
        assets = pd.read_sql_query("SELECT * FROM assets WHERE status='active'", conn)
        
        if not assets.empty:
            # Calculate current values
            assets['current_value'] = assets.apply(
                lambda row: calculate_depreciation(
                    row['purchase_price'],
                    row['useful_life_years'],
                    row['purchase_date']
                ), axis=1
            )
            
            assets['depreciation'] = assets['purchase_price'] - assets['current_value']
            assets['depreciation_rate'] = (assets['depreciation'] / assets['purchase_price'] * 100).round(2)
            
            st.dataframe(assets[[
                'asset_name', 'asset_type', 'purchase_date', 
                'purchase_price', 'current_value', 'depreciation', 'depreciation_rate'
            ]], use_container_width=True)
            
            # Total assets value
            st.metric("Total Current Asset Value", f"${assets['current_value'].sum():,.2f}")
        else:
            st.info("No assets registered yet.")
    
    with tab3:
        st.subheader("Depreciation Analysis")
        
        assets = pd.read_sql_query("SELECT * FROM assets WHERE status='active'", conn)
        
        if not assets.empty:
            assets['current_value'] = assets.apply(
                lambda row: calculate_depreciation(
                    row['purchase_price'],
                    row['useful_life_years'],
                    row['purchase_date']
                ), axis=1
            )
            
            assets['total_depreciation'] = assets['purchase_price'] - assets['current_value']
            
            # Depreciation by asset type
            dep_by_type = assets.groupby('asset_type').agg({
                'total_depreciation': 'sum',
                'current_value': 'sum'
            }).reset_index()
            
            fig = go.Figure()
            fig.add_trace(go.Bar(name='Total Depreciation', 
                                x=dep_by_type['asset_type'], 
                                y=dep_by_type['total_depreciation']))
            fig.add_trace(go.Bar(name='Current Value', 
                                x=dep_by_type['asset_type'], 
                                y=dep_by_type['current_value']))
            
            fig.update_layout(title='Asset Value vs Depreciation by Type',
                            barmode='group')
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No depreciation data available.")
    
    conn.close()

elif selected_menu == "Analytics & Reports":
    st.title("📈 Analytics & Reports")
    st.markdown("### Business Intelligence & Performance Metrics")
    
    conn = get_connection()
    
    # Date range filter
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("From Date", value=datetime.now() - timedelta(days=365))
    with col2:
        end_date = st.date_input("To Date", value=datetime.now())
    
    tab1, tab2, tab3, tab4 = st.tabs([
        "Cost Center Analysis",
        "ROI & Profitability",
        "Seasonal Performance",
        "Export Reports"
    ])
    
    with tab1:
        st.subheader("Expenses by Cost Center")
        
        expenses_by_center = pd.read_sql_query(f"""
            SELECT cc.name, cc.name_ar, cc.category,
                   SUM(e.amount) as total_expenses,
                   COUNT(e.id) as transaction_count
            FROM expenses e
            JOIN cost_centers cc ON e.cost_center_id = cc.id
            WHERE e.date BETWEEN '{start_date}' AND '{end_date}'
            GROUP BY cc.id
            ORDER BY total_expenses DESC
        """, conn)
        
        if not expenses_by_center.empty:
            # Add allocated indirect costs
            indirect_allocated = pd.read_sql_query(f"""
                SELECT cc.name, SUM(ca.allocated_amount) as indirect_costs
                FROM cost_allocations ca
                JOIN cost_centers cc ON ca.cost_center_id = cc.id
                JOIN indirect_costs ic ON ca.indirect_cost_id = ic.id
                WHERE ic.date BETWEEN '{start_date}' AND '{end_date}'
                GROUP BY cc.id
            """, conn)
            
            if not indirect_allocated.empty:
                expenses_by_center = expenses_by_center.merge(
                    indirect_allocated, on='name', how='