from flask import Flask, render_template, request, jsonify
import requests
import datetime

app = Flask(__name__)

# Default location
DEFAULT_LAT = 34.0000
DEFAULT_LON = -109.0000

def get_weather(lat, lon):
    headers = {'User-Agent': 'home_weather_page/1.0 (some  @gmail.com)'}
    points_url = f"https://api.weather.gov/points/{lat},{lon}"
    try:
        points_response = requests.get(points_url, headers=headers)
        points_response.raise_for_status()
        points_data = points_response.json()
        grid_x = points_data['properties']['gridX']
        grid_y = points_data['properties']['gridY']
        office = points_data['properties']['cwa']

        grid_url = f"https://api.weather.gov/gridpoints/{office}/{grid_x},{grid_y}/forecast"
        grid_response = requests.get(grid_url, headers=headers)
        grid_response.raise_for_status()
        forecast_data = grid_response.json()
        forecast_periods = forecast_data['properties']['periods']

        weather_data = []
        for period in forecast_periods[:7]:
            weather_data.append({
                'name': period['name'],
                'temperature': period['temperature'],
                'temperature_unit': period['temperatureUnit'],
                'short_forecast': period['shortForecast'],
                'detailed_forecast': period['detailedForecast'],
                'start_time': datetime.datetime.fromisoformat(period['startTime'].replace('Z', '+00:00')).strftime("%I:%M %p"),
                'end_time': datetime.datetime.fromisoformat(period['endTime'].replace('Z', '+00:00')).strftime("%I:%M %p"),
                'icon': period['icon'],
                'wind_speed': period.get('windSpeed', 'N/A'),
                'wind_direction': period.get('windDirection', 'N/A'),
            })
        return weather_data
    except Exception as e:
        return {"error": str(e)}

def get_solar_data(lat, lon):
    try:
        return {
            "solar_flare_probability": "Low",
            "solar_wind_speed": "420 km/s",
            "solar_activity": "Quiet",
            "sunspot_number": 15
        }
    except Exception as e:
        return {"error": str(e)}

def get_earthquake_data(lat, lon):
    url = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/2.5_day.geojson"
    try:
        res = requests.get(url).json()
        quakes = []
        for quake in res["features"]:
            coords = quake["geometry"]["coordinates"]
            dist = ((coords[1] - lat)**2 + (coords[0] - lon)**2)**0.5
            if dist < 5:  # Within 5 degrees (~500km)
                quakes.append({
                    "magnitude": quake["properties"]["mag"],
                    "place": quake["properties"]["place"],
                    "time": datetime.datetime.fromtimestamp(quake["properties"]["time"]/1000).strftime("%Y-%m-%d %H:%M:%S")
                })
        return quakes
    except Exception as e:
        return {"error": str(e)}

def get_schumann_resonance():
    try:
        return {
            "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "frequency": "7.83 Hz",
            "intensity": "Medium",
            "variations": "0.3 Hz"
        }
    except Exception as e:
        return {"error": str(e)}

def get_uv_index(lat, lon):
    try:
        return {
            "value": 5.2,
            "risk_level": "Moderate",
            "protection": "Stay in shade near midday"
        }
    except Exception as e:
        return {"error": str(e)}


def get_air_quality(lat, lon):
    try:
        # Using a free AQI API (no key required)
        url = f"https://api.waqi.info/feed/geo:{lat};{lon}/?token=demo"
        response = requests.get(url)
        data = response.json()
        
        if data['status'] == 'ok':
            aqi_data = {
                'aqi': {
                    'value': data['data']['aqi'],
                    'last_updated': data['data']['time']['s']
                }
            }
            # Add individual pollutants if available
            iaqi = data['data']['iaqi']
            for pollutant in ['pm25', 'pm10', 'o3', 'no2', 'so2', 'co']:
                if pollutant in iaqi:
                    aqi_data[pollutant] = {
                        'value': iaqi[pollutant]['v'],
                        'unit': 'µg/m³' if pollutant != 'co' else 'mg/m³'
                    }
            return aqi_data
        return {"error": "No air quality data available"}
    except Exception as e:
        return {"error": str(e)}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/data', methods=['GET'])
def api_data():
    lat = float(request.args.get('lat', DEFAULT_LAT))
    lon = float(request.args.get('lon', DEFAULT_LON))

    return jsonify({
        'weather': get_weather(lat, lon),
        'air_quality': get_air_quality(lat, lon),
        'solar': get_solar_data(lat, lon),
        'earthquakes': get_earthquake_data(lat, lon),
        'schumann': get_schumann_resonance(),
        'uv_index': get_uv_index(lat, lon),
        'water_quality': get_water_quality(lat, lon)
    })

@app.route('/api/chat', methods=['POST'])
def chat():
    user_message = request.json.get('message')
    if not user_message:
        return jsonify({'error': 'No message provided'}), 400

    try:
        context_prompt = f"""
        You are an environmental data expert. The user is viewing data about:
        - Weather forecasts
        - Solar activity
        - Recent earthquakes
        - Schumann resonance
        - UV index
        - Air quality
        - Water quality
        
        User question: {user_message}
        
        Provide a helpful and concise response based on general environmental knowledge.
        """
        
        response = requests.post('http://localhost:11434/api/generate', 
                                json={
                                    "model": "llama2",  # Using a standard model
                                    "prompt": context_prompt,
                                    "stream": False
                                },
                                timeout=30)
        
        response.raise_for_status()
        result = response.json()
        
        ai_response = result.get('response', 'No response generated')
        
        return jsonify({'response': ai_response})
    except requests.exceptions.RequestException as e:
        return jsonify({'error': f'Connection error: {str(e)}'}), 500
    except Exception as e:
        return jsonify({'error': f'Error processing request: {str(e)}'}), 500
    
def get_water_quality(lat, lon):
    try:
        url = f"https://waterservices.usgs.gov/nwis/iv/?format=json&bbox={lon-0.1},{lat-0.1},{lon+0.1},{lat+0.1}&parameterCd=00060,00065,00300&siteStatus=all"
        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            return {"error": "Failed to fetch water quality data"}
        
        data = response.json()
        
        water_data = []
        if 'value' in data and 'timeSeries' in data['value']:
            for series in data['value']['timeSeries'][:5]:  # Limit to 5 entries
                try:
                    site_info = series['sourceInfo']
                    variable = series['variable']['variableName']
                    # Handle missing values properly
                    value = 'N/A'
                    if (series['values'] and 
                        series['values'][0]['value'] and 
                        series['values'][0]['value'][0]['value'] not in [None, '']):
                        value = series['values'][0]['value'][0]['value']
                    
                    water_data.append({
                        'site_name': site_info.get('siteName', 'Unknown Site'),
                        'variable': variable,
                        'value': value,
                        'unit': series['variable']['unit'].get('unitCode', ''),
                        'coordinates': site_info['geoLocation']['geogLocation']
                    })
                except (KeyError, IndexError) as e:
                    continue  # Skip malformed entries
        return water_data if water_data else {"error": "No water quality data available"}
    except Exception as e:
        return {"error": f"Error fetching water quality data: {str(e)}"}

if __name__ == '__main__':
    app.run(debug=True)