#!/bin/bash

# Prothome Telegram Bot background e start korbe (& diye background e pathano hoy)
echo "🤖 Starting Telegram Bot..."
python bot.py &

# Tarpor Web App (Streamlit) start korbe
echo "🌐 Starting Web App..."
streamlit run app.py --server.port $PORT --server.address 0.0.0.0