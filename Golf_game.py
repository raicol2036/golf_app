import streamlit as st
import pandas as pd
import io
from streamlit.components.v1 import html

st.set_page_config(page_title="Golf Team 成績系統", layout="wide")
st.title("⛳ Golf Team 成績管理系統")

# ============ 載入 CSV ============
players = pd.read_csv("players.csv", encoding="utf-8-sig")
courses = pd.read_csv("course_db.csv", encoding="utf-8-sig")

# 驗證欄位
if not set(["name", "handicap", "champion", "runnerup"]).issubset(players.columns):
    st.error("❌ players.csv 欄位必須包含: name, handicap, champion, runnerup")
    st.stop()
if not set(["course_name", "area", "hole", "hcp", "par"]).issubset(courses.columns):
    st.error("❌ course_db.csv 欄位必須包含: course_name, area, hole, hcp, par")
    st.stop()

# ============ 選擇球場 ============
st.header("⚙️ 比賽設定")
course_selected = st.selectbox("選擇球場", courses["course_name"].unique())
areas = courses[courses["course_name"] == course_selected]["area"].unique()
area_front = st.selectbox("前九洞區域", areas, key="area_front")
area_back = st.selectbox("後九洞區域", [a for a in areas if a != area_front], key="area_back")

course_data = pd.concat([
    courses[(courses["course_name"] == course_selected) & (courses["area"] == area_front)].sort_values("hole"),
    courses[(courses["course_name"] == course_selected) & (courses["area"] == area_back)].sort_values("hole")
]).reset_index(drop=True)

# ============ 設定比賽人數 ============
st.header("1. 設定比賽人數")
num_players = st.number_input("請輸入參賽人數 (1~24)", min_value=1, max_value=24, value=4, step=1)

# ============ 輸入比賽成績 ============
st.header("2. 輸入比賽成績 (必須18位數字，限制無法輸入第19碼)")
scores = {}
selected_players = []

for i in range(num_players):
    cols = st.columns([1, 2])
    with cols[0]:
        player_name = st.selectbox(f"選擇球員 {i+1}", players["name"].values, key=f"player_{i}")
    selected_players.append(player_name)

    with cols[1]:
        score_str = st.text_input(f"{player_name} 的成績 (18位數字)", key=f"scores_{i}", max_chars=18)

    if score_str:
        if score_str.isdigit() and len(score_str) == 18:
            scores[player_name] = [int(x) for x in score_str]
        else:
            st.error(f"⚠️ {player_name} 成績必須是剛好 18 位數字")
            scores[player_name] = []
    else:
        scores[player_name] = []

# ============ 計算函式 ============
def calculate_gross(scores):
    return {p: sum(s) for p, s in scores.items() if s}

def calculate_net(gross_scores):
    net_scores = {}
    for p, gross in gross_scores.items():
        hcp = int(players.loc[players["name"] == p, "handicap"].values[0])
        net_scores[p] = gross - hcp
    return net_scores

def find_birdies(scores, course_data):
    birdies = {}
    for p, s in scores.items():
        for i, score in enumerate(s):
            if i < len(course_data):
                par = course_data.iloc[i]["par"]
                if score == par - 1:
                    birdies.setdefault(p, []).append(i+1)
    return birdies

def get_winners(scores, course_data):
    gross = calculate_gross(scores)
    net = calculate_net(gross)

    gross_sorted = sorted(gross.items(), key=lambda x: x[1])

    gross_champ, gross_runner = None, None
    for p, _ in gross_sorted:
        if players.loc[players["name"] == p, "champion"].values[0] == "No":
            gross_champ = p
            break
    for p, _ in gross_sorted:
        if p != gross_champ and players.loc[players["name"] == p, "runnerup"].values[0] == "No":
            gross_runner = p
            break

    exclude_players = [gross_champ, gross_runner]
    net_candidates = {p: s for p, s in net.items() if p not in exclude_players}
    net_sorted = sorted(net_candidates.items(), key=lambda x: x[1])

    net_champ, net_runner = None, None
    if len(net_sorted) > 0: net_champ = net_sorted[0][0]
    if len(net_sorted) > 1: net_runner = net_sorted[1][0]

    hcp_updates = {p: 0 for p in scores.keys()}
    if net_champ: hcp_updates[net_champ] = -2
    if net_runner: hcp_updates[net_runner] = -1

    birdies = find_birdies(scores, course_data)

    return {
        "gross": gross,
        "net": net,
        "gross_champion": gross_champ,
        "gross_runnerup": gross_runner,
        "net_champion": net_champ,
        "net_runnerup": net_runner,
        "birdies": birdies,
        "hcp_updates": hcp_updates
    }

# ============ 開始計算 ============
if st.button("開始計算"):
    winners = get_winners(scores, course_data)

    # --- 結果 ---
    st.subheader("🏆 比賽結果")
    col1, col2 = st.columns(2)
    with col1:
        st.write(f"🏅 總桿冠軍: {winners['gross_champion']}")
        st.write(f"🥈 總桿亞軍: {winners['gross_runnerup']}")
    with col2:
        st.write(f"🌟 淨桿冠軍: {winners['net_champion']}")
        st.write(f"🌟 淨桿亞軍: {winners['net_runnerup']}")

    if winners["birdies"]:
        st.write("✨ Birdie 紀錄：")
        for player, holes in winners["birdies"].items():
            hole_str = "/".join([f"第{h}洞" for h in holes])
            st.write(f"- {player}: {hole_str}")
    else:
        st.write("無 Birdie 紀錄")

    # Leaderboard
    st.subheader("📊 Leaderboard 排名表")
    df_leader = pd.DataFrame({
        "球員": list(winners["gross"].keys()),
        "原始差點": [int(players.loc[players["name"] == p, "handicap"].values[0]) for p in winners["gross"].keys()],
        "總桿": list(winners["gross"].values()),
        "淨桿": [winners["net"][p] for p in winners["gross"].keys()],
        "差點更新": [winners["hcp_updates"][p] for p in winners["gross"].keys()]
    })
    df_leader["總桿排名"] = df_leader["總桿"].rank(method="min").astype(int)
    df_leader["淨桿排名"] = df_leader["淨桿"].rank(method="min").astype(int)
    st.dataframe(df_leader.sort_values("淨桿排名"))

    # ============ 個人比分入口 ============
    st.subheader("➡️ 是否進行個人比分？")
    if st.button("進入個人比分模式"):
        st.switch_page("pages/personal_score.py")
  
