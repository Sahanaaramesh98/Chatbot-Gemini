import streamlit as st
import pandas as pd
import google.generativeai as genai
import json
import os
import altair as alt
import re
# SETTING UP LLM
api_key = 'AIzaSyCl2n0vpx49oOC-PqYBIuzbptD008L2ZW4'
genai.configure(api_key=api_key)
safe = [
    {
        "category": "HARM_CATEGORY_HARASSMENT",
        "threshold": "BLOCK_NONE",
    },
    {
        "category": "HARM_CATEGORY_HATE_SPEECH",
        "threshold": "BLOCK_NONE",
    },
    {
        "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
        "threshold": "BLOCK_NONE",
    },
    {
        "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
        "threshold": "BLOCK_NONE",
    },
]
generation_config = {
    "temperature": 1,
    "top_p": 0.95,
    "top_k": 64,
    "max_output_tokens": 8192,
    "response_mime_type": "text/plain",
}
model = genai.GenerativeModel(
    model_name="gemini-1.5-pro",
    generation_config=generation_config,
    safety_settings=safe
)
chat_session = model.start_chat(history=[])
# LOADING DATA
df_main = pd.read_csv(r"C:\Users\HP\OneDrive - Manipal Academy of Higher Education\Documents\dumps\chatbot\all_masked_updated_v1.csv", encoding='utf-8', engine='python')
df = df_main[['contract_id','candidate_id','candidate_name','ethnicity','gender','entity','primary_skill','secondary_skill','domain','bu_owner','client','end_client','state','country','start_date','end_date','job_title','vendor','contract_source','contract_duration','contract_status','contract_type','pay_rate','pay_rate_basis','client_rate','client_rate_basis','margin']]
# QUERY TO SQL
def query_to_sql(query, chat):
    table_schema = """
    CREATE table df (
    contract_id,candidate_id,candidate_name,ethnicity,gender,entity,primary_skill,secondary_skill,domain,bu_owner,client,end_client,state,country,start_date,end_date,job_title,vendor,contract_source,contract_duration,contract_status,contract_type,pay_rate,pay_rate_basis,client_rate,client_rate_basis,margin)
    """
    prompt = f"""
    Hi there! 👋 I'm here to help you turn your question into a SQL query. Just let me know what you're looking for, and I'll generate the query for you.
    Here's the schema of the table I'll be working with:
    ===tables_schema:  {table_schema} ===
    Your Question: {query}
    ===Guidelines===
    1. If the context is enough, I'll create a SQL query without any explanations. It will start with a comment mentioning your question.
    2. If I need more details, I'll let you know why I can't generate a query.
    4. I'll filter the results based on their status unless you specify otherwise.
    5. I'll always use `client` OR `end_client` columns together.
    6. If your query is about skills, I'll include both `primary_skills` and `secondary_skills` unless you specify one.
    7. For job or profession queries, I'll check both `job_title` and `domain` columns.
    8. When finding candidates, I'll include their `name`, `id`, and `contract_id` as well.
    9. If you're searching for a race, I'll use the `ethnicity` column.
    10. I won't use `contract_status - active` unless asked directly.
    11. when asked for top skills and clients, the resulting table should include the top skills, the clients and respective count column
    12. if your query is about clients, include the number of records for each client and also the total number of records
    13. When finding clients, I'll include the client and the primary and secondary skills column.
    14. If the query asks for average or maximum margin, include these calculations in the SQL query.
    15. If the query asks for client rate and pay rate, make sure the margin is greater than zero
    """
    response = chat.send_message(prompt)
    return response.text
def sql_to_pandas(sqlquery, chat):
    prompt = f"""
    Hi! I can help you convert that SQL query into pandas code for your DataFrame. Just give me the SQL query, and I'll turn it into pandas code for you.
    Here's the SQL query you provided:
    {sqlquery}
    ===What I'll Do===
    I'll convert this SQL query into pandas code that works directly on a DataFrame named 'df'. I'll make sure to:
    1. Handle string comparisons case-insensitively
    2. Take care of any aggregate functions or filtering
    3. Use modern pandas methods (avoid deprecated methods like 'append')
    4. Use pd.concat() for combining DataFrames instead of append()
    5. Use df.loc[] for adding new rows instead of append()
    6. Include calculations for average and maximum margin when requested
    Just the pandas code, no extra explanations.
    For queries about pay rate, I'll use df['pay_rate'].mean() for average and df['pay_rate'].max() for maximum pay rate.
    For queries about margin, I'll use df['margin'].mean() for average and df['margin'].max() for maximum margin rate
    """
    response = chat.send_message(prompt)
    cleaned_response = response.text.strip().replace('```python', '').replace('```', '').strip()
    st.write("Debug - Cleaned pandas code:", cleaned_response)
    return cleaned_response
def log_query(query, code_executed, log_file=r"query_code_log.json"):
    log_entry = {
        "query": query,
        "code_executed": code_executed
    }
    if os.path.exists(log_file):
        with open(log_file, "r") as f:
            log_data = json.load(f)
    else:
        log_data = []
    log_data.append(log_entry)
    with open(log_file, "w") as f:
        json.dump(log_data, f, indent=4)
