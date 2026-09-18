import streamlit as st
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


# ---------------------------------------------------------
# 기본 설정
# ---------------------------------------------------------

st.set_page_config(
    page_title="어제의 박스오피스",
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
# 한국 시간 기준으로 '어제' 날짜 계산
# 배포 서버가 해외 시간이어도 한국 시간을 사용합니다.
# ---------------------------------------------------------

def get_yesterday_kst():
    """한국 시간 기준 어제 날짜를 YYYYMMDD 형태로 반환합니다."""
    korea_time = datetime.now(ZoneInfo("Asia/Seoul"))
    yesterday = korea_time - timedelta(days=1)
    return yesterday.strftime("%Y%m%d")


# ---------------------------------------------------------
# KOBIS API에서 일일 박스오피스 가져오기
#
# st.cache_data를 사용해서 같은 날짜를 다시 요청하면
# 약 1시간 동안 저장된 결과를 재사용합니다.
# ---------------------------------------------------------

@st.cache_data(ttl=3600)
def get_boxoffice(target_date, api_key):
    """지정한 날짜의 KOBIS 일일 박스오피스를 가져옵니다."""

    params = {
        "key": api_key,
        "targetDt": target_date,
    }

    try:
        # API 요청
        response = requests.get(
            API_URL,
            params=params,
            timeout=10,
        )

        # HTTP 오류가 발생하면 예외를 발생시킵니다.
        response.raise_for_status()

        # JSON 응답으로 변환합니다.
        data = response.json()

    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "message": f"KOBIS API 요청에 실패했습니다.\n\n{e}",
        }

    except ValueError:
        return {
            "success": False,
            "message": "KOBIS API 응답을 JSON으로 읽을 수 없습니다.",
        }

    # -----------------------------------------------------
    # 인증키가 잘못된 경우에도 HTTP 상태코드는 200일 수 있습니다.
    # 따라서 faultInfo가 있는지 반드시 확인합니다.
    # -----------------------------------------------------

    if "faultInfo" in data:
        fault_info = data["faultInfo"]

        # faultInfo 안의 내용이 어떤 형태로 오더라도
        # 화면에 확인할 수 있도록 문자열로 표시합니다.
        return {
            "success": False,
            "message": (
                "KOBIS API에서 오류를 반환했습니다.\n\n"
                f"{fault_info}"
            ),
        }

    # 예상한 응답 구조가 있는지 확인합니다.
    boxoffice_result = data.get("boxOfficeResult")

    if not boxoffice_result:
        return {
            "success": False,
            "message": (
                "KOBIS 응답에 boxOfficeResult가 없습니다.\n\n"
                "KOBIS API 주소와 인증키, 조회 날짜를 확인해 주세요."
            ),
        }

    movie_list = boxoffice_result.get("dailyBoxOfficeList", [])

    # 영화 목록이 비어 있으면 사용자에게 확인할 내용을 알려줍니다.
    if not movie_list:
        return {
            "success": False,
            "message": (
                "조회된 영화 목록이 없습니다.\n\n"
                "다음 항목을 확인해 주세요.\n"
                "• KOBIS 인증키(KOBIS_KEY)가 올바른지\n"
                "• KOBIS API가 정상적으로 응답하는지\n"
                "• 조회 날짜에 박스오피스 데이터가 존재하는지"
            ),
        }

    return {
        "success": True,
        "data": movie_list,
    }


# ---------------------------------------------------------
# 숫자로 변환
#
# KOBIS API의 숫자 값은 문자열로 오기 때문에
# 정렬과 그래프에 사용할 수 있도록 정수로 변환합니다.
# ---------------------------------------------------------

def convert_to_numbers(movie_list):
    """API에서 받은 숫자 문자열을 정수로 변환합니다."""

    converted = []

    for movie in movie_list:
        item = movie.copy()

        # 숫자로 사용해야 하는 필드들
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
# 제목
# ---------------------------------------------------------

st.title("🎬 어제의 박스오피스")

target_date = get_yesterday_kst()

# 화면에는 YYYY-MM-DD 형태로 보기 좋게 표시합니다.
display_date = datetime.strptime(
    target_date, "%Y%m%d"
).strftime("%Y-%m-%d")

st.caption(f"한국 시간 기준 조회 날짜: {display_date}")


# ---------------------------------------------------------
# Streamlit Cloud Secrets에서 인증키 가져오기
#
# Streamlit Cloud의 Secrets에 다음과 같이 등록합니다.
#
# KOBIS_KEY = "발급받은_인증키"
#
# 실제 인증키는 코드에 작성하지 않습니다.
# ---------------------------------------------------------

try:
    api_key = st.secrets["KOBIS_KEY"]
except KeyError:
    st.error(
        "KOBIS_KEY를 찾을 수 없습니다.\n\n"
        "Streamlit Cloud의 앱 설정에서 Secrets를 열고 "
        "KOBIS_KEY를 등록했는지 확인해 주세요."
    )
    st.stop()


# ---------------------------------------------------------
# 데이터 가져오기
# ---------------------------------------------------------

result = get_boxoffice(target_date, api_key)


# ---------------------------------------------------------
# API 요청 실패 처리
# ---------------------------------------------------------

if not result["success"]:
    st.error("박스오피스 데이터를 가져오지 못했습니다.")
    st.warning(result["message"])

    st.info(
        "확인할 항목:\n"
        "1. Streamlit Cloud Secrets에 KOBIS_KEY가 등록되어 있는지\n"
        "2. 인증키가 정확한지\n"
        "3. KOBIS API 주소에 접속할 수 있는지\n"
        "4. 조회 날짜에 데이터가 존재하는지"
    )

    st.stop()


# ---------------------------------------------------------
# 영화 데이터 숫자 변환
# ---------------------------------------------------------

movies = convert_to_numbers(result["data"])


# ---------------------------------------------------------
# 1위 영화
# ---------------------------------------------------------

first_movie = movies[0]


st.subheader("🥇 오늘의 1위 영화")

st.markdown(f"### {first_movie['movieNm']}")


# 지표 카드 3개
col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        "오늘 관객수",
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
# 관객수 상위 5편 막대그래프
# ---------------------------------------------------------

st.subheader("📊 관객수 상위 5편")

top5 = sorted(
    movies,
    key=lambda movie: movie["audiCnt"],
    reverse=True,
)[:5]

# Streamlit 차트에 사용할 데이터
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
    table_data.append(
        {
            "순위": movie["rank"],
            "영화명": movie["movieNm"],
            "개봉일": movie["openDt"],
            "관객수": movie["audiCnt"],
            "누적관객": movie["audiAcc"],
            "스크린수": movie["scrnCnt"],
        }
    )

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
# 안내 문구
# ---------------------------------------------------------

st.caption(
    "※ 데이터 출처: 영화진흥위원회(KOBIS) 일일 박스오피스 API"
)
