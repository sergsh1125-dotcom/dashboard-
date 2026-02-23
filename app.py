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
    st.write("Знайдені колонки:", df.columns.tolist())
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

# Безпечне обчислення %
region_summary["% забезпечення"] = (
    (region_summary["total_quantity"] / region_summary["total_required"])
    .replace([float("inf"), -float("inf")], 0)
    .fillna(0) * 100
).round(1)

region_summary["Нестача"] = (
    region_summary["total_required"] - region_summary["total_quantity"]
).apply(lambda x: x if x > 0 else 0)

region_summary["Надлишок"] = (
    region_summary["total_quantity"] - region_summary["total_required"]
).apply(lambda x: x if x > 0 else 0)

# ----------------------------
# KPI
# ----------------------------
total_quantity = int(region_summary["total_quantity"].sum())
total_required = int(region_summary["total_required"].sum())

col1, col2 = st.columns(2)
col1.metric("Наявність", total_quantity)
col2.metric("Потреба", total_required)

# ----------------------------
# Таблиця
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

coverage_dict = dict(zip(region_summary["region_name"], region_summary["% забезпечення"]))

# Додаємо % до GeoJSON
for feature in geojson_data["features"]:
    geo_name = feature["properties"]["name"]
    csv_name = [k for k, v in region_name_map.items() if v == geo_name]
    feature["properties"]["coverage"] = coverage_dict.get(csv_name[0], 0) if csv_name else 0


# --- 5 рівнів забезпечення ---
def color_by_coverage(coverage):
    if coverage == 0:
        return "#ffffff"   # білий
    elif coverage < 50:
        return "#d73027"   # червоний
    elif coverage < 75:
        return "#f46d43"   # помаранчевий
    elif coverage < 100:
        return "#fee08b"   # жовтий
    else:
        return "#1a9850"   # зелений


m = folium.Map(location=[49, 32], zoom_start=6, control_scale=True)

folium.GeoJson(
    geojson_data,
    style_function=lambda feature: {
        "fillColor": color_by_coverage(feature["properties"]["coverage"]),
        "color": "black",
        "weight": 1,
        "fillOpacity": 0.75
    },
    tooltip=folium.GeoJsonTooltip(
        fields=["name", "coverage"],
        aliases=["Регіон", "% забезпечення"],
        localize=True
    )
).add_to(m)

# ----------------------------
# Постійні назви регіонів
# ----------------------------
for feature in geojson_data["features"]:
    coords = feature["geometry"]["coordinates"]

    if feature["geometry"]["type"] == "MultiPolygon":
        coords = coords[0][0]
    else:
        coords = coords[0]

    lat = sum([point[1] for point in coords]) / len(coords)
    lon = sum([point[0] for point in coords]) / len(coords)

    folium.Marker(
        location=[lat, lon],
        icon=folium.DivIcon(
            html=f"""
            <div style="
                font-size:9px;
                font-weight:600;
                color:black;
                text-align:center;
                text-shadow: 1px 1px 2px white;
            ">
                {feature["properties"]["name"]}
            </div>
            """
        )
    ).add_to(m)


# ----------------------------
# Видаляємо можливу авто-легенду
# ----------------------------
for key in list(m._children):
    if "color_map" in key:
        del m._children[key]


# ----------------------------
# Кастомна легенда (5 блоків)
# ----------------------------
legend_html = """
<div style="
position: absolute;
bottom: 30px;
left: 30px;
width: 240px;
background-color: white;
border: 2px solid #999;
border-radius: 10px;
z-index: 9999;
font-size: 13px;
padding: 12px;
box-shadow: 3px 3px 8px rgba(0,0,0,0.3);
">

<b style="font-size:15px;">Рівень забезпечення</b><br><br>

<div style="display:flex;align-items:center;margin-bottom:6px;">
<div style="background:#1a9850;width:18px;height:18px;margin-right:8px;"></div>
<span>≥ 100%</span>
</div>

<div style="display:flex;align-items:center;margin-bottom:6px;">
<div style="background:#fee08b;width:18px;height:18px;margin-right:8px;"></div>
<span>75–99%</span>
</div>

<div style="display:flex;align-items:center;margin-bottom:6px;">
<div style="background:#f46d43;width:18px;height:18px;margin-right:8px;"></div>
<span>50–74%</span>
</div>

<div style="display:flex;align-items:center;margin-bottom:6px;">
<div style="background:#d73027;width:18px;height:18px;margin-right:8px;"></div>
<span>< 50%</span>
</div>

<div style="display:flex;align-items:center;">
<div style="background:#ffffff;border:1px solid #999;width:18px;height:18px;margin-right:8px;"></div>
<span>0%</span>
</div>

</div>
"""

m.get_root().html.add_child(folium.Element(legend_html))

st.subheader("Карта рівня забезпечення")
st_folium(m, width=1000, height=700)

# ----------------------------
# Експорт в Excel
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
