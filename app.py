import streamlit as st
import requests
import pandas as pd
import matplotlib.pyplot as plt
import time
import random
import re
from collections import Counter

# --- 設定 Matplotlib 中文字型 (針對不同作業系統) ---
import platform
system_os = platform.system()
if system_os == "Windows":
    plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei']
elif system_os == "Darwin": # Mac
    plt.rcParams['font.sans-serif'] = ['Arial Unicode MS']
else:
    # Linux (Colab/Streamlit Cloud) 可能需要額外字型檔，這裡先用預設避免報錯
    pass
plt.rcParams['axes.unicode_minus'] = False

# --- 核心函式：爬蟲 ---
def fetch_104_jobs(keyword, pages=3):
    job_list = []
    url = "https://www.104.com.tw/jobs/search/list"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Referer": "https://www.104.com.tw/jobs/search/",
    }

    progress_bar = st.progress(0)
    status_text = st.empty()

    for page in range(1, pages + 1):
        status_text.text(f"正在爬取第 {page}/{pages} 頁...")
        params = {
            "ro": "0",
            "kwop": "7",
            "keyword": keyword,
            "expansionType": "area,spec,com,job,wf,wktm",
            "order": "1",
            "asc": "0",
            "page": page,
            "mode": "s",
            "jobsource": "2018indexpoc",
            "langFlag": "0"
        }

        try:
            response = requests.get(url, headers=headers, params=params)
            data = response.json()
            
            if "data" not in data or "list" not in data["data"] or len(data["data"]["list"]) == 0:
                break
                
            jobs = data["data"]["list"]
            
            for job in jobs:
                # 解析擅長工具 (這是 List，需要轉成字串)
                specialties = job.get("specialty", [])
                skill_str = ",".join([s['description'] for s in specialties]) if specialties else "不拘"

                job_info = {
                    "職缺名稱": job.get("jobName"),
                    "公司名稱": job.get("custName"),
                    "地區": job.get("jobAddrNoDesc"),
                    "薪資原文": job.get("salaryDesc"),
                    "學歷": job.get("optionEdu"),
                    "經歷": job.get("periodDesc"),
                    "擅長工具": skill_str, # 重要：技能欄位
                    "工作內容": job.get("description", "")[:100] + "...", # 取前100字預覽
                    "網址": f"https:{job.get('link').get('job')}" if job.get("link") else ""
                }
                job_list.append(job_info)
            
            # 更新進度條
            progress_bar.progress(page / pages)
            time.sleep(random.uniform(0.5, 1.5)) # 稍微快一點，但仍保持禮貌
            
        except Exception as e:
            st.error(f"第 {page} 頁發生錯誤: {e}")
            break
            
    status_text.text("爬取完成！")
    progress_bar.empty()
    return pd.DataFrame(job_list)

# --- 核心函式：薪資清洗 ---
def parse_salary(salary_str):
    """
    將 '月薪 30,000~50,000元' 轉換為平均值 40000
    忽略 '面議', '時薪' 等複雜情況以簡化分析
    """
    if "面議" in salary_str:
        return None
    if "時薪" in salary_str or "日薪" in salary_str:
        return None # 暫時只分析月薪
    
    # 移除千分位逗號
    clean_str = salary_str.replace(",", "")
    # 抓取所有數字
    numbers = re.findall(r'\d+', clean_str)
    
    if len(numbers) == 2:
        return (int(numbers[0]) + int(numbers[1])) / 2
    elif len(numbers) == 1:
        return int(numbers[0]) # 例如 "40000元以上"
    else:
        return None

# --- Streamlit 介面設定 ---
st.set_page_config(page_title="104 職缺戰情室", page_icon="🐈", layout="wide")

# 側邊欄：設定區
st.sidebar.header("🔍 搜尋設定")
keyword = st.sidebar.text_input("輸入職缺關鍵字", "Python 數據分析")
pages_to_scrape = st.sidebar.slider("爬取頁數", 1, 10, 3)
run_btn = st.sidebar.button("開始爬取")

st.sidebar.markdown("---")
st.sidebar.markdown("Developed by **Python Instructor**")

# 主畫面
st.title("📊 104 人力銀行 - 職缺分析戰情室")
st.markdown(f"目標：分析 **{keyword}** 的市場需求、薪資分佈與熱門技能。")

if run_btn:
    # 1. 執行爬蟲
    df = fetch_104_jobs(keyword, pages_to_scrape)
    
    if not df.empty:
        # 2. 資料清洗
        df['縣市'] = df['地區'].apply(lambda x: x[:3])
        df['平均月薪'] = df['薪資原文'].apply(parse_salary)
        
        # 3. 顯示關鍵指標 (KPI)
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("搜尋職缺數", f"{len(df)} 筆")
        with col2:
            avg_salary = df['平均月薪'].mean()
            st.metric("平均月薪 (預估)", f"{int(avg_salary):,} 元" if pd.notnull(avg_salary) else "無法計算")
        with col3:
            top_city = df['縣市'].mode()[0]
            st.metric("最多職缺地區", top_city)

        # 4. 頁籤分頁顯示
        tab1, tab2, tab3 = st.tabs(["📋 詳細資料", "📈 圖表分析", "🛠️ 技能文字雲"])

        with tab1:
            st.dataframe(df, use_container_width=True)
            # 下載按鈕
            csv = df.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
            st.download_button(
                label="📥 下載 CSV 檔案",
                data=csv,
                file_name=f'104_jobs_{keyword}.csv',
                mime='text/csv',
            )

        with tab2:
            col_chart1, col_chart2 = st.columns(2)
            
            with col_chart1:
                st.subheader("📍 各地區職缺分佈")
                # 使用 Streamlit 內建圖表，對中文支援較好
                city_counts = df['縣市'].value_counts()
                st.bar_chart(city_counts)

            with col_chart2:
                st.subheader("💰 薪資分佈 (僅統計月薪)")
                if df['平均月薪'].notnull().sum() > 0:
                    fig, ax = plt.subplots()
                    df['平均月薪'].hist(bins=20, ax=ax, color='orange', edgecolor='white')
                    ax.set_title("月薪分佈圖")
                    ax.set_xlabel("薪資 (TWD)")
                    ax.set_ylabel("職缺數")
                    st.pyplot(fig)
                else:
                    st.info("爬取到的資料中，大部分為面議或無法解析薪資。")

        with tab3:
            st.subheader("🔥 企業最要求的技能 (Top 20)")
            # 統計所有技能標籤
            all_skills = []
            for skills in df['擅長工具']:
                if skills and skills != "不拘":
                    all_skills.extend(skills.split(','))
            
            if all_skills:
                skill_counts = Counter(all_skills).most_common(20)
                skill_df = pd.DataFrame(skill_counts, columns=['技能', '次數'])
                
                # 繪製水平長條圖
                fig_skill, ax_skill = plt.subplots(figsize=(10, 8))
                ax_skill.barh(skill_df['技能'], skill_df['次數'], color='lightgreen')
                ax_skill.invert_yaxis() # 讓最高的在上面
                ax_skill.set_title("熱門技能統計")
                st.pyplot(fig_skill)
            else:
                st.write("本次搜尋未抓取到足夠的技能資料。")

    else:
        st.warning("找不到資料，請嘗試更換關鍵字或檢查網路連線。")

else:
    st.info("👈 請在左側輸入關鍵字並按下「開始爬取」")