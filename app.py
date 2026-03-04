import streamlit as st
import pandas as pd
import io
import json
import folium
from streamlit_folium import st_folium
from openpyxl.styles import PatternFill, Protection
from openpyxl.worksheet.datavalidation import DataValidation
from folium.features import GeoJsonTooltip

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
            "Регіони": allowed_regions + [""]*(max_len - len(allowed_regions)),
            "Засоби": allowed_products + [""]*(max_len - len(allowed_products))
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
            formula1=f"=Довідник!$A$2:$A${len(allowed_regions)+1}",
            allow_blank=True
        )
        dv_region.add("A2:A500")
        data_sheet.add_data_validation(dv_region)

        dv_product = DataValidation(
            type="list",
            formula1=f"=Довідник!$B$2:$B${len(allowed_products)+1}",
            allow_blank=True
        )
        dv_product.add("B2:B500")
        data_sheet.add_data_validation(dv_product)

        dv_number = DataValidation(
            type="decimal",
            operator="greaterThanOrEqual",
            formula1="0",
            allow_blank=True
        )
        dv_number.add("C2:D500")
        data_sheet.add_data_validation(dv_number)

        data_sheet.protection.sheet = True

    return output.getvalue()

# Кнопка завантаження шаблону
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
# 8. КАРТА
# =====================================================
with open("data/ukraine_regions.geojson","r",encoding="utf-8") as f:
    geojson_data = json.load(f)

import folium
from folium.features import GeoJsonTooltip
from streamlit_folium import st_folium

# Словник відповідності українських назв до geojson
region_name_map = {
    "Київ":"Kyiv_city","Вінницька область":"Vinnytska","Волинська область":"Volynska",
    "Дніпропетровська область":"Dnipropetrovska","Донецька область":"Donetska","Житомирська область":"Zhytomyrska",
    "Закарпатська область":"Zakarpatska","Запорізька область":"Zaporizka","Івано-Франківська область":"Ivano-Frankivska",
    "Київська область":"Kyivska","Кіровоградська область":"Kirovohradska","Луганська область":"Luhanska",
    "Львівська область":"Lvivska","Миколаївська область":"Mykolaivska","Одеська область":"Odeska",
    "Полтавська область":"Poltavska","Рівненська область":"Rivnenska","Сумська область":"Sumska",
    "Тернопільська область":"Ternopilska","Харківська область":"Kharkivska","Херсонська область":"Khersonska",
    "Хмельницька область":"Khmelnytska","Черкаська область":"Cherkaska","Чернівецька область":"Chernivetska",
    "Чернігівська область":"Chernihivska","Автономна Республіка Крим":"Crimea"
}

# Створюємо словник покриття
coverage_dict = {eng_name: float(region_summary.loc[region_summary["region_name"]==ukr_name,"% забезпечення"].values[0])
                 if not region_summary.loc[region_summary["region_name"]==ukr_name].empty else 0
                 for ukr_name, eng_name in region_name_map.items()}

def color_by_coverage(c):
    if c>=100: return "#1a9850"    # зелений
    elif c>=75: return "#fee08b"   # жовтий
    elif c>=50: return "#f46d43"   # помаранчевий
    else: return "#d73027"         # червоний

m = folium.Map(location=[49,32], zoom_start=6, tiles="cartodbpositron", control_scale=True)

# Функція стилю з затемненням для невибраного регіону
def style_function(feature):
    eng_name = feature["properties"]["name"]
    coverage = coverage_dict.get(eng_name,0)
    if selected_region != "Всі":
        ukr_name_list = [k for k,v in region_name_map.items() if v==eng_name]
        if not ukr_name_list or ukr_name_list[0] != selected_region:
            return {"fillColor":"#cce5ff","color":"black","weight":1,"fillOpacity":0.4}  # затемнені
    return {"fillColor":color_by_coverage(coverage),"color":"black","weight":1,"fillOpacity":0.75}

# Tooltip з назвою регіону і % забезпечення
tooltip = GeoJsonTooltip(
    fields=["name"],
    aliases=["Регіон:"],
    labels=True,
    sticky=True,
    localize=True,
    style=("background-color: white; color: #333333; font-size: 12px; padding: 5px;")
)

# Додаємо GeoJson
folium.GeoJson(
    geojson_data,
    style_function=style_function,
    tooltip=tooltip
).add_to(m)

# Постійні підписи назв регіонів
for feature in geojson_data["features"]:
    eng_name = feature["properties"]["name"]
    coords = feature["properties"].get("center")  # координати центру в geojson
    if coords:
        ukr_name_list = [k for k,v in region_name_map.items() if v==eng_name]
        if ukr_name_list:
            folium.map.Marker(
                location=[coords[1],coords[0]],
                icon=folium.DivIcon(
                    html=f"""<div style="font-size:10pt; font-weight:bold; color:#000">{ukr_name_list[0]}</div>"""
                )
            ).add_to(m)

# Легенда з квадратиками і цифрами, зверху вниз: зелений -> жовтий -> помаранч -> червоний
legend_html = """
<div style="
position: fixed; bottom: 50px; left: 50px;
width: 140px; height: 120px;
background-color: white; border:2px solid grey;
z-index:9999; font-size:12px; padding: 10px;
">
<i style="background:#1a9850;width:15px;height:15px;display:inline-block"></i> ≥100%<br>
<i style="background:#fee08b;width:15px;height:15px;display:inline-block"></i> 75–99%<br>
<i style="background:#f46d43;width:15px;height:15px;display:inline-block"></i> 50–74%<br>
<i style="background:#d73027;width:15px;height:15px;display:inline-block"></i> <50%
</div>
"""
m.get_root().html.add_child(folium.Element(legend_html))

st.subheader("Карта стану забезпечення засобами РХБ захисту")
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
