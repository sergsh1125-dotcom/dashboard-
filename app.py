import streamlit as st
import pandas as pd
import io
import json
import folium
from streamlit_folium import st_folium
import random
from openpyxl.styles import PatternFill, Protection
from openpyxl.worksheet.datavalidation import DataValidation

st.set_page_config(page_title="Dashboard РХБЗ", layout="wide")
st.title("Дашборд забезпечення засобами РХБ захисту")

# =====================================================
# 1. СТВОРЕННЯ ПРИКЛАДНОГО ШАБЛОНУ
# =====================================================
regions = [
    "Київ","Вінницька область","Волинська область","Дніпропетровська область",
    "Донецька область","Житомирська область","Закарпатська область","Запорізька область",
    "Івано-Франківська область","Київська область","Кіровоградська область","Луганська область",
    "Львівська область","Миколаївська область","Одеська область","Полтавська область",
    "Рівненська область","Сумська область","Тернопільська область","Харківська область",
    "Херсонська область","Хмельницька область","Черкаська область","Чернівецька область",
    "Чернігівська область"
]

products = [
    "спеціальна техніка",
    "прилади РР",
    "прилади ХР",
    "протигази",
    "респіратори",
    "захисний одяг"
]

def generate_example_excel():
    data = []
    for region in regions:
        for product in products:
            required = random.randint(50,200)
            quantity = random.randint(0, required)
            data.append([region, product, quantity, required])
    df = pd.DataFrame(data, columns=["region_name","product_name","quantity","required_quantity"])
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Дані", index=False)
    return output.getvalue()

