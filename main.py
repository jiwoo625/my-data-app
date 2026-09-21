```python
import streamlit as st
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


# ---------------------------------------------------------
# 기본 설정
# ---------------------------------------------------------

st.set_page_config(
    page_title="박스오피스",
    page_icon="🎬",
    layout="wide",
)


# ---------------------------------------------------------
# KOBIS API 주소
# ---------------------------------------------------------

API_URL = (
    "https://www.kobis.or.kr/kobisopenapi/webservice/rest/"
    "boxoffice/searchDailyBoxOfficeList.json"
)


# ---------------------------------------------------------
# 한국 시간 기준 날짜 계산
#
# 배포 서버의 시간이 한국 시간이 아닐 수 있으므로
# 반드시 Asia/Seoul 시간대를 사용합니다.
# ---------------------------------------------------------

def get_korea_today():
    """한국 시간 기준 오늘 날짜를 반환합니다."""
    return datetime.now(ZoneInfo("Asia/Seoul")).date()


# ---------------------------------------------------------
# KOBIS API에서 박스오피스 가져오기
#
# 같은 날짜를 다시 조회하면 1시간 동안 캐시된 결과를
# 사용합니다.
# ---------------------------------------------------------

@st.cache_data(ttl=3600)
def get_boxoffice(target_date, api_key):
    """지정한 날짜의 KOBIS 일일 박스오피스를 가져옵니다."""

    params = {
        "key": api_key,
        "targetDt": target_date,
    }

    try:
        response = requests.get(
            API_URL,
            params=params,
            timeout=10,
        )

        # HTTP 오류가 있으면 예외를 발생시킵니다.
        response.raise_for_status()

        # JSON으로 변환합니다.
        data = response.json()

    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "message": (
                "KOBIS API 요청에 실패했습니다.\n\n"
                f"{e}"
            ),
        }

    except ValueError:
        return {
            "success": False,
            "message": (
                "KOBIS API 응답을 JSON으로 읽을 수 없습니다."
            ),
        }

    # -----------------------------------------------------
    # KOBIS는 인증키가 잘못되어도 HTTP 200을 반환할 수 있습니다.
    # 따라서 faultInfo를 반드시 확인합니다.
    # -----------------------------------------------------

    if "faultInfo" in data:
        return {
            "success": False,
            "message": (
                "KOBIS API에서 오류를 반환했습니다.\n\n"
                f"{data['faultInfo']}"
            ),
        }

    # 예상한 응답 구조인지 확인합니다.
    boxoffice_result = data.get("boxOfficeResult")

    if not boxoffice_result:
        return {
            "success": False,
            "message": (
                "KOBIS 응답에 boxOfficeResult가 없습니다.\n\n"
                "인증키와 KOBIS API 상태를 확인해 주세요."
            ),
        }

    movie_list = boxoffice_result.get(
        "dailyBoxOfficeList",
        []
    )

    # 영화 목록이 없으면 호출한 곳에서
    # '아직 집계 전'으로 안내할 수 있도록 별도로 표시합니다.
    if not movie_list:
        return {
            "success": False,
            "empty": True,
            "message": "그날은 아직 집계 전입니다.",
        }

    return {
        "success": True,
        "empty": False,
        "data": movie_list,
    }


# ---------------------------------------------------------
# 숫자 문자열을 정수로 변환
#
# KOBIS API의 rank, audiCnt 등의 값은 문자열로 옵니다.
# 그래프와 정렬에 사용하기 위해 숫자로 바꿉니다.
# ---------------------------------------------------------

def convert_to_numbers(movie_list):
    """KOBIS의 숫자 문자열을 정수로 변환합니다."""

    converted = []

    for movie in movie_list:
        item = movie.copy()

        number_fields = [
            "rank",
            "rankInten",
            "audiCnt",
            "audiAcc",
            "scrnCnt",
            "showCnt",
        ]

        for field in number_fields:
            try:
                item[field] = int(item.get(field, 0))
            except (TypeError, ValueError):
                item[field] = 0

        converted.append(item)

    return converted


# ---------------------------------------------------------
# 화면 제목
# ---------------------------------------------------------

st.title("🎬 일일 박스오피스")


# ---------------------------------------------------------
# 한국 시간 기준 날짜 범위 만들기
#
# 가장 늦게 고를 수 있는 날짜 = 어제
# ---------------------------------------------------------

today_kst = get_korea_today()
yesterday_kst = today_kst - timedelta(days=1)


# ---------------------------------------------------------
# 달력에서 날짜 선택
#
# 시작 날짜는 넉넉하게 2000-01-01로 설정했습니다.
# 필요하다면 원하는 시작 날짜로 바꿀 수 있습니다.
# ---------------------------------------------------------

selected_date = st.date_input(
    "조회할 날짜를 선택하세요.",
    value=yesterday_kst,
    min_value=datetime(2000, 1, 1).date(),
    max_value=yesterday_kst,
)


# ---------------------------------------------------------
# 날짜를 KOBIS가 요구하는 YYYYMMDD 형태로 변환
# ---------------------------------------------------------

target_date = selected_date.strftime("%Y%m%d")

st.caption(
    f"조회 날짜: {selected_date.strftime('%Y-%m-%d')}"
)


# ---------------------------------------------------------
# Streamlit Secrets에서 인증키 가져오기
#
# Streamlit Cloud > 앱 > Settings > Secrets에서
# KOBIS_KEY를 등록해야 합니다.
# ---------------------------------------------------------

try:
    api_key = st.secrets["KOBIS_KEY"]

except KeyError:
    st.error(
        "KOBIS_KEY를 찾을 수 없습니다."
    )

    st.info(
        "Streamlit Cloud의 Secrets에 다음과 같이 "
        "KOBIS_KEY를 등록했는지 확인해 주세요."
    )

    st.code(
        'KOBIS_KEY = "여기에_실제_인증키"'
    )

    st.stop()


# ---------------------------------------------------------
# KOBIS API 호출
# ---------------------------------------------------------

result = get_boxoffice(
    target_date,
    api_key,
)


# ---------------------------------------------------------
# API 오류 처리
# ---------------------------------------------------------

if not result["success"]:

    # 영화 목록이 없는 경우
    if result.get("empty", False):
        st.warning(
            "📅 그날은 아직 집계 전입니다."
        )

        st.info(
            "다른 날짜를 선택해 주세요. "
            "KOBIS에 일일 박스오피스 데이터가 등록된 "
            "날짜만 영화 목록을 볼 수 있습니다."
        )

    # 그 외 API 오류
    else:
        st.error(
            "박스오피스 데이터를 가져오지 못했습니다."
        )

        st.warning(result["message"])

        st.info(
            "다음 항목을 확인해 주세요.\n\n"
            "• Streamlit Cloud Secrets에 KOBIS_KEY가 등록되어 있는지\n"
            "• 인증키가 정확한지\n"
            "• KOBIS API 주소에 접속할 수 있는지\n"
            "• 선택한 날짜의 데이터가 존재하는지"
        )

    st.stop()


# ---------------------------------------------------------
# 숫자 변환
# ---------------------------------------------------------

movies = convert_to_numbers(
    result["data"]
)


# ---------------------------------------------------------
# 1위 영화
# ---------------------------------------------------------

first_movie = movies[0]

st.subheader("🥇 1위 영화")

st.markdown(
    f"### {first_movie['movieNm']}"
)


# ---------------------------------------------------------
# 1위 영화 지표 카드
# ---------------------------------------------------------

col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        "관객수",
        f"{first_movie['audiCnt']:,}명",
    )

with col2:
    st.metric(
        "누적 관객수",
        f"{first_movie['audiAcc']:,}명",
    )

with col3:
    st.metric(
        "스크린수",
        f"{first_movie['scrnCnt']:,}개",
    )


# ---------------------------------------------------------
# 관객수 상위 5편
# ---------------------------------------------------------

st.subheader("📊 관객수 상위 5편")

top5 = sorted(
    movies,
    key=lambda movie: movie["audiCnt"],
    reverse=True,
)[:5]


# 영화명을 그래프의 이름으로 사용하고
# 관객수를 숫자로 사용합니다.
chart_data = {
    movie["movieNm"]: movie["audiCnt"]
    for movie in top5
}

st.bar_chart(chart_data)


# ---------------------------------------------------------
# 전체 박스오피스 표
# ---------------------------------------------------------

st.subheader("📋 전체 박스오피스")


table_data = []

for movie in movies:

    # -----------------------------------------------------
    # rankInten:
    # 양수 = 전날보다 순위가 올라감
    # 음수 = 전날보다 순위가 내려감
    #
    # 표에서 보기 쉽게 화살표를 붙입니다.
    # -----------------------------------------------------

    rank_change = movie["rankInten"]

    if rank_change > 0:
        rank_display = f"🔴 ↑ {rank_change}"

    elif rank_change < 0:
        rank_display = f"🔵 ↓ {abs(rank_change)}"

    else:
        rank_display = "➖ 0"

    # -----------------------------------------------------
    # 누적 관객수가 100만 명 이상이면
    # 영화명 뒤에 트로피를 붙입니다.
    # -----------------------------------------------------

    movie_name = movie["movieNm"]

    if movie["audiAcc"] >= 1_000_000:
        movie_name = f"{movie_name} 🏆"

    table_data.append(
        {
            "순위": movie["rank"],
            "영화명": movie_name,
            "개봉일": movie["openDt"],
            "관객수": movie["audiCnt"],
            "누적관객": movie["audiAcc"],
            "스크린수": movie["scrnCnt"],
            "전일 대비 순위": rank_display,
        }
    )


# ---------------------------------------------------------
# 표 표시
# ---------------------------------------------------------

st.dataframe(
    table_data,
    use_container_width=True,
    hide_index=True,
    column_config={
        "순위": st.column_config.NumberColumn(
            "순위",
            format="%d",
        ),
        "관객수": st.column_config.NumberColumn(
            "관객수",
            format="%,d",
        ),
        "누적관객": st.column_config.NumberColumn(
            "누적관객",
            format="%,d",
        ),
        "스크린수": st.column_config.NumberColumn(
            "스크린수",
            format="%,d",
        ),
    },
)


# ---------------------------------------------------------
# 데이터 출처
# ---------------------------------------------------------

st.caption(
    "※ 데이터 출처: 영화진흥위원회(KOBIS) 일일 박스오피스 API"
)
```
