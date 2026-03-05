import streamlit as st
import pandas as pd
import io
import json
import folium
from streamlit_folium import st_folium
from openpyxl.styles import PatternFill, Protection
from openpyxl.worksheet.datavalidation import DataValidation

st.set_page_config(page_title="Dashboard РХБЗ", layout="wide")
st.title("Дашборд забезпечення засобами РХБ захисту")

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
            "region_name": [],
            "product_name": [],
            "quantity": [],
            "required_quantity": []
        })

        template_df.to_excel(writer, sheet_name="Дані", index=False)

        max_len = max(len(allowed_regions), len(allowed_products))

        ref_df = pd.DataFrame({
            "Регіони": allowed_regions + [""]*(max_len-len(allowed_regions)),
            "Засоби": allowed_products + [""]*(max_len-len(allowed_products))
        })

        ref_df.to_excel(writer, sheet_name="Довідник", index=False)

        workbook = writer.book
        sheet = workbook["Дані"]

        header_fill = PatternFill(start_color="DDDDDD", end_color="DDDDDD", fill_type="solid")

        for cell in sheet[1]:
            cell.fill = header_fill
            cell.protection = Protection(locked=True)

        dv_region = DataValidation(
            type="list",
            formula1=f"=Довідник!$A$2:$A${len(allowed_regions)+1}"
        )
        dv_region.add("A2:A500")
        sheet.add_data_validation(dv_region)

        dv_product = DataValidation(
            type="list",
            formula1=f"=Довідник!$B$2:$B${len(allowed_products)+1}"
        )
        dv_product.add("B2:B500")
        sheet.add_data_validation(dv_product)

        dv_number = DataValidation(
            type="decimal",
            operator="greaterThanOrEqual",
            formula1="0"
        )

        dv_number.add("C2:D500")
        sheet.add_data_validation(dv_number)

        sheet.protection.sheet = True

    return output.getvalue()


st.sidebar.header("Excel шаблон")

if st.sidebar.button("📄 Завантажити шаблон Excel"):

    st.sidebar.download_button(
        label="📥 Завантажити",
        data=generate_template(),
        file_name="template.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

# =====================================================
# 2. ЗАВАНТАЖЕННЯ EXCEL
# =====================================================

uploaded_file = st.sidebar.file_uploader("Завантаж Excel файл", type=["xlsx"])

if uploaded_file is None:
    st.info("⬅ Завантажте Excel файл")
    st.stop()

df = pd.read_excel(uploaded_file)

df.columns = df.columns.str.strip().str.lower()

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
    "Засіб",
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
    filtered_df
    .groupby("region_name")
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
    region_summary["total_required"] - region_summary["total_quantity"]
).clip(lower=0)

region_summary["Надлишок"] = (
    region_summary["total_quantity"] - region_summary["total_required"]
).clip(lower=0)

# =====================================================
# 5. KPI
# =====================================================

total_quantity = int(region_summary["total_quantity"].sum())
total_required = int(region_summary["total_required"].sum())

col1,col2,col3 = st.columns(3)

col1.metric("Наявність", total_quantity)
col2.metric("Потреба", total_required)

percent_total = round((total_quantity/total_required)*100,1) if total_required>0 else 0
col3.metric("% забезпечення", f"{percent_total}%")

# =====================================================
# 6. ТАБЛИЦЯ
# =====================================================

display_table = region_summary.rename(columns={
"region_name":"Регіон",
"total_quantity":"Наявність",
"total_required":"Потреба"
})

st.subheader("Дані по регіонах")

st.dataframe(display_table, use_container_width=True)

# =====================================================
# 7. ГРАФІК
# =====================================================

st.subheader("Рейтинг регіонів")

st.bar_chart(
    region_summary
    .sort_values("% забезпечення", ascending=False)
    .set_index("region_name")["% забезпечення"]
)

# =====================================================
# 8. КАРТА
# =====================================================

st.subheader("Карта забезпечення")

with open("data/ukraine_regions.geojson","r",encoding="utf-8") as f:
    geojson_data = json.load(f)

region_map = {
"Vinnytska":"Вінницька область",
"Volynska":"Волинська область",
"Dnipropetrovska":"Дніпропетровська область",
"Donetska":"Донецька область",
"Zhytomyrska":"Житомирська область",
"Zakarpatska":"Закарпатська область",
"Zaporizka":"Запорізька область",
"Ivano-Frankivska":"Івано-Франківська область",
"Kyivska":"Київська область",
"Kyiv_city":"Київ",
"Kirovohradska":"Кіровоградська область",
"Luhanska":"Луганська область",
"Lvivska":"Львівська область",
"Mykolaivska":"Миколаївська область",
"Odeska":"Одеська область",
"Poltavska":"Полтавська область",
"Rivnenska":"Рівненська область",
"Sumska":"Сумська область",
"Ternopilska":"Тернопільська область",
"Kharkivska":"Харківська область",
"Khersonska":"Херсонська область",
"Khmelnytska":"Хмельницька область",
"Cherkaska":"Черкаська область",
"Chernivetska":"Чернівецька область",
"Chernihivska":"Чернігівська область"
}

coverage_dict = dict(
zip(region_summary["region_name"], region_summary["% забезпечення"])
)

def color(c):

    if c>=100:
        return "#1a9850"
    elif c>=75:
        return "#fee08b"
    elif c>=51:
        return "#f46d43"
    else:
        return "#d73027"

def style_function(feature):

    eng = feature["properties"]["name"]
    ukr = region_map.get(eng,"")

    percent = coverage_dict.get(ukr,0)

    fill = color(percent)

    if selected_region!="Всі" and ukr!=selected_region:
        fill="#d9d9d9"

    return {
        "fillColor":fill,
        "color":"black",
        "weight":1,
        "fillOpacity":0.8
    }

m = folium.Map(location=[49,32], zoom_start=6, tiles="cartodbpositron")

for feature in geojson_data["features"]:

    eng = feature["properties"]["name"]
    ukr = region_map.get(eng,"")

    percent = coverage_dict.get(ukr,0)

    tooltip = f"{ukr}<br>{percent}% забезпечення"

    folium.GeoJson(
        feature,
        style_function=style_function,
        tooltip=tooltip
    ).add_to(m)

legend = """
<div style="
position: fixed;
bottom: 40px;
left: 40px;
background: white;
border:2px solid grey;
padding:10px;
font-size:14px;
z-index:9999;
">
<div><span style="background:#1a9850;width:18px;height:18px;display:inline-block;margin-right:6px;"></span> ≥100%</div>
<div><span style="background:#fee08b;width:18px;height:18px;display:inline-block;margin-right:6px;"></span> 75–99%</div>
<div><span style="background:#f46d43;width:18px;height:18px;display:inline-block;margin-right:6px;"></span> 51–74%</div>
<div><span style="background:#d73027;width:18px;height:18px;display:inline-block;margin-right:6px;"></span> ≤50%</div>
</div>
"""

m.get_root().html.add_child(folium.Element(legend))

st_folium(m, height=650, use_container_width=True)

# =====================================================
# 9. ЕКСПОРТ
# =====================================================

def convert_to_excel(df):

    output = io.BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)

    return output.getvalue()

st.download_button(
    "📥 Завантажити звіт Excel",
    convert_to_excel(display_table),
    "zvit.xlsx"
)
