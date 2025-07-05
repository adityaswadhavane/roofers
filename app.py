# Import python packages
import streamlit as st
from snowflake.snowpark.context import get_active_session
from uuid import uuid4
import pandas as pd
import snowflake.snowpark as sp
from snowflake.snowpark.functions import col
import datetime
import snowflake.snowpark.context as snowpark_context
import snowflake.snowpark.functions as F
from collections import Counter

# Get Snowflake session
session = snowpark_context.get_active_session()

# Get DB and schema
current_db = session.get_current_database().strip('"')
current_schema = "PUBLIC"
target_schema = "CONFIG_SCHEMA"  # Target schema for filtered views and config tables

# Create target schema if not exists
session.sql(f"CREATE SCHEMA IF NOT EXISTS {target_schema}").collect()

if st.button("🔄 Reset Filters & Rules"):
    for key in st.session_state.keys():
        del st.session_state[key]

    
# Helper: Generate unique view name
def generate_view_name(table_name):
    safe_table = table_name.replace('"', '').replace(' ', '_')
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    uid = str(uuid4())[:6]
    return f"vw_{safe_table}_{timestamp}_{uid}"

# Helper: Get latest version of a saved config
def get_latest_version(table_name):
    result = session.sql(f"""
        SELECT MAX(version) as latest_version
        FROM {target_schema}.configurations
        WHERE table_name = '{table_name}'
    """).collect()
    return result[0]["LATEST_VERSION"] if result[0]["LATEST_VERSION"] is not None else 0

# Build SQL WHERE clause from filters
def build_where_clause(filters):
    clauses = []
    for idx, f in enumerate(filters):
        if f is None:
            continue
        column = f["column"]
        cond = f["condition"]
        val = f["value"]
        filt_type = f["filter_type"].upper().strip()
        cs = f.get("case_sensitive", False)
        logic = f.get("logic", "").strip().upper()
        clause = ""
        if filt_type == "IN":
            values = [v.strip() for v in val.split(",")]
            formatted_values = [f"'{v}'" if not v.replace('.', '', 1).isdigit() else v for v in values]
            if cs:
                clause = f"{column} IN ({', '.join(formatted_values)})"
            else:
                clause = f"LOWER({column}) IN ({', '.join(['LOWER(' + v + ')' if not v.replace('.', '', 1).isdigit() else v for v in formatted_values])})"
        elif filt_type == "BETWEEN":
            try:
                lower, upper = [v.strip() for v in val.split(",")]
                clause = f"{column} BETWEEN {lower} AND {upper}"
            except Exception:
                clause = "-- INVALID BETWEEN FORMAT --"
        elif filt_type == "WHERE":
            is_number = val.replace('.', '', 1).isdigit()
            value_expr = val if is_number else f"'{val}'"
            if cs or is_number:
                clause = f"{column} {cond} {value_expr}"
            else:
                clause = f"LOWER({column}) {cond} LOWER('{val}')"
        else:
            clause = "-- UNSUPPORTED FILTER TYPE --"
        clause = f"({clause}) {logic}" if logic and idx < len(filters) - 1 else f"({clause})"
        clauses.append(clause)
    return f"WHERE {' '.join(clauses)}" if clauses else ""

def make_column_names_unique(col_names):
    counter = Counter()
    result = []
    for col in col_names:
        counter[col] += 1
        if counter[col] == 1:
            result.append(col)
        else:
            result.append(f"{col}_{counter[col]}")
    return result


def build_case_clauses(rules):
    clauses = []
    original_names = [rule['new_col'] for rule in rules]
    unique_names = make_column_names_unique(original_names)

    for idx, rule in enumerate(rules):
        output_col = unique_names[idx]
        if rule["operator"] == "IN":
            values_list = ", ".join("'" + v.strip() + "'" for v in rule["value"].split(','))
            when_clause = f"{rule['column']} IN ({values_list})"
        else:
            when_clause = f"{rule['column']} {rule['operator']} '{rule['value']}'"

        else_clause = f" ELSE '{rule['else']}'" if rule.get("else") else ""
        case_expr = f"CASE WHEN {when_clause} THEN '{output_col}'{else_clause} END AS {output_col}"
        clauses.append(case_expr)
    return clauses


def load_config_filters(config_id, version):
    filters_df = session.sql(f"""
        SELECT * FROM {target_schema}.filters
        WHERE config_id = '{config_id}' AND version = {version}
    """).to_pandas()

    return [{
        "column": row["COLUMN_NAME"],
        "filter_type": row["FILTER_TYPE"],
        "condition": row["OPERATOR"],
        "value": row["VALUE"],
        "case_sensitive": row["CASE_SENSITIVE"],
        "logic": row["AND_OR"]
    } for _, row in filters_df.iterrows()]

