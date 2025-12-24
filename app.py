import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
from datetime import datetime
import base64
from io import BytesIO
from PIL import Image

# إعدادات الصفحة واللغة العربية
st.set_page_config(page_title="نظام إدارة المزرعة المتكامل", layout="wide")
st.markdown("""
    <style>
    .main { text-align: right; direction: rtl; }
    div[data-testid="stSidebarNav"] { text-align: right; direction: rtl; }
    th { text-align: right !important; }
    td { text-align: right !important; }
    </style>
    """, unsafe_allow_html=True)

# --- قاعدة البيانات ---
def init_db():
    conn = sqlite3.connect('farm_data.db')
    c = conn.cursor()
    # جدول المصروفات والإيرادات
    c.execute('''CREATE TABLE IF NOT EXISTS transactions 
                 (id INTEGER PRIMARY KEY, date TEXT, category TEXT, sub_category TEXT, 
                  cost_center TEXT, item_name TEXT, amount_spent REAL, revenue REAL, 
                  quantity REAL, image TEXT, notes TEXT)''')
    # جدول المخزن والمدخلات
    c.execute('''CREATE TABLE IF NOT EXISTS inventory 
                 (id INTEGER PRIMARY KEY, item_name TEXT, current_stock REAL, unit_price REAL)''')
    # جدول الأصول
    c.execute('''CREATE TABLE IF NOT EXISTS assets 
                 (id INTEGER PRIMARY KEY, asset_name TEXT, purchase_date TEXT, cost REAL, depreciation REAL)''')
    conn.commit()
    conn.close()

# دالة لتحويل الصورة لبيانات نصية لتخزينها في SQLite (بشكل مبسط)
def image_to_base64(image_file):
    if image_file is not None:
        img = Image.open(image_file)
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        return base64.b64encode(buffered.getvalue()).decode()
    return None

init_db()

# --- واجهة التطبيق ---
st.title("🚜 نظام حوكمة وإدارة حسابات المزرعة")

tabs = st.tabs(["📊 لوحة التحكم", "💸 إضافة حركة مالية", "📦 المخزن والأصول", "📑 التقارير"])

# --- التاب 1: لوحة التحكم ---
with tabs[0]:
    st.header("ملخص النشاط المالي")
    conn = sqlite3.connect('farm_data.db')
    df = pd.read_sql_query("SELECT * FROM transactions", conn)
    conn.close()

    if not df.empty:
        col1, col2, col3 = st.columns(3)
        total_spent = df['amount_spent'].sum()
        total_revenue = df['revenue'].sum()
        col1.metric("إجمالي المصروفات", f"{total_spent:,.2f} ج.م")
        col2.metric("إجمالي الإيرادات", f"{total_revenue:,.2f} ج.م")
        col3.metric("صافي الربح", f"{(total_revenue - total_spent):,.2f} ج.م")

        # رسوم بيانية
        fig = px.pie(df, values='amount_spent', names='cost_center', title="توزيع المصروفات حسب النشاط")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("لا توجد بيانات لعرضها حالياً. ابدأ بإضافة مصروفات.")

# --- التاب 2: إضافة حركة مالية ---
with tabs[1]:
    st.header("تسجيل مصروف أو إيراد جديد")
    with st.form("transaction_form"):
        col1, col2 = st.columns(2)
        with col1:
            date = st.date_input("التاريخ", datetime.now())
            category = st.selectbox("نوع البند", ["مصروفات مباشرة", "مصروفات غير مباشرة", "إيرادات", "شراء أصل"])
            cost_center = st.selectbox("مركز التكلفة", ["مانجو", "برتقال", "برقوق", "خضار (دورة سريعة)", "مواشي", "دواجن", "عام/إدارة"])
            item_name = st.text_input("اسم البيان (مثلاً: سماد نترات، يومية تقليم)")
        
        with col2:
            amount_spent = st.number_input("المبلغ المنصرف", min_value=0.0)
            revenue = st.number_input("المبلغ المحصل (إيراد)", min_value=0.0)
            quantity = st.number_input("الكمية / العدد", min_value=0.0)
            invoice_img = st.file_uploader("رفع صورة الفاتورة (اختياري)", type=['jpg', 'png', 'jpeg'])
        
        notes = st.text_area("ملاحظات إضافية")
        submit = st.form_submit_button("حفظ البيانات")

        if submit:
            img_str = image_to_base64(invoice_img)
            conn = sqlite3.connect('farm_data.db')
            c = conn.cursor()
            c.execute("INSERT INTO transactions (date, category, cost_center, item_name, amount_spent, revenue, quantity, image, notes) VALUES (?,?,?,?,?,?,?,?,?)",
                      (date.strftime('%Y-%m-%d'), category, cost_center, item_name, amount_spent, revenue, quantity, img_str, notes))
            conn.commit()
            conn.close()
            st.success("تم الحفظ بنجاح!")

# --- التاب 3: المخزن والأصول ---
with tabs[2]:
    st.header("إدارة الأصول والمخزون")
    sub_col1, sub_col2 = st.columns(2)
    
    with sub_col1:
        st.subheader("إضافة أصل (حظيرة، معدات، بئر)")
        with st.form("asset_form"):
            a_name = st.text_input("اسم الأصل")
            a_cost = st.number_input("التكلفة الإجمالية", min_value=0.0)
            a_dep = st.number_input("نسبة الاستهلاك السنوي (%)", min_value=0.0)
            a_date = st.date_input("تاريخ الشراء/البناء")
            if st.form_submit_button("إضافة أصل"):
                conn = sqlite3.connect('farm_data.db')
                conn.execute("INSERT INTO assets (asset_name, purchase_date, cost, depreciation) VALUES (?,?,?,?)",
                             (a_name, a_date.strftime('%Y-%m-%d'), a_cost, a_dep))
                conn.commit()
                conn.close()
                st.success("تم تسجيل الأصل")

    with sub_col2:
        st.subheader("قائمة الأصول المسجلة")
        conn = sqlite3.connect('farm_data.db')
        assets_df = pd.read_sql_query("SELECT * FROM assets", conn)
        conn.close()
        st.dataframe(assets_df, use_container_width=True)

# --- التاب 4: التقارير ---
with tabs[3]:
    st.header("استخراج التقارير")
    conn = sqlite3.connect('farm_data.db')
    full_df = pd.read_sql_query("SELECT date, category, cost_center, item_name, amount_spent, revenue, notes FROM transactions", conn)
    conn.close()
    
    st.write("جدول البيانات الكاملة:")
    st.dataframe(full_df, use_container_width=True)
    
    # خيار التحميل
    csv = full_df.to_csv(index=False).encode('utf-8-sig')
    st.download_button("تحميل البيانات كـ Excel/CSV", data=csv, file_name="farm_report.csv", mime='text/csv')