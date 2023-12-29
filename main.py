import dash
from dash import html, dcc, Input, Output, dash_table, State
import pandas as pd
from datetime import datetime, timedelta
import plotly.graph_objs as go

app = dash.Dash(__name__)

# Verileri yükle ve işle
df = pd.read_excel('Sample_Data.xlsx')
df['orderDate'] = pd.to_datetime(df['orderDate'])
df['month'] = df['orderDate'].dt.strftime('%Y-%m')
df['sapma_%'] = ((df['producedQuantity'] - df['plannedQuantity']) / df['plannedQuantity']) * 100
df['sapma_%'] = df['sapma_%'].round(2)  # Ondalık kısmı iki basamakla sınırla

# İşletme ve Ürün Grupları için Dropdown menü seçenekleri
unique_businesses = [{'label': 'Tümü', 'value': 'Tümü'}] + \
                    [{'label': business, 'value': business} for business in df['productionPlace'].unique()]

unique_product_groups = [{'label': 'Tümü', 'value': 'Tümü'}] + \
                        [{'label': group, 'value': group} for group in df['productName'].unique()]

# Tarih Filtreleme Fonksiyonu
def filter_by_date_range(dataframe, start_date, end_date):
    mask = (dataframe['orderDate'] >= start_date) & (dataframe['orderDate'] <= end_date)
    return dataframe.loc[mask]

# Tarih filtresi için varsayılan değerleri ayarla
default_start_date = datetime.now() - timedelta(days=90)
default_end_date = datetime.now()

app.layout = html.Div([
    html.Div([
        html.Label('İşletme:', style={'font-weight': 'bold', 'font-size': '20px'}),
        dcc.Dropdown(
            id='business-dropdown',
            options=unique_businesses,
            value='Tümü',
            clearable=False
        ),
        html.Label('Ürün Grupları:', style={'font-weight': 'bold', 'font-size': '20px'}),
        dcc.Dropdown(
            id='product-group-dropdown',
            options=unique_product_groups,
            value='Tümü',
            clearable=False
        ),
        dcc.DatePickerRange(
            id='date-picker-range',
            start_date=default_start_date,
            end_date=default_end_date,
            display_format='YYYY-MM-DD'
        )
    ]),
    dash_table.DataTable(
        id='consumption-deviation-table',
        columns=[
            {'name': 'Ürün-Malzeme Adı', 'id': 'productName', 'type': 'text'},
            {'name': 'Birim', 'id': 'plannedUoM', 'type': 'text'},
            {'name': 'Reçete Miktarı', 'id': 'plannedQuantity', 'type': 'numeric'},
            {'name': 'Fiili Miktar', 'id': 'producedQuantity', 'type': 'numeric'},
            {'name': 'Sapma %', 'id': 'sapma_%', 'type': 'numeric'}
        ],
        style_cell={'textAlign': 'center', 'font_size': '18px', 'height': 'auto', 'minWidth': '100px', 'width': '100px', 'maxWidth': '100px'},
        style_header={'fontWeight': 'bold', 'font_size': '20px'},
        data=df.to_dict('records'),
        row_selectable='single'
    ),
    dcc.Graph(id='sku-deviation-chart'),
    html.Div(id='sapma-detay', children=[])
])

@app.callback(
    Output('product-group-dropdown', 'options'),
    [Input('business-dropdown', 'value')]
)
def update_product_group_options(selected_business):
    if selected_business == 'Tümü':
        return unique_product_groups
    else:
        filtered_df = df[df['productionPlace'] == selected_business]
        filtered_groups = [{'label': 'Tümü', 'value': 'Tümü'}] + \
                          [{'label': group, 'value': group} for group in filtered_df['productName'].unique()]
        return filtered_groups

@app.callback(
    [Output('consumption-deviation-table', 'data'),
     Output('sku-deviation-chart', 'figure')],
    [Input('business-dropdown', 'value'),
     Input('product-group-dropdown', 'value'),
     Input('date-picker-range', 'start_date'),
     Input('date-picker-range', 'end_date')]
)
def update_data(selected_business, selected_product_group, start_date, end_date):
    # ... (veri filtreleme ve grafik oluşturma kodları)
    if selected_business == 'Tümü' and selected_product_group == 'Tümü':
        filtered_df = df
    elif selected_business == 'Tümü':
        filtered_df = df[df['productName'] == selected_product_group]
    elif selected_product_group == 'Tümü':
        filtered_df = df[df['productionPlace'] == selected_business]
    else:
        filtered_df = df[(df['productionPlace'] == selected_business) & 
                         (df['productName'] == selected_product_group)]
    
    filtered_df = filter_by_date_range(filtered_df, start_date, end_date)
    
    # SKU Bazlı Sapma Grafik Güncellemesi
    sku_deviation = filtered_df.groupby('orderDate').agg({'producedQuantity': 'sum', 'sapma_%': 'mean'}).reset_index()
    sku_deviation.sort_values(by='orderDate', ascending=True, inplace=True)
    sku_deviation['cumulative_quantity'] = sku_deviation['producedQuantity'].cumsum()

    # Renk baremi tanımla
    colors = ['green' if x < 5 else 'yellow' if x < 50 else 'red' for x in sku_deviation['sapma_%']]

    fig = go.Figure(data=[
        go.Bar(x=sku_deviation['orderDate'], y=sku_deviation['cumulative_quantity'], name='Kümülatif Üretilen Miktar')
    ])
    fig.update_layout(
        title='Zaman Ekseninde Kümülatif Üretilen Miktar',
        xaxis_title='Tarih',
        yaxis_title='Kümülatif Üretilen Miktar'
    )

    table_data = filtered_df.to_dict('records')
    return table_data, fig

@app.callback(
    Output('sapma-detay', 'children'),
    [Input('consumption-deviation-table', 'active_cell')],
    [State('consumption-deviation-table', 'data')]
)
def display_deviation_detail(active_cell, table_data):
    # Etkileşim sonrası açılan tabloya ekstra alanlar ekle
    if active_cell and 'row' in active_cell:
        selected_row = table_data[active_cell['row']]
        selected_product_name = selected_row['productName']
        deviation_details = df[df['productName'] == selected_product_name][[
            'productName', 'plannedUoM', 'plannedQuantity', 'producedQuantity', 'sapma_%'
        ]]

        return html.Div([
            html.H4(f"Detaylar: {selected_product_name}"),
            dash_table.DataTable(
                data=deviation_details.to_dict('records'),
                columns=[
                    {'name': 'SKU Bazlı Sapma', 'id': 'productName'},
                    {'name': 'Birim', 'id': 'plannedUoM'},
                    {'name': 'Reçete Miktar', 'id': 'plannedQuantity'},
                    {'name': 'Fiili Miktar', 'id': 'producedQuantity'},
                    {'name': 'Sapma %', 'id': 'sapma_%'}
                ],
                style_cell={'textAlign': 'center', 'font_size': '18px', 'height': 'auto', 'minWidth': '100px', 'width': '100px', 'maxWidth': '100px'},
                style_header={'fontWeight': 'bold', 'font_size': '20px'},
                page_size=10
            )
        ])
    return html.Div("Detayları görmek için bir sütuna tıklayın.")

if __name__ == '__main__':
    app.run_server(debug=True)
