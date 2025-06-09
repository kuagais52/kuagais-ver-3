import streamlit as st
import random
import datetime
import io
import pandas as pd
import os
import json

# 문제 유형 라벨
TYPE_LABELS = {
    '참거짓': 'True/False',
    '단답형:일반': 'Short Answer',
    '단답형:빈칸': 'Fill in the Blank',
    '단답형:한글': 'Korean Term',
    '단답형:약자': 'Acronym',
    '객관식': 'Multiple Choice'
}

# 문제 불러오기
@st.cache_data
def load_questions_from_json(file):
    raw = json.load(file)
    questions = []
    for item in raw:
        qtype = item.get('type', '객관식')
        label = TYPE_LABELS.get(qtype, qtype)
        question = item['question']
        options = item.get('choices') or item.get('options', [])
        answer = item['answer']
        questions.append({
            'id': item.get('id', ''),
            'type': qtype,
            'label': label,
            'question': question,
            'options': options,
            'answer': answer
        })
    return questions

# 정답 텍스트
def get_correct_answer_text(q):
    if q["type"] == "객관식" and isinstance(q["answer"], str) and q["answer"].isdigit():
        index = int(q["answer"]) - 1
        return q["options"][index] if 0 <= index < len(q["options"]) else "정보 없음"
    return str(q["answer"])

# 정답 판별
def is_user_answer_correct(q, user_input):
    correct_text = get_correct_answer_text(q).strip()
    user_text = user_input.strip()
    if q["type"] == "객관식" and isinstance(q["answer"], str) and q["answer"].isdigit():
        return user_text == correct_text
    return user_text == str(q["answer"]).strip()

# 결과 텍스트 생성
def generate_result_text(questions, user_answers, score):
    output = io.StringIO()
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    output.write(f"GIS 랜덤 퀴즈 결과 - {now}\n")
    output.write(f"총 점수: {score} / {len(questions)}\n\n")
    for idx, (q, ua) in enumerate(zip(questions, user_answers), start=1):
        correct = get_correct_answer_text(q)
        result = "정답" if is_user_answer_correct(q, ua) else "오답"
        output.write(f"{idx}. [{q['label']}] {q['question']}\n")
        output.write(f"    - 정답: {correct} | 내 답: {ua} → {result}\n")
    return output.getvalue()

# 통계 저장
@st.cache_data
def load_stats(filepath="quiz_stats.csv"):
    if os.path.exists(filepath):
        return pd.read_csv(filepath)
    return pd.DataFrame()

def save_stats_to_csv(questions, user_answers, score, filepath="quiz_stats.csv"):
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    data = []
    for q, ua in zip(questions, user_answers):
        correct = get_correct_answer_text(q)
        is_correct = is_user_answer_correct(q, ua)
        data.append({
            "timestamp": now,
            "type": q['type'],
            "label": q['label'],
            "question": q['question'],
            "user_answer": ua.strip(),
            "correct_answer": correct,
            "result": "정답" if is_correct else "오답"
        })
    new_df = pd.DataFrame(data)
    if os.path.exists(filepath):
        existing_df = pd.read_csv(filepath)
        combined_df = pd.concat([existing_df, new_df], ignore_index=True)
    else:
        combined_df = new_df
    combined_df.to_csv(filepath, index=False)

# Streamlit UI 시작
st.title("🌍 GIS 랜덤 퀴즈 (정답 보기 + 오답 다시 풀기)")
uploaded_file = st.file_uploader("📁 문제 JSON 파일을 업로드해주세요", type=['json'])

if uploaded_file:
    all_questions = load_questions_from_json(uploaded_file)
    total_available = len(all_questions)

    if total_available < 5:
        st.warning("❗ 문제 수가 너무 적습니다.")
    else:
        tab1, tab2 = st.tabs(["📝 퀴즈 풀기", "📊 통계 보기"])

        with tab1:
            st.sidebar.subheader("🛠️ 문제 수 설정")
            num_questions = st.sidebar.slider("출제할 문제 수", min_value=1, max_value=total_available, value=min(10, total_available))

            if st.sidebar.button("🔄 문제 새로 뽑기"):
                st.session_state['selected_questions'] = random.sample(all_questions, num_questions)
                st.session_state['from_wrong_top'] = False

            if st.button("🔁 오답 문제 다시 풀기"):
                df = load_stats()
                wrongs = df[df['result'] == '오답']['question'].unique()
                wrong_qs = [q for q in all_questions if q['question'] in wrongs]
                if len(wrong_qs) >= num_questions:
                    st.session_state['selected_questions'] = random.sample(wrong_qs, num_questions)
                    st.session_state['from_wrong_top'] = True
                else:
                    st.warning("오답 문제 수가 부족합니다.")

            if 'selected_questions' not in st.session_state or len(st.session_state['selected_questions']) != num_questions:
                st.session_state['selected_questions'] = random.sample(all_questions, num_questions)

            selected_questions = st.session_state['selected_questions']
            if st.session_state.get('from_wrong_top'):
                st.info("📌 오답률이 높은 문제들입니다.")
                del st.session_state['from_wrong_top']

            st.subheader("📝 퀴즈 문제")
            user_answers = []

            for idx, q in enumerate(selected_questions, start=1):
                st.markdown(f"**{idx}. [{q['label']}]** {q['question']}")
                ans_key = f"user_answer_{idx}"
                if q['type'] == '객관식' and q['options']:
                    st.radio("선택지", options=q['options'], key=ans_key)
                else:
                    st.text_input("답변 입력", key=ans_key)

                toggle_key = f"show_answer_{idx}"
                st.toggle("👁 정답 보기", key=toggle_key)
                if st.session_state.get(toggle_key):
                    correct = get_correct_answer_text(q)
                    st.markdown(f"🟢 정답: **{correct}**")

            if st.button("✅ 제출하기"):
                user_answers = [st.session_state.get(f"user_answer_{idx}", "") for idx in range(1, len(selected_questions)+1)]
                score = sum(is_user_answer_correct(q, ua) for q, ua in zip(selected_questions, user_answers))
                st.subheader("📊 채점 결과")
                for idx, (q, ua) in enumerate(zip(selected_questions, user_answers), start=1):
                    correct = get_correct_answer_text(q)
                    is_correct = is_user_answer_correct(q, ua)
                    st.markdown(f"{idx}. {'✅ 정답' if is_correct else f'❌ 오답'} - 정답: {correct} / 내 답: {ua.strip()}")
                st.success(f"🎯 총 점수: {score} / {len(selected_questions)}")
                result_text = generate_result_text(selected_questions, user_answers, score)
                st.download_button("📥 결과 저장 (txt)", result_text, file_name="quiz_result.txt")
                save_stats_to_csv(selected_questions, user_answers, score)

        with tab2:
            df = load_stats()
            if not df.empty:
                st.dataframe(df.tail(50))
                st.markdown(f"총 퀴즈 수: **{len(df)}** | 정답률: **{(df['result'] == '정답').mean() * 100:.2f}%**")
            else:
                st.info("아직 통계 데이터가 없습니다. 퀴즈를 먼저 풀어보세요!")

