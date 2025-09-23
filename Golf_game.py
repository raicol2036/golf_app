import streamlit as st
import pandas as pd
from streamlit.components.v1 import html
import io
from collections import Counter

st.set_page_config(page_title="Golf Team 成績系統", layout="wide")

# 頁面狀態
if "page" not in st.session_state:
    st.session_state.page = "team"

# ======================================================
# 工具：數字輸入（強制18碼）
# ======================================================
def numeric_input_html(label, key):
    value = st.session_state.get(key, "")
    html(f"""
        <label for="{key}" style="font-weight:bold">{label}</label><br>
        <input id="{key}" name="{key}" inputmode="numeric" pattern="[0-9]*" maxlength="18"
               style="width:100%; font-size:1.1em; padding:0.5em;" value="{value}" />
        <script>
        const input = window.parent.document.getElementById('{key}');
        input.addEventListener('input', () => {{
            const value = input.value;
            window.parent.postMessage({{isStreamlitMessage: true, type: 'streamlit:setComponentValue', key: '{key}', value}}, '*');
        }});
        </script>
    """, height=100)

# ======================================================
# 計算函式
# ======================================================
def calculate_gross(scores):
    return {p: sum(s) for p, s in scores.items() if s}

def calculate_net(gross_scores, players):
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

def get_winners(scores, players, course_data):
    gross = calculate_gross(scores)
    net = calculate_net(gross, players)

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

# ======================================================
# 團體比賽頁面
# ======================================================
def team_page():
    st.title("⛳ Golf Team 成績管理系統")

    # 載入 CSV
    try:
        players = pd.read_csv("players.csv", encoding="utf-8-sig")
        courses = pd.read_csv("course_db.csv", encoding="utf-8-sig")
    except Exception as e:
        st.error(f"❌ 載入資料錯誤: {e}")
        return

    # 球場設定
    st.header("⚙️ 比賽設定")
    course_selected = st.selectbox("選擇球場", courses["course_name"].unique())
    areas = courses[courses["course_name"] == course_selected]["area"].unique()
    area_front = st.selectbox("前九洞區域", areas, key="area_front")
    area_back = st.selectbox("後九洞區域", [a for a in areas if a != area_front], key="area_back")

    course_data = pd.concat([
        courses[(courses["course_name"] == course_selected) & (courses["area"] == area_front)].sort_values("hole"),
        courses[(courses["course_name"] == course_selected) & (courses["area"] == area_back)].sort_values("hole")
    ]).reset_index(drop=True)

    # 比賽人數
    st.header("1. 設定比賽人數")
    num_players = st.number_input("請輸入參賽人數 (1~24)", min_value=1, max_value=24, value=4, step=1)

    # 輸入比賽成績
    st.header("2. 輸入比賽成績 (18位數字)")
    scores = {}
    for i in range(num_players):
        cols = st.columns([1, 2])
        with cols[0]:
            player_name = st.selectbox(f"選擇球員 {i+1}", players["name"].values, key=f"player_{i}")
        with cols[1]:
            score_str = st.text_input(f"{player_name} 的成績", key=f"scores_{i}", max_chars=18)
        if score_str and score_str.isdigit() and len(score_str) == 18:
            scores[player_name] = [int(x) for x in score_str]
        else:
            scores[player_name] = []

    # 獎項設定
    st.header("3. 特殊獎項")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        long_drive = st.multiselect("🏌️‍♂️ 遠距獎 (1–2人)", players["name"].values, max_selections=2)
    with col2:
        near1 = st.multiselect("🎯 一近洞獎 (1–2人)", players["name"].values, max_selections=2)
    with col3:
        near2 = st.multiselect("🎯 二近洞獎 (1–2人)", players["name"].values, max_selections=2)
    with col4:
        near3 = st.multiselect("🎯 三近洞獎 (1–2人)", players["name"].values, max_selections=2)

    st.subheader("🎯 N近洞獎 (可重複，最多18名)")
    n_near_awards = []
    for i in range(1, 19):
        n_near_player = st.selectbox(f"N近洞獎 第{i}名", ["無"] + list(players["name"].values), key=f"n_near_{i}")
        if n_near_player != "無":
            n_near_awards.append(n_near_player)

    awards = {
        "遠距獎": long_drive,
        "一近洞獎": near1,
        "二近洞獎": near2,
        "三近洞獎": near3,
        "N近洞獎": n_near_awards,
    }

    # 開始計算
    if st.button("開始計算"):
        winners = get_winners(scores, players, course_data)

        # --- 結果 ---
        st.subheader("🏆 比賽結果")
        st.write(f"🏅 總桿冠軍: {winners['gross_champion']}")
        st.write(f"🥈 總桿亞軍: {winners['gross_runnerup']}")
        st.write(f"🌟 淨桿冠軍: {winners['net_champion']}")
        st.write(f"🌟 淨桿亞軍: {winners['net_runnerup']}")

        if winners["birdies"]:
            st.write("✨ Birdie 紀錄：")
            for player, holes in winners["birdies"].items():
                hole_str = "/".join([f"第{h}洞" for h in holes])
                st.write(f"- {player}: {hole_str}")
        else:
            st.write("無 Birdie 紀錄")

        # 特殊獎項
        st.subheader("🏅 特殊獎項結果")
        award_texts = []
        for award_name, winners_list in awards.items():
            if winners_list:
                counts = Counter(winners_list)
                formatted = " ".join([f"{p}*{c}" if c > 1 else p for p, c in counts.items()])
                award_texts.append(f"**{award_name}** {formatted}")
            else:
                award_texts.append(f"**{award_name}** 無")
        st.markdown(" ｜ ".join(award_texts))

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

        # 下載
        csv_buffer = io.StringIO()
        df_leader.to_csv(csv_buffer, index=False, encoding="utf-8-sig")
        st.download_button("📥 下載 CSV", data=csv_buffer.getvalue(), file_name="leaderboard.csv", mime="text/csv")

        # 問是否要進入個人比分
        st.subheader("➡️ 是否進行個人比分？")
        if st.button("進入個人比分模式"):
            st.session_state.page = "personal"

