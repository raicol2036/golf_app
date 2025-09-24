import streamlit as st
import pandas as pd
import io

st.title("🏌️ 鴻勁高球隊成績管理")

# === 直接載入 CSV ===
players = pd.read_csv("players.csv", encoding="utf-8-sig")
courses = pd.read_csv("course_db.csv", encoding="utf-8-sig")

# 驗證欄位
if not set(["name","handicap","champion","runnerup"]).issubset(players.columns):
    st.error("❌ players.csv 欄位必須包含: name, handicap, champion, runnerup")
    st.stop()
if not set(["course_name","area","hole","hcp","par"]).issubset(courses.columns):
    st.error("❌ course.csv 欄位必須包含: course_name, area, hole, hcp, par")
    st.stop()

st.success("✅ CSV 已成功載入")
st.header("0. 比賽設定")

# Step 1: 選擇球場
course_names = courses["course_name"].unique()
selected_course = st.selectbox("🏌️‍♂️ 選擇球場", course_names)

# 篩選出該球場的資料
course_filtered = courses[courses["course_name"] == selected_course]

# 取出所有區域 (前九/後九都可選)
all_areas = course_filtered["area"].unique()

# Step 2: 選擇前九洞區域
selected_front = st.selectbox("前九洞區域", all_areas)

# Step 3: 選擇後九洞區域 (排除已選的前九)
back_options = [a for a in all_areas if a != selected_front]
selected_back = st.selectbox("後九洞區域", back_options)

# 最終組合
course_selected = pd.concat([
    course_filtered[(course_filtered["area"] == selected_front) & (course_filtered["hole"] <= 9)],
    course_filtered[(course_filtered["area"] == selected_back) & (course_filtered["hole"] > 9)]
])

st.success(f"✅ 已選擇：{selected_course} / 前九: {selected_front} / 後九: {selected_back}")


# === 設定比賽人數 ===
st.header("1. 設定比賽人數")
num_players = st.number_input("請輸入參賽人數 (1~24)", min_value=1, max_value=24, value=4, step=1)

# === 選擇球員並輸入成績 ===
st.header("2. 輸入比賽成績 (連續輸入18位數字)")
scores = {}
selected_players = []

for i in range(num_players):
    st.subheader(f"球員 {i+1}")
    cols = st.columns([1, 2])  # 左1份寬度，右2份寬度

    with cols[0]:
        player_name = st.selectbox(
            f"選擇球員 {i+1}",
            players["name"].values,
            key=f"player_{i}"
        )
        selected_players.append(player_name)

    with cols[1]:
        score_str = st.text_input(
            f"{player_name} 的成績 (18位數字)",
            key=f"scores_{i}",
            max_chars=18
        )

    if score_str:
        if score_str.isdigit() and len(score_str) == 18:
            scores[player_name] = [int(x) for x in score_str]
        else:
            st.error(f"⚠️ {player_name} 成績必須是剛好 18 位數字")
            scores[player_name] = []
    else:
        scores[player_name] = []


# === 計算函式 ===
def calculate_gross(scores):
    return {p: sum(s) for p, s in scores.items() if s}

def calculate_net(gross_scores):
    net_scores = {}
    for p, gross in gross_scores.items():
        hcp = int(players.loc[players["name"] == p, "handicap"].values[0])
        net_scores[p] = gross - hcp
    return net_scores

def find_birdies(scores, course_selected):
    birdies = []
    for p, s in scores.items():
        for i, score in enumerate(s):
            if i < len(course_selected):
                par = course_selected.iloc[i]["par"]
                if score == par - 1:
                    hole_num = course_selected.iloc[i]["hole"]
                    birdies.append((p, hole_num))
    return birdies

def get_winners(scores, course_selected):
    gross = calculate_gross(scores)
    net = calculate_net(gross)
    birdies = find_birdies(scores, course_selected)

    # === 總桿排序 ===
    gross_sorted = sorted(gross.items(), key=lambda x: x[1])

    # 總桿冠軍：排除曾經得過冠軍
    gross_champ = None
    for p, _ in gross_sorted:
        if players.loc[players["name"]==p,"champion"].values[0] == "No":
            gross_champ = p
            break

    # 總桿亞軍：排除曾經得過亞軍
    gross_runner = None
    for p, _ in gross_sorted:
        if p != gross_champ and players.loc[players["name"]==p,"runnerup"].values[0] == "No":
            gross_runner = p
            break

    # === 淨桿冠亞軍 (排除總桿前兩名) ===
    exclude_players = [gross_champ, gross_runner]
    net_candidates = {p:s for p,s in net.items() if p not in exclude_players}
    net_sorted = sorted(net_candidates.items(), key=lambda x: x[1])

    net_champ, net_runner = None, None
    if len(net_sorted) > 0: net_champ = net_sorted[0][0]
    if len(net_sorted) > 1: net_runner = net_sorted[1][0]

    # 計算差點更新（不直接修改 players）
    hcp_updates = {p: 0 for p in gross.keys()}
    if net_champ:
        hcp_updates[net_champ] = -2
    if net_runner:
        hcp_updates[net_runner] = -1

    hcp_new = {p: int(players.loc[players["name"] == p, "handicap"].values[0]) + hcp_updates[p] for p in gross.keys()}


    birdies = find_birdies(scores, course_selected)

    return {
        "gross": gross,
        "net": net,
        "gross_champion": gross_champ,
        "gross_runnerup": gross_runner,
        "net_champion": net_champ,
        "net_runnerup": net_runner,
        "birdies": birdies,
        "hcp_new": hcp_new,  # 👈 新增
    }