def load_config_rules(config_id, version):
    rules_df = session.sql(f"""
        SELECT * FROM {target_schema}.rules
        WHERE config_id = '{config_id}' AND version = {version}
    """).to_pandas()

    return [{
        "name": row["RULE_NAME"],
        "desc": row["RULE_DESC"],
        "column": row["COLUMN_NAME"],
        "operator": row["OPERATOR"],
        "value": row["VALUE"],
        "new_col": row["OUTPUT_COLUMN"],
        "else": row["ELSE_VALUE"],
        "then": row["OUTPUT_COLUMN"]  # Optional override
    } for _, row in rules_df.iterrows()]

def get_latest_config(table_name):
    config_df = session.sql(f"""
        SELECT config_id, version FROM {target_schema}.configurations
        WHERE table_name = '{table_name}' AND is_latest = TRUE
    """).to_pandas()

    return config_df.iloc[0] if not config_df.empty else None




# Load available tables
query = f"""
    SELECT TABLE_NAME
    FROM INFORMATION_SCHEMA.TABLES
    WHERE TABLE_TYPE = 'BASE TABLE'
    AND TABLE_SCHEMA = '{current_schema}'
    AND TABLE_CATALOG = '{current_db}'
"""
tables_df = session.sql(query).to_pandas()
table_list = tables_df["TABLE_NAME"].tolist()

st.write("📋 DB", current_db)
st.write("📋 Schema", current_schema)
st.write("📋 Available Tables:", table_list)

selected_table = st.selectbox("Select Source Table", table_list)

if selected_table and st.button("📂 Load Existing Configuration"):
    config = get_latest_config(selected_table)
    if config is not None:
        config_id = config["CONFIG_ID"]
        version = config["VERSION"]

        # Load filters
        filters = load_config_filters(config_id, version)
        st.session_state.applied_filters = filters
        st.session_state.add_filter = len(filters)
        st.session_state.filter_types = [f["filter_type"].upper() for f in filters]

        # Load rules (only 1 allowed)
        rules = load_config_rules(config_id, version)
        if rules:
            st.session_state.rules = [rules[0]]  # Ensure only 1

        st.success(f"✅ Loaded configuration v{version} for {selected_table}.")
    else:
        st.warning(f"No saved configuration found for table '{selected_table}'.")
        
###################     Set Session State Config   ###################


if "add_filter" not in st.session_state:
    st.session_state.add_filter = 1

if "filter_types" not in st.session_state:
    st.session_state.filter_types = ["WHERE"] * st.session_state.add_filter
    
if "applied_filters" not in st.session_state:
    st.session_state.applied_filters = [None] * st.session_state.add_filter
    
if "rules" not in st.session_state:
    st.session_state.rules = []
    
# Ensure list stays in sync with number of filters
while len(st.session_state.applied_filters) < st.session_state.add_filter:
    st.session_state.applied_filters.append(None)


###################     Preview Data   ###################

if selected_table:
    df_preview = session.table(selected_table).limit(10).to_pandas()
    st.dataframe(df_preview)
    columns = list(df_preview.columns)

st.header("🔧 Configuration for Filters")


########################  Filtering Maker  ########################

# Add filter button
if st.button("➕ Add New Filter"):
    st.session_state.add_filter += 1
    st.session_state.applied_filters.append(None)

# Ensure filter_types list is up to date
while len(st.session_state.filter_types) < st.session_state.add_filter:
    st.session_state.filter_types.append("WHERE")

# Render all filters
with st.container(border=True):
    for i in range(st.session_state.add_filter):
        st.subheader(f"🧱 Filter #{i + 1}")
        st.session_state.filter_types[i] = st.selectbox(
            "Filter Type", ["WHERE", "IN", "BETWEEN"], key=f"filter_type_selector_{i}")
        selected_filter_type = st.session_state.filter_types[i]

        with st.form(f"filter_form_{i}"):
            col = st.selectbox("Column", columns, key=f"col_{i}")

            if selected_filter_type == "WHERE":
                cond = st.selectbox("Condition", ["=", "!=", "<", ">", "<=", ">=", "LIKE"], key=f"cond_{i}")
                val = st.text_input("Value", key=f"val_{i}")
                cs = st.checkbox("Case Sensitive", key=f"cs_{i}")
                logic = st.selectbox("Combine with next", ["AND", "OR", ""], key=f"logic_{i}")
            elif selected_filter_type == "IN":
                cond = "IN"
                val = st.text_input("Comma-separated values", key=f"val_{i}")
                cs = st.checkbox("Case Sensitive", key=f"cs_{i}")
                logic = st.selectbox("Combine with next", ["AND", "OR", ""], key=f"logic_{i}")
            elif selected_filter_type == "BETWEEN":
                cond = "BETWEEN"
                lower, upper = st.columns(2)
                lower_val = lower.text_input("Lower Limit", key=f"lower_{i}")
                upper_val = upper.text_input("Upper Limit", key=f"upper_{i}")
                val = f"{lower_val},{upper_val}"
                cs = False
                logic = st.selectbox("Combine with next", ["AND", "OR", ""], key=f"logic_{i}")

            apply = st.form_submit_button("✅ Apply Filter")
            cancel = st.form_submit_button("❌ Cancel Filter")

            if apply:
                st.session_state.applied_filters[i] = {
                    "column": col,
                    "filter_type": selected_filter_type,
                    "condition": cond,
                    "value": val,
                    "logic": logic,
                    "case_sensitive": cs
                }
                st.success(f"Filter #{i+1} applied!")

            if cancel:
                st.session_state.applied_filters = [
                    f for j, f in enumerate(st.session_state.applied_filters) if j != i
                ]
                st.session_state.filter_types.pop(i)
                st.session_state.add_filter -= 1
                st.rerun()


