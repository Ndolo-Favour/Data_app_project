import requests
import pandas as pd
import streamlit as st
import json
import zipfile
import io
from fpdf import FPDF

API_URL = "https://script.google.com/macros/s/AKfycbwQ5S7fWduVFhT_xaXUw7cFpiPWwOWBVvyRCr5fouaiugBifFvFpayKBCDzd1H-QqI9/exec"

st.set_page_config(page_title="Livelystone Educational Hub", layout="wide")

@st.cache_data(ttl=300)
def load_entire_database(url):
    try:
        response = requests.get(url, timeout=15)
        if response.status_code == 200:
            try:
                return {tab_name: pd.DataFrame(data) for tab_name, data in response.json().items()}, None
            except Exception as json_err:
                return None, f"JSON Parsing Error: The web app executed but did not return structured database JSON. Raw text received: {response.text[:300]}"
        return None, f"Google Web App Server Error: Returned status code {response.status_code}"
    except Exception as network_err:
        return None, f"Network/Connection Error: {str(network_err)}"

def write_back_to_sheets(dataframe, sheet_name, action_type, extra_metadata=None, log_message=""):
    data_records = dataframe.fillna("").to_dict(orient="records") if not dataframe.empty else []
    payload = {
        "action": action_type,
        "sheetName": sheet_name,
        "data": data_records,
        "meta": extra_metadata or {},
        "logMessage": log_message
    }
    
    try:
        response = requests.post(
            API_URL,
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
            timeout=15
        )
        
        if response.status_code == 200:
            try:
                response_json = response.json()
                if response_json.get("status") == "success":
                    return True, response_json.get("message")
                else:
                    return False, response_json.get("message", "Script executed with an unspecified error.")
            except Exception:
                return False, f"Response was not valid JSON. Raw output: {response.text}"
        return False, f"Server responded with status code: {response.status_code}"
    except Exception as e:
        return False, str(e)

def generate_pdf_report(student_name, student_class, term, year, scores_df):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=16)
    pdf.cell(200, 10, txt="No Limits Sec. School", ln=True, align="C")
    
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt=f"Term Report: {term} ({year})", ln=True, align="C")
    pdf.ln(10)
    
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt=f"Student Name: {student_name}", ln=True, align="L")
    pdf.cell(200, 10, txt=f"Class: {student_class}", ln=True, align="L")
    pdf.ln(10)
    
    pdf.set_font("Arial", size=10)
    pdf.cell(60, 10, "Subject", border=1)
    pdf.cell(30, 10, "CA 1", border=1, align="C")
    pdf.cell(30, 10, "CA 2", border=1, align="C")
    pdf.cell(30, 10, "Exam", border=1, align="C")
    pdf.cell(30, 10, "Total", border=1, align="C")
    pdf.ln()
    
    for idx, row in scores_df.iterrows():
        pdf.cell(60, 10, str(row.get("Subject", "")), border=1)
        pdf.cell(30, 10, str(row.get("CA1", "")), border=1, align="C")
        pdf.cell(30, 10, str(row.get("CA2", "")), border=1, align="C")
        pdf.cell(30, 10, str(row.get("Exam", "")), border=1, align="C")
        pdf.cell(30, 10, str(row.get("Term_Total", "")), border=1, align="C")
        pdf.ln()
        
    pdf_out = pdf.output(dest="S")
    return pdf_out.encode("latin-1") if isinstance(pdf_out, str) else bytes(pdf_out)

db_result, db_error = load_entire_database(API_URL)

if not db_result:
    st.error("Database connection failed due to a network timeout or downtime.")
    if db_error:
        st.warning(db_error)
    if st.button("Retry Connection & Refresh"):
        st.cache_data.clear()
        st.rerun()
