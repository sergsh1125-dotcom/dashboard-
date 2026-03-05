import streamlit as st
import pandas as pd
import io
import json
import folium
from streamlit_folium import st_folium
from folium.features import GeoJsonTooltip
from openpyxl.styles import PatternFill, Protection
from openpyxl.worksheet.datavalidation import DataValidation

st.set_page_config(page_title="Dashboard РХБЗ", layout="wide")
st.title("Дашборд забезпечення засобами РХБ захисту")

# =====================================================
# CACHE GEOJSON
# =====================================================

@st.cache_data
def load_geojson():
    with open("data/ukraine_regions.geojson","r",encoding="utf-8") as f:
        return json.load(f)

geojson_data = load_geojson()

# =====================================================
# 1. ШАБЛОН EXCEL
# =====================================================

def generate_template():

    allowed_products = [
        "спеціальна техніка",
        "прилади РР",
        "прилади ХР",
        "протигази",
        "респіратори",
        "захисний одяг"
    ]

    allowed_regions = [
        "Київ","Вінницька область","Волинська область","Дніпропетровська область",
        "Донецька область","Житомирська область","Закарпатська область","Запорізька область",
        "Івано-Франківська область","Київська область","Кіровоградська область","Луганська область",
        "Львівська область","Миколаївська область","Одеська область","Полтавська область",
        "Рівненська область","Сумська область","Тернопільська область","Харківська область",
        "Херсонська область","Хмельницька область","Черкаська область","Чернівецька область",
        "Чернігівська область"
    ]

    output = io.BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:

        template_df = pd.DataFrame({
            "region_name":[],
            "product_name":[],
            "quantity":[],
            "required_quantity":[]
        })

        template_df.to_excel(writer, sheet_name="Дані", index=False)

        max_len = max(len(allowed_regions), len(allowed_products))

        ref_df = pd.DataFrame({
            "Регіони":allowed_regions + [""]*(max_len-len(allowed_regions)),
            "Засоби":allowed_products + [""]*(max_len-len(allowed_products))
        })

        ref_df.to_excel(writer, sheet_name="Довідник", index=False)

        workbook = writer.book
        data_sheet = workbook["Дані"]

        header_fill = PatternFill(start_color="DDDDDD", end_color="DDDDDD", fill_type="solid")

        for cell in data_sheet[1]:
            cell.fill = header_fill
            cell.protection = Protection(locked=True)

        dv_region = DataValidation(
            type="list",
            formula1=f"=Довідник!$A$2:$A${len(allowed_regions)+1}"
        )

        dv_region.add("A2:A500")
        data_sheet.add_data_validation(dv_region)

        dv_product = DataValidation(
            type="list",
            formula1=f"=Довідник!$B$2:$B${len(allowed_products)+1}"
        )

        dv_product.add("B2:B500")
        data_sheet.add_data_validation(dv_product)

        dv_number = DataValidation(
            type="decimal",
            operator="greaterThanOrEqual",
            formula1="0"
        )

        dv_number.add("C2:D500")
        data_sheet.add_data_validation(dv_number)

        data_sheet.protection.sheet = True

    return output.getvalue()

# =====================================================
# КНОПКА ШАБЛОНУ
# =====================================================

st.sidebar.header("Excel шаблон")

