import requests
import pandas as pd
import streamlit as st
import json
import zipfile
import io
from fpdf import FPDF
from io import BytesIO
from PIL import Image

st.set_page_config(page_title="Livelystone Educational Hub", layout="wide")

@st.cache_data

def load_local_logo(image_path, opacity=0.1):
    try:
        orig_img = Image.open(image_path).convert("RGBA")
        
        watermark_img = orig_img.copy()
        alpha = watermark_img.split()[3]
        alpha = alpha.point(lambda p: p * opacity)
        watermark_img.putalpha(alpha)
        
        solid_img = Image.new("RGB", orig_img.size, (255, 255, 255))
        solid_img.paste(orig_img, mask=orig_img.split()[3])

        solid_path = "solid_logo_temp.png"
        watermark_path = "watermark_temp.png"

        solid_img.save(solid_path)
        watermark_img.save(watermark_path)
        
        return solid_path, watermark_path
    except Exception as e:
        return None, None

solid_logo, faint_logo = load_local_logo("No limit Logo.jpeg", opacity=0.1)

API_URL = "https://script.google.com/macros/s/AKfycbw4pSvjpnf4tcnusDauL39SujQpFpvGOTRuszPVZT40DuJ9ADj-xGRu8bjiCSgHoUf9/exec"

@st.cache_data(ttl=300)
def load_entire_database(url):
    try:
        response = requests.get(url, timeout=45)
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

def generate_pdf_report(
    student_name, class_room, student_code, gender_group,
    days_present, days_absent, session, school_opened,
    term_period, total_classmates,
    student_term_avg, class_term_avg, class_term_pos,
    student_session_avg, class_session_avg, class_session_pos,
    total_offered, total_passed, total_failed,
    scores_df, teacher_comment="", principal_comment="", class_teacher_name=""
):
    pdf = FPDF()
    pdf.add_page()

    page_width = 210
    page_height = 297
    
    if faint_logo is not None:
        watermark_size = 100 
        x_center = (page_width - watermark_size) / 2
        y_center = (page_height - watermark_size) / 2
        pdf.image(faint_logo, x=x_center, y=y_center, w=watermark_size)
    
    if solid_logo is not None:
        logo_size = 20
        y_header_position = 10
        
        pdf.image(solid_logo, x=15, y=y_header_position, w=logo_size, h=logo_size)
        pdf.image(solid_logo, x=page_width - 15 - logo_size, y=y_header_position, w=logo_size, h=logo_size)
    
    pdf.set_text_color(255, 0, 0)
    pdf.set_font("Arial", "B", 16)
    pdf.cell(200, 8, txt="NO LIMITS SECONDARY SCHOOL", ln=True, align="C")
    
    pdf.set_text_color(0, 0, 255)
    pdf.set_font("Arial", "BI", 9)
    pdf.cell(200, 5, txt="64, Canal View Drive, Greenfield Estate, Off Amuwo-Odofin, Ago Palace Way, Lagos.", ln=True, align="C")
    
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", "B", 9)
    pdf.cell(200, 8, txt="END OF THE TERM ASSESSMENT REPORT", ln=True, align="C")
    pdf.ln(1)

    section = "JUNIOR SECONDARY SCHOOL SECTION" if "JSS" in str(class_room).upper() else "SENIOR SECONDARY SCHOOL SECTION"
    pdf.set_font("Arial", "", 10)
    pdf.cell(0, 8, txt=section, ln=True, align="C")
    pdf.ln(4)    

    #Section Separator line - Black
    pdf.set_draw_color(0, 0, 0)
    pdf.set_line_width(0.5)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(1)

    #Section Separator line - Blue
    pdf.set_draw_color(0, 0, 255)
    pdf.set_line_width(0.2)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    # Rest color to black
    pdf.set_draw_color(0, 0, 0)
    pdf.ln(2)

    # 2. Student Demographics (3-Column Layout, Font Size 8)
    pdf.set_font("Arial", "", 8)
    col_w = 63

    pdf.set_font("Arial", "B", 10)
    pdf.cell(col_w, 5, txt=f"{student_name}", ln=0)

    # Reset Font
    pdf.set_font("Arial", "", 8)
    pdf.cell(col_w, 5, txt=f"Class Room: {class_room}", ln=0)
    pdf.cell(col_w, 5, txt=f"Student Code: {student_code}", ln=1)

    pdf.cell(col_w, 5, txt=f"Gender Group: {gender_group}", ln=0)
    pdf.cell(col_w, 5, txt=f"Term Period: {term_period}", ln=0)
    pdf.cell(col_w, 5, txt=f"Session: {session}", ln=1)

    pdf.cell(col_w, 5, txt=f"Days Present: {days_present}", ln=0)
    pdf.cell(col_w, 5, txt=f"Days Absent: {days_absent}", ln=0)
    pdf.cell(col_w, 5, txt=f"School Opened: {school_opened}", ln=1)

    pdf.cell(col_w, 5, txt=f"Total Classmates: {total_classmates}", ln=1)
    pdf.ln(2)

    # 3. Term and Session Summaries (Font Size 8)
    pdf.cell(col_w, 5, txt=f"Student Term Average: {student_term_avg:.2f}", ln=0)
    pdf.cell(col_w, 5, txt=f"Class Average for Term: {class_term_avg:.2f}", ln=0)
    pdf.cell(col_w, 5, txt=f"Class Position for Term: {class_term_pos}", ln=1)

    pdf.cell(col_w, 5, txt=f"Student Session Average: {student_session_avg:.2f}", ln=0)
    pdf.cell(col_w, 5, txt=f"Class Average for Session: {class_session_avg:.2f}", ln=0)
    pdf.cell(col_w, 5, txt=f"Class Position for Session: {class_session_pos}", ln=1)
    pdf.ln(3)

    # 4. Cognitive Domain Scores Header & Table (Font Size 8)
    pdf.set_font("Arial", "B", 9)
    pdf.cell(190, 6, txt="Cognitive Domain Scores", border=1, ln=True, align="C")
    pdf.set_font("Arial","",8)
    
    row_height = 5
    has_session_avg = "Session Average" in scores_df.columns

    if has_session_avg:
        pdf.cell(34, row_height, "Subject", border=1)
        pdf.cell(13, row_height, "1st Term", border=1, align="C")
        pdf.cell(13, row_height, "2nd Term", border=1, align="C")
        pdf.cell(11, row_height, "1st CA", border=1, align="C")
        pdf.cell(11, row_height, "2nd CA", border=1, align="C")
        pdf.cell(11, row_height, "Exam", border=1, align="C")
        pdf.cell(11, row_height, "Total", border=1, align="C")
        pdf.cell(18, row_height, "Session Avg", border=1, align="C")
        pdf.cell(10, row_height, "Grade", border=1, align="C")
        pdf.cell(14, row_height, "Rank", border=1, align="C")
        pdf.cell(44, row_height, "Remark", border=1, align="C")
    else:
        pdf.cell(36, row_height, "Subject", border=1)
        pdf.cell(14, row_height, "1st Term", border=1, align="C")
        pdf.cell(14, row_height, "2nd Term", border=1, align="C")
        pdf.cell(12, row_height, "1st CA", border=1, align="C")
        pdf.cell(12, row_height, "2nd CA", border=1, align="C")
        pdf.cell(12, row_height, "Exam", border=1, align="C")
        pdf.cell(12, row_height, "Total", border=1, align="C")
        pdf.cell(12, row_height, "Grade", border=1, align="C")
        pdf.cell(16, row_height, "Rank", border=1, align="C")
        pdf.cell(50, row_height, "Remark", border=1, align="C")
    pdf.ln()

    def format_whole_score(val):
        try:
            if pd.isna(val) or str(val).lower() == "nan" or str(val).strip() == "":
                return ""
            return str(int(round(float(val))))
        except (ValueError, TypeError):
            return str(val)

    for idx, row in scores_df.iterrows():
        subj = str(row.get("Subject", ""))
        if subj == "Information Communication and Technology":
            subj = "ICT"
        term1 = format_whole_score(row.get("1st Term", "")) 
        term2 = format_whole_score(row.get("2nd Term", ""))
        ca1 = format_whole_score(row.get("1st CA (20)", row.get("CA1", "")))
        ca2 = format_whole_score(row.get("2nd CA (20)", row.get("CA2", "")))
        exam = format_whole_score(row.get("Exam (60)", row.get("Exam", "")))
        total = format_whole_score(row.get("Total (100)", row.get("Term_Total", "")))
        grade = str(row.get("Grade", ""))
        rank = str(row.get("Subject Rank", ""))
        remark = str(row.get("Comment", ""))

        # Save X and Y position before drawing Subject
        x_start = pdf.get_x()
        y_start = pdf.get_y()

        if has_session_avg:
            # Multi_cell handles wrapping
            pdf.multi_cell(34, row_height, subj, border=1)
            row_end_y = pdf.get_y()

            #Return cursor to right of Subject cell
            pdf.set_xy(x_start + 34, y_start)
            s_avg = format_whole_score(row.get("Session Average", ""))
           
            # Draw the rest of the cells
            pdf.cell(13, row_height, term1, border=1, align="C")
            pdf.cell(13, row_height, term2, border=1, align="C")
            pdf.cell(11, row_height, ca1, border=1, align="C")
            pdf.cell(11, row_height, ca2, border=1, align="C")
            pdf.cell(11, row_height, exam, border=1, align="C")
            pdf.cell(11, row_height, total, border=1, align="C")
            pdf.cell(18, row_height, s_avg, border=1, align="C")
            pdf.cell(10, row_height, grade, border=1, align="C")
            pdf.cell(14, row_height, rank, border=1, align="C")
            pdf.cell(44, row_height, remark[:28], border=1, align="C")
            # Move cursor to the row_end_y for the next iteration
            pdf.set_y(row_end_y)
        else:
            pdf.multi_cell(36, row_height, subj, border=1)
            row_end_y = pdf.get_y()
            pdf.set_xy(x_start + 36, y_start)
            
            pdf.cell(36, row_height, subj[:20], border=1)
            pdf.cell(14, row_height, term1, border=1, align="C")
            pdf.cell(14, row_height, term2, border=1, align="C")
            pdf.cell(12, row_height, ca1, border=1, align="C")
            pdf.cell(12, row_height, ca2, border=1, align="C")
            pdf.cell(12, row_height, exam, border=1, align="C")
            pdf.cell(12, row_height, total, border=1, align="C")
            pdf.cell(12, row_height, grade, border=1, align="C")
            pdf.cell(16, row_height, rank, border=1, align="C")
            pdf.cell(50, row_height, remark[:28], border=1, align="C")
            pdf.set_y(row_end_y)
        
    pdf.ln(3)

    # 5. Scores Summary (Font Size 8)
    pdf.cell(63, 5, txt=f"Total Subjects Offered: {total_offered}", ln=0)
    pdf.cell(63, 5, txt=f"Total Subjects Passed: {total_passed}", ln=0)
    pdf.cell(64, 5, txt=f"Total Subjects Failed: {total_failed}", ln=1)
    pdf.ln(3)

    # 6. Legends / Keys Summary (Font Size 8)
    pdf.cell(190, 5, txt="Grading Legend & Keys Summary", border=0, ln=True, align="L")
    
    key_w = 31.6
    pdf.cell(key_w, 5, "A: 80-100 (Excellent)", border=1, align="C")
    pdf.cell(key_w, 5, "B: 70-79 (Very Good)", border=1, align="C")
    pdf.cell(key_w, 5, "C: 60-69 (Fair)", border=1, align="C")
    pdf.cell(key_w, 5, "D: 50-59 (Marginal)", border=1, align="C")
    pdf.cell(key_w, 5, "E: 40-49 (Pass)", border=1, align="C")
    pdf.cell(key_w, 5, "F: 0-39 (Fail)", border=1, align="C")
    pdf.ln(8)

     #Section Separator line - Black
    pdf.set_draw_color(0, 0, 0)
    pdf.set_line_width(0.5)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(1)

    #Section Separator line - Blue
    pdf.set_line_width(0.2)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(5)

    # 7. Comments and Signatories (Font Size 8)
    pdf.set_font("Arial", "", 8)
    
    left_width = 125   
    gap = 6            
    right_x = pdf.l_margin + left_width + gap  
    right_width = 190 - (left_width + gap)     
    
    # Determine active average for principal comment (Session Avg for Third Term, Term Avg otherwise)
    active_avg = student_session_avg if term_period == "Third Term" else student_term_avg
    principal_comment, promotion_status = get_principal_comment(active_avg, student_name, term_period)
    
    # --- Row 1: Class Teacher ---
    y_start = pdf.get_y()
    
    pdf.set_font("Arial", "", 8)
    pdf.multi_cell(left_width, 4, f"Class Teacher Comment:\n{teacher_comment}", border=0)
    y_teacher_end = pdf.get_y()
    
    pdf.set_xy(right_x, y_start)
    pdf.set_font("Arial", "B", 8)
    pdf.cell(right_width, 4, f"Signed: {class_teacher_name}", ln=1, align="R")
    
    pdf.set_x(right_x)
    pdf.set_font("Arial", "I", 8)
    pdf.cell(right_width, 4, "(Class Teacher)", ln=1, align="R")
    y_sig1_end = pdf.get_y()
    
    pdf.set_y(max(y_teacher_end, y_sig1_end) + 4)
    
    # --- Row 2: Principal ---
    y_start = pdf.get_y()
    
    pdf.set_font("Arial", "", 8)
    pdf.multi_cell(left_width, 4, f"Principal Remarks:\n{principal_comment}", border=0)
    
    # Print promotion status in bold on the next line if it's the Third Term
    if promotion_status:
        pdf.set_font("Arial", "B", 8)
        pdf.multi_cell(left_width, 4, promotion_status, border=0)
        pdf.set_font("Arial", "", 8)
    
    y_principal_end = pdf.get_y()
    
    pdf.set_xy(right_x, y_start)
    pdf.set_font("Arial", "B", 8)
    pdf.cell(right_width, 4, "Signed: Mrs Joy Paul", ln=1, align="R")
    
    pdf.set_x(right_x)
    pdf.set_font("Arial", "I", 8)
    pdf.cell(right_width, 4, "(Principal)", ln=1, align="R")
    y_sig2_end = pdf.get_y()
    
    pdf.set_y(max(y_principal_end, y_sig2_end) + 4)

    # Place at the very bottom of the page   
    pdf.set_auto_page_break(auto=False)
    pdf.set_y(-12)
    pdf.set_font("Arial", "I", 7)
    pdf.cell(0, 5, txt="...NO LIMITS SECONDARY SCHOOLS, LAGOS NIGERIA...", align="C")
    pdf.set_auto_page_break(auto=True, margin=15)

    pdf_out = pdf.output(dest="S")
    return pdf_out.encode("latin-1") if isinstance(pdf_out, str) else bytes(pdf_out)
    