else:
    db = db_result
    master_registry = db.get("Master_Registry")
    teacher_registry = db.get("teacher_registry")
    teacher_assignments = db.get("teacher_assignments")
    app_config = db.get("app_config")
    grade_records = db.get("grade_records")
    term_summaries = db.get("term_summaries")
    grading_system = db.get("grading_system")

    if grade_records is None:
        grade_records = pd.DataFrame(columns=["Record_ID", "Student_ID", "Subject", "Term", "CA1", "CA2", "Exam", "Term_Total"])
    if term_summaries is None:
        term_summaries = pd.DataFrame(columns=["Summary_ID", "Student_ID", "Term", "Class", "Teacher_Comment"])
    if app_config is None:
        app_config = pd.DataFrame(columns=["Setting_Name", "Setting_Value"])

    class_teacher_mapping = db.get("class_teacher_mapping") if db.get("class_teacher_mapping") is not None else pd.DataFrame(columns=["Class", "Teacher_ID", "Term"])
    term_historical_analytics = db.get("term_historical_analytics") if db.get("term_historical_analytics") is not None else pd.DataFrame(columns=["Term_ID", "School_Wide_Average", "Total_Enrollment"])

    config_dict = dict(zip(app_config["Setting_Name"], app_config["Setting_Value"])) if not app_config.empty else {}
    current_year = config_dict.get("Current_Academic_Year", "2025/2026")
    current_term = config_dict.get("Current_Term", "First Term")
    min_passing_score = float(config_dict.get("Minimum_Passing_Score", 40))
    max_ca1 = float(config_dict.get("Max_CA1_Score", 20))
    max_ca2 = float(config_dict.get("Max_CA2_Score", 20))
    max_exam = float(config_dict.get("Max_Exam_Score", 60))
    allow_grade_entry = str(config_dict.get("Allow_Teacher_Grade_Entry", "TRUE")).upper() == "TRUE"

    st.sidebar.markdown("## LivelystoneEducational")
    st.sidebar.markdown("# No Limits Sec. School")

    user_role = st.sidebar.radio(
        "Select your access portal:",
        ["Admin Dashboard", "Teacher Portal", "Student Results View"]
    )

    if user_role == "Admin Dashboard":
        st.title("Administrative Management Workspace")

        admin_pin = st.text_input("Enter your unique Admin Access PIN:", type="password", key="admin_portal_pin")

        if admin_pin:
            if teacher_registry is None:
                st.error("Critical Error: The teacher_registry table is missing or could not be loaded.")
            else:
                target_column = "Teacher_ID"
                if target_column in teacher_registry.columns:
                    valid_pins = teacher_registry[target_column].astype(str).values

                    if admin_pin in valid_pins:
                        current_admin = teacher_registry[teacher_registry[target_column].astype(str) == admin_pin].iloc[0]
                        admin_name = current_admin["Teacher_Name"] if "Teacher_Name" in teacher_registry.columns else "Admin"
                        staff_role = current_admin["Staff_role"] if "Staff_role" in teacher_registry.columns else ""

                        if staff_role != "Admin":
                            st.error("You do not have access to this page.")
                        else:
                            st.success(f"Access Granted. Welcome back, {admin_name}!")
                            st.info(f"Active Database Environment: {current_year} and {current_term}")

                            adm_tabs = st.tabs(["School Configurations", "School Analytics Panel", "Review Teacher Work", "Batch Operations"])

                            with adm_tabs[0]:
                                st.subheader("Administrative Controls")
                                config_action = st.selectbox("Select Administration Configuration Goal:", [
                                    "Set Active Academic Session & Term",
                                    "Update Grading Rules & Thresholds",
                                    "Onboard New Staff Profile",
                                    "Register Student to Master Registry",
                                    "Assign Subject Teaching Task",
                                    "Map Class Form Teacher Link"
                                ])
                                
                                dynamic_class_list = master_registry["Class"].dropna().unique().tolist() if master_registry is not None and not master_registry.empty else ["Awaiting Data"]

                                if config_action == "Set Active Academic Session & Term":
                                    st.markdown("#### Global Time and Period Settings")
                                    st.caption("Updating these values restricts the active dataset across all teacher and student portals.")
                                    
                                    new_session = st.selectbox("Select Academic Year:", ["2024/2025", "2025/2026", "2026/2027", "2027/2028"], index=["2024/2025", "2025/2026", "2026/2027", "2027/2028"].index(current_year) if current_year in ["2024/2025", "2025/2026", "2026/2027", "2027/2028"] else 0)
                                    new_term = st.selectbox("Select Active Term:", ["First Term", "Second Term", "Third Term"], index=["First Term", "Second Term", "Third Term"].index(current_term) if current_term in ["First Term", "Second Term", "Third Term"] else 0)
                                    
                                    if st.button("Commit Global Session Update"):
                                        update_df = pd.DataFrame([
                                            {"Setting_Name": "Current_Academic_Year", "Setting_Value": new_session},
                                            {"Setting_Name": "Current_Term", "Setting_Value": new_term}
                                        ])
                                        with st.spinner("Updating global environment variables..."):
                                            log_text = f"Admin {admin_name} updated active environment to {new_session} and {new_term}"
                                            success, message = write_back_to_sheets(update_df, "app_config", "update_config", log_message=log_text)
                                            if success:
                                                st.success(f"System locked to {new_session} and {new_term}. Refreshing environment...")
                                                st.cache_data.clear()
                                                st.rerun()
                                            else:
                                                st.error(f"Configuration update failed: {message}")
                                
                                elif config_action == "Update Grading Rules & Thresholds":
                                    st.markdown("#### Assessment Boundaries & Access Control")
                                    new_min_pass = st.number_input("Minimum Passing Score:", value=int(min_passing_score))
                                    new_ca1 = st.number_input("Max CA1 Score:", value=int(max_ca1))
                                    new_ca2 = st.number_input("Max CA2 Score:", value=int(max_ca2))
                                    new_exam = st.number_input("Max Exam Score:", value=int(max_exam))
                                    portal_open = st.checkbox("Allow Teachers to Edit Grades (Portal Open)", value=allow_grade_entry)
                                    
                                    if st.button("Update Grading Boundaries"):
                                        update_df = pd.DataFrame([
                                            {"Setting_Name": "Minimum_Passing_Score", "Setting_Value": new_min_pass},
                                            {"Setting_Name": "Max_CA1_Score", "Setting_Value": new_ca1},
                                            {"Setting_Name": "Max_CA2_Score", "Setting_Value": new_ca2},
                                            {"Setting_Name": "Max_Exam_Score", "Setting_Value": new_exam},
                                            {"Setting_Name": "Allow_Teacher_Grade_Entry", "Setting_Value": str(portal_open)}
                                        ])
                                        with st.spinner("Applying new threshold architecture..."):
                                            log_text = f"Admin {admin_name} updated master grading rules and portal access"
                                            success, message = write_back_to_sheets(update_df, "app_config", "update_config", log_message=log_text)
                                            if success:
                                                st.success("Grading constraints updated globally.")
                                                st.cache_data.clear()
                                                st.rerun()
                                            else:
                                                st.error(f"Configuration update failed: {message}")

                                elif config_action == "Onboard New Staff Profile":
                                    st.markdown("#### Staff Onboarding Form")
                                    new_name = st.text_input("Enter Teacher Full Name:")
                                    new_pin = st.text_input("Generate / Set Unique Access PIN:", type="password")
                                    new_role = st.selectbox("Assigned System Permissions Level:", ["Teacher", "Admin"])
                                    if st.button("Save Teacher Profile"):
                                        if new_name and new_pin:
                                            new_staff_df = pd.DataFrame([{"Teacher_ID": new_pin, "Teacher_Name": new_name, "Staff_role": new_role}])
                                            log_text = f"Admin {admin_name} registered new staff member {new_name}"
                                            success, message = write_back_to_sheets(new_staff_df, "teacher_registry", "append_row", log_message=log_text)
                                            if success:
                                                st.success(f"Profile created in database for {new_name} as role {new_role}!")
                                                st.cache_data.clear()
                                            else:
                                                st.error(f"Failed to save profile: {message}")
                                        else:
                                            st.error("All form text fields are explicitly required.")

                                elif config_action == "Register Student to Master Registry":
                                    st.markdown("#### Student Onboarding Form")
                                    stu_name = st.text_input("Enter Student Full Name:")
                                    stu_class = st.selectbox("Target Class Arm Mapping Selection:", dynamic_class_list)
                                    if st.button("Commit Student Registry Record"):
                                        if stu_name:
                                            new_student_df = pd.DataFrame([{"STUDENT NAME": stu_name, "Class": stu_class}])
                                            log_text = f"Admin {admin_name} enrolled new student {stu_name} into {stu_class}"
                                            success, message = write_back_to_sheets(new_student_df, "Master_Registry", "append_row", log_message=log_text)
                                            if success:
                                                st.success(f"Successfully appended student into Master Registry for room {stu_class}!")
                                                st.cache_data.clear()
                                            else:
                                                st.error(f"Failed to record student: {message}")
                                        else:
                                            st.error("Student name cannot be left blank.")

                                elif config_action == "Assign Subject Teaching Task":
                                    st.markdown("#### Subject Allocation Assignment Wizard")
                                    if teacher_registry is not None and not teacher_registry.empty:
                                        t_choice = st.selectbox("Select Target Teacher:", teacher_registry["Teacher_Name"].unique())
                                        c_choice = st.selectbox("Select Target Class Assignment Room:", dynamic_class_list)
                                        s_choice = st.text_input("Enter Subject Key Name (e.g., Data Science, Biology):")
                                        if st.button("Deploy Subject Task Assignment Row"):
                                            if s_choice:
                                                t_id = teacher_registry[teacher_registry["Teacher_Name"] == t_choice]["Teacher_ID"].values[0]
                                                new_task_df = pd.DataFrame([{"Teacher_ID": t_id, "Class": c_choice, "Subject": s_choice, "Status": "Pending"}])
                                                log_text = f"Admin {admin_name} assigned {s_choice} to teacher ID {t_id} for class {c_choice}"
                                                success, message = write_back_to_sheets(new_task_df, "teacher_assignments", "append_row", log_message=log_text)
                                                if success:
                                                    st.success(f"Allocated {s_choice} in room {c_choice} directly to active portal plan!")
                                                    st.cache_data.clear()
                                                else:
                                                    st.error(f"Allocation failure: {message}")
                                            else:
                                                st.error("Please specify a valid subject title.")

                                elif config_action == "Map Class Form Teacher Link":
                                    st.markdown("#### Class to Form Teacher Mapping Wizard")
                                    if teacher_registry is not None and not teacher_registry.empty:
                                        t_choice = st.selectbox("Select Form Teacher:", teacher_registry["Teacher_Name"].unique(), key="map_t_choice")
                                        c_choice = st.selectbox("Select Class to Map:", dynamic_class_list, key="map_c_choice")
                                        if st.button("Deploy Form Teacher Mapping Link"):
                                            t_id = teacher_registry[teacher_registry["Teacher_Name"] == t_choice]["Teacher_ID"].values[0]
                                            new_map_df = pd.DataFrame([{"Class": c_choice, "Teacher_ID": t_id}])
                                            log_text = f"Admin {admin_name} mapped teacher ID {t_id} as form master for {c_choice}"
                                            success, message = write_back_to_sheets(new_map_df, "class_teacher_mapping", "append_row", log_message=log_text)
                                            if success:
                                                st.success(f"Successfully mapped form teacher for {c_choice}!")
                                                st.cache_data.clear()
                                            else:
                                                st.error(f"Mapping deployment failed: {message}")
                                    else:
                                        st.warning("Teacher registry configuration is currently empty or unavailable.")

                            with adm_tabs[1]:
                                st.subheader("NLS Institutional Insights")

                                st.markdown("#### Annual Performance Metrics Breakdown")
                                col_t1, col_t2, col_t3 = st.columns(3)

                                averages = []
                                if not term_historical_analytics.empty and "School_Wide_Average" in term_historical_analytics.columns:
                                    historical_records = term_historical_analytics.sort_values(by="Term_ID").tail(3)
                                    averages = pd.to_numeric(historical_records["School_Wide_Average"], errors="coerce").tolist()

                                    val_1 = f"{averages[0]:.2f}%" if len(averages) > 0 and pd.notna(averages[0]) else "Awaiting Data"
                                    val_2 = f"{averages[1]:.2f}%" if len(averages) > 1 and pd.notna(averages[1]) else "Awaiting Data"
                                    val_3 = f"{averages[2]:.2f}%" if len(averages) > 2 and pd.notna(averages[2]) else "Awaiting Data"

                                    col_t1.metric(label="First Term Average", value=val_1)
                                    col_t2.metric(label="Second Term Average", value=val_2)
                                    col_t3.metric(label="Third Term Average", value=val_3)
                                else:
                                    col_t1.metric(label="First Term Average", value="Awaiting Data")
                                    col_t2.metric(label="Second Term Average", value="Awaiting Data")
                                    col_t3.metric(label="Third Term Average", value="Awaiting Data")

                                st.markdown("#### Overview of Class Records")
                                if master_registry is not None and not master_registry.empty:
                                    class_totals = master_registry["Class"].value_counts().reset_index()
                                    class_totals.columns = ["Class", "Total Students Count"]

                                    if "Gender" in master_registry.columns:
                                        gender_counts = pd.crosstab(master_registry["Class"], master_registry["Gender"]).reset_index()
                                        male_col = [c for c in gender_counts.columns if str(c).upper() == "MALE"]
                                        female_col = [c for c in gender_counts.columns if str(c).upper() == "FEMALE"]

                                        gender_counts["Male Count"] = gender_counts[male_col[0]] if male_col else 0
                                        gender_counts["Female Count"] = gender_counts[female_col[0]] if female_col else 0
                                        class_counts = pd.merge(class_totals, gender_counts[["Class", "Male Count", "Female Count"]], on="Class", how="left")
                                    else:
                                        class_counts = class_totals

                                    if not class_teacher_mapping.empty and "Class" in class_teacher_mapping.columns:
                                        merged_matrix = pd.merge(class_counts, class_teacher_mapping, on="Class", how="left")
                                        if "Teacher_ID" in merged_matrix.columns and teacher_registry is not None and not teacher_registry.empty:
                                            merged_matrix["Teacher_ID"] = merged_matrix["Teacher_ID"].astype(str)
                                            teacher_registry_lookup = teacher_registry[["Teacher_ID", "Teacher_Name"]].copy()
                                            teacher_registry_lookup["Teacher_ID"] = teacher_registry_lookup["Teacher_ID"].astype(str)
                                            merged_matrix = pd.merge(merged_matrix, teacher_registry_lookup, on="Teacher_ID", how="left")
                                            merged_matrix["Class_Teacher"] = merged_matrix["Teacher_Name"].fillna("Unassigned Profile")
                                            merged_matrix = merged_matrix.drop(columns=["Teacher_ID", "Teacher_Name"], errors="ignore")
                                        else:
                                            merged_matrix["Class_Teacher"] = "Unassigned Profile"
                                    else:
                                        merged_matrix = class_counts.copy()
                                        merged_matrix["Class_Teacher"] = "No Mapping Found"

                                    st.dataframe(merged_matrix, hide_index=True, use_container_width=True)

                                display_name = "Student_Name" if master_registry is not None and "Student_Name" in master_registry.columns else ("STUDENT NAME" if master_registry is not None and "STUDENT NAME" in master_registry.columns else None)

                                if grade_records is not None and not grade_records.empty and master_registry is not None and not master_registry.empty:
                                    
                                    current_term_grades = grade_records[grade_records["Term"] == current_term].copy()
                                    
                                    if not current_term_grades.empty:
                                        current_term_grades["Term_Total"] = pd.to_numeric(current_term_grades["Term_Total"], errors="coerce").fillna(0)
                                        student_averages = current_term_grades.groupby("Student_ID")["Term_Total"].mean().reset_index()
                                        student_averages.columns = ["Student_ID", "Term_Average"]
                                        calc_reg = pd.merge(student_averages, master_registry, on="Student_ID", how="left")
    
                                        def categorize_section(class_name):
                                            if "JSS" in str(class_name).upper():
                                                return "Junior"
                                            elif "SS" in str(class_name).upper():
                                                return "Senior"
                                            return "Other"
    
                                        calc_reg["Section"] = calc_reg["Class"].apply(categorize_section)
    
                                        st.markdown("### School Leaderboard Engine")
                                        col_jun, col_sen = st.columns(2)
    
                                        lbl_name = display_name if display_name else "Student_Name"
                                        if lbl_name not in calc_reg.columns:
                                            calc_reg[lbl_name] = "Blank Name"
    
                                        with col_jun:
                                            st.markdown("Top 2 Performing Junior Students (JSS1 to JSS3)")
                                            juniors = calc_reg[calc_reg["Section"] == "Junior"].nlargest(2, "Term_Average")
                                            if not juniors.empty:
                                                for idx, row in juniors.iterrows():
                                                    st.write(f"• {row[lbl_name]} ({row['Class']}) Average: {row['Term_Average']:.3f}%")
                                            else:
                                                st.write("Awaiting junior school grades.")
    
                                        with col_sen:
                                            st.markdown("Top 2 Performing Senior Students (SS1 to SS3)")
                                            seniors = calc_reg[calc_reg["Section"] == "Senior"].nlargest(2, "Term_Average")
                                            if not seniors.empty:
                                                for idx, row in seniors.iterrows():
                                                    st.write(f"• {row[lbl_name]} ({row['Class']}) Average: {row['Term_Average']:.3f}%")
                                            else:
                                                st.write("Awaiting senior school grades.")
    
                                        st.markdown("#### Academic Intervention Risk Alerts")
                                        bottom_students = calc_reg[calc_reg["Term_Average"] > 0].nsmallest(2, "Term_Average")
                                        if not bottom_students.empty:
                                            for idx, row in bottom_students.iterrows():
                                                st.error(f"Red Alert: {row[lbl_name]} ({row['Class']}) Current Cumulative Term Avg: {row['Term_Average']:.3f}%")
                                        else:
                                            st.info("No current academic risk alerts to display.")
                                    else:
                                        st.info(f"No grade entries found for the currently active term: {current_term}")
                                else:
                                    st.info("Leaderboard data will compute automatically once scores are submitted to the master registry.")

                                st.markdown("### Predictive Analytics Module")
                                st.info("Model Architecture Pipeline: In the next integration milestone, an analytics engine will analyze historical score curves, flag risk categories, and project terminal performance metrics.")

                            with adm_tabs[2]:
                                st.subheader("Pending Teacher Sheets Review Ledger")
                                if teacher_assignments is not None and not teacher_assignments.empty:
                                    pending_sheets = teacher_assignments[teacher_assignments["Status"] == "Submitted"]
                                    if not pending_sheets.empty:
                                        selected_review = st.selectbox("Select a submitted sheet row to audit:",
                                                                       pending_sheets.apply(lambda r: f"{r['Class']} - {r['Subject']}", axis=1))

                                        st.info(f"Auditing Sheet Data: {selected_review}")
                                        rejection_reason = st.text_area("If rejecting this sheet, you must type a reason explanation note below:", key="admin_reject_note")

                                        btn_app, btn_rej = st.columns(2)
                                        with btn_app:
                                            if st.button("Approve and Lock Score Sheet"):
                                                parsed_sel = selected_review.split(" - ")
                                                log_text = f"Admin {admin_name} approved scores for class {parsed_sel[0]} subject {parsed_sel[1]}"
                                                success, message = write_back_to_sheets(
                                                    dataframe=pd.DataFrame(),
                                                    sheet_name="teacher_assignments",
                                                    action_type="approve_assignment_sheet",
                                                    extra_metadata={"Class": parsed_sel[0], "Subject": parsed_sel[1]},
                                                    log_message=log_text
                                                )
                                                if success:
                                                    st.success("Sheet verified. Grades committed to permanent records.")
                                                    st.cache_data.clear()
                                                else:
                                                    st.error(f"Approval update failed: {message}")
                                        with btn_rej:
                                            if st.button("Reject and Send Back to Teacher Workspace"):
                                                if not rejection_reason.strip():
                                                    st.error("Action Blocked: You must write an explanation note in the text field above before executing a rejection.")
                                                else:
                                                    parsed_sel = selected_review.split(" - ")
                                                    log_text = f"Admin {admin_name} rejected scores for class {parsed_sel[0]} subject {parsed_sel[1]}"
                                                    success, message = write_back_to_sheets(
                                                        dataframe=pd.DataFrame(),
                                                        sheet_name="teacher_assignments",
                                                        action_type="reject_assignment_sheet",
                                                        extra_metadata={"Class": parsed_sel[0], "Subject": parsed_sel[1], "Feedback": rejection_reason},
                                                        log_message=log_text
                                                    )
                                                    if success:
                                                        st.warning(f"Sheet returned to teacher workspace with note: '{rejection_reason}'")
                                                        st.cache_data.clear()
                                                    else:
                                                        st.error(f"Rejection update failed: {message}")
                                    else:
                                        st.success("All submitted grade sheets across the school have been fully processed and approved!")
                                else:
                                    st.caption("No teacher tracking tasks found in database configuration.")

                            with adm_tabs[3]:
                                st.subheader("Centralized Document Compilation Desk")
                                st.markdown("Generate and compile terminal assessment documents in bulk processing queues.")

                                available_classes = master_registry["Class"].dropna().unique().tolist() if master_registry is not None and not master_registry.empty else ["Awaiting Data"]
                                batch_class = st.selectbox("Select Target Class Selection Group:", ["All Classes Combined"] + available_classes)

                                if st.button("Initialize Batch Generation Loop"):
                                    with st.spinner("Compiling PDF reports securely into zip payload..."):
                                        zip_buffer = io.BytesIO()
                                        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                                            
                                            filter_class = None if batch_class == "All Classes Combined" else batch_class
                                            target_students = master_registry if filter_class is None else master_registry[master_registry["Class"] == filter_class]
                                            display_name = "Student_Name" if "Student_Name" in target_students.columns else ("STUDENT NAME" if "STUDENT NAME" in target_students.columns else None)
                                            
                                            if not target_students.empty and grade_records is not None:
                                                term_data = grade_records[grade_records["Term"] == current_term]
                                                
                                                for _, student in target_students.iterrows():
                                                    s_id = student.get("Student_ID")
                                                    s_name = student.get(display_name, "Unknown Student")
                                                    s_class = student.get("Class", "Unknown Class")
                                                    
                                                    student_scores = term_data[term_data["Student_ID"] == s_id]
                                                    if not student_scores.empty:
                                                        pdf_bytes = generate_pdf_report(s_name, s_class, current_term, current_year, student_scores)
                                                        safe_name = str(s_name).replace(" ", "_")
                                                        zip_file.writestr(f"{safe_name}_{s_class}_Report.pdf", pdf_bytes)
                                                        
                                        st.success(f"Successfully processed batch printing profile loops for target group: {batch_class} during {current_term}!")
                                        st.download_button(
                                            label="Download Consolidated Term Report Ledger Bundle",
                                            data=zip_buffer.getvalue(),
                                            file_name=f"Livelystone_Reports_{current_term}.zip",
                                            mime="application/zip"
                                        )

                    else:
                        st.error("Invalid verification PIN. Access denied.")
                else:
                    st.error(f"The column '{target_column}' does not match your sheet.")
        else:
            st.info("Please enter your assigned admin verification code to unlock this dashboard.")

    elif user_role == "Teacher Portal":
        st.title("Teacher Grading Portal")

        teacher_pin = st.text_input("Enter your unique Teacher Access PIN:", type="password", key="teacher_portal_pin")

        if teacher_pin:
            if teacher_registry is None:
                st.error("Critical Error: The teacher_registry table is missing or could not be loaded.")
            else:
                target_column = "Teacher_ID"
                if target_column in teacher_registry.columns:
                    valid_pins = teacher_registry[target_column].astype(str).values

                    if teacher_pin in valid_pins:
                        current_teacher = teacher_registry[teacher_registry[target_column].astype(str) == teacher_pin].iloc[0]
                        teacher_name = current_teacher["Teacher_Name"] if "Teacher_Name" in teacher_registry.columns else "Teacher"
                        staff_role = current_teacher["Staff_role"] if "Staff_role" in teacher_registry.columns else "Teacher"

                        if staff_role not in ["Teacher", "Admin"]:
                            st.error("You do not have access to this page.")
                        else:
                            st.success(f"Access Granted. Welcome back, {teacher_name}!")
                            st.info(f"Active Assessment Environment: {current_year} and {current_term}")

                            if teacher_assignments is None or master_registry is None:
                                st.error("Error: Required tracking tables are missing from the database configuration.")
                            else:
                                teacher_id_string = str(current_teacher[target_column])
                                my_assignments = teacher_assignments[teacher_assignments["Teacher_ID"].astype(str) == teacher_id_string].copy()

                                if "Status" not in my_assignments.columns:
                                    my_assignments["Status"] = "Pending"
                                if "Admin_Feedback" not in my_assignments.columns:
                                    my_assignments["Admin_Feedback"] = ""

                                total_tasks = len(my_assignments)
                                completed_tasks = len(my_assignments[my_assignments["Status"] == "Approved"])
                                progress_percentage = (completed_tasks / total_tasks) if total_tasks > 0 else 0.0

                                st.subheader("Your Termly Completion Progress")
                                st.progress(progress_percentage)
                                st.caption(f"{completed_tasks} of {total_tasks} teaching tasks fully finalized and approved by Admin.")

                                tab_active, tab_submitted = st.tabs(["Active Grading Tasks", "Awaiting Admin Approval"])

                                with tab_active:
                                    active_assignments = my_assignments[my_assignments["Status"] != "Approved"]

                                    if not active_assignments.empty:
                                        assigned_classes = active_assignments["Class"].unique()
                                        selected_class = st.selectbox("Select an active class to manage:", assigned_classes)

                                        class_filtered_assignments = active_assignments[active_assignments["Class"] == selected_class]
                                        assigned_subjects = class_filtered_assignments["Subject"].unique()
                                        selected_subject = st.selectbox("Select subject:", assigned_subjects)

                                        task_row = class_filtered_assignments[class_filtered_assignments["Subject"] == selected_subject]
                                        current_task_status = task_row["Status"].values[0]
                                        admin_feedback = task_row["Admin_Feedback"].values[0] if "Admin_Feedback" in task_row.columns else ""

                                        st.subheader(f"Workspace: {selected_class} for {selected_subject}")

                                        if pd.notna(admin_feedback) and str(admin_feedback).strip() != "":
                                            st.error(f"Rejection Feedback from Admin: {admin_feedback}")

                                        if current_task_status == "Submitted":
                                            st.warning("This task has already been submitted and is locked awaiting Admin Approval.")
                                        elif not allow_grade_entry:
                                            st.warning("Grade entry is currently closed by administration for this term period.")
                                        else:
                                            st.info("Edit your grades below. Leave a score empty to record the student as Absent.")

                                        st.markdown("#### Operational Checklist")
                                        col1, col2 = st.columns(2)
                                        with col1:
                                            lesson_notes = st.checkbox("Submitted lesson notes for the session", value=False, disabled=(current_task_status == "Submitted"))
                                        with col2:
                                            diary_filled = st.checkbox("Filled diary for the session", value=False, disabled=(current_task_status == "Submitted"))

                                        st.markdown("#### Score Entry Sheet")

                                        class_students = master_registry[master_registry["Class"] == selected_class]

                                        if not class_students.empty:
                                            student_count = len(class_students)
                                            st.metric(label="Total Number of Students for this class", value=student_count)

                                            name_col = "Student_Name" if "Student_Name" in class_students.columns else ("STUDENT NAME" if "STUDENT NAME" in class_students.columns else class_students.columns[1] if len(class_students.columns) > 1 else "Student_Name")

                                            workspace_key = f"grades_state_{selected_class}_{selected_subject}_{current_term}"

                                            if workspace_key not in st.session_state:
                                                records_sub = grade_records[
                                                    (grade_records["Subject"] == selected_subject) &
                                                    (grade_records["Term"] == current_term)
                                                ]

                                                entry_rows = []
                                                for _, student in class_students.iterrows():
                                                    s_id = student["Student_ID"]
                                                    s_name = student[name_col]

                                                    match = records_sub[records_sub["Student_ID"] == s_id]
                                                    if not match.empty:
                                                        ca1_val = match["CA1"].iloc[0] if "CA1" in match.columns else match["1CA"].iloc[0] if "1CA" in match.columns else None
                                                        ca2_val = match["CA2"].iloc[0] if "CA2" in match.columns else match["2CA"].iloc[0] if "2CA" in match.columns else None
                                                        exam_val = match["Exam"].iloc[0] if "Exam" in match.columns else None
                                                    else:
                                                        ca1_val, ca2_val, exam_val = None, None, None

                                                    entry_rows.append({
                                                        "Student_ID": s_id,
                                                        "Student_Name": s_name,
                                                        "1CA": ca1_val if pd.notna(ca1_val) and ca1_val != "" else None,
                                                        "2CA": ca2_val if pd.notna(ca2_val) and ca2_val != "" else None,
                                                        "Exam": exam_val if pd.notna(exam_val) and exam_val != "" else None
                                                    })
                                                st.session_state[workspace_key] = pd.DataFrame(entry_rows)

                                            is_disabled = True if (current_task_status == "Submitted" or not allow_grade_entry) else False

                                            # Form block isolates the spreadsheet component to prevent background chatter and keyboard drops on mobile screens
                                            with st.form(key=f"form_block_{workspace_key}"):
                                                
                                                edited_grades_df = st.data_editor(
                                                    st.session_state[workspace_key],
                                                    hide_index=True,
                                                    use_container_width=True,
                                                    disabled=is_disabled,
                                                    key=f"editor_widget_{workspace_key}",
                                                    column_config={
                                                        "Student_ID": st.column_config.TextColumn("Student ID", disabled=True),
                                                        "Student_Name": st.column_config.TextColumn("Student Name", disabled=True),
                                                        "1CA": st.column_config.NumberColumn(f"1CA (Max {max_ca1})", min_value=0.0, max_value=max_ca1, format="%.1f"),
                                                        "2CA": st.column_config.NumberColumn(f"2CA (Max {max_ca2})", min_value=0.0, max_value=max_ca2, format="%.1f"),
                                                        "Exam": st.column_config.NumberColumn(f"Exam (Max {max_exam})", min_value=0.0, max_value=max_exam, format="%.1f")
                                                    }
                                                )

                                                st.session_state[workspace_key] = edited_grades_df

                                                save_draft_action = False
                                                submit_final_action = False
                                                
                                                # Form submission elements instead of traditional unlinked buttons
                                                if not is_disabled:
                                                    col_btn1, col_btn2 = st.columns(2)
                                                    with col_btn1:
                                                        save_draft_action = st.form_submit_button("Save Local Draft Progress")
                                                    with col_btn2:
                                                        submit_final_action = st.form_submit_button("Submit Task Grades for Review")

                                            st.markdown("### Subject Performance Insights (View Only)")

                                            calc_df = edited_grades_df.copy()
                                            calc_df["1CA"] = pd.to_numeric(calc_df["1CA"])
                                            calc_df["2CA"] = pd.to_numeric(calc_df["2CA"])
                                            calc_df["Exam"] = pd.to_numeric(calc_df["Exam"])
                                            calc_df["Total"] = calc_df["1CA"].fillna(0) + calc_df["2CA"].fillna(0) + calc_df["Exam"].fillna(0)

                                            has_scores = calc_df[["1CA", "2CA", "Exam"]].notna().any().any()

                                            if has_scores:
                                                avg_score = calc_df["Total"].mean()
                                                min_score = calc_df["Total"].min()
                                                max_score = calc_df["Total"].max()

                                                col_a, col_b, col_c = st.columns(3)
                                                col_a.metric(label="Average Subject Score", value=f"{avg_score:.2f}")
                                                col_b.metric(label="Lowest Score", value=f"{min_score:.2f}")
                                                col_c.metric(label="Highest Score", value=f"{max_score:.2f}")

                                                needing_help = calc_df[calc_df["Total"] < min_passing_score]
                                                st.markdown("#### Students Needing Intervention")
                                                if not needing_help.empty:
                                                    for idx, row in needing_help.iterrows():
                                                        st.write(f"• {row['Student_Name']} (Current Total: {row['Total']:.1f} marks)")
                                                else:
                                                    st.success("Great news, No student profiles are currently below the target passing standard for this sheet.")
                                            else:
                                                st.caption("Awaiting entries. Class analytics will compute automatically once scores are added.")

                                            # Process operations externally after a form submission event occurs
                                            transmission_df = edited_grades_df.copy()
                                            transmission_df["Subject"] = selected_subject
                                            transmission_df["Term"] = current_term
                                            transmission_df["Term_Total"] = transmission_df["1CA"].fillna(0) + transmission_df["2CA"].fillna(0) + transmission_df["Exam"].fillna(0)

                                            if save_draft_action:
                                                with st.spinner("Synchronizing draft with cloud spreadsheet..."):
                                                    log_text = f"Teacher {teacher_name} saved draft records for class {selected_class} subject {selected_subject}"
                                                    success, message = write_back_to_sheets(
                                                        dataframe=transmission_df,
                                                        sheet_name="grade_records",
                                                        action_type="upsert_rows",
                                                        extra_metadata={"Teacher_ID": teacher_id_string, "Class": selected_class, "Subject": selected_subject, "Term": current_term},
                                                        log_message=log_text
                                                    )
                                                    if success:
                                                        st.success("Draft logs synchronized with Google Sheets successfully!")
                                                        st.cache_data.clear()
                                                    else:
                                                        st.error(f"Cloud update failed: {message}")

                                            if submit_final_action:
                                                with st.spinner("Submitting finalized scores to administration registry..."):
                                                    log_text = f"Teacher {teacher_name} submitted final records for class {selected_class} subject {selected_subject}"
                                                    success, message = write_back_to_sheets(
                                                        dataframe=transmission_df,
                                                        sheet_name="grade_records",
                                                        action_type="upsert_rows",
                                                        extra_metadata={"Teacher_ID": teacher_id_string, "Class": selected_class, "Subject": selected_subject, "Term": current_term},
                                                        log_message=log_text
                                                    )
                                                    if success:
                                                        st.success("Task marks locked and submitted for administrative audit!")
                                                        st.cache_data.clear()
                                                        st.rerun()
                                                    else:
                                                        st.error(f"Submission failed: {message}")
                                                            if success:
                                                                st.success("Task marks locked and submitted for administrative audit!")
                                                                st.cache_data.clear()
                                                                st.rerun()
                                                            else:
                                                                st.error(f"Submission failed: {message}")
                                        else:
                                            st.warning(f"No active student list populated under class registry for {selected_class}.")
                                    else:
                                        st.success("All your assigned educational grading tasks have been completed and approved!")

                                with tab_submitted:
                                    review_assignments = my_assignments[my_assignments["Status"] == "Submitted"]
                                    if not review_assignments.empty:
                                        st.write("The following grading sheets have been sent to the admin and are awaiting final approval:")
                                        st.dataframe(review_assignments[["Class", "Subject", "Status"]], hide_index=True, use_container_width=True)
                                    else:
                                        st.write("You have no tasks currently pending review. Everything submitted has been processed!")

                    else:
                        st.error("Invalid verification PIN. Access denied.")
                else:
                    st.error(f"The column '{target_column}' does not match your sheet.")
        else:
            st.info("Please enter your assigned staff verification code to unlock your dashboard.")

    elif user_role == "Student Results View":
        st.title("Student Term Performance Portal")
        st.info(f"Active View: {current_year} and {current_term}")
        
        st.write("Student results portal loading...")
