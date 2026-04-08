import matplotlib.pyplot as plt
from dash import Dash, html, dcc, Input, Output
import plotly.express as px
import plotly.tools as tls
import pandas as pd
from VisualizationTools import *

###static version
# Example data
'''
df = px.data.iris()

# Create a Plotly figure
fig = px.scatter(df, x="sepal_width", y="sepal_length", color="species")

# Initialize app
app = Dash(__name__)

# Layout
app.layout = html.Div([
    html.H1("My First Dash App"),
    dcc.Graph(figure=fig)
])
'''

def createPlotlyFigure(figures, duties, unique_locomotives, id_mapping):
    plotly_fig = plot_gantt_chart_locomotives_plotly(duties, unique_locomotives, id_mapping)

    figures.append(plotly_fig)

    return figures

def createScheduleDashboard(filename, duties, unique_locomotives, id_mapping):
    #mpl_fig, _ = plot_gantt_chart_locomotives(filename, duties, unique_locomotives, id_mapping)
    #plotly_fig = tls.mpl_to_plotly(mpl_fig)
    plotly_fig = plot_gantt_chart_locomotives_plotly(duties, unique_locomotives, id_mapping)

    #app = Dash(__name__)
    app = Dash("Schedule")
    app.layout = html.Div([
        dcc.Graph(figure=plotly_fig)
    ])

    # Run server
    #if __name__ == "__main__":
    app.run(debug=True)
    ###static version end

def createScheduleDashboard_MultiWindow(instance, method, window_size, iterations, figures):
    # --------------------------
    # Dash app setup
    # --------------------------
    app = Dash(__name__)

    app.layout = html.Div([
        html.H1(f"Window-Based Crew Rescheduling: {instance} | method: {method} | window size: {window_size} | iterations: {iterations}"),
        html.Button("Show Figures", id="show-btn"),
        html.Div(id="graphs-container")  # placeholder for graphs
    ])

    # --------------------------
    # Callback to display figures on button click
    # --------------------------
    @app.callback(
        Output("graphs-container", "children"),
        Input("show-btn", "n_clicks")
    )
    def display_figures(n_clicks):
        if not n_clicks:
            return []  # do not show anything initially
        # Return a Graph component for each figure
        return [dcc.Graph(figure=f) for f in figures]

    return app

'''
###dynamic version
# Example data
df = px.data.iris()

app = Dash(__name__)

app.layout = html.Div([
    html.H1("Interactive Iris Dashboard"),

    # Dropdown for selecting x-axis
    dcc.Dropdown(
        id='x-axis-dropdown',
        options=[
            {'label': 'Sepal Width', 'value': 'sepal_width'},
            {'label': 'Sepal Length', 'value': 'sepal_length'},
            {'label': 'Petal Width', 'value': 'petal_width'},
            {'label': 'Petal Length', 'value': 'petal_length'}
        ],
        value='sepal_width',  # Default value
        clearable=False
    ),

    # Graph that updates when dropdown changes
    dcc.Graph(id='iris-graph')
])

@app.callback(
    Output('iris-graph', 'figure'),
    Input('x-axis-dropdown', 'value')
)
def update_graph(selected_x):
    # Create a new figure based on dropdown choice
    fig = px.scatter(
        df,
        x=selected_x,
        y='sepal_length',
        color='species',
        title=f"Iris Scatter Plot: {selected_x} vs sepal_length"
    )
    return fig

# Run server
if __name__ == "__main__":
    app.run(debug=True)
###dynamic version end
'''