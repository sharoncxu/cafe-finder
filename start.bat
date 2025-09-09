@echo off
echo Starting Location Finding Agent (GitHub Copilot Powered)...
echo.
echo Installing Python dependencies...
C:/Users/sharonxu/location-finding-agent/.venv/Scripts/python.exe -m pip install -r requirements.txt

echo.
echo Testing GitHub Copilot connection...
C:/Users/sharonxu/location-finding-agent/.venv/Scripts/python.exe test_github_copilot.py

echo.
echo Starting Flask backend...
start "Backend" cmd /k "C:/Users/sharonxu/location-finding-agent/.venv/Scripts/python.exe app.py"

echo.
echo Installing frontend dependencies...
cd frontend
npm install

echo.
echo Starting React frontend...
start "Frontend" cmd /k "npm start"

echo.
echo Both servers are starting...
echo Backend will be available at: http://localhost:5000
echo Frontend will be available at: http://localhost:3000
echo.
echo Make sure to:
echo 1. Copy .env.example to .env
echo 2. Add your GitHub Personal Access Token (GITHUB_TOKEN)
echo 3. Add your Google Maps API key (GOOGLE_MAPS_API_KEY)
pause
