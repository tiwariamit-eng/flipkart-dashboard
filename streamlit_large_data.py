"""
Flipkart Inventory Dashboard - Production Version
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google.auth.oauthlib.flow import InstalledAppFlow
import os
import pickle
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="📦 Flipkart Inventory Dashboard",
    page_icon="📦",
    layout="wide"
)

st.markdown("""
    <style>
    .stMetric {
        background-color: #f0f2f6;
        padding: 20px;
        border-radius: 8px;
    }
    </style>
    """, unsafe_allow_html=True)

SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']
CREDENTIALS_FILE = 'credentials.json'
TOKEN_FILE = 'token.pickle'
SPREADSHEET_ID = '1-Kc7uI8v5DGzEkR5EHx2CaR-znH6cLWy61NhTRM_njg'
SHEET_NAME = 'Sheet1'

def authenticate_oauth():
    creds = None
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, 'rb') as token:
            creds = pickle.load(token)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, 'wb') as token:
            pickle.dump(creds, token)
    return creds

@st.cache_resource
def get_sheets_client():
    try:
        creds = authenticate_oauth()
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        st.error(f"❌ Error: {e}")
        return None

@st.cache_data(ttl=600)
def fetch_inventory_data():
    try:
        client = get_sheets_client()
        if not client:
            return None
        spreadsheet = client.open_by_key(SPREADSHEET_ID)
        worksheet = spreadsheet.worksheet(SHEET_NAME)
        all_values = worksheet.get_all_values()
        
        if not all_values or len(all_values) < 2:
            return None
        
        headers = all_values[0]
        data = all_values[1:]
        df = pd.DataFrame(data, columns=headers)
        
        for col in ['quantity', 'atp', 'Age']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        logger.info(f"✓ Loaded {len(df):,} rows")
        return df
    except Exception as e:
        st.error(f"❌ Error: {e}")
        return None

def calculate_kpis(df):
    if df is None or df.empty:
        return {}
    kpis = {
        'total_items': int(df['quantity'].sum()) if 'quantity' in df.columns else 0,
        'total_atp': int(df['atp'].sum()) if 'atp' in df.columns else 0,
        'unique_warehouses': df['warehouse_id'].nunique() if 'warehouse_id' in df.columns else 0,
        'unique_locations': df['storage_location_type'].nunique() if 'storage_location_type' in df.columns else 0,
        'avg_age_days': round(df['Age'].mean(), 1) if 'Age' in df.columns else 0,
    }
    return kpis

def create_aging_chart(df):
    if 'Ageing Bucket' not in df.columns:
        return None
    sample_df = df.sample(min(5000, len(df)))
    aging = sample_df.groupby('Ageing Bucket')['quantity'].sum().reset_index()
    fig = px.bar(aging, x='Ageing Bucket', y='quantity', title='📦 Inventory by Age Group')
    fig.update_layout(height=400)
    return fig

def create_location_chart(df):
    if 'storage_location_type' not in df.columns:
        return None
    sample_df = df.sample(min(5000, len(df)))
    location = sample_df.groupby('storage_location_type')['quantity'].sum().reset_index()
    location = location.nlargest(15, 'quantity')
    fig = px.pie(location, values='quantity', names='storage_location_type', title='📍 Inventory by Location', hole=0.4)
    fig.update_layout(height=400)
    return fig

def create_warehouse_chart(df):
    if 'warehouse_id' not in df.columns:
        return None
    sample_df = df.sample(min(5000, len(df)))
    warehouse = sample_df.groupby('warehouse_id').agg({'quantity': 'sum', 'atp': 'sum'}).reset_index()
    warehouse = warehouse.nlargest(10, 'quantity')
    fig = px.bar(warehouse, x='warehouse_id', y=['quantity', 'atp'], title='🏭 Top 10 Warehouses', barmode='group')
    fig.update_layout(height=400)
    return fig

def main():
    st.markdown('<h1 style="color: #1f77b4;">📦 Flipkart Inventory Dashboard</h1>', unsafe_allow_html=True)
    st.markdown('Production Dashboard for Large Data')
    
    with st.sidebar:
        st.header('⚙️ Controls')
        if st.button('🔄 Refresh Data', use_container_width=True):
            st.cache_data.clear()
            st.rerun()
        st.divider()
        auto_refresh = st.checkbox('Auto-refresh (30 min)', value=False)
        st.divider()
        st.caption('💡 Charts use sampling for speed')
    
    df = fetch_inventory_data()
    
    if df is not None and not df.empty:
        kpis = calculate_kpis(df)
        st.info(f"📊 Dataset: {len(df):,} rows | Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.metric('📦 Total Items', f"{kpis.get('total_items', 0):,}")
        with col2:
            st.metric('✅ ATP Available', f"{kpis.get('total_atp', 0):,}")
        with col3:
            st.metric('🏭 Warehouses', kpis.get('unique_warehouses', 0))
        with col4:
            st.metric('📍 Locations', kpis.get('unique_locations', 0))
        with col5:
            st.metric('📅 Avg Age', kpis.get('avg_age_days', 0))
        
        st.divider()
        
        tab1, tab2, tab3 = st.tabs(['📊 Overview', '📋 Data', '⚙️ Details'])
        
        with tab1:
            st.subheader('Dashboard Overview')
            col1, col2 = st.columns(2)
            with col1:
                fig = create_aging_chart(df)
                if fig:
                    st.plotly_chart(fig, use_container_width=True)
            with col2:
                fig = create_location_chart(df)
                if fig:
                    st.plotly_chart(fig, use_container_width=True)
            fig = create_warehouse_chart(df)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
        
        with tab2:
            st.subheader('Data Explorer')
            col1, col2 = st.columns(2)
            with col1:
                if 'warehouse_id' in df.columns:
                    warehouses = st.multiselect('Filter Warehouse', sorted(df['warehouse_id'].unique()))
                    if warehouses:
                        df = df[df['warehouse_id'].isin(warehouses)]
            with col2:
                if 'storage_location_type' in df.columns:
                    locations = st.multiselect('Filter Location', sorted(df['storage_location_type'].unique()))
                    if locations:
                        df = df[df['storage_location_type'].isin(locations)]
            st.dataframe(df.head(100), use_container_width=True, height=600)
            st.caption(f'Showing first 100 of {len(df):,} rows')
            csv = df.to_csv(index=False)
            st.download_button('📥 Download CSV', csv, f'inventory_{datetime.now().strftime("%Y%m%d")}.csv', 'text/csv')
        
        with tab3:
            st.subheader('Summary Statistics')
            col1, col2, col3 = st.columns(3)
            with col1:
                st.info(f"**Total Records**: {len(df):,}")
            with col2:
                st.info(f"**Warehouses**: {df['warehouse_id'].nunique()}")
            with col3:
                st.info(f"**Locations**: {df['storage_location_type'].nunique()}")
        
        st.divider()
        st.caption(f"✅ Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        if auto_refresh:
            import time
            time.sleep(30 * 60)
            st.rerun()
    else:
        st.error("❌ Unable to fetch data")

if __name__ == '__main__':
    main()