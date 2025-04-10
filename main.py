import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
# %pip install statsmodels
import plotly.graph_objects as go
import plotly.express as px
from statsmodels.tsa.statespace.sarimax import SARIMAX
from datetime import datetime, timedelta
import pickle
import os

# Set page configuration
st.set_page_config(
    page_title="Stock Price Predictor",
    page_icon="📈",
    layout="wide"
)

# Custom styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #1E88E5;
        text-align: center;
    }
    .sub-header {
        font-size: 1.5rem;
        color: #424242;
        margin-bottom: 1rem;
    }
    .prediction-box {
        background-color: #f0f2f6;
        padding: 20px;
        border-radius: 10px;
        margin-bottom: 10px;
    }
    .prediction-value {
        font-size: 1.8rem;
        font-weight: bold;
        color: #1E88E5;
    }
    .sentiment-positive {
        color: #4CAF50;
    }
    .sentiment-negative {
        color: #F44336;
    }
    .sentiment-neutral {
        color: #FF9800;
    }
</style>
""", unsafe_allow_html=True)

# Header
st.markdown("<h1 class='main-header'>Stock Price Predictor with Sentiment Analysis</h1>", unsafe_allow_html=True)
st.markdown("<p class='sub-header'>Forecast future stock prices based on historical data and sentiment analysis</p>", unsafe_allow_html=True)

# Function to load models
@st.cache_resource
def load_models():
    # File paths for saved models
    stock_model_path = 'stock_model.pkl'
    ewma_model_path = 'ewma_model.pkl'
    
    # Check if models exist
    if os.path.exists(stock_model_path) and os.path.exists(ewma_model_path):
        with open(stock_model_path, 'rb') as f:
            full_model_fit = pickle.load(f)
        with open(ewma_model_path, 'rb') as f:
            ewma_model_fit = pickle.load(f)
        return full_model_fit, ewma_model_fit
    else:
        st.error("Model files not found! Please ensure you've trained the models first.")
        return None, None

# Function to load data
@st.cache_data
def load_data():
    try:
        # Load your merged data here - adjust the path as needed
        # This is a placeholder - you'll need to replace with your actual data loading code
        merged_data = pd.read_csv('merged_data.csv', index_col=0, parse_dates=True)
        return merged_data
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return None

# Function to predict stock price for a specified date
def predict_stock_price(target_date, full_model_fit, ewma_model_fit, merged_data):
    # Convert to datetime object if it's not already
    if isinstance(target_date, str):
        target_date = datetime.strptime(target_date, "%Y-%m-%d")
    
    # Calculate how many days ahead we need to predict
    last_date = merged_data.index[-1].to_pydatetime()
    days_ahead = (target_date - last_date.date()).days
    
    if days_ahead <= 0:
        st.error("Target date is not in the future.")
        return None
    
    # Create date range from last data point to target date
    future_dates = pd.date_range(start=last_date + pd.Timedelta(days=1),
                              end=target_date, freq='D')
    
    # Predict future EWMA values using the EWMA model
    ewma_forecast = ewma_model_fit.get_forecast(steps=len(future_dates))
    predicted_ewma = ewma_forecast.predicted_mean
    
    # Reindex predicted_ewma to match future_dates
    predicted_ewma.index = future_dates
    
    # Create DataFrame for future EWMA values
    future_ewma = pd.DataFrame({'ewma_3': predicted_ewma}, index=future_dates)
    
    # Generate stock price predictions using the predicted EWMA values
    future_predictions = full_model_fit.get_forecast(steps=len(future_dates), exog=future_ewma)
    forecast_mean = future_predictions.predicted_mean
    forecast_ci = future_predictions.conf_int(alpha=0.05)
    
    forecast_mean.index = future_dates
    forecast_ci.index = future_dates
    
    # Create a DataFrame with predictions
    forecast_df = pd.DataFrame({
        'Predicted_Close': forecast_mean,
        'Predicted_EWMA': predicted_ewma,
        'Lower_CI': forecast_ci['lower Close'],
        'Upper_CI': forecast_ci['upper Close']
    }, index=future_dates)
    
    return forecast_df

# Function to visualize predictions
def visualize_predictions(historical_data, forecast_df):
    # Create a figure with plotly
    fig = go.Figure()
    
    # Add historical stock price data
    fig.add_trace(go.Scatter(
        x=historical_data.index,
        y=historical_data['Close'],
        mode='lines',
        name='Historical Stock Price',
        line=dict(color='blue')
    ))
    
    # Add predicted stock price
    fig.add_trace(go.Scatter(
        x=forecast_df.index,
        y=forecast_df['Predicted_Close'],
        mode='lines',
        name='Predicted Stock Price',
        line=dict(color='red', dash='dash')
    ))
    
    # Add confidence interval
    fig.add_trace(go.Scatter(
        x=forecast_df.index.tolist() + forecast_df.index.tolist()[::-1],
        y=forecast_df['Upper_CI'].tolist() + forecast_df['Lower_CI'].tolist()[::-1],
        fill='toself',
        fillcolor='rgba(231,107,243,0.2)',
        line=dict(color='rgba(255,255,255,0)'),
        name='95% Confidence Interval'
    ))
    
    # Update layout
    fig.update_layout(
        title='Stock Price Forecast',
        xaxis_title='Date',
        yaxis_title='Stock Price (₹)',
        legend_title='Legend',
        template='plotly_white',
        height=500
    )
    
    return fig

# Function to visualize EWMA sentiment
def visualize_sentiment(historical_data, forecast_df):
    # Create a figure with plotly
    fig = go.Figure()
    
    # Add historical EWMA sentiment
    fig.add_trace(go.Scatter(
        x=historical_data.index,
        y=historical_data['ewma_3'],
        mode='lines',
        name='Historical EWMA Sentiment',
        line=dict(color='green')
    ))
    
    # Add predicted EWMA sentiment
    fig.add_trace(go.Scatter(
        x=forecast_df.index,
        y=forecast_df['Predicted_EWMA'],
        mode='lines',
        name='Predicted EWMA Sentiment',
        line=dict(color='orange', dash='dash')
    ))
    
    # Update layout
    fig.update_layout(
        title='EWMA Sentiment Forecast',
        xaxis_title='Date',
        yaxis_title='EWMA Sentiment',
        legend_title='Legend',
        template='plotly_white',
        height=500
    )
    
    return fig

# Main app
def main():
    # Load models
    full_model_fit, ewma_model_fit = load_models()
    
    # Load data
    merged_data = load_data()
    
    if full_model_fit is None or ewma_model_fit is None or merged_data is None:
        st.warning("Please ensure model files and data are available.")
        return
    
    # App sidebar
    with st.sidebar:
        st.header("Prediction Settings")
        
        # Date range for predictions
        min_date = merged_data.index[-1].date() + timedelta(days=1)
        max_date = min_date + timedelta(days=365)  # Allow predictions up to a year ahead
        
        prediction_date = st.date_input(
            "Select prediction date",
            min_value=min_date,
            max_value=max_date,
            value=min_date + timedelta(days=30)
        )
        
        st.info(f"Last available data: {merged_data.index[-1].date()}")
        
        # Add information about the model
        st.subheader("About the Model")
        st.write("""
        This application uses a SARIMAX model to predict stock prices based on:
        - Historical price data
        - EWMA (Exponentially Weighted Moving Average) sentiment analysis
        
        The model provides predictions with 95% confidence intervals.
        """)
    
    # Make prediction
    try:
        forecast_df = predict_stock_price(prediction_date, full_model_fit, ewma_model_fit, merged_data)
        
        if forecast_df is not None:
            # Display prediction for target date
            target_prediction = forecast_df.loc[prediction_date] if prediction_date in forecast_df.index else forecast_df.iloc[-1]
            
            # Create columns for prediction results
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("<div class='prediction-box'>", unsafe_allow_html=True)
                st.markdown("### Predicted Stock Price")
                st.markdown(f"<div class='prediction-value'>₹{target_prediction['Predicted_Close']:.2f}</div>", unsafe_allow_html=True)
                st.markdown(f"95% Confidence Interval: ₹{target_prediction['Lower_CI']:.2f} - ₹{target_prediction['Upper_CI']:.2f}")
                st.markdown("</div>", unsafe_allow_html=True)
            
            with col2:
                st.markdown("<div class='prediction-box'>", unsafe_allow_html=True)
                st.markdown("### Predicted EWMA Sentiment")
                
                sentiment_value = target_prediction['Predicted_EWMA']
                sentiment_class = "neutral"
                if sentiment_value > 0.05:
                    sentiment_class = "positive"
                elif sentiment_value < -0.05:
                    sentiment_class = "negative"
                
                st.markdown(f"<div class='prediction-value sentiment-{sentiment_class}'>{sentiment_value:.4f}</div>", unsafe_allow_html=True)
                st.markdown("</div>", unsafe_allow_html=True)
            
            # Show visualizations
            st.subheader("Price Forecast Visualization")
            price_fig = visualize_predictions(merged_data.iloc[-90:], forecast_df)  # Show last 90 days of historical data
            st.plotly_chart(price_fig, use_container_width=True)
            
            st.subheader("Sentiment Forecast Visualization")
            sentiment_fig = visualize_sentiment(merged_data.iloc[-90:], forecast_df)  # Show last 90 days of historical data
            st.plotly_chart(sentiment_fig, use_container_width=True)
            
            # Show raw prediction data
            with st.expander("View detailed prediction data"):
                st.dataframe(forecast_df)
    
    except Exception as e:
        st.error(f"Error making prediction: {e}")
        st.exception(e)

if __name__ == "__main__":
    main()