if st.sidebar.button("📄 Завантажити шаблон Excel"):

    template_bytes = generate_template()

    st.sidebar.download_button(
        label="📥 Завантажити шаблон",
        data=template_bytes,
        file_name="template.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

# =====================================================
# 2. ЗАВАНТАЖЕННЯ EXCEL
# =====================================================

uploaded_file = st.sidebar.file_uploader("Завантаж Excel файл", type=["xlsx"])

if uploaded_file is None:
    st.info("⬅ Завантажте Excel файл для початку роботи.")
    st.stop()

df = pd.read_excel(uploaded_file)
df.columns = df.columns.str.strip().str.lower()

required_columns = ["region_name","product_name","quantity","required_quantity"]

if not all(col in df.columns for col in required_columns):
    st.error("У файлі відсутні необхідні колонки.")
    st.stop()

for col in ["quantity","required_quantity"]:
    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

# =====================================================
# 3. ФІЛЬТРИ
# =====================================================

st.sidebar.header("Фільтри")

selected_region = st.sidebar.selectbox(
    "Регіон",
    ["Всі"] + sorted(df["region_name"].unique())
)

selected_product = st.sidebar.selectbox(
    "Засіб РХБЗ",
    ["Всі"] + sorted(df["product_name"].unique())
)

filtered_df = df.copy()

if selected_region != "Всі":
    filtered_df = filtered_df[filtered_df["region_name"] == selected_region]

if selected_product != "Всі":
    filtered_df = filtered_df[filtered_df["product_name"] == selected_product]

# =====================================================
# 4. АГРЕГАЦІЯ
# =====================================================

region_summary = (
    filtered_df.groupby("region_name")
    .agg(
        total_quantity=("quantity","sum"),
        total_required=("required_quantity","sum")
    )
    .reset_index()
)

region_summary["% забезпечення"] = region_summary.apply(
    lambda row: round((row["total_quantity"]/row["total_required"])*100,1)
    if row["total_required"]>0 else 0,
    axis=1
)

region_summary["Нестача"] = (
    region_summary["total_required"] -
    region_summary["total_quantity"]
).clip(lower=0)

region_summary["Надлишок"] = (
    region_summary["total_quantity"] -
    region_summary["total_required"]
).clip(lower=0)

# =====================================================
# KPI
# =====================================================

total_quantity = int(region_summary["total_quantity"].sum())
total_required = int(region_summary["total_required"].sum())

col1,col2,col3 = st.columns(3)

col1.metric("Наявність", total_quantity)
col2.metric("Штатна потреба", total_required)

overall_percent = round((total_quantity/total_required)*100,1) if total_required>0 else 0
col3.metric("Загальний % забезпечення", f"{overall_percent}%")

# =====================================================
# ТАБЛИЦЯ
# =====================================================

display_table = region_summary.rename(columns={
    "region_name":"Регіон",
    "total_required":"Штатна потреба",
    "total_quantity":"Наявність"
})

st.subheader("Інформація по регіонах")
st.dataframe(display_table, use_container_width=True)

# =====================================================
# ГРАФІК
# =====================================================

st.subheader("Рейтинг регіонів за % забезпечення")

st.bar_chart(
    region_summary
    .sort_values("% забезпечення", ascending=False)
    .set_index("region_name")["% забезпечення"]
)

# =====================================================
# КАРТА
# =====================================================

st.subheader("Карта стану забезпечення засобами РХБ захисту")

def color_by_coverage(c):

    if c >= 100:
        return "#1a9850"
    elif c >= 75:
        return "#fee08b"
    elif c >= 51:
        return "#f46d43"
    else:
        return "#d73027"

coverage_dict = dict(
    zip(region_summary["region_name"], region_summary["% забезпечення"])
)

def style_function(feature):

    region = feature["properties"]["name"]

    val = coverage_dict.get(region, 0)

    color = color_by_coverage(val)

    if selected_region != "Всі" and region != selected_region:
        color = "#cccccc"

    return {
        "fillColor": color,
        "color": "black",
        "weight": 1,
        "fillOpacity": 0.8
    }

m = folium.Map(
    location=[49,32],
    zoom_start=6,
    tiles="cartodbpositron"
)

folium.GeoJson(
    geojson_data,
    style_function=style_function,
    tooltip=GeoJsonTooltip(
        fields=["name"],
        aliases=["Регіон:"],
        labels=True,
        sticky=True
    )
).add_to(m)

legend_html = """
<div style="
position: fixed;
bottom: 40px;
left: 40px;
width: 160px;
background: white;
border:2px solid grey;
padding:10px;
font-size:14px;
z-index:9999;
">
<div><span style="background:#1a9850;width:15px;height:15px;display:inline-block"></span> ≥100%</div>
<div><span style="background:#fee08b;width:15px;height:15px;display:inline-block"></span> 75–99%</div>
<div><span style="background:#f46d43;width:15px;height:15px;display:inline-block"></span> 51–74%</div>
<div><span style="background:#d73027;width:15px;height:15px;display:inline-block"></span> ≤50%</div>
</div>
"""

m.get_root().html.add_child(folium.Element(legend_html))

st_folium(m, height=650, use_container_width=True)

# =====================================================
# ЕКСПОРТ
# =====================================================

def convert_to_excel(df):

    output = io.BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)

    return output.getvalue()

st.download_button(
    label="📥 Завантажити звіт Excel",
    data=convert_to_excel(display_table),
    file_name="zvit_po_regionakh.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