st.sidebar.header("Excel шаблон")
if st.sidebar.button("📄 Завантажити приклад шаблону"):
    excel_bytes = generate_example_excel()
    st.sidebar.download_button(
        label="📥 Завантажити приклад Excel",
        data=excel_bytes,
        file_name="example_filled_template.xlsx",
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
    st.write("Знайдені колонки:", df.columns.tolist())
    st.stop()
for col in ["quantity","required_quantity"]:
    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

# =====================================================
# 3. ФІЛЬТРИ
# =====================================================
st.sidebar.header("Фільтри")
selected_region = st.sidebar.selectbox("Регіон", ["Всі"] + sorted(df["region_name"].unique()))
selected_product = st.sidebar.selectbox("Засіб РХБЗ", ["Всі"] + sorted(df["product_name"].unique()))
filtered_df = df.copy()
if selected_region != "Всі":
    filtered_df = filtered_df[filtered_df["region_name"]==selected_region]
if selected_product != "Всі":
    filtered_df = filtered_df[filtered_df["product_name"]==selected_product]

# =====================================================
# 4. АГРЕГАЦІЯ
# =====================================================
region_summary = (
    filtered_df.groupby("region_name")
    .agg(total_quantity=("quantity","sum"), total_required=("required_quantity","sum"))
    .reset_index()
)
region_summary["% забезпечення"] = region_summary.apply(
    lambda row: round((row["total_quantity"]/row["total_required"])*100,1)
    if row["total_required"]>0 else 0,
    axis=1
)
region_summary["Нестача"] = (region_summary["total_required"] - region_summary["total_quantity"]).clip(lower=0)
region_summary["Надлишок"] = (region_summary["total_quantity"] - region_summary["total_required"]).clip(lower=0)

# =====================================================
# 5. KPI
# =====================================================
total_quantity = int(region_summary["total_quantity"].sum())
total_required = int(region_summary["total_required"].sum())
col1,col2,col3 = st.columns(3)
col1.metric("Наявність", total_quantity)
col2.metric("Штатна потреба", total_required)
overall_percent = round((total_quantity/total_required)*100,1) if total_required>0 else 0
col3.metric("Загальний % забезпечення", f"{overall_percent}%")

# =====================================================
# 6. ТАБЛИЦЯ
# =====================================================
display_table = region_summary.rename(columns={
    "region_name":"Регіон",
    "total_required":"Штатна потреба",
    "total_quantity":"Наявність"
})
cols = [c for c in display_table.columns if c != "% забезпечення"] + ["% забезпечення"]
display_table = display_table[cols]
st.subheader("Інформація по регіонах")
st.dataframe(display_table, use_container_width=True)
if (region_summary["% забезпечення"]<50).any():
    st.warning("⚠ Є регіони з критичним рівнем забезпечення (<50%)")

# =====================================================
# 7. ГРАФІК
# =====================================================
st.subheader("Рейтинг регіонів за % забезпечення")
st.bar_chart(region_summary.sort_values("% забезпечення", ascending=False).set_index("region_name")["% забезпечення"])

# =====================================================
# 8. КАРТА (ПРАВИЛЬНА ВЕРСІЯ)
# =====================================================
with open("data/ukraine_regions.geojson","r",encoding="utf-8") as f:
    geojson_data = json.load(f)

region_name_map = {
    "Київ": "Kyiv_city","Вінницька область": "Vinnytska","Волинська область": "Volynska",
    "Дніпропетровська область": "Dnipropetrovska","Донецька область": "Donetska","Житомирська область": "Zhytomyrska",
    "Закарпатська область": "Zakarpatska","Запорізька область": "Zaporizka","Івано-Франківська область": "Ivano-Frankivska",
    "Київська область": "Kyivska","Кіровоградська область": "Kirovohradska","Луганська область": "Luhanska",
    "Львівська область": "Lvivska","Миколаївська область": "Mykolaivska","Одеська область": "Odeska",
    "Полтавська область": "Poltavska","Рівненська область": "Rivnenska","Сумська область": "Sumska",
    "Тернопільська область": "Ternopilska","Харківська область": "Kharkivska","Херсонська область": "Khersonska",
    "Хмельницька область": "Khmelnytska","Черкаська область": "Cherkaska",
    "Чернівецька область": "Chernivetska","Чернігівська область": "Chernihivska"
}

# Формуємо словник % забезпечення
coverage_dict = {}
for ukr_name, eng_name in region_name_map.items():
    row = region_summary[region_summary["region_name"] == ukr_name]
    if not row.empty:
        coverage_dict[eng_name] = float(row["% забезпечення"].values[0])
    else:
        coverage_dict[eng_name] = 0

# 🔴 ОСНОВНЕ ВИПРАВЛЕННЯ — записуємо coverage у GeoJSON
for feature in geojson_data["features"]:
    region_id = feature["properties"]["id"]
    feature["properties"]["coverage"] = coverage_dict.get(region_id, 0)

# Функція кольору
def color_by_coverage(c):
    if c < 50:
        return "#d73027"
    elif c < 75:
        return "#f46d43"
    elif c < 100:
        return "#fee08b"
    else:
        return "#1a9850"

m = folium.Map(location=[49,32], zoom_start=6, tiles="cartodbpositron")

folium.GeoJson(
    geojson_data,
    style_function=lambda f: {
        "fillColor": color_by_coverage(f["properties"]["coverage"]),
        "color": "black",
        "weight": 1,
        "fillOpacity": 0.8
    },
    tooltip=folium.GeoJsonTooltip(
        fields=["name","coverage"],
        aliases=["Регіон:","% забезпечення:"],
        localize=True
    )
).add_to(m)

# Легенда
legend_html = """
<div style="
position: fixed;
bottom: 50px;
left: 50px;
width: 190px;
background-color: white;
border:2px solid grey;
z-index:9999;
font-size:14px;
padding: 10px;
">
<b>Легенда</b><br>
<i style="background:#d73027;width:15px;height:15px;display:inline-block"></i> &lt;50%<br>
<i style="background:#f46d43;width:15px;height:15px;display:inline-block"></i> 50–74%<br>
<i style="background:#fee08b;width:15px;height:15px;display:inline-block"></i> 75–99%<br>
<i style="background:#1a9850;width:15px;height:15px;display:inline-block"></i> ≥100%
</div>
"""
m.get_root().html.add_child(folium.Element(legend_html))

st.subheader("Карта рівня забезпечення")
st_folium(m, width=1000, height=650)
# =====================================================
# 9. ЕКСПОРТ В EXCEL
# =====================================================
def convert_to_excel(df):
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        cols = [c for c in df.columns if c != "% забезпечення"] + ["% забезпечення"]
        df[cols].to_excel(writer, sheet_name="Звіт", index=False)
    return out.getvalue()

st.download_button(
    label="📥 Завантажити звіт в Excel",
    data=convert_to_excel(display_table),
    file_name="zvit_po_regionakh.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