########################  Rule Maker  ########################
st.header("🧠 Attribute Rule Engine")

with st.form("rule_form"):
    
    rule_name = st.text_input("Rule Name")
    rule_desc = st.text_area("Rule Description")
    rule_col = st.selectbox("Select Column", columns, key="rule_col")
    rule_op = st.selectbox("Operator", ["=", "!=", "<", "<=", ">", ">=", "LIKE", "IN"], key="rule_op")
    rule_val = st.text_input("Value", key="rule_val")
    rule_then = st.text_input("Then", key="then_val")
    rule_else = st.text_input("Else Value (optional)", key="rule_else")
    rule_new_col = st.text_input("New Column Name (output of rule)", key="rule_out_col")

    add_rule = st.form_submit_button("➕ Add Rule")

    if add_rule:
        st.session_state.rules.append({
            "name": rule_name,
            "desc": rule_desc,
            "column": rule_col,
            "operator": rule_op,
            "value": rule_val,
            "new_col": rule_new_col,
            "else": rule_else,
            "then":rule_then
            
        })
        st.success(f"✅ Rule '{rule_name}' added.")

    


# Final SQL preview
if selected_table:
    where_clause = build_where_clause(st.session_state.applied_filters)
    case_clauses = build_case_clauses(st.session_state.rules)
    select_expr = "*"
    if case_clauses:
        select_expr += ", " + ", ".join(case_clauses)
    
    qualified_table = f"{current_db}.{current_schema}.{selected_table}"
    full_sql = f"SELECT {select_expr} FROM {qualified_table} {where_clause}"

    # full_sql = f"SELECT * FROM {current_db}.{current_schema}.{selected_table} {where_clause}"
    st.code(full_sql)

    if st.button("▶️ Preview SQL Results"):
        try:
            preview_df = session.sql(full_sql).limit(20).to_pandas()
            st.dataframe(preview_df)
        except Exception as e:
            st.error(f"Query Failed: {str(e)}")

# Save and Create View
st.subheader("💾 Save Configuration")

if st.button("💾 Save Now"):
    config_id = str(uuid4())
    now = datetime.datetime.now()
    latest_version = get_latest_version(selected_table)
    new_version = latest_version + 1

    # Mark previous versions not latest
    session.sql(f"""
        UPDATE {target_schema}.configurations
        SET is_latest = FALSE
        WHERE table_name = '{selected_table}'
    """).collect()

    # Generate unique view name
    view_name = generate_view_name(selected_table)

    # Save configuration metadata
    session.sql(f"""
        INSERT INTO {target_schema}.configurations 
        (config_id, table_name, source_type, created_at, version, is_latest, view_name)
        VALUES ('{config_id}', '{selected_table}', 'table', '{now}', {new_version}, TRUE, '{view_name}')
    """).collect()

    # Save filters
    for fil in st.session_state.applied_filters:
        session.sql(f"""
            INSERT INTO {target_schema}.filters 
            (config_id, version, column_name, filter_type, operator, value, case_sensitive, and_or)
            VALUES (
                '{config_id}', {new_version}, '{fil["column"]}', '{fil["filter_type"]}',
                '{fil["condition"]}', '{fil["value"]}', {fil["case_sensitive"]}, '{fil["logic"]}'
            )
        """).collect()

    for r in st.session_state.rules:
        session.sql(f"""
            INSERT INTO {target_schema}.rules
            (config_id, version, rule_name, rule_desc, column_name, operator, value, output_column, else_value)
            VALUES (
                '{config_id}', {new_version}, '{r["name"]}', '{r["desc"]}', '{r["column"]}',
                '{r["operator"]}', '{r["value"]}', '{r["new_col"]}', '{r["else"]}'
            )
        """).collect()

    # Drop and Create View
    session.sql(f"DROP VIEW IF EXISTS sql_query_generator.{target_schema}.{view_name}").collect()
    session.sql(f"""
        CREATE OR REPLACE VIEW sql_query_generator.{target_schema}.{view_name} AS
        {full_sql}
    """).collect()
    st.code((f"""
        CREATE OR REPLACE VIEW sql_query_generator.{target_schema}.{view_name} AS
        {full_sql}
    """))
    st.success(f"✅ Configuration saved successfully with version {new_version}.")
    st.success(f"✅ View `{target_schema}.{view_name}` created.")