# ======================================================
# 個人比分頁面
# ======================================================
def personal_page():
    st.title("⛳ 個人比分模式")

    try:
        course_df = pd.read_csv("course_db.csv")
        players_df = pd.read_csv("players.csv")
    except Exception as e:
        st.error(f"❌ 載入資料錯誤: {e}")
        return

    # 球場與區域
    course_name = st.selectbox("選擇球場", course_df["course_name"].unique())
    zones = course_df[course_df["course_name"] == course_name]["area"].unique()
    zone_front = st.selectbox("前九洞區域", zones)
    zone_back = st.selectbox("後九洞區域", zones)

    holes_front = course_df[(course_df["course_name"] == course_name) & (course_df["area"] == zone_front)].sort_values("hole")
    holes_back = course_df[(course_df["course_name"] == course_name) & (course_df["area"] == zone_back)].sort_values("hole")
    holes = pd.concat([holes_front, holes_back]).reset_index(drop=True)
    par = holes["par"].tolist()
    hcp = holes["hcp"].tolist()

    # 主球員
    player_list = ["請選擇球員"] + players_df["name"].tolist()
    player_a = st.selectbox("選擇主球員 A", player_list)
    if player_a == "請選擇球員":
        return
    numeric_input_html("主球員快速成績輸入（18位數）", key=f"quick_{player_a}")
    handicaps = {player_a: st.number_input(f"{player_a} 差點", 0, 54, 0, key="hcp_main")}

    # 對手
    opponents = []
    bets = {}
    for i in range(1, 5):
        st.markdown(f"#### 對手球員 B{i}")
        cols = st.columns([2, 1, 1])
        with cols[0]:
            name = st.selectbox(f"球員 B{i} 名稱", player_list + ["✅ Done"], key=f"b{i}_name")
        if name == "請選擇球員":
            return
        if name == "✅ Done":
            break
        if name in [player_a] + opponents:
            return
        opponents.append(name)
        numeric_input_html(f"{name} 快速成績輸入（18位數）", key=f"quick_{name}")
        with cols[1]:
            handicaps[name] = st.number_input("讓桿(前後各讓)：", -18, 18, 0, key=f"hcp_b{i}")
        with cols[2]:
            bets[name] = st.number_input("每洞賭金", 10, 1000, 100, key=f"bet_b{i}")

    # 初始化
    all_players = [player_a] + opponents
    score_data = {p: [] for p in all_players}
    total_earnings = {p: 0 for p in all_players}
    result_tracker = {p: {"win": 0, "lose": 0, "tie": 0} for p in all_players}

    # 處理快速成績
    quick_scores = {}
    for p in all_players:
        value = st.session_state.get(f"quick_{p}", "")
        if value and len(value) == 18 and value.isdigit():
            quick_scores[p] = [int(c) for c in value]
        elif value:
            st.error(f"⚠️ {p} 快速成績輸入需為18位數字串。")

    # 每洞比分輸入
    st.markdown("### 📝 每洞成績與賭金結算")
    for i in range(18):
        st.markdown(f"#### 第{i+1}洞 (Par {par[i]}, HCP {hcp[i]})")
        cols = st.columns(1 + len(opponents))

        # 主球員
        default_score = quick_scores[player_a][i] if player_a in quick_scores else par[i]
        score_main = cols[0].number_input("", 1, 15, default_score, key=f"{player_a}_score_{i}", label_visibility="collapsed")
        score_data[player_a].append(score_main)
        birdie_main = " 🐦" if score_main < par[i] else ""

        with cols[0]:
            st.markdown(
                f"<div style='text-align:center; margin-bottom:-10px'><strong>{player_a} 桿數{birdie_main}</strong></div>",
                unsafe_allow_html=True
            )

        # 對手
        for idx, op in enumerate(opponents):
            default_score = quick_scores[op][i] if op in quick_scores else par[i]
            score_op = cols[idx + 1].number_input("", 1, 15, default_score, key=f"{op}_score_{i}", label_visibility="collapsed")
            score_data[op].append(score_op)

            # 差點讓桿計算
            adj_main = score_main
            adj_op = score_op
            if handicaps[op] > handicaps[player_a] and hcp[i] <= (handicaps[op] - handicaps[player_a]):
                adj_op -= 1
            elif handicaps[player_a] > handicaps[op] and hcp[i] <= (handicaps[player_a] - handicaps[op]):
                adj_main -= 1

            # 勝負與賭金計算
            if adj_op < adj_main:  # 對手勝
                emoji = "👑"
                bonus = 2 if score_op < par[i] else 1
                total_earnings[op] += bets[op] * bonus
                total_earnings[player_a] -= bets[op] * bonus
                result_tracker[op]["win"] += 1
                result_tracker[player_a]["lose"] += 1
            elif adj_op > adj_main:  # 主球員勝
                emoji = "👽"
                bonus = 2 if score_main < par[i] else 1
                total_earnings[op] -= bets[op] * bonus
                total_earnings[player_a] += bets[op] * bonus
                result_tracker[player_a]["win"] += 1
                result_tracker[op]["lose"] += 1
            else:  # 平手
                emoji = "⚖️"
                result_tracker[player_a]["tie"] += 1
                result_tracker[op]["tie"] += 1

            birdie_icon = " 🐦" if score_op < par[i] else ""
            with cols[idx + 1]:
                st.markdown(
                    f"<div style='text-align:center; margin-bottom:-10px'><strong>{op} 桿數 {emoji}{birdie_icon}</strong></div>",
                    unsafe_allow_html=True
                )

    # 總結結果
    st.markdown("### 📊 總結結果（含勝負平統計）")
    summary_data = []
    for p in all_players:
        summary_data.append({
            "球員": p,
            "總賭金結算": total_earnings[p],
            "勝": result_tracker[p]["win"],
            "負": result_tracker[p]["lose"],
            "平": result_tracker[p]["tie"]
        })
    summary_df = pd.DataFrame(summary_data)
    st.dataframe(summary_df.set_index("球員"))

    # 返回
    if st.button("⬅️ 返回團體比賽"):
        st.session_state.page = "team"