def generate_conversational_response(query, df_result, chat):
    if isinstance(df_result, pd.DataFrame):
        data_summary = {
            "Number of records": len(df_result),
            "Columns": ', '.join(df_result.columns),
            "First few rows": df_result.head().to_dict()
        }
        if 'margin' in df_result.columns:
            data_summary["Average Margin"] = df_result['margin'].mean()
            data_summary["Maximum Margin"] = df_result['margin'].max()
    else:
        data_summary = {
            "Number of records": "N/A (not a DataFrame)",
            "Columns": "N/A",
            "First few rows": str(df_result)
        }
    
    prompt = f"""
    Based on the following query and the resulting data, provide a conversational response as if you were a helpful assistant.
    Make the response sound natural and human-like, summarizing the key findings.
    Query: {query}
    Data summary:
    - Number of records: {data_summary["Number of records"]}
    - Columns: {data_summary["Columns"]}
    - First few rows: {data_summary["First few rows"]}
    {f"- Average Margin: {data_summary['Average Margin']:.2f}" if 'Average Margin' in data_summary else ""}
    {f"- Maximum Margin: {data_summary['Maximum Margin']:.2f}" if 'Maximum Margin' in data_summary else ""}
    Please provide a friendly, informative response that answers the query and expands on it more in depth in respect to the data.
    Include information about average and maximum margin if available.
    """
    response = chat.send_message(prompt)
    return response.text
def generate_graph(df_result, query, chat):
    prompt = f"""
    Based on the following query and the resulting data, provide only the Python code to generate an appropriate Altair graph.
    Do not include any explanations, comments, or markdown formatting.
    Use 'df_result' as the DataFrame name and 'alt' for Altair.
    The code should be a single line that creates and returns an Altair chart object.
    
    Important:
    1. If the dataframe has more than 10 rows, only plot the top 10 values.
    2. For bar charts, use 'mark_bar()'.
    3. For line charts (e.g., time series data), use 'mark_line()'.
    4. For scatter plots, use 'mark_circle()'.
    5. Sort the data within the encode function using 'sort='-x'' for descending order.
    6. If margin data is available, consider including it in the visualization.
    
    Examples:
    - For a bar chart: return alt.Chart(df_result.nlargest(10, 'value_column')).mark_bar().encode(x=alt.X('category_column', sort='-y'), y='value_column')
    - For a line chart: return alt.Chart(df_result.nlargest(10, 'value_column')).mark_line().encode(x='date_column', y='value_column')
    - For a scatter plot: return alt.Chart(df_result.nlargest(10, 'value_column')).mark_circle().encode(x='x_column', y='y_column', size='size_column')
    Query: {query}
    Data summary:
    - Number of records: {len(df_result)}
    - Columns: {', '.join(df_result.columns)}
    - First few rows: {df_result.head().to_dict()}
    """
    response = chat.send_message(prompt)
    return response.text.strip().replace('```python', '').replace('```', '').strip()
def safe_eval_chart(code, df_result):
    if code.strip().startswith('alt.Chart'):
        try:
            # Remove 'return' if it's at the beginning of the code
            code = code.replace('return', '', 1).strip()
            # Use eval to create the chart object
            chart = eval(code, {'alt': alt, 'df_result': df_result, 'pd': pd})
            if isinstance(chart, alt.Chart):
                return chart
        except Exception as e:
            st.error(f"Error in chart creation: {str(e)}")
    return None
# SETTING UP WEBPAGE
st.set_page_config(layout="wide")
st.title("VDart Chatbot")
st.markdown("Welcome to the VDart Chatbot! 🤖 Ask me anything about our database, and I'll help you find the information you need.")
col1, col2 = st.columns(2)
with col1:
    st.info("Here's a preview of the database we're working with:")
    st.dataframe(df)
with col2:
    st.info("What do you want to know? Just type your question here, and I'll generate a query for you.")
    query = st.text_area("Type your query here:")
    graph_mode = st.checkbox("Enable Graph Mode")
    generate = st.button("Generate Query")
    if generate:
        if query:
            with st.spinner("I'm working on your query... please wait a moment."):
                sqlquery = query_to_sql(query, chat_session)
                st.write("Here's the SQL query I generated for you:", sqlquery)
                
                pandas_code = sql_to_pandas(sqlquery, chat_session)
                st.write("Here's the pandas code to run this query:", pandas_code)
                log_query(query, pandas_code)
        try:
            # Safely execute the generated pandas code
            local_vars = {"df": df, "pd": pd}
            exec(f"df_result = {pandas_code}", {}, local_vars)
            df_result = local_vars["df_result"]
            
            if not isinstance(df_result, pd.DataFrame):
                if isinstance(df_result, pd.Series):
                    df_result = df_result.reset_index(name='count')
                else:
                    raise ValueError("The result of the pandas code execution is not a DataFrame or Series.")
            # Generate conversational response
            conversational_response = generate_conversational_response(query, df_result, chat_session)
            # Display the conversational response
            st.write("Chatbot Response:")
            st.write(conversational_response)
            
            # Display the result table
            st.dataframe(df_result)
            st.write("Number of records: ", len(df_result))
            
            # Display average and maximum margin if available
            if 'margin' in df_result.columns:
                st.write(f"Average Margin: {df_result['margin'].mean():.2f}")
                st.write(f"Maximum Margin: {df_result['margin'].max():.2f}")
            # Generate and display graph if graph mode is enabled
            if graph_mode:
                graph_code = generate_graph(df_result, query, chat_session)
                st.write("Generated Altair Code:")
                st.code(graph_code, language="python")
                
                st.write("Debug - Graph code to be executed:", graph_code)
                
                chart = safe_eval_chart(graph_code, df_result)
                if chart:
                    st.altair_chart(chart, use_container_width=True)
                else:
                    st.warning("No valid Altair chart was created. Please check the generated code.")
        except Exception as e:
            st.error(f"Oops, something went wrong: {str(e)}")
            st.exception(e)