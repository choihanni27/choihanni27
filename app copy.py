from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import sqlite3
import hashlib
import requests
from datetime import datetime, timedelta
import urllib.parse

app = Flask(__name__)
app.secret_key = "secret"

# 기상청 API 예시 URL (단기예보)
# 실제 서비스용은 인증키와 좌표 필요
WEATHER_API_URL = "https://apihub.kma.go.kr/api/typ01/cgi-bin/url/nph-dfs_shrt_grd?tmfc=2024022505&tmef=2024022506&vars=TMP&authKey=0Fta38EhSJGbWt_BIRiReQ"
SERVICE_KEY = "0Fta38EhSJGbWt_BIRiReQ"  # 기상청 발급 인증키
SERVICE_KEY = urllib.parse.quote(SERVICE_KEY, safe='')
NX = 37.4811  # 예시 X 좌표
NY = 126.9278 # 예시 Y 좌표

def get_db():
    conn = sqlite3.connect('users.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = sqlite3.connect("users.db")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT
        )
    """)
    conn.commit()
    conn.close()

def get_recent_base_time():
    """현재 시간 기준 가장 최근 3시간 단위 예보 base_time 계산"""
    now = datetime.now()
    hour = now.hour
    if hour < 2:
        base_date = (now - timedelta(days=1)).strftime("%Y%m%d")
        base_time = "2300"
    else:
        base_date = now.strftime("20251214")
        # 3시간 단위, 2~5->02, 5~8->05, 8~11->08, 11~14->11, 14~17->14, 17~20->17, 20~23->20, 23~2->23
        base_time_hour = (hour // 3) * 3
        base_time = f"{base_time_hour:02d}00"
    return base_date, base_time

def fetch_weather():
    base_date, base_time = get_recent_base_time()
    params = {
        "serviceKey": SERVICE_KEY,
        "pageNo": "1",
        "numOfRows": "100",
        "dataType": "JSON",
        "base_date": 20251214,
        "base_time": 2330,
        "nx": NX,
        "ny": NY
    }

    try:
        res = requests.get(WEATHER_API_URL, params=params, timeout=5)
        res.raise_for_status()
        items = res.json().get("response", {}).get("body", {}).get("items", {}).get("item", [])

        weather = {"temperature": "-", "sky": "-", "icon": "bi-exclamation-circle-fill"}

        # 필요한 항목 필터링
        for item in items:
            category = item.get("category")
            if category == "T1H":  # 기온
                weather["temperature"] = f"{item['fcstValue']}°C"
            elif category == "SKY":  # 하늘상태
                sky_code = item['fcstValue']
                if sky_code == "1":
                    weather["sky"] = "맑음"
                    weather["icon"] = "bi-sun-fill"
                elif sky_code == "3":
                    weather["sky"] = "구름많음"
                    weather["icon"] = "bi-cloud-fill"
                elif sky_code == "4":
                    weather["sky"] = "흐림"
                    weather["icon"] = "bi-clouds-fill"
        return weather
    except Exception as e:
        print("Weather API Error:", e)
        return {"temperature": "-", "sky": "정보 없음", "icon": "bi-exclamation-circle-fill"}


# @app.route("/")
# def index():
# # 기상청 API 요청
#     params = {
#         "serviceKey": SERVICE_KEY,
#         "pageNo": 1,
#         "numOfRows": 100,
#         "dataType": "JSON",
#         "base_date": "20251214",  # YYYYMMDD
#         "base_time": "0600",      # HHMM
#         "nx": NX,
#         "ny": NY
#     }
#     try:
#         res = requests.get(WEATHER_API_URL, params=params)
#         data = res.json()
#         # 단순화: 필요 데이터만 추출
#         forecast = data.get("response", {}).get("body", {}).get("items", {}).get("item", [])
#         today_weather = {
#             "temperature": "22°C",
#             "weather": "맑음",
#             "icon": "bi-sun-fill"
#         }
#         # 실제 API 결과에 맞춰 mapping 필요
#         # 예시용 임시 데이터 사용
#     except:
#         today_weather = {
#             "temperature": "-",
#             "weather": "정보 없음",
#             "icon": "bi-exclamation-circle-fill"
#         }

#     return render_template("index.html", weather=today_weather)

def get_weather():
    now = datetime.now()
    
    # 3시간 단위 base_time 계산 (0,3,6,9,12,15,18,21)
    hour = (now.hour // 3) * 3
    base_time = f"{hour:02d}00"
    base_date = now.strftime("%Y%m%d")

    params = {
        "serviceKey": SERVICE_KEY,
        "pageNo": 1,
        "numOfRows": 100,
        "dataType": "JSON",
        "base_date": base_date,
        "base_time": base_time,
        "nx": NX,
        "ny": NY
    }

    try:
        res = requests.get(WEATHER_API_URL, params=params, timeout=5)
        res.raise_for_status()
        data = res.json()
        
        items = data.get("response", {}).get("body", {}).get("items", {}).get("item", [])
        if not items:
            raise ValueError("예보 데이터 없음")

        # 예시: 첫 번째 데이터 사용 (필요하면 카테고리별 필터링 가능)
        today_weather = {
            "temperature": items[0].get("fcstValue", "-") + "°C",
            "weather": items[0].get("category", "-"),
            "icon": "bi-sun-fill"  # 카테고리별 아이콘 매핑 가능
        }
    except Exception as e:
        print("Weather API error:", e)
        today_weather = {
            "temperature": "-",
            "weather": "정보 없음",
            "icon": "bi-exclamation-circle-fill"
        }

    return today_weather

def get_current_weather():
    now = datetime.now()
    base_date = now.strftime("%Y%m%d")
    # 기상청 API는 매 시간 단위 기준 0200, 0500, 0800, 1100 ... 이렇게만 가능
    # 가장 가까운 기준시간 선택
    hour = now.hour
    if hour < 2: base_time = "2300"; base_date = (now - timedelta(days=1)).strftime("%Y%m%d")
    elif hour < 5: base_time = "0200"
    elif hour < 8: base_time = "0500"
    elif hour < 11: base_time = "0800"
    elif hour < 14: base_time = "1100"
    elif hour < 17: base_time = "1400"
    elif hour < 20: base_time = "1700"
    elif hour < 23: base_time = "2000"
    else: base_time = "2300"

    params = {
        "serviceKey": SERVICE_KEY,
        "pageNo": 1,
        "numOfRows": 100,
        "dataType": "JSON",
        "base_date": base_date,
        "base_time": base_time,
        "nx": NX,
        "ny": NY
    }

    try:
        res = requests.get(WEATHER_API_URL, params=params)
        items = res.json().get("response", {}).get("body", {}).get("items", {}).get("item", [])

        temperature = None
        pty = None

        # 현재 시간 기준으로 가장 가까운 fcstTime 데이터 사용
        for i in items:
            if i["category"] == "T3H":
                temperature = i["fcstValue"]
            if i["category"] == "PTY":
                pty = i["fcstValue"]

        icon = {
            "0": "bi-sun-fill",
            "1": "bi-cloud-rain-fill",
            "2": "bi-cloud-snow-fill",
            "3": "bi-cloud-sleet-fill",
            "4": "bi-cloud-lightning-rain-fill"
        }.get(str(pty), "bi-sun-fill")

        weather_text = {
            "0": "맑음",
            "1": "비",
            "2": "눈",
            "3": "진눈깨비",
            "4": "천둥"
        }.get(str(pty), "맑음")

        return {
            "temperature": f"{temperature}°C" if temperature else "-",
            "weather": weather_text,
            "icon": icon
        }

    except Exception as e:
        print("Weather API error:", e)
        return {"temperature": "-", "weather": "정보 없음", "icon": "bi-exclamation-circle-fill"}



@app.route("/")
def index():
    now = datetime.now()

    weekday_map = {
        "Monday": "월",
        "Tuesday": "화",
        "Wednesday": "수",
        "Thursday": "목",
        "Friday": "금",
        "Saturday": "토",
        "Sunday": "일"
    }

    date_info = {
        "year": now.strftime("%Y"),
        "date": now.strftime("%m.%d"),
        "weekday": weekday_map[now.strftime("%A")]
    }

    weather = {
        "temperature": "-",
        "weather": "정보 없음",
        "icon": "bi-cloud-slash"
    }

    weather = get_weather()

    return render_template(
        "index.html",
        date_info=date_info,
        weather=weather
    )
    # weather = get_weather()
    # return render_template("index.html", weather=weather)

# @app.route("/")
# def get_weather(base_date="20251214", base_time="0600"):
#     params = {
#         "serviceKey": SERVICE_KEY,
#         "pageNo": 1,
#         "numOfRows": 100,
#         "dataType": "JSON",
#         "base_date": base_date,
#         "base_time": base_time,
#         "nx": NX,
#         "ny": NY
#     }
#     try:
#         res = requests.get(WEATHER_API_URL, params=params)
#         data = res.json()
#         items = data.get("response", {}).get("body", {}).get("items", {}).get("item", [])

#         weather = {
#             "temperature": next((i["fcstValue"] for i in items if i["category"]=="T3H"), "N/A"),
#             "weather": next((i["fcstValue"] for i in items if i["category"]=="PTY"), "맑음")
#         }
#         weather["icon"] = {
#             "0": "bi-sun-fill",
#             "1": "bi-cloud-rain-fill",
#             "2": "bi-cloud-snow-fill",
#             "3": "bi-snow"
#         }.get(weather["weather"], "bi-sun-fill")

#         return weather
#     except Exception as e:
#         print("Weather API error:", e)
#         return {"temperature": "-", "weather": "정보 없음", "icon": "bi-exclamation-circle-fill"}

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = get_db()
        conn.execute(
            "INSERT INTO users (username, password) VALUES (?, ?)",
            (username, password)
        )
        conn.commit()
        conn.close()

        flash("회원가입 완료")
        return redirect(url_for("login"))

    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        # form data 방식
        username = request.form.get("username")
        password = request.form.get("password")

        print("Received form data:", username, password)  # 디버깅용 출력

        conn = get_db()
        user = conn.execute(
            "SELECT * FROM users WHERE username = ? AND password = ?",
            (username, password)
        ).fetchone()
        conn.close()

        if user:
            session["user_id"] = user["id"]
            flash("로그인 성공")
            return redirect(url_for("index"))
        else:
            flash("아이디 또는 비밀번호가 잘못되었습니다.")
            return redirect(url_for("login"))

    # GET 요청 시 로그인 페이지 렌더링
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return render_template("login.html")

@app.route("/upload", methods=["GET", "POST"])
def upload():
    return render_template("upload.html")

@app.route("/closet")
def closet():
    return render_template("closet.html")

@app.route("/profile", methods=["GET", "POST"])
def profile():
    return render_template("profile.html")




if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5001)