# === 4. 獎項選擇 ===
st.header("4. 獎項選擇")

# 共用方法：生成多個下拉框
def award_select(title, key_prefix, slots=2, cols_per_row=2):
    st.subheader(title)
    awards = []
    for i in range(0, slots, cols_per_row):
        cols = st.columns(cols_per_row)
        for j in range(cols_per_row):
            idx = i + j + 1
            if idx > slots:
                break
            with cols[j]:
                player = st.selectbox(
                    f"{title} - 第{idx}人",
                    ["無"] + list(players["name"].values),
                    key=f"{key_prefix}_{idx}"
                )
                if player != "無":
                    awards.append(player)
    return awards

# 四個獎項：每個最多 2 人
long_drive = award_select("🏌️‍♂️ 遠距獎", "long_drive", slots=2)
near1 = award_select("🎯 一近洞獎", "near1", slots=2)
near2 = award_select("🎯 二近洞獎", "near2", slots=2)
near3 = award_select("🎯 三近洞獎", "near3", slots=2)

# N近洞獎：最多 18 人，每行 4 個
st.subheader("🎯 N近洞獎 (最多18位，可重複)")
n_near_awards = []
num_slots = 18
cols_per_row = 4

for i in range(0, num_slots, cols_per_row):
    cols = st.columns(cols_per_row)
    for j in range(cols_per_row):
        idx = i + j + 1
        if idx > num_slots:
            break
        with cols[j]:
            player = st.selectbox(
                f"第{idx}位",
                ["無"] + list(players["name"].values),
                key=f"n_near_{idx}"
            )
            if player != "無":
                n_near_awards.append(player)

# 整合獎項
awards = {
    "遠距獎": long_drive,
    "一近洞獎": near1,
    "二近洞獎": near2,
    "三近洞獎": near3,
    "N近洞獎": n_near_awards,
}


# === 開始計算 ===
if st.button("開始計算"):
    winners = get_winners(scores, course_selected)

    st.subheader("🏆 比賽結果")

    col1, col2 = st.columns(2)
    with col1:
        st.write(f"🏅 總桿冠軍: {winners['gross_champion']}")
    with col2:
        st.write(f"🥈 總桿亞軍: {winners['gross_runnerup']}")

    col3, col4 = st.columns(2)
    with col3:
        st.write(f"🏅 淨桿冠軍: {winners['net_champion']}")
    with col4:
        st.write(f"🥈 淨桿亞軍: {winners['net_runnerup']}")


    if winners["birdies"]:
        st.write("✨ Birdie 紀錄：")
    
        # 整理成 {球員: [洞號,...]}
        birdie_dict = {}
        for player, hole in winners["birdies"]:
            if player not in birdie_dict:
                birdie_dict[player] = []
            birdie_dict[player].append(hole)
    
        # 輸出結果：同一球員的洞號合併
        for player, holes in birdie_dict.items():
            hole_text = "/".join([f"第{h}洞" for h in holes])
            st.write(f"- {player}  {hole_text}")
    else:
        st.write("無 Birdie 紀錄")


    # === 特殊獎項結果 ===
    from collections import Counter

    def format_awards(awards_dict):
        award_texts = []
        for award_name, winners_list in awards_dict.items():
            if winners_list:
                if award_name == "N近洞獎":
                    # 計數
                    counts = Counter(winners_list)
                    formatted = " ".join([f"{name}*{cnt}" for name, cnt in counts.items()])
                    award_texts.append(f"**{award_name}** {formatted}")
                else:
                    award_texts.append(f"**{award_name}** {', '.join(winners_list)}")
            else:
                award_texts.append(f"**{award_name}** 無")
        return award_texts

    # === 特殊獎項結果 ===
    st.subheader("🏅 特殊獎項結果")
    award_texts = format_awards(awards)
    st.markdown(" ｜ ".join(award_texts))


    # === Leaderboard ===
    st.subheader("📊 Leaderboard 排名表")

    player_hcps = {p: int(players.loc[players["name"] == p, "handicap"].values[0]) for p in winners["gross"].keys()}

    df_leader = pd.DataFrame({
        "球員": list(winners["gross"].keys()),
        "原始差點": [player_hcps[p] for p in winners["gross"].keys()],
        "總桿": list(winners["gross"].values()),
        "淨桿": [winners["net"][p] for p in winners["gross"].keys()],
        "總桿排名": pd.Series(winners["gross"]).rank(method="min").astype(int).values,
        "淨桿排名": pd.Series(winners["net"]).rank(method="min").astype(int).values,
        "差點更新": [winners["hcp_new"][p] for p in winners["gross"].keys()]
    })

    # 顯示
    st.dataframe(df_leader.sort_values("淨桿排名"))

    # === 匯出功能 ===
    st.subheader("💾 匯出比賽結果")
    csv_buffer = io.StringIO()
    df_leader.to_csv(csv_buffer, index=False, encoding="utf-8-sig")
    st.download_button("📥 下載 CSV", data=csv_buffer.getvalue(),
                       file_name="leaderboard.csv", mime="text/csv")

    excel_buffer = io.BytesIO()
    with pd.ExcelWriter(excel_buffer, engine="xlsxwriter") as writer:
        df_leader.to_excel(writer, sheet_name="Leaderboard", index=False)
    st.download_button("📥 下載 Excel", data=excel_buffer.getvalue(),
                       file_name="leaderboard.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
