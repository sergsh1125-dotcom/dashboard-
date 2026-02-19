# app.py

```python
import streamlit as st
import pandas as pd
import plotly.express as px

# Заголовок
st.set_page_config(page_title='Дашборд СІЗ', layout='wide')
st.title('Дашборд обліку СІЗ по регіонах України')

# Завантаження прикладових даних
@st.cache_data
def load_data():
    return pd.read_csv('data/example_stock.csv')

df = load_data()

# Вкладки
tab1, tab2 = st.tabs(['Керівницький огляд', 'Робочі таблиці'])

with tab2:
    st.header('Робочі таблиці')
    edited_df = st.data_editor(df, num_rows='dynamic', use_container_width=True)

with tab1:
    st.header('Карта забезпечення СІЗ')
    # Обчислюємо % забезпечення
    df_grouped = edited_df.groupby('region_name').agg({'quantity':'sum'}).reset_index()
    df_grouped['percent_coverage'] = (df_grouped['quantity'] / df_grouped['quantity'].max()) * 100

    # Проста карта з Plotly Express (GeoJSON у data/ukraine_regions.geojson)
    try:
        geojson = 'data/ukraine_regions.geojson'
        fig = px.choropleth(df_grouped,
                            geojson=geojson,
                            locations='region_name',
                            color='percent_coverage',
                            featureidkey='properties.name',
                            color_continuous_scale='Viridis',
                            scope='europe')
        fig.update_geos(fitbounds='locations', visible=False)
        st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.warning(f'Карта не завантажена: {e}')

    # KPI
    st.metric('Середній % забезпечення', f'{df_grouped['percent_coverage'].mean():.1f}%')
    st.metric('Загальна кількість СІЗ', f'{df_grouped['quantity'].sum()}')
```

---

# requirements.txt

```
streamlit>=1.24.0
pandas>=2.0.3
plotly>=5.16.0
```

---

# README.md

```markdown
# Дашборд обліку засобів індивідуального захисту (СІЗ)

Демо-версія керівницького дашборду для обліку СІЗ по 25 регіонах України + 5 підрозділах Києва.

## 📦 Структура проєкту
```

ppe-dashboard/
├── app.py               # Головний файл Streamlit
├── requirements.txt     # Залежності
├── README.md            # Документація
├── data/
│   ├── example_stock.csv        # Прикладові дані СІЗ
│   └── ukraine_regions.geojson  # GeoJSON карта України
└── .streamlit/
└── secrets.toml     # Паролі та доступи (не зберігати в GitHub!)

````

## ⚙️ Встановлення та запуск

1. Клонувати репозиторій:
```bash
git clone https://github.com/yourusername/ppe-dashboard.git
cd ppe-dashboard
````

2. Встановити залежності:

```bash
pip install -r requirements.txt
```

3. Запустити дашборд:

```bash
streamlit run app.py
```

## 🛠 Функціонал

* **Керівницький огляд**: карта України з % забезпечення та KPI
* **Робочі таблиці**: редагування кількості СІЗ, додавання нових партій

## 💡 Рекомендації

* Для великих даних можна підключати Excel-імпорт
* Карта відображає Київ + 5 підрозділів як окремі одиниці
* Реальні дані не повинні потрапляти в репозиторій

```
```

