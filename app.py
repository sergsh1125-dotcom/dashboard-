import streamlit as st
import pandas as pd
import io
import json
import folium
from streamlit_folium import st_folium
import os

st.set_page_config(page_title="Dashboard РХБЗ", layout="wide")
st.title("Стан забезпечення підрозділів ОРСЦЗ засобами РХБ захисту")

# =====================================================
# 1. ЗАВАНТАЖЕННЯ EXCEL
# =====================================================

uploaded_file = st.sidebar.file_uploader("Завантаж Excel файл", type=["xlsx"])

if uploaded_file is None:
    st.info("⬅ Завантажте Excel файл")
    st.stop()

df = pd.read_excel(uploaded_file)

# очистка назв колонок
df.columns = df.columns.str.strip().str.lower()

# перевірка колонок
required_columns = [
    "region_name",
    "category",
    "product_name",
    "quantity",
    "required_quantity"
]

if not all(col in df.columns for col in required_columns):
    st.error("❌ У файлі відсутні необхідні колонки")
    st.write("Знайдено:", df.columns.tolist())
    st.stop()

# очистка даних
df["region_name"] = df["region_name"].astype(str).str.strip()
df["category"] = df["category"].astype(str).str.strip().str.lower()
df["product_name"] = df["product_name"].fillna("").astype(str).str.strip()

# числа
for col in ["quantity", "required_quantity"]:
    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

# =====================================================
# 2. ДОВІДНИКИ
# =====================================================

allowed_categories = [
    "спеціальна техніка",
    "прилади рр",
    "прилади хр",
    "прилади рр_офіцери_рятувальники",
    "прилади хр_офіцери-рятувальники",
    "протигази",
    "респіратори",
    "захисний одяг"
]

category_display = {
    "спеціальна техніка": "Спеціальна техніка",
    "прилади рр": "Прилади РР",
    "прилади хр": "Прилади ХР",
    "прилади рр_офіцери_рятувальники": "Прилади РР (офіцери-рятувальники)",
    "прилади хр_офіцери-рятувальники": "Прилади ХР (офіцери-рятувальники)",
    "протигази": "Протигази",
    "респіратори": "Респіратори",
    "захисний одяг": "Захисний одяг"
}

# =====================================================
# ПІДРОЗДІЛИ (НЕ ДЛЯ КАРТИ)
# =====================================================

subunits = [
    "ГМРЦШР",
    'МРЦШР "Суми"',
    'МРЦШР "Одеса"',
    "САЗ ОРС ЦЗ"
]
# =====================================================
# 3. ФІЛЬТРИ
# =====================================================

st.sidebar.header("Фільтри")

selected_region = st.sidebar.selectbox(
    "Регіон",
    ["Всі"] + sorted(df["region_name"].dropna().unique())
)

selected_category_display = st.sidebar.selectbox(
    "Категорія",
    ["Всі"] + list(category_display.values())
)

reverse_map = {v: k for k, v in category_display.items()}
selected_category = reverse_map.get(selected_category_display, "Всі")

# динамічний список засобів
if selected_category != "Всі":
    product_options = df[df["category"] == selected_category]["product_name"].unique()
else:
    product_options = df["product_name"].unique()

product_options = pd.Series(product_options).dropna().astype(str)

selected_product = st.sidebar.selectbox(
    "Найменування засобу РХБЗ",
    ["Всі"] + sorted(product_options.unique())
)

# =====================================================
# 4. ФІЛЬТРАЦІЯ
# =====================================================

filtered_df = df.copy()

if selected_region != "Всі":
    filtered_df = filtered_df[filtered_df["region_name"] == selected_region]

if selected_category != "Всі":
    filtered_df = filtered_df[filtered_df["category"] == selected_category]

if selected_product != "Всі":
    filtered_df = filtered_df[filtered_df["product_name"] == selected_product]

# =====================================================
# 5. АГРЕГАЦІЯ
# =====================================================

region_summary = (
    filtered_df
    .groupby("region_name")
    .agg(
        total_quantity=("quantity", "sum"),
        total_required=("required_quantity", "sum")
    )
    .reset_index()
)

region_summary["% забезпечення"] = region_summary.apply(
    lambda row: round((row["total_quantity"] / row["total_required"]) * 100, 1)
    if row["total_required"] > 0 else 0,
    axis=1
)

region_summary["Нестача"] = (
    region_summary["total_required"] - region_summary["total_quantity"]
).clip(lower=0)

region_summary["Надлишок"] = (
    region_summary["total_quantity"] - region_summary["total_required"]
).clip(lower=0)

# =====================================================
# 6. KPI
# =====================================================

total_quantity = int(region_summary["total_quantity"].sum())
total_required = int(region_summary["total_required"].sum())

col1, col2, col3 = st.columns(3)

col1.metric("Наявність", total_quantity)
col2.metric("Потреба", total_required)

percent_total = round((total_quantity / total_required) * 100, 1) if total_required > 0 else 0
col3.metric("% забезпечення", f"{percent_total}%")

# =====================================================
# 7. ТАБЛИЦЯ
# =====================================================

display_table = region_summary.rename(columns={
    "region_name": "Регіон",
    "total_quantity": "Наявність",
    "total_required": "Потреба"
})

display_table["Тип"] = display_table["Регіон"].apply(
    lambda x: "Підрозділ" if x in subunits else "Регіон"
)

st.subheader("Дані по регіонах")
st.dataframe(display_table, use_container_width=True)

# =====================================================
# 8. ГРАФІК
# =====================================================

st.subheader("Графік забезпечення (%)")

st.bar_chart(
    region_summary
    .sort_values("% забезпечення", ascending=False)
    .set_index("region_name")["% забезпечення"]
)

# =====================================================
# 9. КАРТА
# =====================================================

st.subheader("Карта забезпечення")

geojson_path = "data/ukraine_regions.geojson"

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

if os.path.exists(geojson_path):

    with open(geojson_path, "r", encoding="utf-8") as f:
        geojson_data = json.load(f)

    coverage_dict = {}
    # тільки справжні регіони (без підрозділів)
    region_summary_map = region_summary[
        ~region_summary["region_name"].isin(subunits)
]

coverage_dict = {}

for ukr, eng in region_name_map.items():
    row = region_summary_map[region_summary_map["region_name"] == ukr]
    coverage_dict[eng] = float(row["% забезпечення"].values[0]) if not row.empty else 0

    def color(c):
        if c >= 100: return "#1a9850"
        elif c >= 75: return "#fee08b"
        elif c >= 50: return "#f46d43"
        else: return "#d73027"

    m = folium.Map(location=[49, 32], zoom_start=6, tiles="cartodbpositron")

    folium.GeoJson(
        geojson_data,
        style_function=lambda f: {
            "fillColor": color(coverage_dict.get(f["properties"]["name"], 0)),
            "color": "black",
            "weight": 1,
            "fillOpacity": 0.7
        }
    ).add_to(m)

    st_folium(m, width="100%", height=600)

# =====================================================
# 10. ЕКСПОРТ
# =====================================================

def convert_to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)
    return output.getvalue()

st.download_button(
    "📥 Завантажити звіт",
    convert_to_excel(display_table),
    "zvit.xlsx"
)