def get_principal_comment(average, student_name, term_period=""):
    # Base comment logic
    if average >= 90:
        comment = f"{student_name} has demonstrated outstanding academic excellence and a commendable work ethic this term."
    elif average >= 80:
        comment = f"{student_name} has shown a strong grasp of the curriculum and consistent dedication to their studies."
    elif average >= 70:
        comment = f"{student_name} has achieved a solid performance, demonstrating steady progress and a good understanding of the material."
    elif average >= 60:
        comment = f"{student_name} has delivered a satisfactory performance, though greater consistency will help unlock their true potential."
    elif average >= 50:
        comment = f"{student_name} has met the basic requirements, but developing a more regular study routine is recommended."
    elif average >= 40:
        comment = f"{student_name} is finding some core concepts challenging and needs to focus on mastering the basics next term."
    elif average >= 30:
        comment = f"{student_name}’s results are of concern, and a structured revision plan is urgently needed to address gaps in learning."
    else:
        comment = f"Immediate intervention and close collaboration are required to help {student_name} rebuild their academic foundation."

    # Determine status if it's the third term
    status = None
    if term_period == "Third Term":
        if average >= 50:
            status = "Status: Promoted to the Next Class"
        elif average >= 30:
            status = "Status: Promoted Conditionally"
        else:
            status = "Status: Advised to Meet the Principal for Placement"

    return comment, status

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
        ["Admin Dashboard", "Teacher Portal", "Term Summaries", "Student Results View"]
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
                                        if c_choice.startswith("JSS"):
                                            group_filter = master_registry["Class"].astype(str).str.startswith("JSS")
                                        elif "SCIENCE" in c_choice.upper():
                                            group_filter = master_registry["Class"].astype(str).str.upper().str.contains("SCIENCE")
                                        elif "ARTS & COMMERCIAL" in c_choice.upper():
                                            group_filter = master_registry["Class"].astype(str).str.upper().str.contains("ARTS & COMMERCIAL")
                                        else:
                                            group_filter = pd.Series([True] * len(master_registry))
                                    
                                        #identify student IDs to link classes
                                        id_col = "Student_ID" if "Student_ID" in master_registry.columns else "STUDENT NAME"
                                        relevant_student_ids = master_registry[group_filter][id_col].unique()
                                        # Extract unique subjects
                                        grade_id_col = "Student_ID" if "Student_ID" in grade_records.columns else "STUDENT NAME"
                                        filtered_subjects = grade_records[grade_records[grade_id_col].isin(relevant_student_ids)]["Subject"].dropna().unique().tolist()
                                        # Fallback to all subjects if filtered list is empty
                                        if not filtered_subjects:
                                            filtered_subjects = grade_records["Subject"].dropna().unique().tolist()
                                    
                                        # Dropdown selection instead of manual input
                                        s_choice = st.selectbox("Select Subject Name:", sorted(filtered_subjects))
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
                                        current_term_grades["Term_Total"] = pd.to_numeric(current_term_grades["Term_Total"], errors="coerce")
                                        
                                        # Strict filter to omit rows without marks or with explicit zero totals
                                        current_term_grades = current_term_grades[current_term_grades["Term_Total"].notna() & (current_term_grades["Term_Total"] > 0)]
                                        
                                        if not current_term_grades.empty:
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
                                            st.info(f"No active grade entries found for the currently active term: {current_term}")
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
                                        # Map assignments into unique strings to accurately locate the matching row index
                                        pending_options = pending_sheets.apply(lambda r: f"{r['Class']} - {r['Subject']} (Teacher ID: {r['Teacher_ID']})", axis=1).tolist()
                                        selected_option = st.selectbox("Select a submitted sheet row to audit:", pending_options)
                                        
                                        selected_idx = pending_options.index(selected_option)
                                        selected_row = pending_sheets.iloc[selected_idx]

                                        selected_class = selected_row["Class"]
                                        selected_subject = selected_row["Subject"]
                                        selected_teacher_id = selected_row["Teacher_ID"]

                                        st.info(f"Auditing Sheet Data: {selected_class} - {selected_subject}")
                                        
                                        st.markdown("### Submitted Grades Preview")
                                        if grade_records is not None and master_registry is not None:
                                            class_students = master_registry[master_registry["Class"] == selected_class]
                                            sub_grades = grade_records[
                                                (grade_records["Subject"] == selected_subject) & 
                                                (grade_records["Term"] == current_term)
                                            ]
                                            
                                            if not class_students.empty:
                                                name_col = "Student_Name" if "Student_Name" in class_students.columns else ("STUDENT NAME" if "STUDENT NAME" in class_students.columns else class_students.columns[1] if len(class_students.columns) > 1 else "Student_Name")
                                                
                                                preview_rows = []
                                                for _, student in class_students.iterrows():
                                                    s_id = student["Student_ID"]
                                                    s_name = student[name_col]
                                                    
                                                    match = sub_grades[sub_grades["Student_ID"] == s_id]
                                                    if not match.empty:
                                                        ca1_val = match["CA1"].iloc[0] if "CA1" in match.columns else match["1CA"].iloc[0] if "1CA" in match.columns else None
                                                        ca2_val = match["CA2"].iloc[0] if "CA2" in match.columns else match["2CA"].iloc[0] if "2CA" in match.columns else None
                                                        exam_val = match["Exam"].iloc[0] if "Exam" in match.columns else None
                                                        total_val = match["Term_Total"].iloc[0] if "Term_Total" in match.columns else None
                                                    else:
                                                        ca1_val, ca2_val, exam_val, total_val = None, None, None, None
                                                        
                                                    preview_rows.append({
                                                        "Student ID": s_id,
                                                        "Student Name": s_name,
                                                        "1CA": ca1_val,
                                                        "2CA": ca2_val,
                                                        "Exam": exam_val,
                                                        "Total Score": total_val
                                                    })
                                                
                                                preview_df = pd.DataFrame(preview_rows)
                                                st.dataframe(preview_df, hide_index=True, use_container_width=True)
                                            else:
                                                st.warning("No students found registered under this class roster arm.")
                                        else:
                                            st.warning("Grade data records or Master Registry tables are unavailable for evaluation.")

                                        rejection_reason = st.text_area("If rejecting this sheet, you must type a reason explanation note below:", key="admin_reject_note")

                                        btn_app, btn_rej = st.columns(2)
                                        with btn_app:
                                            if st.button("Approve and Lock Score Sheet"):
                                                log_text = f"Admin {admin_name} approved scores for class {selected_class} subject {selected_subject}"
                                                
                                                approval_df = pd.DataFrame([{
                                                    "Teacher_ID": str(selected_teacher_id),
                                                    "Class": str(selected_class),
                                                    "Subject": str(selected_subject),
                                                    "Status": "Approved",
                                                    "Admin_Feedback": ""
                                                }])
                                                
                                                success, message = write_back_to_sheets(
                                                    dataframe=approval_df,
                                                    sheet_name="teacher_assignments",
                                                    action_type="approve_assignment_sheet",
                                                    extra_metadata={
                                                        "Teacher_ID": str(selected_teacher_id),
                                                        "Class": str(selected_class),
                                                        "Subject": str(selected_subject)
                                                    },
                                                    log_message=log_text
                                                )
                                                if success:
                                                    st.success("Sheet verified. Grades committed to permanent records.")
                                                    st.cache_data.clear()
                                                    st.rerun()
                                                else:
                                                    st.error(f"Approval update failed: {message}")
                                                    
                                        with btn_rej:
                                            if st.button("Reject and Send Back to Teacher Workspace"):
                                                if not rejection_reason.strip():
                                                    st.error("Action Blocked: You must write an explanation note in the text field above before executing a rejection.")
                                                else:
                                                    log_text = f"Admin {admin_name} rejected scores for class {selected_class} subject {selected_subject}"
                                                    
                                                    rejection_df = pd.DataFrame([{
                                                        "Teacher_ID": str(selected_teacher_id),
                                                        "Class": str(selected_class),
                                                        "Subject": str(selected_subject),
                                                        "Status": "Rejected",
                                                        "Admin_Feedback": rejection_reason
                                                    }])
                                                    
                                                    success, message = write_back_to_sheets(
                                                        dataframe=rejection_df,
                                                        sheet_name="teacher_assignments",
                                                        action_type="reject_assignment_sheet",
                                                        extra_metadata={
                                                            "Teacher_ID": str(selected_teacher_id),
                                                            "Class": str(selected_class),
                                                            "Subject": str(selected_subject),
                                                            "Feedback": rejection_reason
                                                        },
                                                        log_message=log_text
                                                    )
                                                    if success:
                                                        st.warning(f"Sheet returned to teacher workspace with note: '{rejection_reason}'")
                                                        st.cache_data.clear()
                                                        st.rerun()
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
                                                term_data = grade_records[grade_records["Term"] == current_term].copy()
                                                term_data["Term_Total"] = pd.to_numeric(term_data["Term_Total"], errors="coerce")
                                                term_data = term_data[(term_data["Term_Total"] > 0) & (term_data["Term_Total"].notna())]
                                                
                                                is_third_term = "3" in str(current_term) or "third" in str(current_term).lower()
                                                
                                                session_data = pd.DataFrame()
                                                if is_third_term:
                                                    session_data = grade_records.copy()
                                                    session_data["Term_Total"] = pd.to_numeric(session_data["Term_Total"], errors="coerce")
                                                    session_data = session_data[(session_data["Term_Total"] > 0) & (session_data["Term_Total"].notna())]
                                                
                                                for _, student in target_students.iterrows():
                                                    s_id = str(student.get("Student_ID"))
                                                    s_name = student.get(display_name, "Unknown Student")
                                                    s_class = student.get("Class", "Unknown Class")
                                                    s_gender = student.get("Gender", "N/A")
                                                    
                                                    classmate_ids = master_registry[master_registry["Class"] == s_class]["Student_ID"].unique()
                                                    class_grades = term_data[term_data["Student_ID"].isin(classmate_ids)].copy()
                                                    
                                                    student_averages = class_grades.groupby("Student_ID")["Term_Total"].mean().reset_index()
                                                    student_averages.columns = ["Student_ID", "Student_Average"]
                                                    student_averages["Rank"] = student_averages["Student_Average"].rank(ascending=False, method="min")
                                                    
                                                    class_avg = student_averages["Student_Average"].mean() if not student_averages.empty else 0.000
                                                    total_class_size = len(classmate_ids)
                                                    
                                                    target_summary = student_averages[student_averages["Student_ID"] == s_id]
                                                    
                                                    def to_ordinal(num):
                                                        if pd.isna(num): return "N/A"
                                                        val = int(num)
                                                        if 11 <= (val % 100) <= 13: return f"{val}th"
                                                        return f"{val}" + {1: "st", 2: "nd", 3: "rd"}.get(val % 10, "th")

                                                    if not target_summary.empty:
                                                        student_avg = target_summary["Student_Average"].values[0]
                                                        student_rank_num = int(target_summary["Rank"].values[0])
                                                        student_position = to_ordinal(student_rank_num)
                                                    else:
                                                        student_avg = 0.000
                                                        student_position = "N/A"
                                                        
                                                    student_session_avg = 0.000
                                                    class_session_avg = 0.000
                                                    class_session_pos = "N/A"
                                                    class_session_grades = pd.DataFrame()
                                                    
                                                    if is_third_term:
                                                        class_session_grades = session_data[session_data["Student_ID"].isin(classmate_ids)].copy()
                                                        classmates_session_summaries = class_session_grades.groupby("Student_ID")["Term_Total"].mean().reset_index()
                                                        classmates_session_summaries.columns = ["Student_ID", "Classmate_Session_Avg"]
                                                        classmates_session_summaries["Session_Rank"] = classmates_session_summaries["Classmate_Session_Avg"].rank(ascending=False, method="min")
                                                        class_session_avg = classmates_session_summaries["Classmate_Session_Avg"].mean() if not classmates_session_summaries.empty else 0.000
                                                        
                                                        target_sess_rank_match = classmates_session_summaries[classmates_session_summaries["Student_ID"] == s_id]
                                                        if not target_sess_rank_match.empty:
                                                            student_session_avg = target_sess_rank_match["Classmate_Session_Avg"].values[0]
                                                            class_session_pos = to_ordinal(int(target_sess_rank_match["Session_Rank"].values[0]))
                                                    
                                                    class_grades["Subject_Rank_Val"] = class_grades.groupby("Subject")["Term_Total"].rank(ascending=False, method="min")
                                                    class_grades["Subject_Rank"] = class_grades["Subject_Rank_Val"].apply(lambda r: to_ordinal(r) if pd.notna(r) else "N/A")
                                                    student_subject_records = class_grades[class_grades["Student_ID"] == s_id].copy()
                                                    
                                                    attendance_opened = "N/A"
                                                    attendance_present = "N/A"
                                                    attendance_absent = "N/A"
                                                    teacher_comment = ""
                                                    principal_comment = ""
                                                    
                                                    if term_summaries is not None and not term_summaries.empty:
                                                        matched_summary = term_summaries[(term_summaries["Term"] == current_term) & (term_summaries["Student_ID"].astype(str) == s_id)]
                                                        if not matched_summary.empty:
                                                            s_row = matched_summary.iloc[0]
                                                            attendance_opened = s_row.get("Attendance_Opened", "N/A")
                                                            attendance_present = s_row.get("Attendance_Present", "N/A")
                                                            attendance_absent = s_row.get("Attendance_Absent", "N/A")
                                                            teacher_comment = s_row.get("Teacher_Comment", "")
                                                            principal_comment = s_row.get("Principal_Comment", "")
                                                    
                                                    form_teacher_name = "N/A"
                                                    if class_teacher_mapping is not None and not class_teacher_mapping.empty and teacher_registry is not None:
                                                        mapping = class_teacher_mapping[class_teacher_mapping["Class"] == s_class]
                                                        if not mapping.empty:
                                                            t_id = mapping.iloc[0]["Teacher_ID"]
                                                            t_record = teacher_registry[teacher_registry["Teacher_ID"].astype(str) == str(t_id)]
                                                            if not t_record.empty:
                                                                form_teacher_name = t_record.iloc[0].get("Teacher_Name", "N/A")
                                                                
                                                    def evaluate_score_grade(score):
                                                        if pd.isna(score): return "F", "Absent"
                                                        val = float(score)
                                                        if val >= 80.0: return "A", "Excellent"
                                                        elif val >= 70.0: return "B", "Very Good"
                                                        elif val >= 60.0: return "C", "Fair"
                                                        elif val >= 50.0: return "D", "Marginal"
                                                        elif val >= 40.0: return "E", "Pass"
                                                        else: return "F", "Fail"
                                                        
                                                    total_passed = 0
                                                    total_failed = 0
                                                    cognitive_rows = []
                                                    
                                                    term_1_totals = {}
                                                    term_2_totals = {}
                                                    if is_third_term:
                                                        student_all_grades = session_data[session_data["Student_ID"].astype(str) == s_id]
                                                        for _, g_row in student_all_grades.iterrows():
                                                            t_val = str(g_row.get("Term", "")).strip().lower()
                                                            score_val = g_row.get("Term_Total")
                                                            if "1st" in t_val or "first" in t_val: term_1_totals[g_row.get("Subject")] = score_val
                                                            elif "2nd" in t_val or "second" in t_val: term_2_totals[g_row.get("Subject")] = score_val
                                                            
                                                    for _, row in student_subject_records.iterrows():
                                                        subj = row["Subject"]
                                                        ca1 = row.get("CA1", row.get("1CA", None))
                                                        ca2 = row.get("CA2", row.get("2CA", None))
                                                        exam = row.get("Exam", None)
                                                        total_val = row.get("Term_Total", None)
                                                        
                                                        if pd.notna(total_val):
                                                            if total_val >= min_passing_score: total_passed += 1
                                                            else: total_failed += 1
                                                            
                                                        if is_third_term:
                                                            t1_total = term_1_totals.get(subj, float("nan"))
                                                            t2_total = term_2_totals.get(subj, float("nan"))
                                                            valid_terms = [v for v in [t1_total, t2_total, total_val] if pd.notna(v)]
                                                            session_avg_val = sum(valid_terms) / len(valid_terms) if valid_terms else float("nan")
                                                            
                                                            grade, comment = evaluate_score_grade(session_avg_val) if pd.notna(session_avg_val) else ("F", "Absent")
                                                            
                                                            subj_class_grades = class_session_grades[class_session_grades["Subject"] == subj].copy()
                                                            subj_student_avgs = subj_class_grades.groupby("Student_ID")["Term_Total"].mean().reset_index()
                                                            subj_student_avgs["Rank"] = subj_student_avgs["Term_Total"].rank(ascending=False, method="min")
                                                            subj_rank_row = subj_student_avgs[subj_student_avgs["Student_ID"] == s_id]
                                                            subject_rank_str = to_ordinal(int(subj_rank_row["Rank"].values[0])) if not subj_rank_row.empty else "N/A"
                                                            
                                                            cognitive_rows.append({
                                                                "Subject": subj,
                                                                "1st Term": t1_total,
                                                                "2nd Term": t2_total,
                                                                "1st CA (20)": ca1,
                                                                "2nd CA (20)": ca2,
                                                                "Exam (60)": exam,
                                                                "Total (100)": total_val,
                                                                "Session Average": session_avg_val,
                                                                "Grade": grade,
                                                                "Subject Rank": subject_rank_str,
                                                                "Comment": comment
                                                            })
                                                        else:
                                                            grade, comment = evaluate_score_grade(total_val) if pd.notna(total_val) else ("F", "Absent")
                                                            cognitive_rows.append({
                                                                "Subject": subj,
                                                                "1st CA (20)": ca1,
                                                                "2nd CA (20)": ca2,
                                                                "Exam (60)": exam,
                                                                "Total (100)": total_val,
                                                                "Grade": grade,
                                                                "Subject Rank": row.get("Subject_Rank", "N/A"),
                                                                "Comment": comment
                                                            })
                                                            
                                                    scores_df = pd.DataFrame(cognitive_rows)
                                                    total_offered = len(scores_df)
                                                    
                                                    try:
                                                        pdf_bytes = generate_pdf_report(
                                                            student_name=s_name,
                                                            class_room=s_class,
                                                            student_code=s_id,
                                                            gender_group=s_gender,
                                                            days_present=attendance_present,
                                                            days_absent=attendance_absent,
                                                            session=current_year,
                                                            school_opened=attendance_opened,
                                                            term_period=current_term,
                                                            total_classmates=total_class_size,
                                                            student_term_avg=student_avg,
                                                            class_term_avg=class_avg,
                                                            class_term_pos=student_position,
                                                            student_session_avg=student_session_avg,
                                                            class_session_avg=class_session_avg,
                                                            class_session_pos=class_session_pos,
                                                            total_offered=total_offered,
                                                            total_passed=total_passed,
                                                            total_failed=total_failed,
                                                            scores_df=scores_df,
                                                            teacher_comment=teacher_comment,
                                                            principal_comment=principal_comment,
                                                            class_teacher_name=form_teacher_name
                                                        )
                                                        safe_name = str(s_name).replace(" ", "_")
                                                        zip_file.writestr(f"{safe_name}_{s_class}_Report.pdf", pdf_bytes)
                                                    except Exception as e:
                                                        st.error(f"Failed to generate PDF for {s_name}: {str(e)}")
                                                        
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
                                if not my_assignments.empty:
                                    assigned_classes = my_assignments["Class"].unique()
                                    selected_class = st.selectbox("Select an assigned class to view or manage:", assigned_classes)

                                    class_filtered_assignments = my_assignments[my_assignments["Class"] == selected_class]
                                    
                                    assigned_subjects = class_filtered_assignments["Subject"].unique()
                                    selected_subject = st.selectbox("Select subject:", assigned_subjects)

                                    task_row = class_filtered_assignments[class_filtered_assignments["Subject"] == selected_subject]
                                    current_task_status = task_row["Status"].values[0]
                                    admin_feedback = task_row["Admin_Feedback"].values[0] if "Admin_Feedback" in task_row.columns else ""

                                    st.subheader(f"Workspace: {selected_class} for {selected_subject}")

                                    if pd.notna(admin_feedback) and str(admin_feedback).strip() != "":
                                        st.error(f"Rejection Feedback from Admin: {admin_feedback}")

                                    if current_task_status == "Submitted":
                                        st.warning("This task has been submitted and is locked awaiting feedback from admin.")
                                    elif current_task_status == "Approved":
                                        st.success("This sheet has been Approved and permanently locked by Administration.")
                                    elif not allow_grade_entry:
                                        st.warning("Grade entry is currently closed by administration for this term period.")
                                    else:
                                        st.info("Edit your grades below. Leave a score empty to record the student as Absent.")

                                    st.markdown("#### Operational Checklist")
                                    col1, col2 = st.columns(2)
                                    with col1:
                                        lesson_notes = st.checkbox("Submitted lesson notes for the session", value=False, disabled=(current_task_status in ["Submitted", "Approved"]))
                                    with col2:
                                        diary_filled = st.checkbox("Filled diary for the session", value=False, disabled=(current_task_status in ["Submitted", "Approved"]))

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

                                        is_disabled = True if (current_task_status in ["Submitted", "Approved"] or not allow_grade_entry) else False

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

                                            needing_help = calc_df[calc_df["Total"] < min_passing_score].sort_values(by="Total", ascending=True).head(3)
                                            st.markdown("#### Students Needing Intervention")
                                            if not needing_help.empty:
                                                for idx, row in needing_help.iterrows():
                                                    st.write(f"• {row['Student_Name']} (Current Total: {row['Total']:.1f} marks)")
                                            else:
                                                st.success("Great news, No student profiles are currently below the target passing standard for this sheet.")
                                        else:
                                            st.caption("Awaiting entries. Class analytics will compute automatically once scores are added.")

                                        transmission_df = edited_grades_df.copy().rename(columns={"1CA": "CA1", "2CA": "CA2"})
                                        transmission_df["Subject"] = selected_subject
                                        transmission_df["Term"] = current_term
                                        transmission_df["Term_Total"] = transmission_df["CA1"].fillna(0) + transmission_df["CA2"].fillna(0) + transmission_df["Exam"].fillna(0)

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
                                                
                                                success_grades, message_grades = write_back_to_sheets(
                                                    dataframe=transmission_df,
                                                    sheet_name="grade_records",
                                                    action_type="upsert_rows",
                                                    extra_metadata={"Teacher_ID": teacher_id_string, "Class": selected_class, "Subject": selected_subject, "Term": current_term},
                                                    log_message=log_text
                                                )
                                                
                                                if success_grades:
                                                    status_payload = pd.DataFrame([{
                                                        "Teacher_ID": teacher_id_string,
                                                        "Class": selected_class,
                                                        "Subject": selected_subject,
                                                        "Status": "Submitted"
                                                    }])
                                                    
                                                    success_status, message_status = write_back_to_sheets(
                                                        dataframe=status_payload,
                                                        sheet_name="teacher_assignments",
                                                        action_type="update_task_status",
                                                        log_message="Locked task sheet for Admin review"
                                                    )
                                                    
                                                    st.success("Task marks locked and submitted for administrative audit!")
                                                    st.cache_data.clear()
                                                    st.keys_to_clear = [workspace_key]
                                                    st.rerun()
                                                else:
                                                    st.error(f"Submission failed: {message_grades}")
                                    else:
                                        st.warning(f"No active student list populated under class registry for {selected_class}.")
                                else:
                                    st.success("You do not have any teaching assignments currently mapped to your profile.")

                            with tab_submitted:
                                review_assignments = my_assignments[my_assignments["Status"].isin(["Submitted", "Approved", "Rejected"])]
                                if not review_assignments.empty:
                                    st.write("Tracking ledger for sheets sent to administration:")
                                    st.dataframe(review_assignments[["Class", "Subject", "Status", "Admin_Feedback"]], hide_index=True, use_container_width=True)
                                else:
                                    st.write("You have no tasks currently pending review or processed.")
                    else:
                        st.error("Invalid verification PIN. Access denied.")
                else:
                    st.error(f"The column '{target_column}' does not match your sheet.")
        else:
            st.info("Please enter your assigned staff verification code to unlock your dashboard.")

    elif user_role == "Term Summaries":
        st.title("Form Teacher Term Summaries")

        summary_pin = st.text_input("Enter your unique Access PIN:", type="password", key="summary_portal_pin")

        if summary_pin:
            if teacher_registry is None or class_teacher_mapping is None:
                st.error("Critical Error: Required tracking tables are missing or could not be loaded.")
            else:
                target_column = "Teacher_ID"
                valid_pins = teacher_registry[target_column].astype(str).values

                if summary_pin in valid_pins:
                    current_user = teacher_registry[teacher_registry[target_column].astype(str) == summary_pin].iloc[0]
                    staff_role = current_user.get("Staff_role", "")
                    teacher_id_str = str(current_user.get("Teacher_ID", ""))
                    teacher_name = current_user.get("Teacher_Name", "Teacher")

                    is_admin = staff_role == "Admin"
                    is_form_teacher = teacher_id_str in class_teacher_mapping["Teacher_ID"].astype(str).values

                    if not (is_admin or is_form_teacher):
                        st.error("You do not have access to this page.")
                    else:
                        st.success(f"Access Granted. Welcome, {teacher_name}!")
                        st.info(f"Active Session Context: {current_year} and {current_term}")
                        
                        if is_admin and not is_form_teacher:
                            assigned_classes = class_teacher_mapping["Class"].unique().tolist()
                        else:
                            assigned_classes = class_teacher_mapping[class_teacher_mapping["Teacher_ID"].astype(str) == teacher_id_str]["Class"].unique().tolist()
                            
                        if not assigned_classes:
                            st.warning("You are not currently mapped as a form teacher to any class.")
                        else:
                            selected_class = st.selectbox("Select assigned class roster:", assigned_classes)
                            
                            st.subheader(f"Term Summaries Entry: {selected_class}")
                            
                            if master_registry is not None:
                                class_students = master_registry[master_registry["Class"] == selected_class].copy()
                                
                                if class_students.empty:
                                    st.warning("No students found registered for this specific class arm.")
                                else:
                                    display_name_col = "Student_Name" if "Student_Name" in class_students.columns else ("STUDENT NAME" if "STUDENT NAME" in class_students.columns else class_students.columns[1])
                                    
                                    current_term_grades = grade_records[(grade_records["Term"] == current_term) & (grade_records["Student_ID"].isin(class_students["Student_ID"]))].copy()
                                    current_term_grades["Term_Total"] = pd.to_numeric(current_term_grades["Term_Total"], errors="coerce")
                                    current_term_grades = current_term_grades[current_term_grades["Term_Total"] > 0]
                                    
                                    if not current_term_grades.empty:
                                        student_avgs = current_term_grades.groupby("Student_ID")["Term_Total"].mean().reset_index()
                                        student_avgs.columns = ["Student_ID", "Term_Average"]
                                    else:
                                        student_avgs = pd.DataFrame(columns=["Student_ID", "Term_Average"])
                                    
                                    editor_df = pd.merge(class_students[["Student_ID", display_name_col]], student_avgs, on="Student_ID", how="left")
                                    editor_df["Term_Average"] = editor_df["Term_Average"].fillna(0.0)
                                    editor_df = editor_df.sort_values(by="Term_Average", ascending=False)
                                    
                                    existing_summaries = term_summaries[(term_summaries["Term"] == current_term) & (term_summaries["Class"] == selected_class)]
                                    
                                    target_columns = [
                                        "Teacher_Comment", "Attendance_Opened", "Attendance_Present", "Attendance_Absent",
                                        "Punctuality", "Neatness", "Leadership", "Helping_Others", "Attentiveness", 
                                        "Attitude_to_Work", "Handwriting", "Verbal_Fluency", "Games", "Sport", 
                                        "Handling_Tools", "Drawing_Painting"
                                    ]
                                    
                                    for col in target_columns:
                                        if col not in existing_summaries.columns:
                                            existing_summaries[col] = ""
                                            
                                    merged_data = pd.merge(editor_df, existing_summaries[["Student_ID"] + target_columns], on="Student_ID", how="left")
                                    for col in target_columns:
                                        merged_data[col] = merged_data[col].fillna("")
                                        
                                    st.write("Please fill in the remarks, attendance data, and affective/psychomotor skills. The grid is sorted dynamically by the current Term Average.")
                                    
                                    with st.form(key=f"term_summary_form_{selected_class}"):
                                        edited_summaries = st.data_editor(
                                            merged_data,
                                            hide_index=True,
                                            use_container_width=True,
                                            column_config={
                                                "Student_ID": st.column_config.TextColumn("Student ID", disabled=True),
                                                display_name_col: st.column_config.TextColumn("Student Name", disabled=True),
                                                "Term_Average": st.column_config.NumberColumn("Term Average", format="%.3f", disabled=True)
                                            }
                                        )
                                        
                                        if st.form_submit_button("Commit Term Summaries"):
                                            with st.spinner("Syncing behavioural logs to the centralized database..."):
                                                transmission_df = edited_summaries.copy()
                                                transmission_df["Term"] = current_term
                                                transmission_df["Class"] = selected_class
                                                transmission_df["Summary_ID"] = transmission_df["Student_ID"].astype(str) + "_" + current_term.replace(" ", "")
                                                
                                                columns_to_keep = ["Summary_ID", "Student_ID", "Term", "Class"] + target_columns
                                                transmission_df = transmission_df[columns_to_keep]
                                                
                                                log_text = f"Form Teacher {teacher_name} updated term summaries for {selected_class}"
                                                success, message = write_back_to_sheets(
                                                    dataframe=transmission_df,
                                                    sheet_name="term_summaries",
                                                    action_type="upsert_rows",
                                                    extra_metadata={"Class": selected_class, "Term": current_term},
                                                    log_message=log_text
                                                )
                                                
                                                if success:
                                                    st.success("Term summaries successfully saved to the master records!")
                                                    st.cache_data.clear()
                                                else:
                                                    st.error(f"Failed to save summary sheet: {message}")
                            else:
                                st.error("Master registry data table is missing.")
                else:
                    st.error("Invalid verification PIN. Access denied.")
    
    elif user_role == "Student Results View":
        st.title("Student Term Performance Portal")
        st.info(f"Active Session: {current_year} | {current_term}")

        student_id_input = st.text_input("Enter Student ID to view result:").strip()

        if student_id_input:
            if master_registry is not None and not master_registry.empty:
                # Find the student matching the code case-insensitively
                match = master_registry[master_registry["Student_ID"].astype(str).str.strip().str.lower() == student_id_input.lower()]

                if not match.empty:
                    student_row = match.iloc[0]
                    student_id = str(student_row["Student_ID"])
                    
                    # Resolve display name and demographic fields
                    display_name_col = "Student_Name" if "Student_Name" in master_registry.columns else ("STUDENT NAME" if "STUDENT NAME" in master_registry.columns else "Student_ID")
                    student_name = student_row.get(display_name_col, "Unknown Student")
                    student_class = student_row.get("Class", "Unknown Class")
                    student_gender = student_row.get("Gender", "N/A")

                    # 1. POSITIONAL AND AVERAGE CALCULATIONS
                    # Get IDs of all registered classmates in this specific class
                    classmate_ids = master_registry[master_registry["Class"] == student_class]["Student_ID"].unique()

                    # Filter term scores for classmates
                    term_grades = grade_records[grade_records["Term"] == current_term].copy()
                    term_grades["Term_Total"] = pd.to_numeric(term_grades["Term_Total"], errors="coerce")
                    class_grades = term_grades[term_grades["Student_ID"].isin(classmate_ids)].copy()

                    # Filter out subjects with 0 or NaN totals ("removing 0 total subjects")
                    class_grades = class_grades[(class_grades["Term_Total"] > 0) & (class_grades["Term_Total"].notna())].copy()

                    # Calculate terminal average for each classmate
                    student_averages = class_grades.groupby("Student_ID")["Term_Total"].mean().reset_index()
                    student_averages.columns = ["Student_ID", "Student_Average"]

                    # Rank classmate averages to find positions (highest score is position 1)
                    student_averages["Rank"] = student_averages["Student_Average"].rank(ascending=False, method="min")

                    def to_ordinal(num):
                        if pd.isna(num): 
                            return "N/A"
                        val = int(num)
                        if 11 <= (val % 100) <= 13: 
                            return f"{val}th"
                        return f"{val}" + {1: "st", 2: "nd", 3: "rd"}.get(val % 10, "th")

                    # Extract target student average and rank metrics
                    target_summary = student_averages[student_averages["Student_ID"] == student_id]
                    if not target_summary.empty:
                        student_avg = target_summary["Student_Average"].values[0]
                        student_rank_num = int(target_summary["Rank"].values[0])
                        student_position = to_ordinal(student_rank_num)
                    else:
                        student_avg = 0.000
                        student_position = "N/A"

                    # Calculate global class average
                    class_avg = student_averages["Student_Average"].mean() if not student_averages.empty else 0.000
                    total_class_size = len(classmate_ids)

                    # Determine term rules
                    is_third_term = "3" in str(current_term) or "third" in str(current_term).lower()

                    # 2. RUN SESSION COMPUTATIONS IF IT IS 3RD TERM
                    student_session_avg = 0.000
                    class_session_avg = 0.000
                    student_session_position = "N/A"
                    class_session_grades = pd.DataFrame()

                    if is_third_term and grade_records is not None and not grade_records.empty:
                        # Fetch all classmate records across all terms for the entire session
                        class_session_grades = grade_records[grade_records["Student_ID"].isin(classmate_ids)].copy()
                        class_session_grades["Term_Total"] = pd.to_numeric(class_session_grades["Term_Total"], errors="coerce")
                        
                        # Filter out subjects with 0 or NaN totals ("removing 0 total subjects")
                        class_session_grades = class_session_grades[(class_session_grades["Term_Total"] > 0) & (class_session_grades["Term_Total"].notna())].copy()

                        # Target Student Session Average calculation
                        target_session_grades = class_session_grades[class_session_grades["Student_ID"] == student_id]
                        student_session_avg = target_session_grades["Term_Total"].mean() if not target_session_grades.empty else 0.000

                        # Calculate classmate session averages to resolve ranking
                        classmates_session_summaries = class_session_grades.groupby("Student_ID")["Term_Total"].mean().reset_index()
                        classmates_session_summaries.columns = ["Student_ID", "Classmate_Session_Avg"]
                        classmates_session_summaries["Session_Rank"] = classmates_session_summaries["Classmate_Session_Avg"].rank(ascending=False, method="min")

                        # Global Class Session Average calculation
                        class_session_avg = classmates_session_summaries["Classmate_Session_Avg"].mean() if not classmates_session_summaries.empty else 0.000

                        target_sess_rank_match = classmates_session_summaries[classmates_session_summaries["Student_ID"] == student_id]
                        if not target_sess_rank_match.empty:
                            student_session_position = to_ordinal(int(target_sess_rank_match["Session_Rank"].values[0]))

                    # Calculate subject positions within the class roster for First/Second Term defaults
                    class_grades["Subject_Rank_Val"] = class_grades.groupby("Subject")["Term_Total"].rank(ascending=False, method="min")
                    class_grades["Subject_Rank"] = class_grades["Subject_Rank_Val"].apply(lambda r: to_ordinal(r) if pd.notna(r) else "N/A")

                    # Filter active student subject records
                    student_subject_records = class_grades[class_grades["Student_ID"] == student_id].copy()

                    # 3. HARVEST EXPANDED TERM SUMMARIES AND BEHAVIOR DATA
                    attendance_opened = "N/A"
                    attendance_present = "N/A"
                    attendance_absent = "N/A"
                    teacher_comment = "No comment logged."
                    principal_comment = "No comment logged."

                    affective_keys = ["Punctuality", "Neatness", "Leadership", "Helping_Others", "Attentiveness", "Attitude_to_Work"]
                    affective_ratings = {key: "N/A" for key in affective_keys}

                    psychomotor_keys = ["Handwriting", "Verbal_Fluency", "Games", "Sport", "Handling_Tools", "Drawing_Painting"]
                    psychomotor_ratings = {key: "N/A" for key in psychomotor_keys}

                    if term_summaries is not None and not term_summaries.empty:
                        matched_summary = term_summaries[
                            (term_summaries["Term"] == current_term) &
                            (term_summaries["Student_ID"].astype(str).str.strip().str.lower() == student_id.lower())
                        ]
                        if not matched_summary.empty:
                            summary_row = matched_summary.iloc[0]

                            def safe_get(row, col_name, default="N/A"):
                                if col_name in row.index:
                                    val = row[col_name]
                                    if isinstance(val, pd.Series):
                                        val = val.iloc[0]
                                    if pd.notna(val) and str(val).strip() != "":
                                        return val
                                renamed_cols = [col for col in row.index if str(col).startswith(col_name + ".")]
                                for renamed_col in renamed_cols:
                                    val = row[renamed_col]
                                    if pd.notna(val) and str(val).strip() != "":
                                        return val
                                return default

                            attendance_opened = safe_get(summary_row, "Attendance_Opened")
                            attendance_present = safe_get(summary_row, "Attendance_Present")
                            attendance_absent = safe_get(summary_row, "Attendance_Absent")
                            teacher_comment = safe_get(summary_row, "Teacher_Comment")
                            principal_comment = safe_get(summary_row, "Principal_Comment")

                            for key in affective_keys:
                                affective_ratings[key] = safe_get(summary_row, key)
                            for key in psychomotor_keys:
                                psychomotor_ratings[key] = safe_get(summary_row, key)

                    # Resolve Principal's comments and status using the updated function
                    active_avg = student_session_avg if is_third_term else student_avg
                    try:
                        principal_comment, promotion_status = get_principal_comment(active_avg, student_name, current_term)
                    except Exception as e:
                        principal_comment = None
                        promotion_status = None
                        st.write(f"Debug: Error in get_principal_comment - {str(e)}")
                        
                    # Fallback check for the comment
                    if principal_comment is None or str(principal_comment).strip() == "":
                        principal_comment = "No comment logged."
                    
                    # 4. BUILD COGNITIVE PERFORMANCE DOMAIN TABLES
                    def evaluate_score_grade(score):
                        if pd.isna(score): return "F", "Absent"
                        val = float(score)
                        if val >= 80.0: return "A", "Excellent"
                        elif val >= 70.0: return "B", "Very Good"
                        elif val >= 60.0: return "C", "Fair"
                        elif val >= 50.0: return "D", "Marginal"
                        elif val >= 40.0: return "E", "Pass"
                        else: return "F", "Fail"

                    total_marks_obtained = student_subject_records["Term_Total"].sum() if not student_subject_records.empty else 0.000
                    total_subjects_offered = len(student_subject_records)
                    total_mark_obtainable = total_subjects_offered * 100.000

                    # Pre-calculate totals across older terms for 3rd term comparative metrics
                    term_1_totals = {}
                    term_2_totals = {}
                    if is_third_term and grade_records is not None and not grade_records.empty:
                        student_all_grades = grade_records[grade_records["Student_ID"].astype(str).str.strip().str.lower() == student_id.lower()]
                        for _, g_row in student_all_grades.iterrows():
                            term_val = str(g_row.get("Term", "")).strip().lower()
                            subj_val = g_row.get("Subject")
                            score_val = pd.to_numeric(g_row.get("Term_Total"), errors="coerce")
                            if pd.notna(score_val) and score_val > 0:
                                if "1st" in term_val or "first" in term_val:
                                    term_1_totals[subj_val] = score_val
                                elif "2nd" in term_val or "second" in term_val:
                                    term_2_totals[subj_val] = score_val

                    total_subjects_passed = 0
                    total_subjects_failed = 0
                    cognitive_rows = []

                    for _, row in student_subject_records.iterrows():
                        subj = row["Subject"]
                        ca1 = row.get("CA1", row.get("1CA", None))
                        ca2 = row.get("CA2", row.get("2CA", None))
                        exam = row.get("Exam", None)
                        total = row.get("Term_Total", None)

                        ca1_num = pd.to_numeric(ca1, errors="coerce")
                        ca2_num = pd.to_numeric(ca2, errors="coerce")
                        exam_num = pd.to_numeric(exam, errors="coerce")
                        total_num = pd.to_numeric(total, errors="coerce")

                        # Handle absent/zero sub-scores explicitly inside the loops using float("nan")
                        ca1_val = ca1_num if (pd.notna(ca1_num) and ca1_num > 0) else float("nan")
                        ca2_val = ca2_num if (pd.notna(ca2_num) and ca2_num > 0) else float("nan")
                        exam_val = exam_num if (pd.notna(exam_num) and exam_num > 0) else float("nan")
                        total_val = total_num if (pd.notna(total_num) and total_num > 0) else float("nan")

                        if pd.notna(total_val):
                            if total_val >= min_passing_score:
                                total_subjects_passed += 1
                            else:
                                total_subjects_failed += 1

                        if is_third_term:
                            t1_total = term_1_totals.get(subj, float("nan"))
                            t2_total = term_2_totals.get(subj, float("nan"))
                            t3_total = total_val
                            
                            # Session Average calculation (ignoring absent terms dynamically)
                            valid_terms = [v for v in [t1_total, t2_total, t3_total] if pd.notna(v)]
                            session_avg_val = sum(valid_terms) / len(valid_terms) if valid_terms else float("nan")
                            grade, comment = evaluate_score_grade(session_avg_val) if pd.notna(session_avg_val) else ("F", "Absent")

                            # Subject Rank mapped dynamically on Session Average
                            subj_class_grades = class_session_grades[class_session_grades["Subject"] == subj].copy()
                            subj_student_avgs = subj_class_grades.groupby("Student_ID")["Term_Total"].mean().reset_index()
                            subj_student_avgs.columns = ["Student_ID", "Avg_Score"]
                            subj_student_avgs["Rank"] = subj_student_avgs["Avg_Score"].rank(ascending=False, method="min")
                            
                            subj_rank_row = subj_student_avgs[subj_student_avgs["Student_ID"] == student_id]
                            subject_rank_str = to_ordinal(int(subj_rank_row["Rank"].values[0])) if not subj_rank_row.empty else "N/A"

                            cognitive_rows.append({
                                "Subject": subj,
                                "1st Term": t1_total,
                                "2nd Term": t2_total,
                                "1st CA (20)": ca1_val,
                                "2nd CA (20)": ca2_val,
                                "Exam (60)": exam_val,
                                "Total (100)": t3_total,
                                "Session Average": session_avg_val,
                                "Grade": grade,
                                "Subject Rank": subject_rank_str,
                                "Comment": comment
                            })
                        else:
                            grade, comment = evaluate_score_grade(total_val) if pd.notna(total_val) else ("F", "Absent")
                            cognitive_rows.append({
                                "Subject": subj,
                                "1st CA (20)": ca1_val,
                                "2nd CA (20)": ca2_val,
                                "Exam (60)": exam_val,
                                "Total (100)": total_val,
                                "Grade": grade,
                                "Subject Rank": row.get("Subject_Rank", "N/A"),
                                "Comment": comment
                            })

                    cognitive_df = pd.DataFrame(cognitive_rows)

                    # 5. RENDER ASSESSMENT REPORT CARD UI
                    st.markdown(
                        '<div style="text-align: center; font-size: 20px; font-weight: bold; color: #FF0000; margin-bottom: 2px;">NO LIMITS SECONDARY SCHOOL</div>', 
                        unsafe_allow_html=True
                    )
                    st.markdown(
                        '<div style="text-align: center; font-style: italic; font-size: 14px; color: #0000FF; margin-bottom: 8px;">64, Canal View Drive, Greenfield Estate, Off Amuwo-Odofin, Ago Palace Way, Lagos.</div>', 
                        unsafe_allow_html=True
                    )
                    st.markdown(
                        '<div style="text-align: center; font-size: 16px; font-weight: bold; margin-bottom: 4px;">End of Term Assessment Report</div>', 
                        unsafe_allow_html=True
                    )
                    
                    # Dynamically resolve section based on Class
                    section = "JUNIOR SECONDARY SCHOOL SECTION" if "JSS" in str(student_class).upper() else "SENIOR SECONDARY SCHOOL SECTION"
                    st.markdown(
                        f'<div style="text-align: center; font-size: 16px; margin-bottom: 12px;">{section}</div>', 
                        unsafe_allow_html=True
                    )

                    # Student's Name row
                    st.markdown(
                        f'<div style="font-size: 16px; font-weight: bold; margin-bottom: 12px;">Student\'s Name: {student_name}</div>', 
                        unsafe_allow_html=True
                    )

                    # Demographic grid using 4 columns
                    col_card1, col_card2, col_card3, col_card4 = st.columns(4)
                    with col_card1:
                        st.markdown(
                            f'<div style="white-space: nowrap; font-size: 12px; margin-bottom: 4px;"><span style="opacity: 0.65;">Class Room:</span> <span style="font-weight: bold; opacity: 1.0;">{student_class}</span></div>'
                            f'<div style="white-space: nowrap; font-size: 12px; margin-bottom: 4px;"><span style="opacity: 0.65;">Student Code:</span> <span style="font-weight: bold; opacity: 1.0;">{student_id}</span></div>', 
                            unsafe_allow_html=True
                        )
                    with col_card2:
                        st.markdown(
                            f'<div style="white-space: nowrap; font-size: 12px; margin-bottom: 4px;"><span style="opacity: 0.65;">Gender Group:</span> <span style="font-weight: bold; opacity: 1.0;">{student_gender}</span></div>'
                            f'<div style="white-space: nowrap; font-size: 12px; margin-bottom: 4px;"><span style="opacity: 0.65;">Days Present:</span> <span style="font-weight: bold; opacity: 1.0;">{attendance_present}</span></div>'
                            f'<div style="white-space: nowrap; font-size: 12px; margin-bottom: 4px;"><span style="opacity: 0.65;">Days Absent:</span> <span style="font-weight: bold; opacity: 1.0;">{attendance_absent}</span></div>', 
                            unsafe_allow_html=True
                        )
                    with col_card3:
                        st.markdown(
                            f'<div style="white-space: nowrap; font-size: 12px; margin-bottom: 4px;"><span style="opacity: 0.65;">Session:</span> <span style="font-weight: bold; opacity: 1.0;">{current_year}</span></div>'
                            f'<div style="white-space: nowrap; font-size: 12px; margin-bottom: 4px;"><span style="opacity: 0.65;">School Opened:</span> <span style="font-weight: bold; opacity: 1.0;">{attendance_opened}</span></div>', 
                            unsafe_allow_html=True
                        )
                    with col_card4:
                        st.markdown(
                            f'<div style="white-space: nowrap; font-size: 12px; margin-bottom: 4px;"><span style="opacity: 0.65;">Term Period:</span> <span style="font-weight: bold; opacity: 1.0;">{current_term}</span></div>'
                            f'<div style="white-space: nowrap; font-size: 12px; margin-bottom: 4px;"><span style="opacity: 0.65;">Total Classmates:</span> <span style="font-weight: bold; opacity: 1.0;">{total_class_size}</span></div>', 
                            unsafe_allow_html=True
                        )

                    # 6. RENDER SUMMARY METRIC BLOCKS (Values rounded to 2 decimal places)
                    if is_third_term:
                        col_term_sum, col_session_sum = st.columns(2)
                        with col_term_sum:
                            st.markdown('<div style="color: #0000FF; font-size: 12px; font-weight: bold; margin-bottom: 4px;">Term Summary</div>', unsafe_allow_html=True)
                            st.markdown(
                                f'<div style="white-space: nowrap; font-size: 12px; margin-bottom: 4px;"><span style="opacity: 0.65;">Student Term Average:</span> <span style="font-weight: bold; opacity: 1.0;">{student_avg:.2f}%</span></div>'
                                f'<div style="white-space: nowrap; font-size: 12px; margin-bottom: 4px;"><span style="opacity: 0.65;">Class Average for the Term:</span> <span style="font-weight: bold; opacity: 1.0;">{class_avg:.2f}%</span></div>'
                                f'<div style="white-space: nowrap; font-size: 12px; margin-bottom: 4px;"><span style="opacity: 0.65;">Class Position for the Term:</span> <span style="font-weight: bold; opacity: 1.0;">{student_position}</span></div>',
                                unsafe_allow_html=True
                            )
                        with col_session_sum:
                            st.markdown('<div style="color: #0000FF; font-size: 12px; font-weight: bold; margin-bottom: 4px;">Session Summary</div>', unsafe_allow_html=True)
                            st.markdown(
                                f'<div style="white-space: nowrap; font-size: 12px; margin-bottom: 4px;"><span style="opacity: 0.65;">Student Session Average:</span> <span style="font-weight: bold; opacity: 1.0;">{student_session_avg:.2f}%</span></div>'
                                f'<div style="white-space: nowrap; font-size: 12px; margin-bottom: 4px;"><span style="opacity: 0.65;">Class Average for the Session:</span> <span style="font-weight: bold; opacity: 1.0;">{class_session_avg:.2f}%</span></div>'
                                f'<div style="white-space: nowrap; font-size: 12px; margin-bottom: 4px;"><span style="opacity: 0.65;">Class Position for the Session:</span> <span style="font-weight: bold; opacity: 1.0;">{student_session_position}</span></div>',
                                unsafe_allow_html=True
                            )
                    else:
                        col_metric1, col_metric2, col_metric3 = st.columns(3)
                        with col_metric1:
                            st.metric("Student's Average", f"{student_avg:.2f}%")
                            st.write(f"Total Marks Obtained: {total_marks_obtained:.2f}")
                        with col_metric2:
                            st.metric("Class Average", f"{class_avg:.2f}%")
                            st.write(f"Total Mark Obtainable: {total_mark_obtainable:.2f}")
                        with col_metric3:
                            st.metric("Position in Class", student_position)
                            st.write(f"Total Classmates: {total_class_size}")

                    # 7. RENDER COGNITIVE SCORE TABLES
                    st.markdown("##### Cognitive Domain Scores")
                    if not cognitive_df.empty:
                        # Precision formats changed to whole numbers
                        format_dict = {
                            "1st CA (20)": "{:.0f}",
                            "2nd CA (20)": "{:.0f}",
                            "Exam (60)": "{:.0f}",
                            "Total (100)": "{:.0f}"
                        }
                        if is_third_term:
                            format_dict["1st Term"] = "{:.0f}"
                            format_dict["2nd Term"] = "{:.0f}"
                            format_dict["Session Average"] = "{:.0f}"

                        def assign_grade_color(val):
                            color = "black"
                            if val == "A":
                                color = "green"
                            elif val == "B":
                                color = "blue"
                            elif val == "D":
                                color = "yellow"
                            elif val == "E":
                                color = "brown"
                            elif val == "F":
                                color = "red"
                            return f"color: {color}"

                        # Format styler mapping missing numbers to abs and assigning grade colors
                        formatted_cognitive_df = (
                            cognitive_df.style
                            .format(format_dict, na_rep="abs")
                            .map(assign_grade_color, subset=["Grade"])
                        )
                        
                        st.dataframe(formatted_cognitive_df, hide_index=True, use_container_width=True)
                    else:
                        st.warning("No academic score records found for this student profile.")

                    # 8. RENDER COGNITIVE SUMMARY 
                    col_subj1, col_subj2, col_subj3 = st.columns(3)
                    with col_subj1:
                        st.write(f"Total Subjects Offered: {total_subjects_offered}")
                    with col_subj2:
                        st.write(f"Total Subjects Passed: {total_subjects_passed}")
                    with col_subj3:
                        st.write(f"Total Subjects Failed: {total_subjects_failed}")

                    # 9. RENDER COMBINED HORIZONTAL LEGEND MATRIX TABLE
                    st.write("Legends Keys Summary")
                    combined_legend = pd.DataFrame([
                        {
                            "Legend Category": "Behavioural Keys",
                            "Scale / Range Mapping": "Excellent=5,  Good=4,  Average=3,  Poor=2,  Fair=1"
                        },
                        {
                            "Legend Category": "Academic Keys",
                            "Scale / Range Mapping": "A=(80-100),  B=(70-79),  C=(50-69),  D=(40-49),  F=(0-39)"
                        }
                    ])
                    st.dataframe(combined_legend, hide_index=True, use_container_width=True)

                    # 10. RESOLVE CLASS TEACHER NAME DYNAMICALLY & RENDER ENDORSEMENT STATEMENT MATRIX
                    class_teacher_name = "N/A"
                    mapping_df = locals().get("class_teacher_mapping", globals().get("class_teacher_mapping"))
                    registry_df = locals().get("teacher_registry", globals().get("teacher_registry"))

                    if mapping_df is not None and not mapping_df.empty:
                        class_match = mapping_df[mapping_df["Class"].astype(str).str.strip().str.lower() == str(student_class).strip().lower()]
                        if not class_match.empty:
                            teacher_id_val = class_match.iloc[0].get("Teacher_ID")
                            if teacher_id_val and registry_df is not None and not registry_df.empty:
                                teacher_match = registry_df[registry_df["Teacher_ID"].astype(str).str.strip().str.lower() == str(teacher_id_val).strip().lower()]
                                if not teacher_match.empty:
                                    name_col = next((col for col in registry_df.columns if "name" in col.lower()), "Teacher_Name")
                                    class_teacher_name = str(teacher_match.iloc[0].get(name_col, "N/A"))

                    admin_endorsements_data = [
                        {
                            "Role / Endorsement": "Class Teacher Comment",
                            "Remarks": teacher_comment,
                            "Authorized Signatory": class_teacher_name
                        },
                        {
                            "Role / Endorsement": "School Principal Remarks",
                            "Remarks": principal_comment,
                            "Authorized Signatory": "Mrs Joy Paul"
                        }
                    ]
                    
                    st.write("---")
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.write("**Class Teacher Comment**")
                        st.write(teacher_comment)
                        st.write("**Signatory:** " + class_teacher_name)
                    
                    with col2:
                        st.write("**School Principal Remarks**")
                        st.write(principal_comment)
                        st.write("**Signatory:** Mrs Joy Paul")

                    pdf_data = generate_pdf_report(
                        student_name=student_name, 
                        class_room=student_class, 
                        student_code=student_id, 
                        gender_group=student_gender,
                        days_present=attendance_present, 
                        days_absent=attendance_absent, 
                        session=current_year, 
                        school_opened=attendance_opened,
                        term_period=current_term, 
                        total_classmates=total_class_size,
                        student_term_avg=student_avg, 
                        class_term_avg=class_avg, 
                        class_term_pos=student_position,
                        student_session_avg=student_session_avg, 
                        class_session_avg=class_session_avg, 
                        class_session_pos=student_session_position,
                        total_offered=total_subjects_offered, 
                        total_passed=total_subjects_passed, 
                        total_failed=total_subjects_failed,
                        scores_df=cognitive_df, 
                        teacher_comment=teacher_comment, 
                        #principal_comment=principal_comment: now handled dynamically
                        class_teacher_name=class_teacher_name
                    )
                    st.download_button(
                        label="Download Result as PDF",
                        data=pdf_data,
                        file_name=f"{student_name}_Result.pdf",
                        mime="application/pdf"
                    )
                
                else:
                    st.error("The Student ID or Access Code could not be found in the registry database.")
