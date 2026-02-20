import streamlit as st
import pandas as pd
import json
import folium
from streamlit_folium import st_folium
import io

st.set_page_config(page_title="Dashboard", layout="wide")
st.title("Дашборд забезпечення виробами")

# ----------------------------
# Завантаження даних
# ----------------------------
@st.cache_data
def load_data():
    df = pd.read_csv("data/example_stock.csv")
    df.columns = df.columns.str.strip().str.lower()
    return df

df = load_data()

required_columns = [
    "region_name",
    "product_name",
    "year_of_manufacture",
    "quantity",
    "required_quantity"
]

if not all(col in df.columns for col in required_columns):
    st.error("У CSV відсутні необхідні колонки.")
    st.stop()

# ----------------------------
# Фільтри
# ----------------------------
st.sidebar.header("Фільтри")

selected_region = st.sidebar.selectbox(
    "Регіон",
    ["Всі"] + sorted(df["region_name"].unique())
)

selected_product = st.sidebar.selectbox(
    "Виріб",
    ["Всі"] + sorted(df["product_name"].unique())
)

filtered_df = df.copy()
if selected_region != "Всі":
    filtered_df = filtered_df[filtered_df["region_name"] == selected_region]
if selected_product != "Всі":
    filtered_df = filtered_df[filtered_df["product_name"] == selected_product]

# ----------------------------
# Агрегація по регіонах
# ----------------------------
region_summary = (
    filtered_df
    .groupby("region_name")
    .agg(
        total_quantity=("quantity", "sum"),
        total_required=("required_quantity", "sum")
    )
    .reset_index()
)

region_summary["Нестача"] = (region_summary["total_required"] - region_summary["total_quantity"]).apply(lambda x: x if x > 0 else 0)
region_summary["Надлишок"] = (region_summary["total_quantity"] - region_summary["total_required"]).apply(lambda x: x if x > 0 else 0)
region_summary["% забезпечення"] = (region_summary["total_quantity"] / region_summary["total_required"] * 100).fillna(0).round(1)

# ----------------------------
# KPI
# ----------------------------
total_quantity = region_summary["total_quantity"].sum()
total_required = region_summary["total_required"].sum()
col1, col2 = st.columns(2)
col1.metric("Наявність", int(total_quantity))
col2.metric("Потреба", int(total_required))

# ----------------------------
# Таблиця по регіонах
# ----------------------------
display_table = region_summary.rename(columns={
    "region_name": "Регіон",
    "total_required": "Потреба",
    "total_quantity": "Наявність"
})[["Регіон","Потреба","Наявність","Нестача","Надлишок","% забезпечення"]]

st.subheader("Інформація по регіонах")
st.dataframe(display_table, use_container_width=True)

# ----------------------------
# Карта
# ----------------------------
with open("data/ukraine_regions.geojson", "r", encoding="utf-8") as f:
    geojson_data = json.load(f)

region_name_map = {
    "Київ": "Kyiv_city",
    "Київська область": "Kyivska",
    "Львівська область": "Lvivska",
    "Одеська область": "Odeska",
    "Харківська область": "Kharkivska",
    "Дніпропетровська область": "Dnipropetrovska",
    "Полтавська область": "Poltavska",
    "Сумська область": "Sumska",
    "Вінницька область": "Vinnytska",
    "Волинська область": "Volynska",
    "Закарпатська область": "Zakarpatska",
    "Запорізька область": "Zaporizka",
    "Івано-Франківська область": "Ivano-Frankivska",
    "Кіровоградська область": "Kirovohradska",
    "Луганська область": "Luhanska",
    "Миколаївська область": "Mykolaivska",
    "Рівненська область": "Rivnenska",
    "Тернопільська область": "Ternopilska",
    "Херсонська область": "Khersonska",
    "Хмельницька область": "Khmelnytska",
    "Черкаська область": "Cherkaska",
    "Чернігівська область": "Chernihivska",
    "Чернівецька область": "Chernivetska",
    "Житомирська область": "Zhytomyrska"
}

coverage_dict = dict(zip(region_summary["region_name"], region_summary["% забезпечення"]))

for feature in geojson_data["features"]:
    geo_name = feature["properties"]["name"]
    csv_name = [k for k, v in region_name_map.items() if v == geo_name]
    feature["properties"]["coverage"] = coverage_dict.get(csv_name[0], 0) if csv_name else 0

def color_by_coverage(coverage):
    if coverage >= 100:
        return "green"
    elif coverage >= 75:
        return "orange"
    else:
        return "red"

m = folium.Map(location=[49, 32], zoom_start=6)
folium.GeoJson(
    geojson_data,
    style_function=lambda feature: {
        "fillColor": color_by_coverage(feature["properties"]["coverage"]),
        "color": "black",
        "weight": 1,
        "fillOpacity": 0.6
    },
    tooltip=folium.GeoJsonTooltip(
        fields=["name","coverage"],
        aliases=["Регіон","% забезпечення"]
    )
).add_to(m)

# ----------------------------
# Легенда
# ----------------------------
legend_html = """
<div style="
position: fixed;
bottom: 50px;
left: 50px;
width: 220px;
background-color: white;
border:2px solid grey;
z-index:9999;
font-size:14px;
padding:10px;
">
<b>Рівень забезпечення</b><br>
<i style="background:green;width:15px;height:15px;display:inline-block"></i>
&nbsp; ≥ 100%<br>
<i style="background:orange;width:15px;height:15px;display:inline-block"></i>
&nbsp; 75–99%<br>
<i style="background:red;width:15px;height:15px;display:inline-block"></i>
&nbsp; < 75%
</div>
"""
m.get_root().html.add_child(folium.Element(legend_html))

st.subheader("Карта рівня забезпечення")
st_folium(m, width=1000, height=600)

# ----------------------------
# ЕКСПОРТ В EXCEL
# ----------------------------
def convert_to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Звіт", index=False)
    return output.getvalue()

excel_data = convert_to_excel(display_table)
st.download_button(
    label="📥 Завантажити звіт в Excel",
    data=excel_data,
    file_name="zvit_po_regionakh.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
